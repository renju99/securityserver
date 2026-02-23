from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class RequestCreate(BaseModel):
    department: str
    doc_type: str
    template_name: str
    form_data: Dict[str, Any]
    requester_email: Optional[str] = None
    requester_name: Optional[str] = None

class ApprovalResponse(BaseModel):
    id: int
    role: str
    status: str
    signed_at: Optional[datetime]
    step_number: int  # Added step_number for ordering logic

class RequestResponse(BaseModel):
    id: int
    requester_name: Optional[str]
    requester_email: Optional[str]
    department: str
    doc_type: str
    template_name: str
    form_data: Dict[str, Any]
    status: str
    created_at: datetime
    current_pdf_url: Optional[str]
    approvals: List[ApprovalResponse] = []

    class Config:
        from_attributes = True

class WorkflowCreate(BaseModel):
    department: str
    doc_type: str
    approvers: List[str]
    signers: List[str]

class WorkflowResponse(BaseModel):
    id: int
    department: str
    doc_type: str
    approvers: List[str]
    signers: List[str]
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    email: str
    full_name: str
    job_position: Optional[str] = None
    password: Optional[str] = None
    role: str = "User" # Admin/User
    access_scope: str = "global"
    permissions: Optional[Dict[str, Any]] = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    job_position: Optional[str] = None
    role: str
    auth_provider: str
    access_scope: Optional[str] = "global"
    permissions: Optional[Dict[str, Any]] = None
    saved_signature_url: Optional[str] = None
    saved_initials_url: Optional[str] = None
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    job_position: Optional[str] = None
    role: Optional[str] = None
    access_scope: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    password: Optional[str] = None

class MasterDataCreate(BaseModel):
    name: str

class MasterDataResponse(BaseModel):
    id: int
    name: str
    class Config: 
        from_attributes = True

class LoginRequest(BaseModel):
    email: str
    password: str

class TemplateCreate(BaseModel):
    name: str
    category: str
    layout: List[Dict[str, Any]]

class TemplateResponse(BaseModel):
    id: int
    name: str
    category: str
    layout: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ApprovalSignRequest(BaseModel):
    signature_base64: Optional[str] = None # Optional if using saved
    user_email: str
    use_saved: bool = False
    sig_type: str = "full" # "full" or "initial"

class UserSignatureUpdate(BaseModel):
    email: str
    signature_base64: str
    sig_type: str = "full" # "full" or "initial"

class EmailConfigResponse(BaseModel):
    id: int
    smtp_server: str
    smtp_port: int
    username: Optional[str] = None
    from_email: str
    from_name: str
    encryption: str
    imap_server: Optional[str] = None
    imap_port: int = 993
    imap_username: Optional[str] = None
    imap_ssl: bool = True

    class Config:
        from_attributes = True

class EmailConfigUpdate(BaseModel):
    smtp_server: str
    smtp_port: int
    username: Optional[str] = None
    password: Optional[str] = None # Optional, if not updated, keep existing
    from_email: str
    from_name: str
    encryption: str
    
    imap_server: Optional[str] = None
    imap_port: int = 993
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None # Optional
    imap_ssl: bool = True

class EmailTestRequest(BaseModel):
    target_email: str

class ArchiveRequest(BaseModel):
    request_ids: List[int]
    user_email: str

class PdfTemplateCreate(BaseModel):
    name: str
    blob_url: str
    form_fields: Optional[List[Dict[str, Any]]] = []
    department: Optional[str] = None
    doc_type: Optional[str] = None

class PdfTemplateUpdate(BaseModel):
    name: Optional[str] = None
    form_fields: Optional[List[Dict[str, Any]]] = None
    department: Optional[str] = None
    doc_type: Optional[str] = None

class PdfTemplateResponse(BaseModel):
    id: int
    name: str
    blob_url: str
    form_fields: List[Dict[str, Any]]
    department: Optional[str] = None
    doc_type: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class EmailLogResponse(BaseModel):
    id: int
    recipient: str
    subject: str
    status: str
    error_message: Optional[str] = None
    sent_at: datetime
    request_id: Optional[int] = None
    class Config:
        from_attributes = True
