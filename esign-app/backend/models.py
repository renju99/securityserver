from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
import datetime
from database import Base

class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_name = Column(String, default="User")
    requester_email = Column(String, nullable=True)
    department = Column(String)
    doc_type = Column(String)
    template_name = Column(String)
    form_data = Column(JSON) # Stores form input values
    status = Column(String, default="Draft") # Draft, Pending Approval, Approved, Rejected
    
    current_pdf_url = Column(String, nullable=True) # URL of the generated PDF (unsigned or partially signed)
    original_pdf_url = Column(String, nullable=True) # Original unsigned PDF
    supporting_documents = Column(JSON, default=list) # List of { name, url, size }
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    approvals = relationship("Approval", back_populates="request")

class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("document_requests.id"))
    
    role = Column(String) # e.g. "IT Manager", "CTO"
    step_number = Column(Integer) # Order of approval
    status = Column(String, default="Pending") # Pending, Signed, Rejected
    
    signed_at = Column(DateTime, nullable=True)
    signature_url = Column(String, nullable=True) # URL to signature image if any
    
    request = relationship("DocumentRequest", back_populates="approvals")

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String)
    doc_type = Column(String)
    approvers = Column(JSON) # List of strings e.g. ["Manager", "HR"]
    signers = Column(JSON)   # List of strings e.g. ["CEO"]
    
    from sqlalchemy import UniqueConstraint
    __table_args__ = (UniqueConstraint('department', 'doc_type', name='_dept_doctype_uc'),)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    job_position = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True) # Null for SSO users
    role = Column(String, default="User") # "Admin" or "User"
    auth_provider = Column(String, default="local") # "local" or "microsoft"
    access_scope = Column(String, default="global") # "global", "department", or "own"
    permissions = Column(JSON, default=dict) # e.g. {"departments": ["IT"], "can_delete": false}
    saved_signature_url = Column(String, nullable=True) # Adobe-style saved signature
    saved_initials_url = Column(String, nullable=True)  # Adobe-style saved initials

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class DocumentType(Base):
    __tablename__ = "document_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class DynamicTemplate(Base):
    __tablename__ = "dynamic_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    category = Column(String) # e.g. "HR", "Finance"
    layout = Column(JSON) # Stores the sequence of blocks/fields
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class EmailConfig(Base):
    __tablename__ = "email_config"
    id = Column(Integer, primary_key=True, index=True)
    smtp_server = Column(String, default="smtp.sendgrid.net")
    smtp_port = Column(Integer, default=587)
    username = Column(String, nullable=True) # e.g. "apikey"
    password = Column(String, nullable=True) # The actual API key or password
    from_email = Column(String, default="noreply@domain.com")
    from_name = Column(String, default="eSign Notifications")
    encryption = Column(String, default="tls") # "none", "tls", "ssl"

    # Incoming Server (IMAP/POP3)
    imap_server = Column(String, nullable=True)
    imap_port = Column(Integer, default=993)
    imap_username = Column(String, nullable=True)
    imap_password = Column(String, nullable=True)
    imap_ssl = Column(Boolean, default=True)

class PdfTemplate(Base):
    __tablename__ = "pdf_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    blob_url = Column(String) # URL to the PDF file
    form_fields = Column(JSON, default=list) # List of { id, type: 'signature', page, x, y, width, height, assignee_role }
    department = Column(String, nullable=True)
    doc_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EmailLog(Base):
    __tablename__ = "email_logs"
    id = Column(Integer, primary_key=True, index=True)
    recipient = Column(String)
    subject = Column(String)
    status = Column(String) # "Sent", "Failed"
    error_message = Column(String, nullable=True)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)
    request_id = Column(Integer, ForeignKey("document_requests.id"), nullable=True)


