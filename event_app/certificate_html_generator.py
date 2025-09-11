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
            
            @page {{
                size: A4 landscape;
                margin: 0;
            }}
            
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Montserrat', sans-serif;
                background-color: #ffffff;
                width: 297mm;
                height: 210mm;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            
            .certificate-container {{
                width: 280mm;
                height: 190mm;
                background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
                position: relative;
                border: 4px solid #2563eb;
                border-radius: 15px;
                box-shadow: 0 8px 32px rgba(37, 99, 235, 0.15);
                overflow: hidden;
            }}
            
            .certificate {{
                padding: 25mm;
                text-align: center;
                color: #1e293b;
                position: relative;
                z-index: 10;
                height: 100%;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }}
            
            .header {{
                margin-bottom: 15mm;
            }}
            
            .header h1 {{
                font-size: 18px;
                font-weight: 700;
                color: #2563eb;
                margin: 2px 0;
                line-height: 1.3;
            }}
            
            .header .address {{
                font-size: 12px;
                color: #64748b;
                margin: 8px 0;
                font-weight: 500;
            }}
            
            .header .department {{
                font-size: 14px;
                color: #2563eb;
                font-weight: 600;
                margin: 8px 0;
            }}
            
            .main-content {{
                flex-grow: 1;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                margin: 10mm 0;
            }}
            
            .certificate-title {{
                font-size: 48px;
                font-weight: 700;
                color: #1e40af;
                margin: 10px 0;
                font-family: 'Merriweather', serif;
                text-shadow: 2px 2px 4px rgba(30, 64, 175, 0.1);
            }}
            
            .subtitle {{
                font-size: 16px;
                color: #2563eb;
                font-weight: 600;
                margin: 5px 0 20px 0;
                letter-spacing: 3px;
                text-transform: uppercase;
            }}
            
            .proudly-presented {{
                font-size: 14px;
                color: #475569;
                margin: 15px 0 10px 0;
                font-weight: 500;
                letter-spacing: 1px;
            }}
            
            .participant-name {{
                font-size: 36px;
                font-weight: 700;
                color: #1e40af;
                margin: 15px 0;
                font-family: 'Merriweather', serif;
                border-bottom: 3px solid #2563eb;
                padding: 5px 20px;
                display: inline-block;
                min-width: 400px;
                letter-spacing: 2px;
            }}
            
            .participation-text {{
                font-size: 16px;
                color: #475569;
                margin: 12px 0;
                line-height: 1.6;
                max-width: 600px;
            }}
            
            .event-date {{
                font-size: 16px;
                color: #1e40af;
                margin: 12px 0;
                font-weight: 600;
            }}
            
            .class-section {{
                font-size: 14px;
                color: #64748b;
                margin: 8px 0;
                font-style: italic;
            }}
            
            .organized-by {{
                font-size: 14px;
                color: #475569;
                margin: 20px 0 10px 0;
                font-style: italic;
                font-weight: 500;
            }}
            
            .footer {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: auto;
                padding: 0 40px;
            }}
            
            .signature {{
                text-align: center;
                flex: 1;
            }}
            
            .signature-line {{
                width: 150px;
                height: 2px;
                background-color: #334155;
                margin: 0 auto 8px;
            }}
            
            .signature p {{
                margin: 0;
                font-size: 11px;
                font-weight: 600;
                color: #334155;
                letter-spacing: 0.5px;
            }}
            
            /* Decorative elements */
            .shape {{
                position: absolute;
                border-radius: 50%;
                z-index: 1;
                opacity: 0.08;
            }}
            
            .shape-1 {{
                width: 200px;
                height: 200px;
                background: linear-gradient(135deg, #fbbf24, #f59e0b);
                top: -80px;
                left: -80px;
            }}
            
            .shape-2 {{
                width: 120px;
                height: 120px;
                background: linear-gradient(135deg, #3b82f6, #2563eb);
                bottom: -40px;
                right: -40px;
            }}
            
            .shape-3 {{
                width: 160px;
                height: 160px;
                background: linear-gradient(135deg, #10b981, #059669);
                bottom: -60px;
                left: 100px;
            }}
            
            .shape-4 {{
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #8b5cf6, #7c3aed);
                top: 40px;
                right: 60px;
            }}
            
            /* Border decoration */
            .certificate-container::before {{
                content: '';
                position: absolute;
                top: 15px;
                left: 15px;
                right: 15px;
                bottom: 15px;
                border: 2px solid #e2e8f0;
                border-radius: 10px;
                z-index: 2;
            }}
        </style>
    </head>
    <body>
        <div class="certificate-container">
            <div class="certificate">
                <div class="header">
                    <h1>VIVEKANANDA COLLEGE OF ARTS,</h1>
                    <h1>SCIENCE & COMMERCE (AUTONOMOUS)</h1>
                    <p class="address">NEHRU NAGAR, PUTTUR D.K., 574203</p>
                    <p class="department">DEPARTMENT OF COMPUTER SCIENCE</p>
                    <p class="department">INFORMATION TECHNOLOGY CLUB</p>
                </div>
                
                <div class="main-content">
                    <h2 class="certificate-title">Certificate</h2>
                    <h3 class="subtitle">OF {subtitle}</h3>
                    
                    <p class="proudly-presented">PROUDLY PRESENTED TO</p>
                    
                    <div class="participant-name">{student_name.upper()}</div>
                    
                    <p class="participation-text">
                        for actively participating in the {participation_text}
                    </p>
                    
                    <p class="event-date">held during {event_date}</p>
                    
                    {f'<p class="class-section">Class: {class_section}</p>' if class_section else ''}
                    
                    <p class="organized-by">Organised by - III BCA 'D' -</p>
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
            <div class="shape shape-4"></div>
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
        
        # Draw outer border
        c.setStrokeColor(HexColor('#2563eb'))
        c.setLineWidth(4)
        c.rect(20, 20, width-40, height-40, fill=0)
        
        # Draw inner border
        c.setStrokeColor(HexColor('#e2e8f0'))
        c.setLineWidth(2)
        c.rect(35, 35, width-70, height-70, fill=0)
        
        # College header
        c.setFillColor(HexColor('#2563eb'))
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height-60, "VIVEKANANDA COLLEGE OF ARTS,")
        c.drawCentredString(width/2, height-80, "SCIENCE & COMMERCE (AUTONOMOUS)")
        
        c.setFillColor(HexColor('#64748b'))
        c.setFont("Helvetica", 12)
        c.drawCentredString(width/2, height-105, "NEHRU NAGAR, PUTTUR D.K., 574203")
        
        c.setFillColor(HexColor('#2563eb'))
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, height-130, "DEPARTMENT OF COMPUTER SCIENCE")
        c.drawCentredString(width/2, height-150, "INFORMATION TECHNOLOGY CLUB")
        
        # Certificate title
        c.setFillColor(HexColor('#1e40af'))
        c.setFont("Helvetica-Bold", 48)
        c.drawCentredString(width/2, height-210, "Certificate")
        
        # Subtitle
        c.setFillColor(HexColor('#2563eb'))
        c.setFont("Helvetica-Bold", 16)
        subtitle_text = "OF SEMINAR PARTICIPATION" if certificate_type == 'seminar' else "OF EVENT PARTICIPATION"
        c.drawCentredString(width/2, height-240, subtitle_text)
        
        # "Proudly presented to" text
        c.setFillColor(HexColor('#475569'))
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, height-280, "PROUDLY PRESENTED TO")
        
        # Student name with underline
        c.setFillColor(HexColor('#1e40af'))
        c.setFont("Helvetica-Bold", 32)
        c.drawCentredString(width/2, height-320, student_name.upper())
        
        # Draw line under name
        name_width = c.stringWidth(student_name.upper(), "Helvetica-Bold", 32)
        line_start = (width - max(name_width + 40, 400)) / 2
        line_end = line_start + max(name_width + 40, 400)
        c.setStrokeColor(HexColor('#2563eb'))
        c.setLineWidth(3)
        c.line(line_start, height-330, line_end, height-330)
        
        # Participation text
        c.setFillColor(HexColor('#475569'))
        c.setFont("Helvetica", 16)
        if certificate_type == 'seminar':
            c.drawCentredString(width/2, height-370, "for actively participating in the")
            c.drawCentredString(width/2, height-390, "Web Development with AI Seminar Session")
        else:
            c.drawCentredString(width/2, height-370, f"for actively participating in the event")
            c.setFillColor(HexColor('#2563eb'))
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(width/2, height-390, event_name)
        
        # Event date
        c.setFillColor(HexColor('#1e40af'))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height-420, f"held during {event_date}")
        
        # Class section if provided
        if class_section:
            c.setFillColor(HexColor('#64748b'))
            c.setFont("Helvetica", 12)
            c.drawCentredString(width/2, height-445, f"Class: {class_section}")
        
        # Organized by text
        c.setFillColor(HexColor('#475569'))
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, height-480, "Organised by - III BCA 'D' -")
        
        # Signature sections
        c.setFillColor(HexColor('#334155'))
        c.setFont("Helvetica-Bold", 11)
        
        # Left signature
        left_x = width * 0.25
        c.setLineWidth(2)
        c.line(left_x - 75, 90, left_x + 75, 90)
        c.drawCentredString(left_x, 70, "HEAD OF DEPARTMENT")
        
        # Right signature
        right_x = width * 0.75
        c.line(right_x - 75, 90, right_x + 75, 90)
        c.drawCentredString(right_x, 70, "IT CLUB CONVENER")
        
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
