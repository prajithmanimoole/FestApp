"""
Root-level main.py for Railway deployment.
This file simply imports the app from the wsgi.py file.
"""
from wsgi import app
import os

if __name__ == "__main__":
    # Get port from environment variable or use 8080 as default
    port = int(os.environ.get("PORT", 8080))
    # Run the app with host 0.0.0.0 to make it externally visible
    app.run(host="0.0.0.0", port=port)
