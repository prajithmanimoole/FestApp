# Script to save the certificate template
import os
import shutil
import sys

def setup_certificate_template():
    """
    Setup the certificate template by copying the provided image to the static folder
    """
    # Get the directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create certificate directory if it doesn't exist
    certificates_dir = os.path.join(current_dir, 'event_app', 'static', 'certificates')
    os.makedirs(certificates_dir, exist_ok=True)
    
    # Check if template already exists
    template_path = os.path.join(certificates_dir, 'certificate_template.jpg')
    
    if not os.path.exists(template_path):
        print("Certificate template not found.")
        print(f"Please copy your certificate template image to: {template_path}")
    else:
        print(f"Certificate template already exists at: {template_path}")

if __name__ == '__main__':
    setup_certificate_template()
