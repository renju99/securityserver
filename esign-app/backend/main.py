from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
import models
from routers import auth, templates, admin, requests
from core.security import get_password_hash
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize Database
Base.metadata.create_all(bind=engine)

def ensure_schema():
    """Healer for database columns across versions."""
    with engine.connect() as conn:
        # We handle transactions manually to avoid aborting the whole block if one fails
        
        # 1. Audit Logs
        try:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip_address TEXT"))
            conn.commit()
        except Exception:
            conn.rollback()

        # 2. Document Requests
        request_cols = [
            ("requester_name", "TEXT"),
            ("requester_email", "TEXT"),
            ("department", "TEXT"),
            ("doc_type", "TEXT"),
            ("template_name", "TEXT"),
            ("form_data", "JSON"),
            ("status", "TEXT"),
            ("current_pdf_url", "TEXT"),
            ("original_pdf_url", "TEXT"),
            ("supporting_documents", "JSON"),
            ("current_pdf_blob", "TEXT"),
            ("original_pdf_blob", "TEXT")
        ]
        for col, col_type in request_cols:
            try:
                conn.execute(text(f"ALTER TABLE document_requests ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                conn.commit()
            except Exception:
                conn.rollback()

        # 3. Approvals
        approval_cols = [
            ("comment", "TEXT"),
            ("delegated_to", "TEXT"),
            ("reminded_at", "TIMESTAMP")
        ]
        for col, col_type in approval_cols:
            try:
                conn.execute(text(f"ALTER TABLE approvals ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                conn.commit()
            except Exception:
                conn.rollback()

        # 4. Users
        user_cols = [
            ("job_position", "TEXT"),
            ("auth_provider", "TEXT"),
            ("access_scope", "TEXT"),
            ("saved_signature_url", "TEXT"),
            ("saved_initials_url", "TEXT")
        ]
        for col, col_type in user_cols:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                conn.commit()
            except Exception:
                conn.rollback()

        # 5. Email Config
        email_cols = [
            ("from_name", "TEXT"),
            ("encryption", "TEXT"),
            ("imap_server", "TEXT"),
            ("imap_port", "INTEGER"),
            ("imap_username", "TEXT"),
            ("imap_password", "TEXT"),
            ("imap_ssl", "BOOLEAN")
        ]
        for col, col_type in email_cols:
            try:
                conn.execute(text(f"ALTER TABLE email_config ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                conn.commit()
            except Exception:
                conn.rollback()

def seed_data():
    db = SessionLocal()
    try:
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
        
        if not db.query(models.Department).filter(models.Department.name == "IT").first():
            db.add(models.Department(name="IT"))
        if not db.query(models.DocumentType).filter(models.DocumentType.name == "Capex").first():
            db.add(models.DocumentType(name="Capex"))
            
        db.commit()
    finally:
        db.close()

# Core Lifecycle
ensure_schema()
seed_data()

app = FastAPI(
    title="Berkeley eSign API",
    description="Enterprise Document Generation and Digital Signature Platform",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root Endpoint
@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "eSign API",
        "version": "2.0.0",
        "docs": "/docs"
    }

# Mount Routers
app.include_router(auth.router)
app.include_router(templates.router)
app.include_router(admin.router)
app.include_router(requests.router)
