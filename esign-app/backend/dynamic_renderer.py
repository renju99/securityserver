import os
import subprocess
import tempfile
import base64

def generate_dynamic_pdf(layout, data, output_pdf_path):
    """
    Renders a JSON layout with provided data into a PDF using HTML + LibreOffice.
    """
    # Load Logo
    logo_b64 = ""
    try:
        with open("berkeley_logo.jpg", "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"Could not load logo: {e}")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Arial', sans-serif; color: #333; line-height: 1.6; margin: 40px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; margin-bottom: 20px; }}
            .logo {{ font-size: 24px; font-weight: bold; color: #1e3a8a; }}
            .title {{ text-align: center; font-size: 20px; font-weight: bold; color: #1e3a8a; margin-bottom: 30px; text-transform: uppercase; }}
            .section {{ margin-bottom: 20px; }}
            .field {{ margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
            .label {{ font-weight: bold; color: #555; width: 200px; display: inline-block; }}
            .value {{ color: #000; }}
            .signature-box {{ margin-top: 50px; border-top: 1px solid #000; width: 250px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">
                {'<img src="data:image/jpeg;base64,' + logo_b64 + '" style="max-height: 50px;" />' if logo_b64 else 'Berkeley eSign'}
            </div>
            <div style="font-style: italic; color: #999; font-size: 12px;">Official Document</div>
        </div>
        <div class="title">Dynamic Document Submission</div>
        <div class="content" style="display: flex; flex-wrap: wrap;">
    """

    for block in layout:
        block_type = block.get('type')
        label = block.get('label', '')
        width_val = block.get('width', 12)
        width_percent = (width_val / 12) * 100
        
        # Map label to data key (e.g., "Employee Name" -> "employee_name")
        data_key = label.lower().replace(' ', '_').replace('?', '')
        value = data.get(data_key, 'N/A')

        # Flex item wrapper
        html_content += f'<div style="width: {width_percent}%; box-sizing: border-box; padding: 10px;">'

        if block_type == 'text' or block_type == 'date':
            html_content += f"""
            <div class="field">
                <div class="label" style="font-size: 10px; text-transform: uppercase; color: #777;">{label}</div>
                <div class="value" style="border-bottom: 1px solid #ddd; padding: 5px 0;">{value}</div>
            </div>
            """
        elif block_type == 'textarea':
             html_content += f"""
            <div class="section">
                <div class="label" style="font-size: 10px; text-transform: uppercase; color: #777; margin-bottom: 5px;">{label}</div>
                <div class="value" style="border: 1px solid #eee; padding: 10px; border-radius: 4px; min-height: 60px; background: #f9f9f9;">{value}</div>
            </div>
            """
        elif block_type == 'signature':
            html_content += f"""
            <div class="signature-box" style="margin-top: 20px; border-top: 2px solid #333; padding-top: 5px;">
                <span style="font-size: 10px; font-weight: bold;">{label}</span><br/>
                <span style="font-size: 8px; color: #888;">Digitally Verified via Berkeley eSign</span>
            </div>
            """
        
        html_content += '</div>'

    html_content += """
        </div>
        <div style="margin-top: 40px; font-size: 10px; color: #aaa; text-align: center;">
            Generated via Berkeley eSign Portal • Trusted Signature Workflow
        </div>
    </body>
    </html>
    """

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
        tf.write(html_content.encode('utf-8'))
        html_path = tf.name

    try:
        # Convert to PDF
        output_dir = os.path.dirname(os.path.abspath(output_pdf_path))
        subprocess.run([
            'soffice', '--headless', '--convert-to', 'pdf',
            '--outdir', output_dir, html_path
        ], check=True)
        
        # Identify converted PDF path (soffice puts it in --outdir with same basename)
        base_name = os.path.basename(html_path).replace('.html', '.pdf')
        actual_converted_pdf = os.path.join(output_dir, base_name)
        
        if os.path.exists(actual_converted_pdf):
            if os.path.abspath(actual_converted_pdf) != os.path.abspath(output_pdf_path):
                if os.path.exists(output_pdf_path):
                    os.remove(output_pdf_path)
                os.rename(actual_converted_pdf, output_pdf_path)
        
    finally:
        if os.path.exists(html_path):
            os.remove(html_path)

if __name__ == "__main__":
    # Test
    sample_layout = [
        {"type": "text", "label": "Employee Name"},
        {"type": "date", "label": "Submission Date"},
        {"type": "textarea", "label": "Reason for Request"},
        {"type": "signature", "label": "Applicant Signature"}
    ]
    sample_data = {
        "employee_name": "John Doe",
        "submission_date": "2026-02-16",
        "reason_for_request": "Need a new workstation laptop for development."
    }
    generate_dynamic_pdf(sample_layout, sample_data, "test_dynamic.pdf")
    print("Test PDF generated: test_dynamic.pdf")
