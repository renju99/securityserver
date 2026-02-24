from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import models
import schemas
from database import get_db
from core.security import verify_password, get_password_hash
from services.audit_service import audit_service
import base64
from typing import List

router = APIRouter(tags=["authentication"])

@router.post("/login", response_model=schemas.UserResponse)
def login(login_data: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == login_data.email).first()
    if not user or not user.hashed_password:
        audit_service.log_event(db, login_data.email, "LOGIN_FAILED", "USER", None, {"reason": "invalid_credentials"}, ip_address=request.client.host)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(login_data.password, user.hashed_password):
        audit_service.log_event(db, login_data.email, "LOGIN_FAILED", "USER", str(user.id), {"reason": "wrong_password"}, ip_address=request.client.host)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    audit_service.log_event(db, user.email, "LOGIN_SUCCESS", "USER", str(user.id), ip_address=request.client.host)
    return user

@router.post("/auth/microsoft", response_model=schemas.UserResponse)
def login_microsoft(payload: dict, request: Request, db: Session = Depends(get_db)):
    """
    Verifies Microsoft ID Token and logs in/registers the user.
    """
    token = payload.get("access_token") 
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
        
    email = payload.get("email")
    full_name = payload.get("name")
    
    if not email:
         raise HTTPException(status_code=400, detail="Email required from token")
 
    # JIT Provisioning
    user = db.query(models.User).filter(models.User.email.ilike(email)).first()
    if not user:
        user = models.User(
            email=email,
            full_name=full_name or email.split("@")[0],
            hashed_password=None,
            auth_provider="microsoft",
            role="User",
            permissions={"departments": []}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        audit_service.log_event(db, email, "USER_REGISTER_MS", "USER", str(user.id), ip_address=request.client.host)
    else:
        audit_service.log_event(db, email, "LOGIN_SUCCESS_MS", "USER", str(user.id), ip_address=request.client.host)
    
    return user

@router.post("/users/save-signature")
async def save_user_signature(payload: schemas.UserSignatureUpdate, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    img_data = payload.signature_base64.split(",")[1] if "," in payload.signature_base64 else payload.signature_base64
    img_bytes = base64.b64decode(img_data)
    
    import os
    filename = f"signatures/user_{user.id}_{os.urandom(4).hex()}.png"
    from services.blob_service import blob_service
    blob_service.upload_blob(img_bytes, filename)
    
    url = blob_service.get_sas_url(filename, expiry_hours=87600) # 10 years
    
    if payload.sig_type == "initial":
        user.saved_initials_url = url
    else:
        user.saved_signature_url = url
        
    db.commit()
    audit_service.log_event(db, payload.email, "SAVE_SIGNATURE", "USER", str(user.id), {"type": payload.sig_type}, ip_address=request.client.host)
    return {"message": f"{payload.sig_type.capitalize()} saved successfully", "url": url}
