from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from database import get_db
from core.security import get_password_hash
from services.audit_service import audit_service

router = APIRouter(tags=["admin"])

# --- Master Data ---

@router.get("/departments", response_model=List[schemas.MasterDataResponse])
def get_departments(db: Session = Depends(get_db)):
    return db.query(models.Department).all()

@router.post("/departments", response_model=schemas.MasterDataResponse)
def create_department(data: schemas.MasterDataCreate, request: Request, db: Session = Depends(get_db)):
    dept = db.query(models.Department).filter(models.Department.name == data.name).first()
    if dept:
        raise HTTPException(status_code=400, detail="Department already exists")
    dept = models.Department(name=data.name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    audit_service.log_event(db, "admin", "CREATE_DEPT", "CONFIG", str(dept.id), {"name": data.name}, ip_address=request.client.host)
    return dept

@router.delete("/departments/{dept_id}")
def delete_department(dept_id: int, request: Request, db: Session = Depends(get_db)):
    dept = db.query(models.Department).filter(models.Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(dept)
    db.commit()
    audit_service.log_event(db, "admin", "DELETE_DEPT", "CONFIG", str(dept_id), ip_address=request.client.host)
    return {"message": "Department deleted"}

@router.get("/document-types", response_model=List[schemas.MasterDataResponse])
def get_document_types(db: Session = Depends(get_db)):
    return db.query(models.DocumentType).all()

@router.post("/document-types", response_model=schemas.MasterDataResponse)
def create_document_type(data: schemas.MasterDataCreate, request: Request, db: Session = Depends(get_db)):
    dt = db.query(models.DocumentType).filter(models.DocumentType.name == data.name).first()
    if dt:
        raise HTTPException(status_code=400, detail="Document type already exists")
    dt = models.DocumentType(name=data.name)
    db.add(dt)
    db.commit()
    db.refresh(dt)
    audit_service.log_event(db, "admin", "CREATE_DOCTYPE", "CONFIG", str(dt.id), {"name": data.name}, ip_address=request.client.host)
    return dt

@router.delete("/document-types/{dt_id}")
def delete_document_type(dt_id: int, request: Request, db: Session = Depends(get_db)):
    dt = db.query(models.DocumentType).filter(models.DocumentType.id == dt_id).first()
    if not dt:
        raise HTTPException(status_code=404, detail="Document type not found")
    db.delete(dt)
    db.commit()
    audit_service.log_event(db, "admin", "DELETE_DOCTYPE", "CONFIG", str(dt_id), ip_address=request.client.host)
    return {"message": "Document type deleted"}

# --- User Management ---

@router.get("/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

@router.post("/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    db_user = models.User(
        email=user.email,
        full_name=user.full_name,
        job_position=user.job_position,
        hashed_password=get_password_hash(user.password) if user.password else None,
        role=user.role,
        auth_provider="local" if user.password else "microsoft",
        permissions=user.permissions or {"departments": []}
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    audit_service.log_event(db, "admin", "CREATE_USER", "USER", str(db_user.id), {"email": user.email}, ip_address=request.client.host)
    return db_user

@router.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(user_id: int, user_update: schemas.UserUpdate, request: Request, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
    if user_update.job_position is not None:
        db_user.job_position = user_update.job_position
    if user_update.role is not None:
        db_user.role = user_update.role
    if user_update.access_scope is not None:
        db_user.access_scope = user_update.access_scope
    if user_update.permissions is not None:
        db_user.permissions = user_update.permissions
    if user_update.password:
        db_user.hashed_password = get_password_hash(user_update.password)
        db_user.auth_provider = "local"
        
    db.commit()
    db.refresh(db_user)
    audit_service.log_event(db, "admin", "UPDATE_USER", "USER", str(user_id), ip_address=request.client.host)
    return db_user

@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    audit_service.log_event(db, "admin", "DELETE_USER", "USER", str(user_id), ip_address=request.client.host)
    return {"message": "User deleted"}

# --- Workflows ---

@router.get("/workflows", response_model=List[schemas.WorkflowResponse])
def get_workflows(db: Session = Depends(get_db)):
    return db.query(models.Workflow).all()

@router.post("/workflows", response_model=schemas.WorkflowResponse)
def create_or_update_workflow(wf: schemas.WorkflowCreate, request: Request, db: Session = Depends(get_db)):
    existing = db.query(models.Workflow).filter(
        models.Workflow.department == wf.department,
        models.Workflow.doc_type == wf.doc_type
    ).first()
    
    if existing:
        existing.approvers = wf.approvers
        existing.signers = wf.signers
        db.commit()
        db.refresh(existing)
        audit_service.log_event(db, "admin", "UPDATE_WORKFLOW", "CONFIG", str(existing.id), ip_address=request.client.host)
        return existing
    else:
        new_wf = models.Workflow(
            department=wf.department,
            doc_type=wf.doc_type,
            approvers=wf.approvers,
            signers=wf.signers
        )
        db.add(new_wf)
        db.commit()
        db.refresh(new_wf)
        audit_service.log_event(db, "admin", "CREATE_WORKFLOW", "CONFIG", str(new_wf.id), ip_address=request.client.host)
        return new_wf

# --- Email Config ---

@router.get("/email-config", response_model=schemas.EmailConfigResponse)
def get_email_config(db: Session = Depends(get_db)):
    config = db.query(models.EmailConfig).first()
    if not config:
        config = models.EmailConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

@router.post("/email-config", response_model=schemas.EmailConfigResponse)
def save_email_config(config_in: schemas.EmailConfigUpdate, request: Request, db: Session = Depends(get_db)):
    config = db.query(models.EmailConfig).first()
    if not config:
        config = models.EmailConfig()
        db.add(config)
    
    config.smtp_server = config_in.smtp_server
    config.smtp_port = config_in.smtp_port
    config.username = config_in.username
    if config_in.password:
        config.password = config_in.password
    config.from_email = config_in.from_email
    config.from_name = config_in.from_name
    config.encryption = config_in.encryption
    
    config.imap_server = config_in.imap_server
    config.imap_port = config_in.imap_port
    config.imap_username = config_in.imap_username
    if config_in.imap_password:
        config.imap_password = config_in.imap_password
    config.imap_ssl = config_in.imap_ssl
    
    db.commit()
    db.refresh(config)
    audit_service.log_event(db, "admin", "UPDATE_EMAIL_CONFIG", "CONFIG", str(config.id), ip_address=request.client.host)
    return config

@router.get("/email-logs", response_model=List[schemas.EmailLogResponse])
def get_email_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.EmailLog).order_by(models.EmailLog.sent_at.desc()).offset(skip).limit(limit).all()

# --- Audit Logs ---

@router.get("/audit-logs", response_model=List[schemas.AuditLogResponse])
def get_audit_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
