from flask import Flask, request
import os
import sys

# Add the event_app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'event_app'))

# Import the Flask app from your existing code
from app import app as flask_app

# Export the app for Vercel
app = flask_app

# This is for local testing only
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
