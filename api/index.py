from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
import sqlite3
import os
import sys
import shutil

# Database setup for Vercel
DATABASE_NAME = 'database.db'

def get_database_path():
    # For Vercel deployment, copy database to /tmp for write access
    if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        source_db = os.path.join(os.path.dirname(__file__), DATABASE_NAME)
        target_db = os.path.join('/tmp', DATABASE_NAME)
        
        try:
            if os.path.exists(source_db):
                if not os.path.exists(target_db):
                    shutil.copy2(source_db, target_db)
                    print(f"Database copied to {target_db}")
                return target_db
            else:
                print(f"Source database not found: {source_db}")
                return target_db  # Return the target path anyway
        except Exception as e:
            print(f"Error copying database: {e}")
            return target_db
    else:
        # Local development
        return os.path.join(os.path.dirname(__file__), '..', 'event_app', DATABASE_NAME)

def get_db():
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db()
        
        # Create tables
        conn.execute('''
            CREATE TABLE IF NOT EXISTS allowed_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                game_id INTEGER,
                team_id INTEGER,
                FOREIGN KEY (game_id) REFERENCES games (id),
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                team_size INTEGER NOT NULL,
                description TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                game_id INTEGER NOT NULL,
                leader_user_id INTEGER NOT NULL,
                FOREIGN KEY (game_id) REFERENCES games (id),
                FOREIGN KEY (leader_user_id) REFERENCES users (id)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (team_id) REFERENCES teams (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Create Flask app factory
def create_app():
    app = Flask(__name__,
                template_folder='../event_app/templates',
                static_folder='../event_app/static')
    app.secret_key = 'your-secret-key-here'

    @app.before_request
    def before_request():
        g.db = get_db()

    @app.teardown_appcontext
    def close_db(error):
        if hasattr(g, 'db'):
            g.db.close()

    @app.route('/')
    def index():
        return redirect(url_for('login'))

    return app

# Instantiate app for Vercel and initialize database once on cold start
app = create_app()
try:
    init_db()
except Exception as _e:
    # Log but don't crash
    print(f"init_db error: {_e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        
        # Check if user exists in allowed users
        allowed_user = g.db.execute(
            'SELECT * FROM allowed_users WHERE phone = ?', (phone,)
        ).fetchone()
        
        if allowed_user:
            # Check if user already has an account
            existing_user = g.db.execute(
                'SELECT * FROM users WHERE phone = ?', (phone,)
            ).fetchone()
            
            if existing_user:
                session['user_id'] = existing_user['id']
                session['is_admin'] = existing_user['is_admin']
                if existing_user['is_admin']:
                    return redirect(url_for('admin'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                session['temp_phone'] = phone
                session['temp_is_admin'] = allowed_user['is_admin']
                return redirect(url_for('signup'))
        else:
            flash('Phone number not authorized. Please contact administrator.')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'temp_phone' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        phone = session['temp_phone']
        is_admin = session['temp_is_admin']
        
        # Create user account
        g.db.execute(
            'INSERT INTO users (name, phone, is_admin) VALUES (?, ?, ?)',
            (name, phone, is_admin)
        )
        g.db.commit()
        
        # Get the new user
        user = g.db.execute(
            'SELECT * FROM users WHERE phone = ?', (phone,)
        ).fetchone()
        
        session['user_id'] = user['id']
        session['is_admin'] = user['is_admin']
        session.pop('temp_phone', None)
        session.pop('temp_is_admin', None)
        
        if user['is_admin']:
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('dashboard'))
    
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = g.db.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    
    games = g.db.execute('SELECT * FROM games').fetchall()
    
    user_team = None
    if user['team_id']:
        user_team = g.db.execute(
            'SELECT t.*, g.name as game_name FROM teams t '
            'JOIN games g ON t.game_id = g.id '
            'WHERE t.id = ?', (user['team_id'],)
        ).fetchone()
    
    return render_template('dashboard.html', user=user, games=games, user_team=user_team)

@app.route('/join_game/<int:game_id>')
def join_game(game_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Check if user is already in a game
    user = g.db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user['game_id']:
        flash('You are already registered for a game.')
        return redirect(url_for('dashboard'))
    
    game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    if not game:
        flash('Game not found.')
        return redirect(url_for('dashboard'))
    
    if game['team_size'] == 1:
        # Single player game
        g.db.execute('UPDATE users SET game_id = ? WHERE id = ?', (game_id, user_id))
        g.db.commit()
        flash(f'Successfully registered for {game["name"]}!')
    else:
        # Team game - redirect to team selection
        return redirect(url_for('join_team', game_id=game_id))
    
    return redirect(url_for('dashboard'))

@app.route('/join_team/<int:game_id>')
def join_team(game_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Check if user is already in a game
    user = g.db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user['game_id']:
        flash('You are already registered for a game.')
        return redirect(url_for('dashboard'))
    
    game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    if not game:
        flash('Game not found.')
        return redirect(url_for('dashboard'))
    
    # Get existing teams for this game
    teams = g.db.execute(
        'SELECT t.*, u.name as leader_name, '
        '(SELECT COUNT(*) FROM team_members tm WHERE tm.team_id = t.id) + 1 as current_size '
        'FROM teams t '
        'JOIN users u ON t.leader_user_id = u.id '
        'WHERE t.game_id = ?', (game_id,)
    ).fetchall()
    
    return render_template('join_team.html', game=game, teams=teams)

@app.route('/create_team/<int:game_id>', methods=['POST'])
def create_team(game_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    team_name = request.form['team_name']
    
    # Create team
    g.db.execute(
        'INSERT INTO teams (name, game_id, leader_user_id) VALUES (?, ?, ?)',
        (team_name, game_id, user_id)
    )
    
    # Get the new team ID
    team_id = g.db.lastrowid
    
    # Update user
    g.db.execute(
        'UPDATE users SET game_id = ?, team_id = ? WHERE id = ?',
        (game_id, team_id, user_id)
    )
    
    g.db.commit()
    flash(f'Team "{team_name}" created successfully!')
    return redirect(url_for('dashboard'))

@app.route('/join_existing_team/<int:team_id>')
def join_existing_team(team_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Get team info
    team = g.db.execute(
        'SELECT t.*, g.team_size FROM teams t '
        'JOIN games g ON t.game_id = g.id '
        'WHERE t.id = ?', (team_id,)
    ).fetchone()
    
    if not team:
        flash('Team not found.')
        return redirect(url_for('dashboard'))
    
    # Check team capacity
    current_members = g.db.execute(
        'SELECT COUNT(*) as count FROM team_members WHERE team_id = ?', (team_id,)
    ).fetchone()['count'] + 1  # +1 for leader
    
    if current_members >= team['team_size']:
        flash('Team is full.')
        return redirect(url_for('join_team', game_id=team['game_id']))
    
    # Add user to team
    g.db.execute(
        'INSERT INTO team_members (team_id, user_id) VALUES (?, ?)',
        (team_id, user_id)
    )
    
    # Update user
    g.db.execute(
        'UPDATE users SET game_id = ?, team_id = ? WHERE id = ?',
        (team['game_id'], team_id, user_id)
    )
    
    g.db.commit()
    flash('Successfully joined the team!')
    return redirect(url_for('dashboard'))

@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Access denied.')
        return redirect(url_for('login'))
    
    games = g.db.execute('SELECT * FROM games').fetchall()
    
    # Get all participants with game and team info using LEFT JOIN
    participants = g.db.execute('''
        SELECT u.id, u.name, u.phone, 
               COALESCE(g.name, 'Not Registered') as game_name,
               COALESCE(t.name, 'No Team') as team_name,
               CASE 
                   WHEN t.leader_user_id = u.id THEN 'Leader'
                   WHEN u.team_id IS NOT NULL THEN 'Member'
                   ELSE 'Individual'
               END as role
        FROM users u 
        LEFT JOIN games g ON u.game_id = g.id 
        LEFT JOIN teams t ON u.team_id = t.id
        WHERE u.is_admin = 0
        ORDER BY u.name
    ''').fetchall()
    
    return render_template('admin.html', games=games, participants=participants)

@app.route('/admin/add_game', methods=['POST'])
def add_game():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    name = request.form['name']
    team_size = int(request.form['team_size'])
    description = request.form['description']
    
    g.db.execute(
        'INSERT INTO games (name, team_size, description) VALUES (?, ?, ?)',
        (name, team_size, description)
    )
    g.db.commit()
    
    flash('Game added successfully!')
    return redirect(url_for('admin'))

@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    name = request.form['name']
    phone = request.form['phone']
    is_admin = 'is_admin' in request.form
    
    try:
        g.db.execute(
            'INSERT INTO allowed_users (name, phone, is_admin) VALUES (?, ?, ?)',
            (name, phone, is_admin)
        )
        g.db.commit()
        flash('User added successfully!')
    except sqlite3.IntegrityError:
        flash('Phone number already exists!')
    
    return redirect(url_for('admin'))

@app.route('/remove_game_registration/<int:user_id>')
def remove_game_registration(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    # If user is leader of a team, delete team and unassign all members
    team = g.db.execute('SELECT * FROM teams WHERE leader_user_id = ?', (user_id,)).fetchone()
    if team:
        member_ids = [r['user_id'] for r in g.db.execute('SELECT user_id FROM team_members WHERE team_id = ?', (team['id'],)).fetchall()]
        for member_id in member_ids:
            g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (member_id,))
        g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (team['leader_user_id'],))
        g.db.execute('DELETE FROM team_members WHERE team_id = ?', (team['id'],))
        g.db.execute('DELETE FROM teams WHERE id = ?', (team['id'],))
    else:
        # If user is a regular team member or single participant, unassign
        g.db.execute('DELETE FROM team_members WHERE user_id = ?', (user_id,))
        g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (user_id,))
    
    g.db.commit()
    flash('User removed from game successfully!')
    return redirect(url_for('admin'))

@app.route('/team_register/<int:game_id>')
def team_register(game_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    if not game:
        flash('Game not found.')
        return redirect(url_for('admin'))
    
    # Get users not registered for any game
    available_users = g.db.execute(
        'SELECT * FROM users WHERE game_id IS NULL AND is_admin = 0'
    ).fetchall()
    
    return render_template('team_register.html', game=game, users=available_users)

@app.route('/admin/register_team/<int:game_id>', methods=['POST'])
def register_team(game_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    team_name = request.form['team_name']
    leader_id = int(request.form['leader_id'])
    member_ids = [int(id) for id in request.form.getlist('member_ids') if id]
    
    # Create team
    g.db.execute(
        'INSERT INTO teams (name, game_id, leader_user_id) VALUES (?, ?, ?)',
        (team_name, game_id, leader_id)
    )
    team_id = g.db.lastrowid
    
    # Update leader
    g.db.execute(
        'UPDATE users SET game_id = ?, team_id = ? WHERE id = ?',
        (game_id, team_id, leader_id)
    )
    
    # Add members
    for member_id in member_ids:
        g.db.execute(
            'INSERT INTO team_members (team_id, user_id) VALUES (?, ?)',
            (team_id, member_id)
        )
        g.db.execute(
            'UPDATE users SET game_id = ?, team_id = ? WHERE id = ?',
            (game_id, team_id, member_id)
        )
    
    g.db.commit()
    flash('Team registered successfully!')
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API Routes for JavaScript functionality
@app.route('/api/test')
def test_route():
    return {"status": "ok", "message": "API is working"}

@app.route('/api/remove-user/<int:user_id>', methods=['GET', 'POST'])
def api_remove_user(user_id):
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

@app.route('/api/complete-remove-user/<int:user_id>', methods=['GET', 'POST'])
def api_complete_remove_user(user_id):
    try:
        # First get the user to get their phone
        user = g.db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        phone = user['phone']
        
        # Handle teams related cleanup
        g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE team_id IN (SELECT id FROM teams WHERE leader_user_id = ?)', (user_id,))
        g.db.execute('DELETE FROM team_members WHERE team_id IN (SELECT id FROM teams WHERE leader_user_id = ?)', (user_id,))
        g.db.execute('DELETE FROM teams WHERE leader_user_id = ?', (user_id,))
        
        # Remove user from teams as a member
        g.db.execute('DELETE FROM team_members WHERE user_id = ?', (user_id,))
        
        # Delete user and credentials
        g.db.execute('DELETE FROM users WHERE id = ?', (user_id,))
        g.db.execute('DELETE FROM allowed_users WHERE phone = ?', (phone,))
        
        # Commit all changes
        g.db.commit()
        
        return jsonify({"success": True, "message": "User completely removed"})
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Failed to remove user"
        }), 500

# Error handlers
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
