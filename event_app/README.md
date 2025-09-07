## Event App - Quickstart

### Run locally

1. Create a virtual environment (optional but recommended)
   - Windows PowerShell:
     - `python -m venv .venv`
     - `.venv\\Scripts\\Activate.ps1`
2. Install dependencies
   - `pip install -r requirements.txt`
3. Start the app
   - `python app.py`
4. Open `http://localhost:5000`

### Flow
- Unauthenticated users land on Sign up first. Create an account, then Sign in.
- Admin cannot register for games.

### Test credentials
- Admin: phone `9990001111`, password `admin123`

### Deploy to Render
1. Push this folder to a GitHub repo.
2. Create a new Render Web Service
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
3. Set environment variable `SECRET_KEY` to a strong random value.
4. After deploy, visit the URL. Optionally connect a custom domain.


