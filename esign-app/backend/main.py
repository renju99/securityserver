from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import os
import tempfile
import subprocess
import shutil
import json
from typing import List, Optional, Dict, Any
from urllib.parse import quote
from dotenv import load_dotenv

from docxtpl import DocxTemplate
from dynamic_renderer import generate_dynamic_pdf
from passlib.context import CryptContext
import fitz # PyMuPDF
import base64
import io
import smtplib
import imaplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import models
import schemas
from workflow_config import APPROVAL_FLOWS

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Initialize Database
Base.metadata.create_all(bind=engine)

# Lightweight schema healer for Postgres deployments where new columns may be missing.
def ensure_schema():
    with engine.connect() as conn:
        # DocumentRequest core columns (for older databases that predate this model)
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS requester_name TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS requester_email TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS department TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS doc_type TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS template_name TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS form_data JSONB;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS status TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
        """))

        # DocumentRequest columns introduced after initial deployment
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS current_pdf_url TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS original_pdf_url TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS supporting_documents JSONB;
        """))
        conn.execute(text("""
            ALTER TABLE document_requests
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
        """))
        conn.commit()

ensure_schema()

# Seed Admin User and Initial Data
def seed_data():
    db = SessionLocal()
    try:
        # Seed Admin
        admin = db.query(models.User).filter(models.User.email == "admin@esign.com").first()
        if not admin:
            admin = models.User(
                email="admin@esign.com",
                full_name="Admin User",
                hashed_password=get_password_hash("admin123"),
                role="Admin",
                auth_provider="local",
                permissions={"departments": [], "can_delete": True}
            )
            db.add(admin)
        
        # Seed IT Department
        it_dept = db.query(models.Department).filter(models.Department.name == "IT").first()
        if not it_dept:
            db.add(models.Department(name="IT"))
            
        # Seed Capex DocType
        capex_type = db.query(models.DocumentType).filter(models.DocumentType.name == "Capex").first()
        if not capex_type:
            db.add(models.DocumentType(name="Capex"))
            
        db.commit()
    finally:
        db.close()

seed_data()
load_dotenv()

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure Storage Setup
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "esign-vault")

try:
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    if not container_client.exists():
        container_client.create_container()
except Exception as e:
    print(f"Azure Storage Error: {e}")

# Helper to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"message": "eSign API is running"}

def optimize_pdf(input_bytes: bytes) -> bytes:
    """Optimizes PDF bytes using PyMuPDF."""
    try:
        doc = fitz.open(stream=input_bytes, filetype="pdf")
        output_stream = io.BytesIO()
        # garbage=3: moderate cleanup, deflate=True: compress streams
        doc.save(output_stream, garbage=3, deflate=True)
        optimized_bytes = output_stream.getvalue()
        doc.close()
        # Only return optimized if it's actually smaller
        if len(optimized_bytes) < len(input_bytes):
            return optimized_bytes
        return input_bytes
    except Exception as e:
        print(f"Optimization failed: {e}")
        return input_bytes

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), folder: str = "templates", optimize: bool = False):
    try:
        file_content = await file.read()
        
        if optimize and file.filename.lower().endswith(".pdf"):
            print(f"Optimizing {file.filename} (original size: {len(file_content)} bytes)")
            file_content = optimize_pdf(file_content)
            print(f"New size: {len(file_content)} bytes")

        blob_path = f"{folder}/{file.filename}"
        blob_client = container_client.get_blob_client(blob_path)
        blob_client.upload_blob(file_content, overwrite=True)
        
        # Generate a SAS link for the uploaded file
        sas_token = generate_blob_sas(
            account_name=blob_client.account_name,
            container_name=CONTAINER_NAME,
            blob_name=blob_path,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=365),
            start_time=datetime.utcnow() - timedelta(minutes=15) # Buffer for clock skew
        )
        url = f"https://{blob_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{quote(blob_path, safe='/')}?{sas_token}"
        
        return {
            "filename": file.filename, 
            "url": url,
            "size": len(file_content),
            "message": "File uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-link/{filename}")
async def get_sas_link(filename: str):
    try:
        blob_client = container_client.get_blob_client(filename)
        if not blob_client.exists():
            # Check if it exists in templates/
            blob_client = container_client.get_blob_client(f"templates/{filename}")
            if not blob_client.exists():
                 raise HTTPException(status_code=404, detail="File not found")

        sas_token = generate_blob_sas(
            account_name=blob_client.account_name,
            container_name=CONTAINER_NAME,
            blob_name=blob_client.blob_name,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=12), # Increased from 1h for stability
            start_time=datetime.utcnow() - timedelta(minutes=15)
        )
        url = f"https://{blob_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{quote(blob_client.blob_name, safe='/')}?{sas_token}"
        return {"url": url}
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

@app.get("/templates")
async def list_templates():
    try:
        templates = []
        blob_list = container_client.list_blobs(name_starts_with="templates/")
        for blob in blob_list:
            if blob.name.endswith(".docx") or blob.name.endswith(".pdf"):
                templates.append(os.path.basename(blob.name))
        return {"templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/templates/{filename}")
async def delete_template(filename: str, db: Session = Depends(get_db)):
    try:
        blob_client = container_client.get_blob_client(f"templates/{filename}")
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail="Template not found")
        blob_client.delete_blob()
        
        # Also clean up PdfTemplate metadata if exists
        db_tpl = db.query(models.PdfTemplate).filter(models.PdfTemplate.name == filename).first()
        if db_tpl:
            db.delete(db_tpl)
            db.commit()
            
        return {"message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/template-schema/{filename}")
async def get_template_schema(filename: str):
    """
    Extracts variable placeholders ({{ var }}) from the specified template.
    """
    is_pdf = filename.lower().endswith(".pdf")
    suffix = ".pdf" if is_pdf else ".docx"
    
    try:
        blob_client = container_client.get_blob_client(f"templates/{filename}")
        if not blob_client.exists():
             raise HTTPException(status_code=404, detail="Template not found")

        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        
        with open(tmp_path, "wb") as f:
            f.write(blob_client.download_blob().readall())

        if is_pdf:
            import re
            doc = fitz.open(tmp_path)
            vars_set = set()
            for page in doc:
                text = page.get_text()
                # Find all {{ var_name }}
                found = re.findall(r"\{\{\s*(.*?)\s*\}\}", text)
                for f in found:
                    vars_set.add(f.strip())
            doc.close()
        else:
            doc = DocxTemplate(tmp_path)
            vars_set = doc.get_undeclared_template_variables() 
        
        return {"placeholders": list(vars_set)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

# --- Authentication Endpoints ---

@app.post("/login", response_model=schemas.UserResponse)
def login(login_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == login_data.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    return user

@app.post("/auth/microsoft", response_model=schemas.UserResponse)
def login_microsoft(payload: dict, db: Session = Depends(get_db)):
    """
    Verifies Microsoft ID Token and logs in/registers the user.
    """
    token = payload.get("access_token") # or id_token
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
        
    # In a production environment, verify the token signature using PyJWT/python-jose
    # against Microsoft's public keys: https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys
    
    # For now (Simulated/Dev), we decode without verification if testing, 
    # OR we just trust the email sent by client (NOT SECURE for Prod, but OK for MVP if behind firewall)
    # Better: Use the email from the payload which MSAL extracted
    
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
            hashed_password=None, # SSO users have no local password
            auth_provider="microsoft",
            role="User", # Default role
            permissions={"departments": []}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user

@app.post("/users/save-signature")
async def save_user_signature(payload: schemas.UserSignatureUpdate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Process Base64 image
    img_data = payload.signature_base64
    if "," in img_data:
        img_data = img_data.split(",")[1]
    
    img_bytes = base64.b64decode(img_data)
    
    # Upload to Azure
    filename = f"signatures/user_{user.id}_{os.urandom(4).hex()}.png"
    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(img_bytes, overwrite=True)
    
    # Generate SAS URL (long-lived or permanent for user profile)
    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=CONTAINER_NAME,
        blob_name=filename,
        account_key=blob_service_client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(days=3650) # 10 years
    )
    url = f"https://{blob_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{filename}?{sas_token}"
    
    if payload.sig_type == "initial":
        user.saved_initials_url = url
    else:
        user.saved_signature_url = url
        
    db.commit()
    
    return {"message": f"{payload.sig_type.capitalize()} saved successfully", "url": url}

# --- Master Data Management (Admin) ---

@app.get("/departments", response_model=List[schemas.MasterDataResponse])
def get_departments(db: Session = Depends(get_db)):
    return db.query(models.Department).all()

@app.post("/departments", response_model=schemas.MasterDataResponse)
def create_department(data: schemas.MasterDataCreate, db: Session = Depends(get_db)):
    dept = db.query(models.Department).filter(models.Department.name == data.name).first()
    if dept:
        raise HTTPException(status_code=400, detail="Department already exists")
    dept = models.Department(name=data.name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept

@app.delete("/departments/{dept_id}")
def delete_department(dept_id: int, db: Session = Depends(get_db)):
    dept = db.query(models.Department).filter(models.Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(dept)
    db.commit()
    return {"message": "Department deleted"}

@app.get("/document-types", response_model=List[schemas.MasterDataResponse])
def get_document_types(db: Session = Depends(get_db)):
    return db.query(models.DocumentType).all()

@app.post("/document-types", response_model=schemas.MasterDataResponse)
def create_document_type(data: schemas.MasterDataCreate, db: Session = Depends(get_db)):
    dt = db.query(models.DocumentType).filter(models.DocumentType.name == data.name).first()
    if dt:
        raise HTTPException(status_code=400, detail="Document type already exists")
    dt = models.DocumentType(name=data.name)
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return dt

@app.delete("/document-types/{dt_id}")
def delete_document_type(dt_id: int, db: Session = Depends(get_db)):
    dt = db.query(models.DocumentType).filter(models.DocumentType.id == dt_id).first()
    if not dt:
        raise HTTPException(status_code=404, detail="Document type not found")
    db.delete(dt)
    db.commit()
    return {"message": "Document type deleted"}

# --- Dynamic Template Builder API ---

@app.get("/dynamic-templates", response_model=List[schemas.TemplateResponse])
def get_dynamic_templates(db: Session = Depends(get_db)):
    """List all visuals-built templates."""
    return db.query(models.DynamicTemplate).all()

@app.post("/dynamic-templates", response_model=schemas.TemplateResponse)
def create_dynamic_template(template: schemas.TemplateCreate, db: Session = Depends(get_db)):
    """Create a new visual template definition."""
    db_tpl = models.DynamicTemplate(
        name=template.name,
        category=template.category,
        layout=template.layout
    )
    db.add(db_tpl)
    db.commit()
    db.refresh(db_tpl)
    return db_tpl

@app.get("/dynamic-templates/{template_id}", response_model=schemas.TemplateResponse)
def get_dynamic_template(template_id: int, db: Session = Depends(get_db)):
    db_tpl = db.query(models.DynamicTemplate).filter(models.DynamicTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return db_tpl

@app.put("/dynamic-templates/{template_id}", response_model=schemas.TemplateResponse)
def update_dynamic_template(template_id: int, template: schemas.TemplateCreate, db: Session = Depends(get_db)):
    db_tpl = db.query(models.DynamicTemplate).filter(models.DynamicTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db_tpl.name = template.name
    db_tpl.category = template.category
    db_tpl.layout = template.layout
    db.commit()
    db.refresh(db_tpl)
    return db_tpl

@app.delete("/dynamic-templates/{template_id}")
def delete_dynamic_template(template_id: int, db: Session = Depends(get_db)):
    """Delete a visual template definition."""
    db_tpl = db.query(models.DynamicTemplate).filter(models.DynamicTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(db_tpl)
    db.commit()
    return {"message": "Template deleted"}

# --- PDF Template With Signatures API ---

@app.get("/pdf-templates", response_model=List[schemas.PdfTemplateResponse])
def get_pdf_templates(db: Session = Depends(get_db)):
    """List all PDF templates with signature configurations."""
    return db.query(models.PdfTemplate).all()

@app.post("/pdf-templates", response_model=schemas.PdfTemplateResponse)
def create_pdf_template(template: schemas.PdfTemplateCreate, db: Session = Depends(get_db)):
    """Create a new PDF template definition."""
    db_tpl = models.PdfTemplate(
        name=template.name,
        blob_url=template.blob_url,
        form_fields=template.form_fields,
        department=template.department,
        doc_type=template.doc_type
    )
    db.add(db_tpl)
    db.commit()
    db.refresh(db_tpl)
    return db_tpl

@app.get("/pdf-templates/{template_id}", response_model=schemas.PdfTemplateResponse)
def get_pdf_template(template_id: int, db: Session = Depends(get_db)):
    db_tpl = db.query(models.PdfTemplate).filter(models.PdfTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return db_tpl

@app.put("/pdf-templates/{template_id}", response_model=schemas.PdfTemplateResponse)
def update_pdf_template(template_id: int, template: schemas.PdfTemplateUpdate, db: Session = Depends(get_db)):
    db_tpl = db.query(models.PdfTemplate).filter(models.PdfTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template.name is not None:
        db_tpl.name = template.name
    if template.form_fields is not None:
        db_tpl.form_fields = template.form_fields
    if template.department is not None:
        db_tpl.department = template.department
    if template.doc_type is not None:
        db_tpl.doc_type = template.doc_type
        
    db.commit()
    db.refresh(db_tpl)
    return db_tpl

@app.delete("/pdf-templates/{template_id}")
def delete_pdf_template(template_id: int, db: Session = Depends(get_db)):
    db_tpl = db.query(models.PdfTemplate).filter(models.PdfTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(db_tpl)
    db.commit()
    return {"message": "Template deleted"}

# --- User Management (Admin) ---

@app.get("/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

@app.post("/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
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
    return db_user

@app.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
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
    return db_user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted"}

# --- Workflow Management Endpoints ---

@app.get("/workflows", response_model=List[schemas.WorkflowResponse])
def get_workflows(db: Session = Depends(get_db)):
    return db.query(models.Workflow).all()

@app.post("/workflows", response_model=schemas.WorkflowResponse)
def create_or_update_workflow(wf: schemas.WorkflowCreate, db: Session = Depends(get_db)):
    # Check if exists
    existing = db.query(models.Workflow).filter(
        models.Workflow.department == wf.department,
        models.Workflow.doc_type == wf.doc_type
    ).first()
    
    if existing:
        existing.approvers = wf.approvers
        existing.signers = wf.signers
        db.commit()
        db.refresh(existing)
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
        return new_wf

def prepare_request_pdf(db: Session, req: models.DocumentRequest):
    """
    Resolves the workflow and generates the PDF for a request.
    Ensures current_pdf_url is populated for review.
    """
    # 1. Determine approvers from workflow (DB Logic)
    db_workflow = db.query(models.Workflow).filter(
        models.Workflow.department == req.department,
        models.Workflow.doc_type == req.doc_type
    ).first()

    if db_workflow:
        approvers = db_workflow.approvers
        signers = db_workflow.signers
    else:
        # Fallback to file config
        workflow_data = APPROVAL_FLOWS.get(req.department, {}).get(req.doc_type)
        if not workflow_data:
             # Default fallback
             approvers = ["Manager"]
             signers = []
        else:
             approvers = workflow_data.get("approvers", [])
             signers = workflow_data.get("signers", [])

    all_steps = approvers + signers
    
    # Update form data to include approvers for template rendering
    form_data = dict(req.form_data)
    for idx, role in enumerate(all_steps):
        # Look up user by role OR email (case-insensitive)
        user = db.query(models.User).filter(
            or_(
                models.User.role.ilike(role.strip()),
                models.User.email.ilike(role.strip())
            )
        ).first()
        if user:
            form_data[f"approver_{idx+1}_name"] = user.full_name
            form_data[f"approver_{idx+1}_position"] = user.job_position or user.role
        else:
            # Fallback to the role name if no specific person is assigned
            form_data[f"approver_{idx+1}_name"] = role 
            form_data[f"approver_{idx+1}_position"] = role
        
    # Ensure we clear unused slots up to 5
    for i in range(len(all_steps) + 1, 6):
        form_data[f"approver_{i}_name"] = ""
        form_data[f"approver_{i}_position"] = ""
        
    req.form_data = form_data 

    # 2. Generate PDF
    dynamic_template = db.query(models.DynamicTemplate).filter(models.DynamicTemplate.name == req.template_name).first()
    pdf_template = db.query(models.PdfTemplate).filter(models.PdfTemplate.name == req.template_name).first()
    
    pdf_text_fields = []
    if pdf_template and pdf_template.form_fields:
        pdf_text_fields = [f for f in pdf_template.form_fields if f.get('type') == 'text']
    
    try:
        layout = dynamic_template.layout if dynamic_template else None
        pdf_url, signature_anchors = generate_pdf_logic(req.template_name, form_data, layout=layout, pdf_text_fields=pdf_text_fields)
        req.current_pdf_url = pdf_url
        if not req.original_pdf_url:
            req.original_pdf_url = pdf_url # Keep original
    except Exception as e:
        print(f"PDF Prep Error: {e}")
        # For submission it's critical. For draft, we try our best.
        if req.status != "Draft":
            raise HTTPException(status_code=500, detail=f"PDF Generation failed: {e}")

    return all_steps

# --- Document Request Workflow Endpoints ---

@app.post("/requests", response_model=schemas.RequestResponse)
def create_draft(request: schemas.RequestCreate, db: Session = Depends(get_db)):
    """Creates a new document request in 'Draft' status."""
    db_request = models.DocumentRequest(
        template_name=request.template_name,
        requester_name=request.requester_name if request.requester_name else request.form_data.get('full_name', 'User'),
        requester_email=request.requester_email,
        department=request.department,
        doc_type=request.doc_type,
        form_data=request.form_data,
        supporting_documents=request.supporting_documents if request.supporting_documents else [],
        status="Draft"
    )
    db.add(db_request)
    
    # Generate PDF preview even for Draft
    try:
        prepare_request_pdf(db, db_request)
    except Exception as e:
        print(f"Draft PDF generation warning: {e}")
        # We don't crash the draft save if PDF gen fails, but we log it.

    db.commit()
    db.refresh(db_request)
    return db_request

@app.get("/requests", response_model=List[schemas.RequestResponse])
def read_requests(user_email: Optional[str] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List requests. 
    If user_email is provided, filter based on user role and permissions.
    """
    query = db.query(models.DocumentRequest)
    
    # Filter out Archived by default
    query = query.filter(models.DocumentRequest.status != "Archived")
    
    if user_email:
        user = db.query(models.User).filter(models.User.email.ilike(user_email)).first()
        if user and user.role != "Admin":
            scope = user.access_scope or "global"
            # Robustly handle missing/null permissions JSON
            permissions = user.permissions or {}
            if not isinstance(permissions, dict):
                permissions = {}
            
            # Base filters for access scope
            scope_filters = []
            if scope == "own":
                scope_filters.append(models.DocumentRequest.requester_email == user_email)
            elif scope == "department":
                allowed_depts = permissions.get("departments", [])
                if allowed_depts:
                    scope_filters.append(models.DocumentRequest.department.in_(allowed_depts))
                else:
                    # If no departments allowed, they can at least see their own or those they sign
                    scope_filters.append(models.DocumentRequest.requester_email == user_email)

            # CRITICAL FIX: Also include requests where the user is an approver/signer
            # This ensures that even with 'own' or 'department' scope, they see what they need to sign.
            signer_filter = models.DocumentRequest.approvals.any(
                or_(
                    models.Approval.role.ilike(user.role),
                    models.Approval.role.ilike(user_email)
                )
            )
            
            if scope_filters:
                # User sees: (Scope Permissions) OR (Requests they need to sign)
                query = query.filter(or_(*scope_filters, signer_filter))
            else:
                # Global scope or fallback: still allow seeing signed requests
                # (Though global already sees everything not archived)
                pass
                
    return query.offset(skip).limit(limit).all()

@app.get("/requests/{request_id}", response_model=schemas.RequestResponse)
def read_request(request_id: int, db: Session = Depends(get_db)):
    """Get request details."""
    req = db.query(models.DocumentRequest).filter(models.DocumentRequest.id == request_id).first()
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # JIT PDF generation for old drafts if needed
    if req.status == "Draft" and not req.current_pdf_url:
        try:
            prepare_request_pdf(db, req)
            db.commit()
            db.refresh(req)
        except Exception as e:
            print(f"JIT PDF generation warning: {e}")

    return req

@app.post("/requests/archive")
def bulk_archive_requests(payload: schemas.ArchiveRequest, db: Session = Depends(get_db)):
    """Bulk archive requests (Admin only)."""
    user = db.query(models.User).filter(models.User.email == payload.user_email).first()
    if not user or user.role != "Admin":
         raise HTTPException(status_code=403, detail="Only Admins can archive documents")
    
    # Update all requests in the list
    db.query(models.DocumentRequest).filter(models.DocumentRequest.id.in_(payload.request_ids)).update(
        {models.DocumentRequest.status: "Archived"}, synchronize_session=False
    )
    db.commit()
    return {"message": f"{len(payload.request_ids)} requests archived successfully"}

def send_email_notification(db: Session, to_email: str, subject: str, content: str, request_id: int):
    """
    Sends an email notification using the configured SMTP server.
    Logs the attempt to the database.
    """
    config = db.query(models.EmailConfig).first()
    if not config:
        log = models.EmailLog(
            recipient=to_email,
            subject=subject,
            status="Failed",
            error_message="Email configuration not found",
            request_id=request_id
        )
        db.add(log)
        db.commit()
        print("Email Config Missing")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{config.from_name} <{config.from_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(content, 'html'))

        if config.encryption == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, context=context) as server:
                if config.username and config.password:
                    server.login(config.username, config.password)
                server.send_message(msg)
        else:
             with smtplib.SMTP(config.smtp_server, config.smtp_port) as server:
                if config.encryption == "tls":
                    server.starttls()
                if config.username and config.password:
                    server.login(config.username, config.password)
                server.send_message(msg)
        
        log = models.EmailLog(
            recipient=to_email,
            subject=subject,
            status="Sent",
            request_id=request_id
        )
        db.add(log)
        db.commit()
        print(f"Email sent to {to_email}")

    except Exception as e:
        print(f"Failed to send email: {e}")
        log = models.EmailLog(
            recipient=to_email,
            subject=subject,
            status="Failed",
            error_message=str(e),
            request_id=request_id
        )
        db.add(log)
        db.commit()

@app.post("/requests/{request_id}/submit")
def submit_request(request_id: int, db: Session = Depends(get_db)):
    """
    Submits a draft request for approval.
    """
    """
    Submits a draft request for approval.
    1. Locks the content (generates PDF).
    2. Updates status to 'Pending'.
    3. Creates approval steps based on workflow (DB Logic).
    """
    try:
        req = db.query(models.DocumentRequest).filter(models.DocumentRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        
        if req.status != "Draft":
             raise HTTPException(status_code=400, detail=f"Cannot submit request in status: {req.status}")

        # 1. & 2. Resolve workflow and Generate PDF
        all_steps = prepare_request_pdf(db, req)

        # 3. Create Approval Steps
        for idx, role in enumerate(all_steps):
            step = models.Approval(
                request_id=req.id,
                role=role,
                step_number=idx + 1,
                status="Pending"
            )
            db.add(step)

        req.status = "Pending Approval"
        db.commit()
        
        # 4. Send Email Notification to First Approver
        try:
            first_step = all_steps[0]
            # Resolve email
            user = db.query(models.User).filter(
                or_(
                    models.User.role.ilike(first_step.strip()),
                    models.User.email.ilike(first_step.strip())
                )
            ).first()
            
            target_email = user.email if user else (first_step if "@" in first_step else None)
            
            if target_email:
                subject = f"Action Required: Approve {req.doc_type} Request #{req.id}"
                content = f"""
                <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                    <div style="background-color: #003366; color: white; padding: 20px; text-align: center;">
                        <h2 style="margin: 0; font-weight: 500;">Action Required: Document Approval</h2>
                    </div>
                    <div style="padding: 30px; background-color: #fcfcfc;">
                        <p style="font-size: 16px; margin-top: 0;">Hello,</p>
                        <p style="font-size: 15px; color: #555;">A new <strong>{req.doc_type}</strong> document request has been submitted and requires your review and approval.</p>
                        
                        <div style="background-color: #ffffff; border: 1px solid #eee; border-radius: 6px; padding: 15px; margin: 20px 0;">
                            <p style="margin: 5px 0; font-size: 14px;"><strong>Request ID:</strong> #{req.id}</p>
                            <p style="margin: 5px 0; font-size: 14px;"><strong>Requester:</strong> {req.requester_name}</p>
                            <p style="margin: 5px 0; font-size: 14px;"><strong>Document Type:</strong> {req.doc_type}</p>
                        </div>
                        
                        <div style="text-align: center; margin-top: 30px;">
                            <a href="https://esign.berkeleyuae.com" style="background-color: #0055a5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">View and Sign Document</a>
                        </div>
                    </div>
                    <div style="background-color: #f4f4f4; padding: 15px; text-align: center; font-size: 12px; color: #888;">
                        <p style="margin: 0;">This is an automated notification from the Esign Notifications. Please do not reply.</p>
                    </div>
                </div>
                """
                send_email_notification(db, target_email, subject, content, req.id)
            else:
                print(f"Could not resolve email for first approver: {first_step}")

        except Exception as e:
            print(f"Email Notification Error: {e}")

        return {"message": "Request submitted successfully", "pdf_url": req.current_pdf_url}
    except Exception as e:
        print(f"SUBMIT ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approvals/{approval_id}/sign")
def sign_approval(approval_id: int, payload: schemas.ApprovalSignRequest, db: Session = Depends(get_db)):
    """
    Signs an approval step by embedding the signature image into the PDF.
    """
    approval = db.query(models.Approval).filter(models.Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval step not found")
    
    if approval.status != "Pending":
        raise HTTPException(status_code=400, detail="Approval is not pending")
        
    req = approval.request
    if not req.current_pdf_url:
        raise HTTPException(status_code=400, detail="No PDF generated for this request")
        
    # Validation: Ensure strict sequence (Chain of Command)
    # Check if there are any pending steps with a lower step number
    pending_prior_approvals = db.query(models.Approval).filter(
        models.Approval.request_id == req.id,
        models.Approval.step_number < approval.step_number,
        models.Approval.status != "Signed"
    ).first()
    
    if pending_prior_approvals:
        raise HTTPException(status_code=400, detail="Previous approval steps must be completed in order.")
        
    # Validation: Ensure signer matches the approval role
    signer_email = payload.user_email
    if not signer_email:
        raise HTTPException(status_code=400, detail="User email required for signing")

    signer = db.query(models.User).filter(models.User.email == signer_email).first()
    if not signer:
        raise HTTPException(status_code=404, detail="Signer user not found")

    # Loose check: If user is Admin, allow override? 
    # Or strict check: User role must match approval role (case insensitive)
    # Also check if the 'approval.role' is actually a Person's Name or a Role?
    # In earlier steps we saw: form_data[f"approver_{idx+1}_name"] = user.full_name OR role
    # The models.Approval.role stores the JOB TITLE / ROLE name (e.g. "IT Manager").
    
    # We compare signer.role (from DB) with approval.role
    # Normalize strings
    signer_role = (signer.role or "").strip().lower()
    required_role = (approval.role or "").strip().lower()
    signer_email = (signer.email or "").strip().lower()
    
    if signer_role != required_role and signer_role != "admin" and signer_email != required_role:
         raise HTTPException(status_code=403, detail=f"Unauthorized. You are '{signer.role}', but this step requires '{approval.role}'.")
        
    try:
        # Extract blob name from URL
        parts = req.current_pdf_url.split(f"/{CONTAINER_NAME}/")
        if len(parts) < 2:
             # Fallback if URL format is different
             # try to find 'generated/' in path
             if "generated/" in req.current_pdf_url:
                 path_after = req.current_pdf_url.split("generated/")[1]
                 blob_name = "generated/" + path_after.split("?")[0]
             else:
                 raise HTTPException(status_code=500, detail="Could not parse PDF URL")
        else:
             blob_name = parts[1].split('?')[0] # remove query params

        # Download PDF
        blob_client = container_client.get_blob_client(blob_name)
        stream = blob_client.download_blob()
        pdf_bytes = stream.readall()
        
        # Determine Signature Source
        if payload.use_saved:
            saved_url = signer.saved_initials_url if payload.sig_type == "initial" else signer.saved_signature_url
            if not saved_url:
                raise HTTPException(status_code=400, detail=f"No saved {payload.sig_type} found for this user.")
            
            # Fetch saved signature from Azure
            s_parts = saved_url.split(f"/{CONTAINER_NAME}/")
            if len(s_parts) < 2:
                 raise HTTPException(status_code=500, detail=f"Invalid saved {payload.sig_type} URL")
            s_blob_name = s_parts[1].split('?')[0]
            s_blob_client = container_client.get_blob_client(s_blob_name)
            sig_bytes = s_blob_client.download_blob().readall()
        else:
            # Decode Signature Image from payload
            sig_b64 = payload.signature_base64
            if not sig_b64:
                 raise HTTPException(status_code=400, detail="Signature image data required")
            if "," in sig_b64:
                sig_b64 = sig_b64.split(",")[1]
            sig_bytes = base64.b64decode(sig_b64)
        
        # Apply Signature using PyMuPDF (fitz)
        doc = fitz.open("pdf", pdf_bytes)
        
        # HEAL: Attempt to fill any remaining placeholders using the request's form_data
        # This handles cases where the PDF was generated before the filling logic was added.
        if req.form_data:
            _fill_pdf_placeholders(doc, req.form_data)
            
        page = doc[len(doc) - 1] # Sign last page
        
        # --- Signature/Field Placement Logic ---
        pdf_template = db.query(models.PdfTemplate).filter(models.PdfTemplate.name == req.template_name).first()
        fields_placed = 0

        if pdf_template and pdf_template.form_fields:
            target_role = (approval.role or "").strip().lower()
            for f in pdf_template.form_fields:
                if (f.get('assignee') or "").strip().lower() == target_role:
                    page_idx = f.get('page', 1) - 1
                    if page_idx >= len(doc): continue
                    p_rect = doc[page_idx].rect
                    x0, y0 = (f['x'] / 100) * p_rect.width, (f['y'] / 100) * p_rect.height
                    x1, y1 = ((f['x'] + f['width']) / 100) * p_rect.width, ((f['y'] + f['height']) / 100) * p_rect.height
                    ftype = f.get('type', 'signature')
                    rect = fitz.Rect(x0, y0, x1, y1)
                    if ftype == 'date':
                        date_str = datetime.now().strftime("%Y-%m-%d")
                        for fs in range(12, 4, -1):
                            r = fitz.Rect(rect)
                            text_h = fs * 1.2
                            if r.height > text_h: r.y0 += (r.height - text_h) / 2
                            if doc[page_idx].insert_textbox(r, date_str, fontsize=fs, align=1) >= 0: break
                    elif ftype == 'name':
                        signer_name = signer.full_name if signer else (f.get('assignee') or target_role)
                        signer_text = f"{signer_name}\n({signer.job_position})" if signer and getattr(signer, 'job_position', None) else signer_name
                        lines = signer_text.count('\n') + 1
                        for fs in range(12, 4, -1):
                            r = fitz.Rect(rect)
                            text_h = fs * 1.2 * lines
                            if r.height > text_h: r.y0 += (r.height - text_h) / 2
                            if doc[page_idx].insert_textbox(r, signer_text, fontsize=fs, align=1) >= 0: break
                    elif ftype != 'text':
                        # Signature or Initial
                        
                        # Pad the signature box slightly to look nicely centered
                        pad = min(rect.width, rect.height) * 0.1
                        r = rect + fitz.Rect(pad, pad, -pad, -pad)
                        doc[page_idx].insert_image(r, stream=sig_bytes)
                    
                    fields_placed += 1
            if fields_placed > 0: print(f"DEBUG: Placed {fields_placed} coordinate fields for {approval.role}")

        # Fallback: Underscore/Header Search logic
        if fields_placed == 0:
            page = doc[len(doc) - 1] # Sign last page
            # Dynamic Signature Placement (Improved)
            # Search for the signature placeholder lines
            sig_line_text = "________________________"
            all_lines = page.search_for(sig_line_text)
            
            # Search for the date placeholder lines
            date_line_text = "__________"
            all_date_lines = page.search_for(date_line_text)
            
            print(f"DEBUG: Found {len(all_lines)} signature lines and {len(all_date_lines)} date lines for step {approval.step_number}")
            
            if len(all_lines) >= approval.step_number:
                # Use the specific line for this step
                line_rect = all_lines[approval.step_number - 1]
                
                # Place signature box directly above the line
                x0 = line_rect.x0
                x1 = line_rect.x1
                y1 = line_rect.y0 - 2  # 2pt gap above line
                y0 = y1 - 30           # 30pt height
                
                rect = fitz.Rect(x0, y0, x1, y1)
                print(f"DEBUG: Placing signature at {rect}")
                
                # Date Insertion Logic
                if len(all_date_lines) >= approval.step_number:
                    date_rect = all_date_lines[approval.step_number - 1]
                    # Insert date text centered above/on the line
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    
                    # Calculate position: Center of line, slightly above
                    text_x = date_rect.x0 + 2 # slight padding
                    text_y = date_rect.y1 - 4 # slightly above baseline
                    
                    # Insert Text
                    page.insert_text((text_x, text_y), date_str, fontsize=9, color=(0, 0, 0))
                    print(f"DEBUG: Inserted date '{date_str}' at {text_x},{text_y}")

            else:
                # Fallback to the previous "search for header" logic if lines not found
                header_rects = page.search_for("Signature") # Changed from "Signature & Date"
                if header_rects:
                    header_rect = header_rects[-1]
                    # If we couldn't find lines, the table might have shifted.
                    # Estimate position 40pts below header per step
                    y_offset = approval.step_number * 35 # approx row height
                    rect = fitz.Rect(header_rect.x0, header_rect.y1 + y_offset - 30, header_rect.x0 + 120, header_rect.y1 + y_offset - 2)
                else:
                    # Absolute fallback
                    rect = fitz.Rect(450, 650, 570, 700)
                print(f"DEBUG: Falling back to rect {rect}")

            page.insert_image(rect, stream=sig_bytes)
            print(f"DEBUG: Placed fallback signature at {rect}")
        
        # Save to bytes
        out_buffer = io.BytesIO()
        doc.save(out_buffer)
        doc.close()
        out_buffer.seek(0)
        
        # Upload new PDF
        new_filename = f"generated/signed_{req.id}_{approval.step_number}_{os.urandom(4).hex()}.pdf"
        new_blob = container_client.get_blob_client(new_filename)
        new_blob.upload_blob(out_buffer, overwrite=True)
        
        # Generate SAS
        sas_token = generate_blob_sas(
            account_name=new_blob.account_name,
            container_name=CONTAINER_NAME,
            blob_name=new_filename,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=365)
        )
        new_url = f"https://{new_blob.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{new_filename}?{sas_token}"
        
        # Update State
        approval.status = "Signed"
        approval.signed_at = datetime.utcnow()
        approval.signature_url = "embedded" # indicate it's in the PDF
        
        req.current_pdf_url = new_url
        req.updated_at = datetime.utcnow()
        
        # Check if all signed
        all_apps = db.query(models.Approval).filter(models.Approval.request_id == req.id).all()
        if all(a.status == "Signed" for a in all_apps):
            req.status = "Approved"
            
        db.commit()
        
        # Notify next approver if exists
        next_step = db.query(models.Approval).filter(
            models.Approval.request_id == req.id,
            models.Approval.step_number == approval.step_number + 1
        ).first()

        if next_step:
            try:
                # Resolve email for next step
                next_role = next_step.role
                user = db.query(models.User).filter(
                    or_(
                        models.User.role.ilike(next_role.strip()),
                        models.User.email.ilike(next_role.strip())
                    )
                ).first()
                
                target_email = user.email if user else (next_role if "@" in next_role else None)
                
                if target_email:
                    subject = f"Action Required: Approve {req.doc_type} Request #{req.id}"
                    content = f"""
                    <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                        <div style="background-color: #003366; color: white; padding: 20px; text-align: center;">
                            <h2 style="margin: 0; font-weight: 500;">Action Required: Document Approval</h2>
                        </div>
                        <div style="padding: 30px; background-color: #fcfcfc;">
                            <p style="font-size: 16px; margin-top: 0;">Hello,</p>
                            <p style="font-size: 15px; color: #555;">Step {approval.step_number} is complete. Your approval is now required for step {next_step.step_number} of this request.</p>
                            
                            <div style="background-color: #ffffff; border: 1px solid #eee; border-radius: 6px; padding: 15px; margin: 20px 0;">
                                <p style="margin: 5px 0; font-size: 14px;"><strong>Request ID:</strong> #{req.id}</p>
                                <p style="margin: 5px 0; font-size: 14px;"><strong>Requester:</strong> {req.requester_name}</p>
                                <p style="margin: 5px 0; font-size: 14px;"><strong>Document Type:</strong> {req.doc_type}</p>
                            </div>
                            
                            <div style="text-align: center; margin-top: 30px;">
                                <a href="https://esign.berkeleyuae.com" style="background-color: #0055a5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">View and Sign Document</a>
                            </div>
                        </div>
                        <div style="background-color: #f4f4f4; padding: 15px; text-align: center; font-size: 12px; color: #888;">
                            <p style="margin: 0;">This is an automated notification from the Esign Notifications. Please do not reply.</p>
                        </div>
                    </div>
                    """
                    send_email_notification(db, target_email, subject, content, req.id)
            except Exception as e:
                print(f"Email Notification Error: {e}")
        
        return {"message": "Signature applied successfully", "pdf_url": new_url}

    except Exception as e:
        print(f"Signing Error: {e}")
        # In case of 404 from azure, capture it
        raise HTTPException(status_code=500, detail=f"Signing failed: {str(e)}")


# --- Helper Function for PDF Generation (Refactored from original logic) ---

def _fill_pdf_placeholders(doc, context: dict):
    """
    Helper to search and replace {{ key }} placeholders in a PyMuPDF doc.
    Modifies the doc in-place.
    """
    if not context or not isinstance(context, dict):
        return

    for page in doc:
        # 1. search for all placeholders
        text = page.get_text()
        import re
        # Find pattern {{ key }}
        placeholders = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", text))
        
        for key in placeholders:
            val = context.get(key, "")
            if val is None: val = ""
            val = str(val)
            
            # Search for specific patterns to find rects
            # We try: {{ key }}, {{key}}, {{  key  }}
            hits = page.search_for(f"{{{{ {key} }}}}") + \
                   page.search_for(f"{{{{{key}}}}}") + \
                   page.search_for(f"{{{{  {key}  }}}}")
            
            for rect in hits:
                # Redact old text
                page.add_redact_annot(rect, fill=(1, 1, 1)) # White fill
                
                # Insert new text
                # Simple insertion at top-left of rect
                # Font size 11 is generic; could likely be improved by analyzing existing text span,
                # but PyMuPDF's low-level API makes that complex. 11/Helv is safe for standard forms.
                page.insert_text(
                    rect.tl, 
                    val,
                    fontsize=11,
                    fontname="helv",
                    color=(0, 0, 0)
                )
        
        page.apply_redactions()

def generate_pdf_logic(template_name: str, context: dict, layout: list = None, pdf_text_fields: list = None):
    """
    Core logic to generate PDF from DOCX or dynamic layout.
    """
    tmp_docx_path = None
    rendered_docx_path = None
    tmp_pdf_path = None
    
    try:
        is_pdf = template_name.lower().endswith(".pdf")

        # Feature: If PDF is requested but a DOCX exists, prefer DOCX (docxtpl is more robust)
        if is_pdf:
             docx_name = template_name.replace(".pdf", ".docx")
             blob_check = container_client.get_blob_client(f"templates/{docx_name}")
             if blob_check.exists():
                 print(f"DEBUG: Found source DOCX {docx_name} for requested PDF. Switching to docxtpl.")
                 template_name = docx_name
                 is_pdf = False

        if layout:
            # Dynamic Rendering
            fd, tmp_pdf_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            generate_dynamic_pdf(layout, context, tmp_pdf_path)
        elif is_pdf:
            # Native PDF Template
            blob_client = container_client.get_blob_client(f"templates/{template_name}")
            if not blob_client.exists():
                raise Exception("Template not found")

            fd, tmp_pdf_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            # Download original PDF
            pdf_data = blob_client.download_blob().readall()
            
            # Open with PyMuPDF for editing
            doc = fitz.open("pdf", pdf_data)
            
            # Fill placeholders
            _fill_pdf_placeholders(doc, context)
            
            # Fill configured text fields from PdfAnnotator
            if pdf_text_fields:
                for f in pdf_text_fields:
                    assignee = f.get('assignee', '')
                    val = str(context.get(assignee, ''))
                    page_idx = f.get('page', 1) - 1
                    if page_idx >= len(doc): continue
                    
                    p_rect = doc[page_idx].rect
                    x0, y0 = (f['x'] / 100) * p_rect.width, (f['y'] / 100) * p_rect.height
                    x1, y1 = ((f['x'] + f['width']) / 100) * p_rect.width, ((f['y'] + f['height']) / 100) * p_rect.height
                    
                    rect = fitz.Rect(x0, y0, x1, y1)
                    doc[page_idx].insert_textbox(rect, val, fontsize=11, fontname="helv", color=(0, 0, 0), align=0)
            
            doc.save(tmp_pdf_path)
        else:
            # Legacy DOCX Rendering
            blob_client = container_client.get_blob_client(f"templates/{template_name}")
            if not blob_client.exists():
                raise Exception("Template not found")

            fd, tmp_docx_path = tempfile.mkstemp(suffix=".docx")
            os.close(fd)
            with open(tmp_docx_path, "wb") as f:
                f.write(blob_client.download_blob().readall())

            # Render
            doc = DocxTemplate(tmp_docx_path)
            doc.render(context)
            
            fd2, rendered_docx_path = tempfile.mkstemp(suffix=".docx")
            os.close(fd2)
            doc.save(rendered_docx_path)

            # Convert to PDF
            subprocess.run(
                ['soffice', '--headless', '--convert-to', 'pdf', '--outdir', os.path.dirname(rendered_docx_path), rendered_docx_path],
                check=True
            )
            tmp_pdf_path = rendered_docx_path.replace(".docx", ".pdf")
        
        # Upload generated PDF
        unique_id = f"doc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"
        pdf_blob_name = f"generated/{unique_id}.pdf"
        
        out_blob_client = container_client.get_blob_client(pdf_blob_name)
        with open(tmp_pdf_path, "rb") as data:
            out_blob_client.upload_blob(data, overwrite=True)

        # Generate SAS URL
        sas_token = generate_blob_sas(
            account_name=out_blob_client.account_name,
            container_name=CONTAINER_NAME,
            blob_name=pdf_blob_name,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=7) 
        )
        url = f"https://{out_blob_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{pdf_blob_name}?{sas_token}"
        
        return url, [] 

    except Exception as e:
        print(f"PDF GEN ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        if tmp_docx_path and os.path.exists(tmp_docx_path): os.remove(tmp_docx_path)
        if rendered_docx_path and os.path.exists(rendered_docx_path): os.remove(rendered_docx_path)
        if tmp_pdf_path and os.path.exists(tmp_pdf_path): os.remove(tmp_pdf_path)

# Retaining original endpoint for backward compatibility / testing
@app.post("/generate-document")
async def generate_document(payload: dict):
    # This is effectively a stateless version of submit_request
    # For now, just call the logic helper
    try:
        url, anchors = generate_pdf_logic(payload.get('template_name'), payload.get('data', {}))
        return {"url": url, "signature_anchors": anchors, "message": "Document generated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Email Configuration (Admin) ---

@app.get("/email-config", response_model=schemas.EmailConfigResponse)
def get_email_config(db: Session = Depends(get_db)):
    config = db.query(models.EmailConfig).first()
    if not config:
        # Return default placeholder
        return schemas.EmailConfigResponse(
            id=0,
            smtp_server="smtp.sendgrid.net",
            smtp_port=587,
            username="apikey",
            from_email="noreply@domain.com",
            from_name="eSign Notifications",
            encryption="tls",
            imap_server="imap.sendgrid.net", # Placeholder
            imap_port=993,
            imap_ssl=True
        )
    return config

@app.post("/email-config", response_model=schemas.EmailConfigResponse)
def save_email_config(config_in: schemas.EmailConfigUpdate, db: Session = Depends(get_db)):
    db_config = db.query(models.EmailConfig).first()
    if not db_config:
        db_config = models.EmailConfig()
        db.add(db_config)
    
    db_config.smtp_server = config_in.smtp_server
    db_config.smtp_port = config_in.smtp_port
    db_config.username = config_in.username
    if config_in.password: # Only update if provided
        db_config.password = config_in.password
    db_config.from_email = config_in.from_email
    db_config.from_name = config_in.from_name
    db_config.encryption = config_in.encryption
    
    # Incoming
    db_config.imap_server = config_in.imap_server
    db_config.imap_port = config_in.imap_port
    db_config.imap_username = config_in.imap_username
    if config_in.imap_password:
        db_config.imap_password = config_in.imap_password
    db_config.imap_ssl = config_in.imap_ssl
    
    db.commit()
    db.refresh(db_config)
    return db_config

@app.get("/email-logs", response_model=List[schemas.EmailLogResponse])
def get_email_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get email logs for admin review.
    """
    logs = db.query(models.EmailLog).order_by(models.EmailLog.sent_at.desc()).offset(skip).limit(limit).all()
    return logs

@app.post("/email-config/test")
def test_email_connection(payload: schemas.EmailTestRequest, db: Session = Depends(get_db)):
    config = db.query(models.EmailConfig).first()
    
    if not config:
         raise HTTPException(status_code=400, detail="Please save configuration first.")

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{config.from_name} <{config.from_email}>"
        msg['To'] = payload.target_email
        msg['Subject'] = "eSign Test Email"
        body = "This is a test email from your eSign application configuration."
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect
        if config.encryption == "ssl":
             server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port)
        else:
             server = smtplib.SMTP(config.smtp_server, config.smtp_port)
             if config.encryption == "tls":
                 server.starttls()
        
        if config.username and config.password:
            server.login(config.username, config.password)
            
        server.send_message(msg)
        server.quit()
        return {"message": "Test email sent successfully!"}
    except Exception as e:
        print(f"SMTP Error: {e}")
        # Return 400 so frontend shows it nicely
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")

@app.post("/email-config/test-incoming")
def test_email_incoming(db: Session = Depends(get_db)):
    config = db.query(models.EmailConfig).first()
    
    if not config:
         raise HTTPException(status_code=400, detail="Please save configuration first.")

    try:
        # Use config details
        host = config.imap_server
        port = config.imap_port or 993
        user = config.imap_username
        password = config.imap_password
        use_ssl = config.imap_ssl if config.imap_ssl is not None else True

        if not host or not user:
            raise HTTPException(status_code=400, detail="IMAP settings (host/user) are incomplete.")
            
        if not password:
            raise HTTPException(status_code=400, detail="IMAP password is required.")

        print(f"Testing IMAP: {host}:{port}, User: {user}, SSL: {use_ssl}")

        if use_ssl:
            mail = imaplib.IMAP4_SSL(host, port)
        else:
            mail = imaplib.IMAP4(host, port)

        mail.login(user, password)
        mail.select('inbox')
        typ, data = mail.search(None, 'ALL')
        
        count = 0
        if data and data[0]:
             count = len(data[0].split())
             
        mail.logout()
        
        return {"message": f"Connection successful! Inbox has {count} messages."}
    except Exception as e:
        print(f"IMAP Error: {e}")
        # Return 400 so frontend shows it nicely
        raise HTTPException(status_code=400, detail=f"Incoming connection failed: {str(e)}")
