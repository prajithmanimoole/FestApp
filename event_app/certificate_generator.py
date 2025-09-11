from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from PIL import Image, ImageDraw, ImageFont
import os
import io

# Register fonts (you might need to adjust these paths for your system)
try:
    pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
    pdfmetrics.registerFont(TTFont('ArialBold', 'Arial Bold.ttf'))
except:
    # Fallback to built-in fonts
    pass

def create_certificate_template():
    """Creates a basic certificate template PDF file"""
    width, height = landscape(A4)
    buffer = io.BytesIO()
    
    # Create a canvas
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    # Set background color
    c.setFillColor(white)
    c.rect(0, 0, width, height, fill=True)
    
    # Draw border
    c.setStrokeColor(black)
    c.setLineWidth(3)
    c.rect(20, 20, width-40, height-40, fill=0)
    
    # Title
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width/2, height-70, "CERTIFICATE OF PARTICIPATION")
    
    # Logo placeholder
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height-100, "ORGANIZATION LOGO")
    
    # Body text
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height-150, "This is to certify that")
    
    # Name placeholder
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height/2+50, "NAME_PLACEHOLDER")
    
    # Class placeholder
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height/2+10, "CLASS_PLACEHOLDER")
    
    # Event details
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height/2-30, "has successfully participated in")
    
    # Event name placeholder
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height/2-70, "EVENT_PLACEHOLDER")
    
    # Date placeholder
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height/2-100, "DATE_PLACEHOLDER")
    
    # Signature placeholders
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/3, 80, "____________________")
    c.drawCentredString(width/3, 60, "Organizer Signature")
    
    c.drawCentredString(2*width/3, 80, "____________________")
    c.drawCentredString(2*width/3, 60, "Principal Signature")
    
    c.save()
    buffer.seek(0)
    return buffer

def generate_simple_certificate_pdf(student_name, event_name, event_date, class_section=None, certificate_type='event'):
    """
    Generate a simple PDF certificate using ReportLab as fallback
    
    Args:
        student_name: Name of the student
        event_name: Name of the event
        event_date: Date of the event
        class_section: Class and section of the student (optional)
        certificate_type: Type of certificate ('event' or 'seminar')
    
    Returns:
        BytesIO object containing the PDF certificate
    """
    from io import BytesIO
    
    width, height = landscape(A4)
    buffer = BytesIO()
    
    # Create a canvas
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    # Set background color
    c.setFillColor(white)
    c.rect(0, 0, width, height, fill=True)
    
    # Draw border
    c.setStrokeColor(black)
    c.setLineWidth(3)
    c.rect(20, 20, width-40, height-40, fill=0)
    
    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height-70, "CERTIFICATE OF PARTICIPATION")
    
    # College info
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, height-100, "VIVEKANANDA COLLEGE OF ARTS, SCIENCE & COMMERCE")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height-120, "NEHRU NAGAR, PUTTUR D.K., 574203")
    c.drawCentredString(width/2, height-140, "DEPARTMENT OF COMPUTER SCIENCE")
    c.drawCentredString(width/2, height-160, "INFORMATION TECHNOLOGY CLUB")
    
    # Body text
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height-200, "This is to certify that")
    
    # Student name
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height-240, student_name.upper())
    
    # Event participation text
    participation_text = f"has actively participated in the {'Web Development with AI Seminar Session' if certificate_type == 'seminar' else f'event {event_name}'}"
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height-280, participation_text)
    c.drawCentredString(width/2, height-300, f"held during {event_date}")
    
    # Class section if provided
    if class_section:
        c.setFont("Helvetica", 12)
        c.drawCentredString(width/2, height-320, f"Class: {class_section}")
    
    # Signature lines
    c.setFont("Helvetica", 10)
    c.line(100, 80, 250, 80)
    c.drawCentredString(175, 60, "HEAD OF DEPARTMENT")
    
    c.line(width-250, 80, width-100, 80)
    c.drawCentredString(width-175, 60, "IT CLUB CONVENER")
    
    c.save()
    buffer.seek(0)
    return buffer

def generate_certificate(student_name, class_section, event_name, date, output_path=None):
    """
    Generate a personalized certificate for a student using the template image
    
    Args:
        student_name: Name of the student
        class_section: Class and section of the student
        event_name: Name of the event
        date: Date of the event
        output_path: Path to save the certificate (if None, returns BytesIO object)
    
    Returns:
        BytesIO object containing the certificate PDF if output_path is None
        Otherwise saves the certificate to the specified path
    """
    width, height = landscape(A4)
    buffer = io.BytesIO()
    
    # Create a canvas
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    # Get the template image path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, 'static', 'certificates', 'certificate_template.jpg')
    
    # Check if template exists and use it, otherwise create a fallback template
    try:
        # Try to use the template image as background
        if os.path.exists(template_path):
            c.drawImage(template_path, 0, 0, width=width, height=height, preserveAspectRatio=True)
        else:
            raise FileNotFoundError(f"Certificate template not found at {template_path}")
    except Exception as e:
        # Fallback to creating a simple certificate
        print(f"Error using template image: {e}")
        
        # Set background color
        c.setFillColor(white)
        c.rect(0, 0, width, height, fill=True)
        
        # Draw border
        c.setStrokeColor(black)
        c.setLineWidth(3)
        c.rect(20, 20, width-40, height-40, fill=0)
        
        # Title
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(width/2, height-70, "CERTIFICATE OF PARTICIPATION")
    
    # Student name (centered in the dotted line area)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 20)
    name_y_position = height/2 - 10  # Position for the name
    c.drawCentredString(width/2, name_y_position, student_name)
    
    # Event name (replace the placeholder in the certificate)
    c.setFont("Helvetica", 16)
    event_y_position = height/2 - 80  # Position for the event name
    c.drawCentredString(width/2, event_y_position, event_name)
    
    # Date (add below event name)
    current_date = date
    c.setFont("Helvetica", 14)
    date_y_position = height/2 - 120  # Position for the date
    c.drawCentredString(width/2, date_y_position, f"held during {current_date}")
    
    # Add signature lines if using fallback template
    if not os.path.exists(template_path):
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/3, 80, "____________________")
        c.drawCentredString(width/3, 60, "Organizer Signature")
        
        c.drawCentredString(2*width/3, 80, "____________________")
        c.drawCentredString(2*width/3, 60, "Principal Signature")
    
    c.save()
    buffer.seek(0)
    
    if output_path:
        with open(output_path, 'wb') as f:
            f.write(buffer.getvalue())
        return None
    else:
        return buffer
