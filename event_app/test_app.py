#!/usr/bin/env python3

import traceback

try:
    print("Testing app import...")
    from app import create_app
    print("App imported successfully")
    
    print("Creating app instance...")
    app = create_app()
    print("App created successfully")
    
    print("Testing certificate generation...")
    from certificate_html_generator import generate_certificate_pdf
    pdf = generate_certificate_pdf('Test Student', 'Test Event', '2024-01-15')
    print("Certificate generated successfully")
    
    print("Starting Flask app...")
    app.run(host='127.0.0.1', port=5000, debug=True)
    
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()