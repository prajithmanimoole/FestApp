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
- Admin: phone `9990001111`, password `1234`

### Notes
This project is set up for local usage. Remove any cloud deployment configs.
