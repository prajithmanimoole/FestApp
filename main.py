"""
Root-level app.py for Railway deployment.
This file simply imports the app from the wsgi.py file.
"""
from wsgi import app

if __name__ == "__main__":
    app.run()
