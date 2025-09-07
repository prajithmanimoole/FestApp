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

# Fix the issue with form submission not working on Vercel
# We need to add this middleware to handle form submission properly
@app.before_request
def fix_form_submission():
    # For POST requests without proper form data, set empty form data
    if request.method == 'POST' and not request.form and not request.files and not request.is_json:
        from werkzeug.datastructures import ImmutableMultiDict
        request.form = ImmutableMultiDict([])

# Add error handling for debugging on Vercel
@app.errorhandler(500)
def handle_500(e):
    import traceback
    return {
        "error": "Internal Server Error",
        "traceback": traceback.format_exc()
    }, 500

# Direct remove handler to ensure it works on Vercel
@app.route('/api/remove-user/<int:user_id>', methods=['GET', 'POST'])
def api_remove_user(user_id):
    from flask import g, redirect, url_for, flash
    import sqlite3
    
    # Get a database connection
    conn = sqlite3.connect(os.environ['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    g.db = conn
    
    try:
        # If user is leader of a team, delete team and unassign all members
        team = g.db.execute('SELECT * FROM teams WHERE leader_user_id = ?', (user_id,)).fetchone()
        if team:
            member_ids = [r['user_id'] for r in g.db.execute('SELECT user_id FROM team_members WHERE team_id = ?', (team['id'],)).fetchall()]
            for mid in member_ids:
                g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (mid,))
            g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (team['leader_user_id'],))
            g.db.execute('DELETE FROM team_members WHERE team_id = ?', (team['id'],))
            g.db.execute('DELETE FROM teams WHERE id = ?', (team['id'],))
        else:
            # If user is a regular team member or single participant, unassign
            g.db.execute('DELETE FROM team_members WHERE user_id = ?', (user_id,))
            g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (user_id,))
        g.db.commit()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        if g.db:
            g.db.close()

# This is for local testing only
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
