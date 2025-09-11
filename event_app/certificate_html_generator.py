import os
import pdfkit
from jinja2 import Template
from io import BytesIO
import os
import base64
from typing import Optional
import tempfile
import zipfile
try:
    from .certificate_generator import generate_simple_certificate_pdf
except ImportError:
    from certificate_generator import generate_simple_certificate_pdf

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    print("WeasyPrint not available, using pdfkit/fallback")

def generate_html_certificate(student_name: str, event_name: str, event_date: str, class_section: Optional[str] = None, certificate_type: str = 'event') -> str:
    """
    Generate HTML certificate with dynamic content
    
    Args:
        student_name: Name of the student
        event_name: Name of the event
        event_date: Date of the event
        class_section: Class and section of the student (optional)
    
    Returns:
        HTML string of the certificate
    """
    
    try:
        # Get the certificate template directory - fix path resolution
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels: event_app -> FestApp -> CERTIFICATE
        fest_app_dir = os.path.dirname(current_dir)
        cert_template_dir = os.path.join(fest_app_dir, 'CERTIFICATE')
        
        # Read the HTML template
        html_template_path = os.path.join(cert_template_dir, 'index.html')
        css_template_path = os.path.join(cert_template_dir, 'style.css')
        logo_path = os.path.join(cert_template_dir, 'VC logo.png')
        
        print(f"Looking for template at: {html_template_path}")
        print(f"Template exists: {os.path.exists(html_template_path)}")
        
        # Check if files exist
        if not os.path.exists(html_template_path):
            print(f"HTML template not found at: {html_template_path}")
            return generate_fallback_certificate_html(student_name, event_name, event_date, class_section, certificate_type)
        
        if not os.path.exists(css_template_path):
            print(f"CSS template not found at: {css_template_path}")
            return generate_fallback_certificate_html(student_name, event_name, event_date, class_section, certificate_type)
        
        # Read template files
        with open(html_template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        with open(css_template_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
    except Exception as e:
        print(f"Error reading template files: {e}")
        return generate_fallback_certificate_html(student_name, event_name, event_date, class_section, certificate_type)
    
    # Convert logo to base64 for embedding
    logo_base64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            logo_data = f.read()
            logo_base64 = base64.b64encode(logo_data).decode('utf-8')
    
    # Format class section if provided
    class_info = f" from {class_section}" if class_section else ""
    
    # Determine certificate content based on type
    if certificate_type == 'seminar':
        participation_text = f'for actively participating in the Web Development with AI Seminar Session{class_info} held during'
        event_display_name = 'Web Development Seminar'
    else:
        participation_text = f'for actively participating in the event {event_name}{class_info} held during'
        event_display_name = event_name
    
    # Replace static placeholders with dynamic content
    certificate_html = html_content
    
    # Replace participant name placeholder
    certificate_html = certificate_html.replace(
        '<p class="participant-line">....................................................................................</p>',
        f'<p class="participant-line" style="font-size: 18px; font-weight: 600; color: #1e3a8a; margin: 10px 0; text-decoration: underline;">{student_name.upper()}</p>'
    )
    
    # Replace participation text
    certificate_html = certificate_html.replace(
        'for actively participating in the event .................................... held during',
        participation_text
    )
    
    # Replace event date
    certificate_html = certificate_html.replace(
        "'IT CLUB EVENT'",
        f"'{event_date}'"
    )
    
    # Embed logo if available
    if logo_base64:
        certificate_html = certificate_html.replace(
            'src="VC logo.png"',
            f'src="data:image/png;base64,{logo_base64}"'
        )
    
    # Embed CSS inline
    certificate_html = certificate_html.replace(
        '<link rel="stylesheet" href="style.css">',
        f'<style>{css_content}</style>'
    )
    
    return certificate_html

def generate_fallback_certificate_html(student_name: str, event_name: str, event_date: str, class_section: Optional[str] = None, certificate_type: str = 'event') -> str:
    """
    Generate a simple fallback HTML certificate when template files are not available
    """
    class_info = f" from {class_section}" if class_section else ""
    
    if certificate_type == 'seminar':
        participation_text = f'for actively participating in the Web Development Seminar Session{class_info} held during'
        event_display_name = 'Web Development Seminar'
    else:
        participation_text = f'for actively participating in the event {event_name}{class_info} held during'
        event_display_name = event_name
    
    fallback_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Certificate of Participation</title>
        <style>
            body {{
                font-family: 'Times New Roman', serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .certificate-container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border: 3px solid #1e3a8a;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .college-name {{
                font-size: 20px;
                font-weight: bold;
                color: #1e3a8a;
                margin-bottom: 5px;
            }}
            .college-address {{
                font-size: 14px;
                color: #666;
                margin-bottom: 10px;
            }}
            .department {{
                font-size: 16px;
                font-weight: bold;
                color: #1e3a8a;
                margin-bottom: 5px;
            }}
            .club {{
                font-size: 14px;
                font-weight: bold;
                color: #1e3a8a;
            }}
            .certificate-title {{
                text-align: center;
                font-size: 32px;
                font-weight: bold;
                color: #1e3a8a;
                margin: 30px 0;
                text-decoration: underline;
            }}
            .participant-name {{
                text-align: center;
                font-size: 24px;
                font-weight: bold;
                color: #1e3a8a;
                margin: 20px 0;
                text-decoration: underline;
            }}
            .participation-text {{
                text-align: center;
                font-size: 16px;
                margin: 20px 0;
                line-height: 1.5;
            }}
            .event-name {{
                text-align: center;
                font-size: 20px;
                font-weight: bold;
                color: #1e3a8a;
                margin: 20px 0;
            }}
            .signatures {{
                display: flex;
                justify-content: space-between;
                margin-top: 60px;
            }}
            .signature {{
                text-align: center;
            }}
            .signature-line {{
                border-bottom: 2px solid #000;
                width: 200px;
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="certificate-container">
            <div class="header">
                <div class="college-name">VIVEKANANDA COLLEGE OF ARTS, SCIENCE & COMMERCE (AUTONOMOUS)</div>
                <div class="college-address">NEHRU NAGAR, PUTTUR D.K., 574203</div>
                <div class="department">DEPARTMENT OF COMPUTER SCIENCE</div>
                <div class="club">INFORMATION TECHNOLOGY CLUB</div>
            </div>
            
            <div class="certificate-title">CERTIFICATE OF PARTICIPATION</div>
            
            <div style="text-align: center; margin: 30px 0;">
                <div style="font-size: 18px; margin-bottom: 20px;">This is to certify that</div>
                <div class="participant-name">{student_name.upper()}</div>
                <div class="participation-text">{participation_text}</div>
                <div class="event-name">'{event_date}'</div>
            </div>
            
            <div class="signatures">
                <div class="signature">
                    <div class="signature-line"></div>
                    <div>HEAD OF DEPARTMENT</div>
                </div>
                <div class="signature">
                    <div class="signature-line"></div>
                    <div>IT CLUB CONVENER</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return fallback_html

def generate_certificate_pdf(student_name: str, event_name: str, event_date: str, class_section: Optional[str] = None, certificate_type: str = 'event') -> BytesIO:
    """
    Generate PDF certificate from HTML template
    
    Args:
        student_name: Name of the student
        event_name: Name of the event  
        event_date: Date of the event
        class_section: Class and section of the student (optional)
    
    Returns:
        BytesIO object containing the PDF certificate
    """
    try:
        # Generate HTML certificate
        html_content = generate_html_certificate(student_name, event_name, event_date, class_section, certificate_type)
        
        # Configure PDF options for better rendering
        options = {
            'page-size': 'A4',
            'orientation': 'Landscape',
            'margin-top': '0.2in',
            'margin-right': '0.2in',
            'margin-bottom': '0.2in',
            'margin-left': '0.2in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None,
            'print-media-type': None,
            'disable-smart-shrinking': None,
            'zoom': 1.0,
            'dpi': 300,
            'image-quality': 100,
            'javascript-delay': 1000
        }
        
        # Try WeasyPrint first (better CSS support)
        if WEASYPRINT_AVAILABLE:
            try:
                pdf_buffer = BytesIO()
                HTML(string=html_content).write_pdf(pdf_buffer)
                pdf_buffer.seek(0)
                return pdf_buffer
            except Exception as e:
                print(f"WeasyPrint failed: {e}, trying pdfkit...")
        
        # Fallback to pdfkit
        try:
            pdf_data = pdfkit.from_string(html_content, False, options=options)
            pdf_buffer = BytesIO(pdf_data)
            pdf_buffer.seek(0)
            return pdf_buffer
        except OSError as e:
            if 'wkhtmltopdf' in str(e):
                print("wkhtmltopdf not found, falling back to simple PDF generation")
                raise Exception("HTML to PDF conversion not available")
            else:
                raise e
        
    except Exception as e:
        print(f"Error generating PDF certificate: {e}")
        # Fallback to simple PDF generation
        return generate_simple_certificate_pdf(student_name, event_name, event_date, class_section, certificate_type)

def generate_simple_certificate_pdf(student_name: str, event_name: str, event_date: str, class_section: Optional[str] = None, certificate_type: str = 'event') -> BytesIO:
    """
    Fallback simple PDF certificate generator using reportlab
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import black, blue
        
        width, height = landscape(A4)
        buffer = BytesIO()
        
        c = canvas.Canvas(buffer, pagesize=landscape(A4))
        
        # Draw border
        c.setStrokeColor(black)
        c.setLineWidth(3)
        c.rect(30, 30, width-60, height-60, fill=0)
        
        # Title
        c.setFillColor(blue)
        c.setFont("Helvetica-Bold", 32)
        c.drawCentredString(width/2, height-80, "CERTIFICATE OF PARTICIPATION")
        
        # College name
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height-120, "VIVEKANANDA COLLEGE OF ARTS, SCIENCE & COMMERCE")
        c.setFont("Helvetica", 12)
        c.drawCentredString(width/2, height-140, "NEHRU NAGAR, PUTTUR D.K., 574203")
        
        # Department
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, height-170, "DEPARTMENT OF COMPUTER SCIENCE")
        c.drawCentredString(width/2, height-190, "INFORMATION TECHNOLOGY CLUB")
        
        # Main content
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, height-240, "This is to certify that")
        
        # Student name
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(blue)
        c.drawCentredString(width/2, height-280, student_name.upper())
        
        # Class section
        if class_section:
            c.setFillColor(black)
            c.setFont("Helvetica", 16)
            c.drawCentredString(width/2, height-310, f"from {class_section}")
        
        # Event details
        c.setFillColor(black)
        c.setFont("Helvetica", 14)
        
        if certificate_type == 'seminar':
            c.drawCentredString(width/2, height-350, f"has actively participated in the")
            c.setFont("Helvetica-Bold", 18)
            c.setFillColor(blue)
            c.drawCentredString(width/2, height-380, "Web Development Seminar Session")
        else:
            c.drawCentredString(width/2, height-350, f"has actively participated in the event")
            c.setFont("Helvetica-Bold", 18)
            c.setFillColor(blue)
            c.drawCentredString(width/2, height-380, event_name)
        
        c.setFillColor(black)
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, height-410, f"held during {event_date}")
        
        # Signatures
        c.setFont("Helvetica", 12)
        c.drawCentredString(200, 100, "____________________")
        c.drawCentredString(200, 80, "HEAD OF DEPARTMENT")
        
        c.drawCentredString(width-200, 100, "____________________")
        c.drawCentredString(width-200, 80, "IT CLUB CONVENER")
        
        c.save()
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"Error generating simple PDF: {e}")
        # Return empty buffer as last resort
        buffer = BytesIO()
        buffer.write(b"Certificate generation failed")
        buffer.seek(0)
        return buffer

def generate_dual_certificates(student_name: str, event_name: str, event_date: str, class_section: Optional[str] = None) -> BytesIO:
    """
    Generate both event participation and seminar certificates in a ZIP file
    
    Args:
        student_name: Name of the student
        event_name: Name of the event
        event_date: Date of the event
        class_section: Class and section of the student (optional)
    
    Returns:
        BytesIO object containing ZIP file with both certificates
    """
    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            certificate_files = []
            
            # Generate event participation certificate
            event_cert_buffer = generate_certificate_pdf(
                student_name=student_name,
                event_name=event_name,
                event_date=event_date,
                class_section=class_section,
                certificate_type='event'
            )
            
            event_cert_path = os.path.join(temp_dir, f"{student_name.replace(' ', '_')}_Event_Certificate.pdf")
            with open(event_cert_path, 'wb') as f:
                f.write(event_cert_buffer.getvalue())
            certificate_files.append(event_cert_path)
            
            # Generate seminar participation certificate
            seminar_cert_buffer = generate_certificate_pdf(
                student_name=student_name,
                event_name=event_name,
                event_date=event_date,
                class_section=class_section,
                certificate_type='seminar'
            )
            
            seminar_cert_path = os.path.join(temp_dir, f"{student_name.replace(' ', '_')}_Seminar_Certificate.pdf")
            with open(seminar_cert_path, 'wb') as f:
                f.write(seminar_cert_buffer.getvalue())
            certificate_files.append(seminar_cert_path)
            
            # Create ZIP file
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in certificate_files:
                    file_name = os.path.basename(file_path)
                    zip_file.write(file_path, file_name)
            
            zip_buffer.seek(0)
            return zip_buffer
            
    except Exception as e:
        print(f"Error generating dual certificates: {e}")
        # Fallback to single event certificate
        return generate_certificate_pdf(student_name, event_name, event_date, class_section, 'event')
