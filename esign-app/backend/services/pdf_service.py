import io
import os
import tempfile
import subprocess
import re
import fitz
from datetime import datetime
from docxtpl import DocxTemplate
from dynamic_renderer import generate_dynamic_pdf
from services.blob_service import blob_service
from typing import List, Dict, Any, Tuple

class PdfService:
    @staticmethod
    def optimize_pdf(input_bytes: bytes) -> bytes:
        """Optimizes PDF bytes using PyMuPDF."""
        try:
            doc = fitz.open(stream=input_bytes, filetype="pdf")
            output_stream = io.BytesIO()
            doc.save(output_stream, garbage=3, deflate=True)
            optimized_bytes = output_stream.getvalue()
            doc.close()
            if len(optimized_bytes) < len(input_bytes):
                return optimized_bytes
            return input_bytes
        except Exception as e:
            print(f"Optimization failed: {e}")
            return input_bytes

    @staticmethod
    def _fill_pdf_placeholders(doc, context: dict):
        """Helper to search and replace {{ key }} placeholders in a PyMuPDF doc."""
        if not context or not isinstance(context, dict):
            return

        for page in doc:
            text = page.get_text()
            placeholders = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", text))
            
            for key in placeholders:
                val = str(context.get(key, "") or "")
                hits = page.search_for(f"{{{{ {key} }}}}") + \
                       page.search_for(f"{{{{{key}}}}}") + \
                       page.search_for(f"{{{{  {key}  }}}}")
                
                for rect in hits:
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    page.insert_text(rect.tl, val, fontsize=11, fontname="helv", color=(0, 0, 0))
            
            page.apply_redactions()

    @staticmethod
    def generate_pdf_logic(template_name: str, context: dict, layout: list = None, pdf_text_fields: list = None) -> Tuple[str, str]:
        """Core logic to generate PDF from DOCX, PDF, or dynamic layout."""
        tmp_docx_path = None
        rendered_docx_path = None
        tmp_pdf_path = None
        
        try:
            is_pdf = template_name.lower().endswith(".pdf")

            # Check for source DOCX if PDF requested
            if is_pdf:
                docx_name = template_name.replace(".pdf", ".docx")
                # Note: This is an optimization, we check if DOCX exists locally/blob
                try:
                    # We assume it's in templates/ folder in blob
                    blob_service.download_blob(f"templates/{docx_name}")
                    template_name = docx_name
                    is_pdf = False
                except:
                    pass

            if layout:
                fd, tmp_pdf_path = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                generate_dynamic_pdf(layout, context, tmp_pdf_path)
            elif is_pdf:
                pdf_data = blob_service.download_blob(f"templates/{template_name}")
                fd, tmp_pdf_path = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                
                doc = fitz.open("pdf", pdf_data)
                PdfService._fill_pdf_placeholders(doc, context)
                
                if pdf_text_fields:
                    for f in pdf_text_fields:
                        assignee = f.get('assignee', '')
                        val = str(context.get(assignee, ''))
                        page_idx = f.get('page', 1) - 1
                        if page_idx < len(doc):
                            p_rect = doc[page_idx].rect
                            x0, y0 = (f['x'] / 100) * p_rect.width, (f['y'] / 100) * p_rect.height
                            x1, y1 = ((f['x'] + f['width']) / 100) * p_rect.width, ((f['y'] + f['height']) / 100) * p_rect.height
                            rect = fitz.Rect(x0, y0, x1, y1)
                            doc[page_idx].insert_textbox(rect, val, fontsize=11, fontname="helv", color=(0, 0, 0), align=0)
                
                doc.save(tmp_pdf_path)
            else:
                docx_data = blob_service.download_blob(f"templates/{template_name}")
                fd, tmp_docx_path = tempfile.mkstemp(suffix=".docx")
                os.close(fd)
                with open(tmp_docx_path, "wb") as f:
                    f.write(docx_data)

                doc = DocxTemplate(tmp_docx_path)
                doc.render(context)
                
                fd2, rendered_docx_path = tempfile.mkstemp(suffix=".docx")
                os.close(fd2)
                doc.save(rendered_docx_path)

                subprocess.run(
                    ['soffice', '--headless', '--convert-to', 'pdf', '--outdir', os.path.dirname(rendered_docx_path), rendered_docx_path],
                    check=True
                )
                tmp_pdf_path = rendered_docx_path.replace(".docx", ".pdf")
            
            # Upload generated PDF
            unique_id = f"doc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"
            pdf_blob_name = f"generated/{unique_id}.pdf"
            
            with open(tmp_pdf_path, "rb") as data:
                blob_service.upload_blob(data.read(), pdf_blob_name)

            url = blob_service.get_sas_url(pdf_blob_name, expiry_hours=168) # 7 days
            return url, pdf_blob_name

        except Exception as e:
            print(f"PDF GEN ERROR: {e}")
            raise e
        finally:
            for path in [tmp_docx_path, rendered_docx_path, tmp_pdf_path]:
                if path and os.path.exists(path): os.remove(path)

pdf_service = PdfService()
