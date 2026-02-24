import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from models import AuditLog
from typing import Optional, Any, Dict

class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        user_email: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """Logs a system event to the audit_logs table."""
        try:
            log_entry = AuditLog(
                user_email=user_email,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                timestamp=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            print(f"Failed to log audit event: {e}")
            db.rollback()

    @staticmethod
    def calculate_pdf_hash(pdf_bytes: bytes) -> str:
        """Calculates SHA-256 hash of PDF bytes for integrity verification."""
        return hashlib.sha256(pdf_bytes).hexdigest()

audit_service = AuditService()
