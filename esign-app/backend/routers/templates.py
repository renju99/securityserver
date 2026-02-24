from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session
import models
import schemas
import os
import tempfile
import fitz
import re
from docxtpl import DocxTemplate
from database import get_db
from services.blob_service import blob_service
from services.audit_service import audit_service
from typing import List

router = APIRouter(tags=["templates"])

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), folder: str = "templates", optimize: bool = False):
    try:
        file_content = await file.read()
        if optimize and file.filename.lower().endswith(".pdf"):
            file_content = pdf_service.optimize_pdf(file_content)

        blob_path = f"{folder}/{file.filename}"
        blob_service.upload_blob(file_content, blob_path)
        
        url = blob_service.get_sas_url(blob_path, expiry_hours=8760) # 1 year
        return {"filename": file.filename, "url": url, "size": len(file_content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get-link/{filename}")
async def get_sas_link(filename: str):
    url = blob_service.get_sas_url(filename) or blob_service.get_sas_url(f"templates/{filename}")
    if not url:
        raise HTTPException(status_code=404, detail="File not found")
    return {"url": url}

@router.get("/templates")
async def list_templates():
    try:
        templates = []
        blob_list = blob_service.list_blobs(name_starts_with="templates/")
        for blob in blob_list:
            if blob.name.endswith(".docx") or blob.name.endswith(".pdf"):
                templates.append(os.path.basename(blob.name))
        return {"templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/templates/{filename}")
async def delete_template(filename: str, request: Request, db: Session = Depends(get_db)):
    try:
        success = blob_service.delete_blob(f"templates/{filename}")
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Clean up PdfTemplate metadata
        db_tpl = db.query(models.PdfTemplate).filter(models.PdfTemplate.name == filename).first()
        if db_tpl:
            db.delete(db_tpl)
            db.commit()
            
        audit_service.log_event(db, "system", "DELETE_TEMPLATE_FILE", "TEMPLATE", filename, ip_address=request.client.host)
        return {"message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/template-schema/{filename}")
async def get_template_schema(filename: str):
    is_pdf = filename.lower().endswith(".pdf")
    suffix = ".pdf" if is_pdf else ".docx"
    
    try:
        content = blob_service.download_blob(f"templates/{filename}")
        
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        
        with open(tmp_path, "wb") as f:
            f.write(content)

        vars_set = set()
        if is_pdf:
            doc = fitz.open(tmp_path)
            for page in doc:
                text = page.get_text()
                found = re.findall(r"\{\{\s*(.*?)\s*\}\}", text)
                for f in found:
                    vars_set.add(f.strip())
            doc.close()
        else:
            doc = DocxTemplate(tmp_path)
            vars_set = doc.get_undeclared_template_variables() 
        
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        return {"placeholders": list(vars_set)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Dynamic Template Builder ---

@router.get("/dynamic-templates", response_model=List[schemas.TemplateResponse])
def get_dynamic_templates(db: Session = Depends(get_db)):
    return db.query(models.DynamicTemplate).all()

@router.post("/dynamic-templates", response_model=schemas.TemplateResponse)
def create_dynamic_template(template: schemas.TemplateCreate, request: Request, db: Session = Depends(get_db)):
    db_tpl = models.DynamicTemplate(
        name=template.name,
        category=template.category,
        layout=template.layout
    )
    db.add(db_tpl)
    db.commit()
    db.refresh(db_tpl)
    audit_service.log_event(db, "system", "CREATE_DYNAMIC_TEMPLATE", "TEMPLATE", str(db_tpl.id), ip_address=request.client.host)
    return db_tpl

@router.get("/dynamic-templates/{template_id}", response_model=schemas.TemplateResponse)
def get_dynamic_template(template_id: int, db: Session = Depends(get_db)):
    db_tpl = db.query(models.DynamicTemplate).filter(models.DynamicTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return db_tpl

@router.put("/dynamic-templates/{template_id}", response_model=schemas.TemplateResponse)
def update_dynamic_template(template_id: int, template: schemas.TemplateCreate, request: Request, db: Session = Depends(get_db)):
    db_tpl = db.query(models.DynamicTemplate).filter(models.DynamicTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db_tpl.name = template.name
    db_tpl.category = template.category
    db_tpl.layout = template.layout
    db.commit()
    db.refresh(db_tpl)
    audit_service.log_event(db, "system", "UPDATE_DYNAMIC_TEMPLATE", "TEMPLATE", str(template_id), ip_address=request.client.host)
    return db_tpl

@router.delete("/dynamic-templates/{template_id}")
def delete_dynamic_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    db_tpl = db.query(models.DynamicTemplate).filter(models.DynamicTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(db_tpl)
    db.commit()
    audit_service.log_event(db, "system", "DELETE_DYNAMIC_TEMPLATE", "TEMPLATE", str(template_id), ip_address=request.client.host)
    return {"message": "Template deleted"}

# --- PDF Template With Signatures ---

@router.get("/pdf-templates", response_model=List[schemas.PdfTemplateResponse])
def get_pdf_templates(db: Session = Depends(get_db)):
    return db.query(models.PdfTemplate).all()

@router.post("/pdf-templates", response_model=schemas.PdfTemplateResponse)
def create_pdf_template(template: schemas.PdfTemplateCreate, request: Request, db: Session = Depends(get_db)):
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
    audit_service.log_event(db, "system", "CREATE_PDF_TEMPLATE", "TEMPLATE", str(db_tpl.id), ip_address=request.client.host)
    return db_tpl

@router.get("/pdf-templates/{template_id}", response_model=schemas.PdfTemplateResponse)
def get_pdf_template(template_id: int, db: Session = Depends(get_db)):
    db_tpl = db.query(models.PdfTemplate).filter(models.PdfTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return db_tpl

@router.put("/pdf-templates/{template_id}", response_model=schemas.PdfTemplateResponse)
def update_pdf_template(template_id: int, template: schemas.PdfTemplateUpdate, request: Request, db: Session = Depends(get_db)):
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
    audit_service.log_event(db, "system", "UPDATE_PDF_TEMPLATE", "TEMPLATE", str(template_id), ip_address=request.client.host)
    return db_tpl

@router.delete("/pdf-templates/{template_id}")
def delete_pdf_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    db_tpl = db.query(models.PdfTemplate).filter(models.PdfTemplate.id == template_id).first()
    if not db_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(db_tpl)
    db.commit()
    audit_service.log_event(db, "system", "DELETE_PDF_TEMPLATE", "TEMPLATE", str(template_id), ip_address=request.client.host)
    return {"message": "Template deleted"}
