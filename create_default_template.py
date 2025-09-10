from PIL import Image, ImageDraw, ImageFont
import os

def create_default_template():
    """
    Create a default certificate template image based on the design shared
    """
    # Create a new image with a white background
    width, height = 842, 595  # A4 landscape size in points
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Define colors
    blue = (33, 65, 169)      # Dark blue for main text
    light_blue = (65, 105, 225)  # Light blue for decorations
    yellow = (255, 215, 0)    # Yellow for decorations
    teal = (100, 200, 180)    # Teal for decorations
    
    # Draw decorative circles
    draw.ellipse((-150, -150, 300, 300), fill=yellow)  # Top-right yellow circle
    draw.ellipse((width-200, -100, width+100, 200), fill=teal)  # Top-right teal circle
    draw.ellipse((-100, height-200, 200, height+100), fill=teal)  # Bottom-left teal circle
    draw.ellipse((width-300, height-300, width+100, height+100), fill=light_blue)  # Bottom-right blue circle
    
    # Load fonts (using default if custom fonts aren't available)
    try:
        title_font = ImageFont.truetype("Arial Bold.ttf", 36)
        header_font = ImageFont.truetype("Arial Bold.ttf", 24)
        normal_font = ImageFont.truetype("Arial.ttf", 18)
        small_font = ImageFont.truetype("Arial.ttf", 14)
    except IOError:
        # Fallback to default font
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        normal_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Add college name
    draw.text((width/2, 40), "VIVEKANANDA COLLEGE OF ARTS,", fill=blue, font=header_font, anchor="mt")
    draw.text((width/2, 70), "SCIENCE & COMMERCE (AUTONOMOUS)", fill=blue, font=header_font, anchor="mt")
    draw.text((width/2, 100), "NEHRU NAGAR, PUTTUR D.K, 574203", fill=blue, font=normal_font, anchor="mt")
    
    # Add department name
    draw.text((width/2, 150), "DEPARTMENT OF COMPUTER SCIENCE", fill=blue, font=normal_font, anchor="mt")
    draw.text((width/2, 185), "INFORMATION TECHNOLOGY CLUB", fill=blue, font=normal_font, anchor="mt")
    
    # Draw laurel wreath (simplified with a circle)
    draw.ellipse((width/2-100, 220, width/2+100, 420), outline=yellow, width=2)
    
    # Add certificate title
    draw.text((width/2, 320), "Certificate", fill=(0, 0, 0), font=title_font, anchor="mm")
    
    # Add "OF PARTICIPATION" text
    draw.text((width/2, 370), "OF PARTICIPATION", fill=blue, font=normal_font, anchor="mm")
    
    # Add dotted line for name
    draw.line((width/2-150, 450, width/2+150, 450), fill=(0, 0, 0), width=1)
    
    # Add remaining text
    draw.text((width/2, 500), "for actively participating in the event", fill=(0, 0, 0), font=small_font, anchor="mm")
    draw.text((width/2, 550), "held during", fill=(0, 0, 0), font=small_font, anchor="mm")
    
    # Add event name
    draw.text((width/2, 590), "IT CLUB EVENT", fill=blue, font=normal_font, anchor="mm")
    
    # Add "Organised by" text
    draw.text((width/2, 630), "Organised by - III BCA 'D' -", fill=(0, 0, 0), font=small_font, anchor="mm")
    
    # Add signature lines
    draw.line((width/3-50, 700, width/3+50, 700), fill=(0, 0, 0), width=1)
    draw.text((width/3, 720), "HEAD OF DEPARTMENT", fill=(0, 0, 0), font=small_font, anchor="mm")
    
    draw.line((2*width/3-50, 700, 2*width/3+50, 700), fill=(0, 0, 0), width=1)
    draw.text((2*width/3, 720), "IT CLUB CONVENER", fill=(0, 0, 0), font=small_font, anchor="mm")
    
    # Save the image
    directory = os.path.join('event_app', 'static', 'certificates')
    os.makedirs(directory, exist_ok=True)
    image_path = os.path.join(directory, 'certificate_template.jpg')
    image.save(image_path, quality=95)
    print(f"Default certificate template created at: {image_path}")
    return image_path

if __name__ == "__main__":
    create_default_template()
