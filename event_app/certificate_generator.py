from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
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

def generate_certificate(student_name, class_section, event_name, date, output_path=None):
    """
    Generate a personalized certificate for a student
    
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
    
    # Logo placeholder - replace with actual logo path when available
    # c.drawImage("path_to_logo.png", width/2-50, height-120, width=100, height=50)
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height-100, "FEST APP")
    
    # Body text
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height-150, "This is to certify that")
    
    # Student name
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height/2+50, student_name)
    
    # Class and section
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height/2+10, class_section)
    
    # Event details
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height/2-30, "has successfully participated in")
    
    # Event name
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height/2-70, event_name)
    
    # Date
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height/2-100, date)
    
    # Signature placeholders
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
