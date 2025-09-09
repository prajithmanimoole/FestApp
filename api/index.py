from http.server import BaseHTTPRequestHandler
import os
import sys

# Add the main directory to the path so we can import the wsgi app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from wsgi import app as flask_app
except ImportError:
    flask_app = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if flask_app:
            # This is a minimal wrapper to test that Flask can be imported
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write('Flask app successfully imported!'.encode())
        else:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write('Error: Could not import Flask app'.encode())