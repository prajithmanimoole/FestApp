"""
Certificate HTML Generator for FestApp
Uses WeasyPrint and reportlab for PDF generation
"""

import os
import tempfile
from io import BytesIO
from datetime import datetime
import zipfile

# Try to import certificate generation libraries
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import black, white, blue, HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_html_certificate(student_name, event_name, event_date, class_section=None, certificate_type='event'):
    """
    Generate HTML certificate content using the provided template
    """
    # Determine certificate content based on type
    if certificate_type == 'seminar':
        participation_event = "Web Development with AI Seminar Session"
        event_display_name = "'WEB DEVELOPMENT WITH AI SEMINAR'"
    else:
        participation_event = f"event {event_name}"
        event_display_name = f"'{event_name.upper()}'"
    
    # For the logo, we'll use a base64 encoded version or a relative path
    # Since we're generating this from Python, we'll use a data URL approach
    import os
    import base64
    
    # Try to load the logo and convert to base64
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'VC_logo.png')
    logo_data_url = ""
    
    try:
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as logo_file:
                logo_data = base64.b64encode(logo_file.read()).decode('utf-8')
                logo_data_url = f"data:image/png;base64,{logo_data}"
    except Exception as e:
        print(f"Could not load logo: {e}")
        # Fallback to a placeholder or no logo
        logo_data_url = ""
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Certificate of Participation</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Montserrat:wght@400;500;600&display=swap');
            
            @page {{
                size: A4 landscape;
                margin: 0;
            }}

            body {{
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background-color: #f0f2f5;
                font-family: 'Montserrat', sans-serif;
                width: 297mm;
                height: 210mm;
            }}

            .certificate-container {{
                width: 800px;
                height: 565px;
                background: linear-gradient(to bottom right, #ffffff, #f8fafc);
                position: relative;
                overflow: hidden;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                border-radius: 12px;
            }}

            .certificate {{
                padding: 40px;
                text-align: center;
                color: #333;
                position: relative;
                z-index: 10;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 8px;
                margin: 20px;
                height: calc(100% - 40px);
                box-sizing: border-box;
            }}

            .header {{
                display: flex;
                align-items: center;
                justify-content: center;
                padding-bottom: 20px;
            }}

            .college-logo {{
                width: 80px;
                margin-right: 20px;
            }}

            .header-text {{
                text-align: left;
            }}

            .header h1 {{
                color: #1e3a8a;
                font-size: 18px;
                font-weight: 600;
                margin: 0;
            }}

            .header p {{
                font-size: 12px;
                margin: 5px 0 20px;
            }}

            .header h2 {{
                font-size: 14px;
                font-weight: 500;
                margin: 0;
            }}

            .header h3 {{
                font-size: 16px;
                font-weight: 600;
                margin: 5px 0 30px;
            }}

            .main-content h4 {{
                font-family: 'Merriweather', serif;
                font-size: 48px;
                font-weight: 700;
                margin: 0;
                color: #000;
            }}

            .main-content h5 {{
                font-size: 14px;
                font-weight: 500;
                color: #bfa100;
                margin: 0 0 20px;
                position: relative;
            }}

            .main-content h5::before, .main-content h5::after {{
                content: '';
                position: absolute;
                width: 50px;
                height: 1px;
                background-color: #bfa100;
                top: 50%;
            }}

            .main-content h5::before {{
                left: 35%;
            }}

            .main-content h5::after {{
                right: 35%;
            }}

            .main-content h6 {{
                font-size: 12px;
                font-weight: 500;
                margin: 20px 0 5px;
                letter-spacing: 1px;
            }}

            .participant-name {{
                margin: 10px auto;
                font-size: 24px;
                color: #1e3a8a;
                letter-spacing: 2px;
                font-weight: 700;
                font-family: 'Merriweather', serif;
                border-bottom: 2px dotted #333;
                padding-bottom: 5px;
                display: inline-block;
                min-width: 400px;
            }}

            .participation-text {{
                font-size: 14px;
                margin: 10px 0;
            }}

            .event-name {{
                font-size: 18px;
                font-weight: 600;
                color: #1e3a8a;
                margin: 20px 0;
            }}

            .organised-by {{
                font-size: 14px;
                margin-bottom: 30px;
            }}

            .footer {{
                display: flex;
                justify-content: space-between;
                margin-top: 40px;
                padding: 0 40px;
            }}

            .signature {{
                text-align: center;
                flex: 1;
            }}

            .signature p {{
                margin: 0;
                font-size: 12px;
                font-weight: 500;
            }}

            /* Decorative Shapes - Fixed positioning to prevent overlap */
            .shape {{
                position: absolute;
                border-radius: 50%;
                z-index: 0;
                opacity: 0.8;
            }}

            .shape-1 {{
                width: 150px;
                height: 150px;
                background-color: #facc15;
                top: -75px;
                left: -75px;
            }}

            .shape-2 {{
                width: 80px;
                height: 80px;
                background-color: #60a5fa;
                bottom: 40px;
                right: -40px;
            }}

            .shape-3 {{
                width: 120px;
                height: 120px;
                background: linear-gradient(to top right, #4ade80, #34d399);
                bottom: -60px;
                left: 80px;
            }}

            .shape-4 {{
                width: 50px;
                height: 50px;
                background-color: #facc15;
                bottom: 30px;
                left: 200px;
            }}

            .shape-5 {{
                width: 70px;
                height: 70px;
                background-color: #3b82f6;
                bottom: -35px;
                left: -35px;
            }}
        </style>
    </head>
    <body>
        <div class="certificate-container">
            <div class="certificate">
                <div class="header">
                    {f'<img src="{logo_data_url}" alt="College Logo" class="college-logo">' if logo_data_url else ''}
                    <div class="header-text">
                        <h1>VIVEKANANDA COLLEGE OF ARTS, SCIENCE & COMMERCE (AUTONOMOUS)</h1>
                        <p>NEHRU NAGAR, PUTTUR D.K., 574203</p>
                        <h2>DEPARTMENT OF COMPUTER SCIENCE</h2>
                        <h3>INFORMATION TECHNOLOGY CLUB</h3>
                    </div>
                </div>
                <div class="main-content">
                    <h4>Certificate</h4>
                    <h5>OF PARTICIPATION</h5>
                    <h6>PROUDLY PRESENTED TO</h6>
                    <div class="participant-name">{student_name.upper()}</div>
                    <p class="participation-text">for actively participating in the {participation_event} held during</p>
                    <p class="event-name">{event_date}</p>
                    <p class="organised-by">Organised by - III BCA 'D' -</p>
                </div>
                <div class="footer">
                    <div class="signature">
                        <p>_________________________</p>
                        <p>HEAD OF DEPARTMENT</p>
                    </div>
                    <div class="signature">
                        <p>_________________________</p>
                        <p>PRINCIPAL</p>
                    </div>
                    <div class="signature">
                        <p>_________________________</p>
                        <p>IT CLUB CONVENER</p>
                    </div>
                </div>
            </div>
            <div class="shape shape-1"></div>
            <div class="shape shape-2"></div>
            <div class="shape shape-3"></div>
            <div class="shape shape-4"></div>
            <div class="shape shape-5"></div>
        </div>
    </body>
    </html>
    """
    
    return html_content


def generate_certificate_pdf_weasyprint(student_name, event_name, event_date, class_section=None, certificate_type='event'):
    """
    Generate PDF certificate using WeasyPrint
    """
    try:
        html_content = generate_html_certificate(student_name, event_name, event_date, class_section, certificate_type)
        
        # Create PDF from HTML
        font_config = FontConfiguration()
        html_doc = HTML(string=html_content)
        
        # Generate PDF
        pdf_bytes = html_doc.write_pdf(font_config=font_config)
        
        # Return as BytesIO
        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"WeasyPrint PDF generation failed: {e}")
        raise


def generate_certificate_pdf_reportlab(student_name, event_name, event_date, class_section=None, certificate_type='event'):
    """
    Fallback PDF generation using reportlab matching the template design
    """
    try:
        from .certificate_generator import generate_simple_certificate_pdf
        return generate_simple_certificate_pdf(student_name, event_name, event_date, class_section, certificate_type)
    except ImportError:
        # Create a certificate matching the template design
        width, height = landscape(A4)
        buffer = BytesIO()
        
        c = canvas.Canvas(buffer, pagesize=landscape(A4))
        
        # Set background
        c.setFillColor(white)
        c.rect(0, 0, width, height, fill=True)
        
        # Add decorative shapes (simplified circles) - Fixed positioning
        # Shape 1 - Yellow circle top-left (smaller, positioned to not overlap)
        c.setFillColor(HexColor('#facc15'))
        c.setAlpha(0.8)
        c.circle(-40, height-80, 75)
        
        # Shape 2 - Blue circle bottom-right (smaller, positioned safely)
        c.setFillColor(HexColor('#60a5fa'))
        c.circle(width-40, 80, 40)
        
        # Shape 3 - Green circle bottom-left (positioned to not overlap content)
        c.setFillColor(HexColor('#4ade80'))
        c.circle(120, 40, 60)
        
        # Shape 4 - Small yellow circle bottom area
        c.setFillColor(HexColor('#facc15'))
        c.circle(200, 50, 25)
        
        # Shape 5 - Small blue circle bottom-left corner
        c.setFillColor(HexColor('#3b82f6'))
        c.circle(-20, 35, 35)
        
        # Reset alpha for text
        c.setAlpha(1.0)
        
        # Header section with logo space
        header_y = height - 80
        
        # College name and details
        c.setFillColor(HexColor('#1e3a8a'))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(150, header_y, "VIVEKANANDA COLLEGE OF ARTS, SCIENCE & COMMERCE (AUTONOMOUS)")
        
        c.setFillColor(black)
        c.setFont("Helvetica", 12)
        c.drawString(150, header_y - 25, "NEHRU NAGAR, PUTTUR D.K., 574203")
        
        c.setFont("Helvetica", 14)
        c.drawString(150, header_y - 50, "DEPARTMENT OF COMPUTER SCIENCE")
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(150, header_y - 75, "INFORMATION TECHNOLOGY CLUB")
        
        # Certificate title
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 48)
        c.drawCentredString(width/2, height-200, "Certificate")
        
        # OF PARTICIPATION with decorative lines
        c.setFillColor(HexColor('#bfa100'))
        c.setFont("Helvetica", 14)
        participation_text = "OF PARTICIPATION"
        text_width = c.stringWidth(participation_text, "Helvetica", 14)
        
        # Draw the text
        c.drawCentredString(width/2, height-230, participation_text)
        
        # Draw decorative lines on both sides
        line_y = height-225
        line_start_left = (width/2) - (text_width/2) - 70
        line_end_left = (width/2) - (text_width/2) - 20
        line_start_right = (width/2) + (text_width/2) + 20
        line_end_right = (width/2) + (text_width/2) + 70
        
        c.setStrokeColor(HexColor('#bfa100'))
        c.setLineWidth(1)
        c.line(line_start_left, line_y, line_end_left, line_y)
        c.line(line_start_right, line_y, line_end_right, line_y)
        
        # "PROUDLY PRESENTED TO"
        c.setFillColor(black)
        c.setFont("Helvetica", 12)
        c.drawCentredString(width/2, height-270, "PROUDLY PRESENTED TO")
        
        # Student name with dotted underline
        c.setFillColor(HexColor('#1e3a8a'))
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width/2, height-310, student_name.upper())
        
        # Draw dotted line under name
        name_width = c.stringWidth(student_name.upper(), "Helvetica-Bold", 24)
        line_start = (width - max(name_width + 100, 400)) / 2
        line_end = line_start + max(name_width + 100, 400)
        
        # Create dotted line effect
        c.setStrokeColor(black)
        c.setLineWidth(1)
        dot_spacing = 5
        current_x = line_start
        while current_x < line_end:
            c.line(current_x, height-320, min(current_x + 3, line_end), height-320)
            current_x += dot_spacing
        
        # Participation text
        c.setFillColor(black)
        c.setFont("Helvetica", 14)
        
        if certificate_type == 'seminar':
            participation_event = "Web Development with AI Seminar Session"
            event_display_name = "'WEB DEVELOPMENT WITH AI SEMINAR'"
        else:
            participation_event = f"event {event_name}"
            event_display_name = f"'{event_name.upper()}'"
        
        c.drawCentredString(width/2, height-360, f"for actively participating in the {participation_event} held during")
        
        # Event date (instead of event name)
        c.setFillColor(HexColor('#1e3a8a'))
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height-390, event_date)
        
        # Organized by text (removed class section display)
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, height-420, "Organised by - III BCA 'D' -")
        
        # Signature sections - Updated to three columns
        c.setFillColor(black)
        c.setFont("Helvetica", 12)
        
        # Left signature - Head of Department
        left_x = width * 0.2
        c.drawCentredString(left_x, 80, "_________________________")
        c.drawCentredString(left_x, 60, "HEAD OF DEPARTMENT")
        
        # Center signature - Principal
        center_x = width * 0.5
        c.drawCentredString(center_x, 80, "_________________________")
        c.drawCentredString(center_x, 60, "PRINCIPAL")
        
        # Right signature - IT Club Convener
        right_x = width * 0.8
        c.drawCentredString(right_x, 80, "_________________________")
        c.drawCentredString(right_x, 60, "IT CLUB CONVENER")
        
        c.save()
        buffer.seek(0)
        return buffer


def generate_certificate_pdf(student_name, event_name, event_date, class_section=None, certificate_type='event'):
    """
    Main function to generate certificate PDF with fallback support
    """
    # Try WeasyPrint first
    if WEASYPRINT_AVAILABLE:
        try:
            return generate_certificate_pdf_weasyprint(student_name, event_name, event_date, class_section, certificate_type)
        except Exception as e:
            print(f"WeasyPrint failed, falling back to reportlab: {e}")
    
    # Fallback to reportlab
    if REPORTLAB_AVAILABLE:
        try:
            return generate_certificate_pdf_reportlab(student_name, event_name, event_date, class_section, certificate_type)
        except Exception as e:
            print(f"Reportlab failed: {e}")
            raise
    
    # If nothing works, raise an error
    raise RuntimeError("No PDF generation library available")


def generate_dual_certificates(student_name, event_name, event_date, class_section=None):
    """
    Generate both event and seminar certificates in a ZIP file
    """
    buffer = BytesIO()
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Generate event certificate
        try:
            event_cert = generate_certificate_pdf(student_name, event_name, event_date, class_section, 'event')
            zip_file.writestr(f"{student_name.replace(' ', '_')}_Event_Certificate.pdf", event_cert.getvalue())
        except Exception as e:
            print(f"Failed to generate event certificate: {e}")
        
        # Generate seminar certificate
        try:
            seminar_cert = generate_certificate_pdf(student_name, event_name, event_date, class_section, 'seminar')
            zip_file.writestr(f"{student_name.replace(' ', '_')}_Seminar_Certificate.pdf", seminar_cert.getvalue())
        except Exception as e:
            print(f"Failed to generate seminar certificate: {e}")
    
    buffer.seek(0)
    return buffer


# Test function
if __name__ == "__main__":
    # Test certificate generation
    test_cert = generate_certificate_pdf("John Doe", "Web Development Workshop", "March 15, 2024", "III BCA 'D'")
    with open("test_certificate.pdf", "wb") as f:
        f.write(test_cert.getvalue())
    print("Test certificate generated successfully!")
