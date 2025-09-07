from flask import Flask, request
import os
import sys

# Add the event_app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'event_app'))

# Set environment variables for database path - important for Vercel
# First try to copy the included database to /tmp for write access
try:
    source_db = os.path.join(os.path.dirname(__file__), 'database.db')
    target_db = os.path.join('/tmp', 'database.db')
    
    # Only copy if the source exists and target doesn't exist yet
    if os.path.exists(source_db) and not os.path.exists(target_db):
        import shutil
        shutil.copy2(source_db, target_db)
        print(f"Database copied from {source_db} to {target_db}")
except Exception as e:
    print(f"Error copying database: {str(e)}")
    
# Set the database path to the writable location
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
