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
    Generate HTML certificate content
    """
    # Determine certificate title and content based on type
    if certificate_type == 'seminar':
        participation_text = "Web Development with AI Seminar Session"
        subtitle = "SEMINAR PARTICIPATION"
    else:
        participation_text = f"event {event_name}"
        subtitle = "EVENT PARTICIPATION"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Certificate of Participation</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Montserrat:wght@400;500;600&display=swap');
            
            body {{
                margin: 0;
                padding: 20px;
                font-family: 'Montserrat', sans-serif;
                background-color: #f0f2f5;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }}
            
            .certificate-container {{
                width: 800px;
                height: 565px;
                background: linear-gradient(to bottom right, #ffffff, #f0f2f5);
                position: relative;
                overflow: hidden;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                border: 3px solid #2563eb;
                border-radius: 10px;
            }}
            
            .certificate {{
                padding: 40px;
                text-align: center;
                color: #333;
                position: relative;
                z-index: 2;
                height: 100%;
                box-sizing: border-box;
            }}
            
            .header {{
                margin-bottom: 20px;
            }}
            
            .header h1 {{
                font-size: 24px;
                font-weight: 700;
                color: #2563eb;
                margin: 5px 0;
                line-height: 1.2;
            }}
            
            .header p {{
                font-size: 14px;
                color: #666;
                margin: 2px 0;
            }}
            
            .main-content {{
                margin: 30px 0;
            }}
            
            .certificate-title {{
                font-size: 48px;
                font-weight: 700;
                color: #1e40af;
                margin: 20px 0;
                font-family: 'Merriweather', serif;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
            }}
            
            .subtitle {{
                font-size: 18px;
                color: #2563eb;
                font-weight: 600;
                margin-bottom: 30px;
                letter-spacing: 2px;
            }}
            
            .proudly-presented {{
                font-size: 16px;
                color: #374151;
                margin-bottom: 10px;
                font-weight: 500;
            }}
            
            .participant-name {{
                font-size: 32px;
                font-weight: 700;
                color: #1e40af;
                margin: 20px 0;
                font-family: 'Merriweather', serif;
                border-bottom: 2px solid #2563eb;
                padding-bottom: 5px;
                display: inline-block;
                min-width: 400px;
            }}
            
            .participation-text {{
                font-size: 16px;
                color: #374151;
                margin: 15px 0;
                line-height: 1.6;
            }}
            
            .event-name {{
                font-size: 20px;
                font-weight: 600;
                color: #2563eb;
                margin: 15px 0;
                font-style: italic;
            }}
            
            .event-date {{
                font-size: 16px;
                color: #374151;
                margin: 15px 0;
            }}
            
            .class-section {{
                font-size: 14px;
                color: #666;
                margin: 10px 0;
            }}
            
            .footer {{
                display: flex;
                justify-content: space-around;
                margin-top: 40px;
                position: absolute;
                bottom: 30px;
                left: 50%;
                transform: translateX(-50%);
                width: 600px;
            }}
            
            .signature {{
                text-align: center;
            }}
            
            .signature-line {{
                width: 200px;
                height: 1px;
                background-color: #333;
                margin: 0 auto 5px;
            }}
            
            .signature p {{
                margin: 0;
                font-size: 12px;
                font-weight: 500;
                color: #333;
            }}
            
            /* Decorative elements */
            .shape {{
                position: absolute;
                border-radius: 50%;
                z-index: 1;
                opacity: 0.3;
            }}
            
            .shape-1 {{
                width: 150px;
                height: 150px;
                background-color: #facc15;
                top: -50px;
                left: -50px;
            }}
            
            .shape-2 {{
                width: 80px;
                height: 80px;
                background-color: #60a5fa;
                bottom: 20px;
                right: -20px;
            }}
            
            .shape-3 {{
                width: 120px;
                height: 120px;
                background: linear-gradient(to top right, #4ade80, #34d399);
                bottom: -60px;
                left: 80px;
            }}
        </style>
    </head>
    <body>
        <div class="certificate-container">
            <div class="certificate">
                <div class="header">
                    <h1>VIVEKANANDA COLLEGE OF ARTS,</h1>
                    <h1>SCIENCE & COMMERCE (AUTONOMOUS)</h1>
                    <p>NEHRU NAGAR, PUTTUR D.K., 574203</p>
                    <h1 style="font-size: 18px; margin-top: 15px;">DEPARTMENT OF COMPUTER SCIENCE</h1>
                    <h1 style="font-size: 16px;">INFORMATION TECHNOLOGY CLUB</h1>
                </div>
                
                <div class="main-content">
                    <h2 class="certificate-title">Certificate</h2>
                    <h3 class="subtitle">OF {subtitle}</h3>
                    
                    <p class="proudly-presented">PROUDLY PRESENTED TO</p>
                    
                    <div class="participant-name">{student_name.upper()}</div>
                    
                    <p class="participation-text">
                        for actively participating in the {participation_text}
                    </p>
                    
                    <p class="event-date">held during <strong>{event_date}</strong></p>
                    
                    {f'<p class="class-section">Class: {class_section}</p>' if class_section else ''}
                    
                    <p class="participation-text" style="margin-top: 25px; font-style: italic;">
                        Organised by - III BCA 'D' -
                    </p>
                </div>
                
                <div class="footer">
                    <div class="signature">
                        <div class="signature-line"></div>
                        <p>HEAD OF DEPARTMENT</p>
                    </div>
                    <div class="signature">
                        <div class="signature-line"></div>
                        <p>IT CLUB CONVENER</p>
                    </div>
                </div>
            </div>
            
            <div class="shape shape-1"></div>
            <div class="shape shape-2"></div>
            <div class="shape shape-3"></div>
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
    Fallback PDF generation using reportlab
    """
    try:
        from .certificate_generator import generate_simple_certificate_pdf
        return generate_simple_certificate_pdf(student_name, event_name, event_date, class_section, certificate_type)
    except ImportError:
        # If the certificate_generator is not available, create a simple certificate
        width, height = landscape(A4)
        buffer = BytesIO()
        
        c = canvas.Canvas(buffer, pagesize=landscape(A4))
        
        # Set background
        c.setFillColor(white)
        c.rect(0, 0, width, height, fill=True)
        
        # Draw border
        c.setStrokeColor(HexColor('#2563eb'))
        c.setLineWidth(3)
        c.rect(20, 20, width-40, height-40, fill=0)
        
        # Title
        c.setFillColor(HexColor('#1e40af'))
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(width/2, height-70, "CERTIFICATE OF PARTICIPATION")
        
        # College info
        c.setFillColor(HexColor('#2563eb'))
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, height-100, "VIVEKANANDA COLLEGE OF ARTS, SCIENCE & COMMERCE")
        c.setFont("Helvetica", 12)
        c.drawCentredString(width/2, height-120, "NEHRU NAGAR, PUTTUR D.K., 574203")
        c.drawCentredString(width/2, height-140, "DEPARTMENT OF COMPUTER SCIENCE")
        c.drawCentredString(width/2, height-160, "INFORMATION TECHNOLOGY CLUB")
        
        # Student name
        c.setFillColor(HexColor('#1e40af'))
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(width/2, height-220, student_name.upper())
        
        # Event info
        c.setFillColor(black)
        c.setFont("Helvetica", 16)
        if certificate_type == 'seminar':
            c.drawCentredString(width/2, height-260, "has actively participated in the")
            c.drawCentredString(width/2, height-280, "Web Development with AI Seminar Session")
        else:
            c.drawCentredString(width/2, height-260, f"has actively participated in the event")
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(width/2, height-280, event_name)
        
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, height-310, f"held during {event_date}")
        
        if class_section:
            c.setFont("Helvetica", 12)
            c.drawCentredString(width/2, height-330, f"Class: {class_section}")
        
        # Signatures
        c.setFont("Helvetica", 10)
        c.line(100, 80, 250, 80)
        c.drawCentredString(175, 60, "HEAD OF DEPARTMENT")
        
        c.line(width-250, 80, width-100, 80)
        c.drawCentredString(width-175, 60, "IT CLUB CONVENER")
        
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
