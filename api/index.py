from flask import Flask, request
import os
import sys

# Add the event_app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'event_app'))

# Set environment variables for database path - important for Vercel
os.environ['DATABASE_PATH'] = os.path.join('/tmp', 'database.db')

# Import the Flask app from your existing code
from app import create_app

# Create Flask app instance - don't use the existing instance
app = create_app()

# Add a simple test route for debugging
@app.route('/api/test')
def test_route():
    return {"status": "ok", "message": "API is working"}

# Add error handling for debugging on Vercel
@app.errorhandler(500)
def handle_500(e):
    import traceback
    return {
        "error": "Internal Server Error",
        "traceback": traceback.format_exc()
    }, 500

# This is for local testing only
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
