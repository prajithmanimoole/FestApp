import os
import sqlite3
import random
import string
from contextlib import closing
from datetime import datetime
from typing import Optional, Dict, Any, List

from flask import Flask, g, render_template, request, redirect, url_for, session, flash, send_file


# Use environment variable if set, otherwise use the default path
DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'database.db'))


def generate_team_code() -> str:
    """Generate a unique 6-character team code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        # Check if code already exists
        with closing(get_db()) as db:
            exists = db.execute('SELECT 1 FROM teams WHERE team_code = ?', (code,)).fetchone()
            if not exists:
                return code


def create_app() -> Flask:
    # Ensure template and static folders are correctly specified
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret')

    @app.before_request
    def before_request() -> None:
        g.db = get_db()
        try:
            exists = g.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='allowed_users'").fetchone()
            if not exists:
                ensure_schema_and_seed()
        except Exception:
            ensure_schema_and_seed()

    @app.teardown_request
    def teardown_request(exception: Optional[BaseException]) -> None:  # noqa: ARG001
        db = g.pop('db', None)
        if db is not None:
            db.close()

    ensure_schema_and_seed()

    register_routes(app)
    return app


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema_and_seed() -> None:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    with closing(get_db()) as db:
        cur = db.cursor()
        # Users
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                game_id INTEGER,
                team_id INTEGER,
                is_admin INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Games
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                slots INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('single','team'))
            )
            """
        )
        # Add team_size column if missing
        try:
            cols = [r[1] for r in cur.execute('PRAGMA table_info(games)').fetchall()]
            if 'team_size' not in cols:
                cur.execute('ALTER TABLE games ADD COLUMN team_size INTEGER')
        except Exception:
            pass
        # Teams
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                leader_user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                team_code TEXT UNIQUE NOT NULL
            )
            """
        )
        # Add team_code column if missing
        try:
            cols = [r[1] for r in cur.execute('PRAGMA table_info(teams)').fetchall()]
            if 'team_code' not in cols:
                cur.execute('ALTER TABLE teams ADD COLUMN team_code TEXT')
            # Generate codes for existing teams that don't have them
            for team in cur.execute('SELECT id FROM teams WHERE team_code IS NULL').fetchall():
                code = generate_team_code()
                cur.execute('UPDATE teams SET team_code = ? WHERE id = ?', (code, team['id']))
        except Exception:
            pass
        # Team members
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL
            )
            """
        )
        # Allowed users (admin-provided credentials)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS allowed_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.commit()

        # Seed minimal data if empty: only admin user, no games
        user_count = cur.execute('SELECT COUNT(1) FROM users').fetchone()[0]
        if user_count == 0:
            cur.execute(
                'INSERT INTO users (phone, password, name, is_admin) VALUES (?,?,?,?)',
                ('9990001111', 'admin123', 'Admin User', 1),
            )
        # Ensure admin exists in allowed_users
        allowed_admin = cur.execute('SELECT 1 FROM allowed_users WHERE phone = ?', ('9990001111',)).fetchone()
        if not allowed_admin:
            cur.execute(
                'INSERT INTO allowed_users (phone, password, name, is_admin) VALUES (?,?,?,1)',
                ('9990001111', 'admin123', 'Admin User'),
            )
        # Migrate any existing users into allowed_users if missing
        for row in cur.execute('SELECT phone, password, name, is_admin FROM users'):
            exists = cur.execute('SELECT 1 FROM allowed_users WHERE phone = ?', (row[0],)).fetchone()
            if not exists:
                cur.execute(
                    'INSERT INTO allowed_users (phone, password, name, is_admin) VALUES (?,?,?,?)',
                    (row[0], row[1], row[2], row[3]),
                )
        db.commit()


def fetch_current_user() -> Optional[sqlite3.Row]:
    user_id = session.get('user_id')
    if not user_id:
        return None
    row = g.db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    return row


def is_registered_elsewhere(user_row: sqlite3.Row) -> bool:
    return bool(user_row['game_id'])


def get_available_slots(game_id: int) -> int:
    game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    if not game:
        return 0
    if game['type'] == 'single':
        registered = g.db.execute('SELECT COUNT(1) FROM users WHERE game_id = ? AND (team_id IS NULL)', (game_id,)).fetchone()[0]
        return max(0, int(game['slots']) - int(registered))
    # team-based: slots represent number of teams
    teams = g.db.execute('SELECT COUNT(1) FROM teams WHERE game_id = ?', (game_id,)).fetchone()[0]
    return max(0, int(game['slots']) - int(teams))


def register_routes(app: Flask) -> None:
    @app.route('/')
    def index():
        if session.get('user_id'):
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            phone = request.form.get('phone', '').strip()
            password = request.form.get('password', '').strip()
            # Validate against allowed_users first
            allowed = g.db.execute('SELECT * FROM allowed_users WHERE phone = ? AND password = ?', (phone, password)).fetchone()
            if allowed:
                # Ensure a corresponding users row exists
                user_row = g.db.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
                if not user_row:
                    cur = g.db.cursor()
                    cur.execute('INSERT INTO users (phone, password, name, is_admin) VALUES (?,?,?,?)', (allowed['phone'], allowed['password'], allowed['name'], allowed['is_admin']))
                    g.db.commit()
                    user_row = g.db.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
                # Sync admin flag and name if changed
                if user_row['is_admin'] != allowed['is_admin'] or user_row['name'] != allowed['name']:
                    g.db.execute('UPDATE users SET is_admin = ?, name = ? WHERE id = ?', (allowed['is_admin'], allowed['name'], user_row['id']))
                    g.db.commit()
                session['user_id'] = user_row['id']
                flash('Signed in successfully.', 'success')
                return redirect(url_for('dashboard'))
            flash('Invalid credentials.', 'danger')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Logged out.', 'info')
        return redirect(url_for('login'))

    @app.route('/dashboard')
    def dashboard():
        user = fetch_current_user()
        if not user:
            return redirect(url_for('login'))
        games = g.db.execute('SELECT * FROM games ORDER BY id').fetchall()
        registration: Dict[str, Any] = {}
        if user['game_id']:
            game = g.db.execute('SELECT * FROM games WHERE id = ?', (user['game_id'],)).fetchone()
            if game['type'] == 'single':
                registration = {'type': 'single', 'game': game}
            else:
                team = g.db.execute('SELECT * FROM teams WHERE id = ?', (user['team_id'],)).fetchone()
                members = g.db.execute(
                    'SELECT u.* FROM team_members tm JOIN users u ON u.id = tm.user_id WHERE tm.team_id = ? ORDER BY u.name',
                    (team['id'],),
                ).fetchall()
                registration = {'type': 'team', 'game': game, 'team': team, 'members': members}
        # decorate games with available slots
        games_with_slots: List[sqlite3.Row] = []
        for g_row in games:
            available = get_available_slots(g_row['id'])
            record = dict(g_row)
            record['available'] = available
            games_with_slots.append(record)  # type: ignore[arg-type]
        return render_template('dashboard.html', user=user, games=games_with_slots, registration=registration)

    @app.route('/register/single/<int:game_id>', methods=['POST'])
    def register_single(game_id: int):
        user = fetch_current_user()
        if not user:
            return redirect(url_for('login'))
        if user['is_admin']:
            flash('Admins cannot register for games.', 'danger')
            return redirect(url_for('dashboard'))
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
        if not game or game['type'] != 'single':
            flash('Invalid game.', 'danger')
            return redirect(url_for('dashboard'))
        if is_registered_elsewhere(user):
            flash('You are already registered in a game.', 'warning')
            return redirect(url_for('dashboard'))
        if get_available_slots(game_id) <= 0:
            flash('No slots available.', 'warning')
            return redirect(url_for('dashboard'))
        g.db.execute('UPDATE users SET game_id = ? WHERE id = ?', (game_id, user['id']))
        g.db.commit()
        flash('Registered successfully!', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/team/register/<int:game_id>', methods=['GET', 'POST'])
    def team_register(game_id: int):
        user = fetch_current_user()
        if not user:
            return redirect(url_for('login'))
        if user['is_admin']:
            flash('Admins cannot register for games.', 'danger')
            return redirect(url_for('dashboard'))
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
        if not game or game['type'] != 'team':
            flash('Invalid team game.', 'danger')
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            team_name = request.form.get('team_name', '').strip()

            if is_registered_elsewhere(user):
                flash('You are already registered in a game.', 'warning')
                return redirect(url_for('dashboard'))
            if get_available_slots(game_id) <= 0:
                flash('No team slots available.', 'warning')
                return redirect(url_for('dashboard'))

            cur = g.db.cursor()
            team_code = generate_team_code()
            cur.execute('INSERT INTO teams (name, leader_user_id, game_id, team_code) VALUES (?,?,?,?)', (team_name, user['id'], game_id, team_code))
            team_id = cur.lastrowid
            # Assign leader
            cur.execute('UPDATE users SET game_id = ?, team_id = ? WHERE id = ?', (game_id, team_id, user['id']))
            g.db.commit()
            flash(f'Team "{team_name}" created successfully! Team Code: {team_code}. Share this code with your team members.', 'success')
            return redirect(url_for('dashboard'))
        return render_template('team_register.html', game=game)

    @app.route('/team/join', methods=['GET', 'POST'])
    def join_team():
        user = fetch_current_user()
        if not user:
            return redirect(url_for('login'))
        if user['is_admin']:
            flash('Admins cannot join teams.', 'danger')
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            team_code = request.form.get('team_code', '').strip().upper()
            
            if is_registered_elsewhere(user):
                flash('You are already registered in a game.', 'warning')
                return redirect(url_for('dashboard'))
            
            # Find team by code
            team = g.db.execute('SELECT * FROM teams WHERE team_code = ?', (team_code,)).fetchone()
            if not team:
                flash('Invalid team code.', 'danger')
                return redirect(url_for('dashboard'))
            
            # Get game info
            game = g.db.execute('SELECT * FROM games WHERE id = ?', (team['game_id'],)).fetchone()
            if not game:
                flash('Game not found.', 'danger')
                return redirect(url_for('dashboard'))
            
            # Check if team is full (if team size is configured)
            if game['team_size'] is not None:
                current_members = g.db.execute('SELECT COUNT(1) FROM team_members WHERE team_id = ?', (team['id'],)).fetchone()[0]
                leader_count = 1  # Leader is always counted
                if current_members + leader_count >= int(game['team_size']):
                    flash('This team is full.', 'warning')
                    return redirect(url_for('dashboard'))
            
            # Add user to team
            cur = g.db.cursor()
            cur.execute('INSERT INTO team_members (team_id, user_id) VALUES (?,?)', (team['id'], user['id']))
            cur.execute('UPDATE users SET game_id = ?, team_id = ? WHERE id = ?', (team['game_id'], team['id'], user['id']))
            g.db.commit()
            flash(f'Successfully joined team "{team["name"]}"!', 'success')
            return redirect(url_for('dashboard'))
        
        return render_template('join_team.html')

    @app.route('/admin', methods=['GET', 'POST'])
    def admin():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))

        # Handle Add Game form
        if request.method == 'POST' and request.form.get('form_type') == 'add_game':
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            slots = int(request.form.get('slots') or 0)
            gtype = request.form.get('type')
            team_size_val = request.form.get('team_size')
            team_size = int(team_size_val) if team_size_val else None
            if gtype == 'team' and (team_size is None or team_size < 2):
                flash('Team size must be at least 2 for team games (including leader).', 'danger')
            elif name and slots > 0 and gtype in ('single', 'team'):
                if gtype == 'team':
                    g.db.execute('INSERT INTO games (name, description, slots, type, team_size) VALUES (?,?,?,?,?)', (name, description, slots, gtype, team_size))
                else:
                    g.db.execute('INSERT INTO games (name, description, slots, type, team_size) VALUES (?,?,?,?,NULL)', (name, description, slots, gtype))
                g.db.commit()
                flash('Game added.', 'success')
            else:
                flash('Invalid game details.', 'danger')

        # Handle Add Credential form
        if request.method == 'POST' and request.form.get('form_type') == 'add_credential':
            cname = request.form.get('cred_name', '').strip()
            cphone = request.form.get('cred_phone', '').strip()
            cpass = request.form.get('cred_password', '').strip()
            if not cname or not cphone or not cpass:
                flash('All credential fields are required.', 'danger')
            else:
                exists = g.db.execute('SELECT 1 FROM allowed_users WHERE phone = ?', (cphone,)).fetchone()
                if exists:
                    flash('Phone already exists in credentials.', 'warning')
                else:
                    g.db.execute('INSERT INTO allowed_users (phone, password, name, is_admin) VALUES (?,?,?,0)', (cphone, cpass, cname))
                    g.db.commit()
                    # Optionally ensure a user row exists for quick usage
                    urow = g.db.execute('SELECT id FROM users WHERE phone = ?', (cphone,)).fetchone()
                    if not urow:
                        g.db.execute('INSERT INTO users (phone, password, name, is_admin) VALUES (?,?,?,0)', (cphone, cpass, cname))
                        g.db.commit()
                    flash('Credential added.', 'success')

        games = g.db.execute('SELECT * FROM games ORDER BY id').fetchall()
        single_participants = g.db.execute(
            'SELECT u.id as user_id, u.name, u.phone, g.name AS game_name FROM users u JOIN games g ON g.id = u.game_id WHERE g.type = "single" ORDER BY g.name, u.name'
        ).fetchall()
        teams = g.db.execute(
            'SELECT t.id, t.game_id, t.name AS team_name, t.team_code, g.name AS game_name, u.name AS leader_name, u.phone AS leader_phone, u.id AS leader_user_id '
            'FROM teams t JOIN games g ON g.id = t.game_id JOIN users u ON u.id = t.leader_user_id ORDER BY g.name, t.name'
        ).fetchall()
        team_members = g.db.execute(
            'SELECT tm.team_id, u.id as user_id, u.name, u.phone FROM team_members tm JOIN users u ON u.id = tm.user_id ORDER BY tm.team_id, u.name'
        ).fetchall()
        # Build a dict team_id -> members
        members_map: Dict[int, List[sqlite3.Row]] = {}
        for tm in team_members:
            members_map.setdefault(tm['team_id'], []).append(tm)

        # Group teams by game for rendering dropdowns per team
        game_to_teams: Dict[int, List[sqlite3.Row]] = {}
        for t in teams:
            game_to_teams.setdefault(t['game_id'], []).append(t)

        # Build per-game participants and counts
        game_participants: Dict[int, List[sqlite3.Row]] = {}
        game_member_counts: Dict[int, int] = {}
        for g_row in games:
            if g_row['type'] == 'single':
                plist = g.db.execute(
                    'SELECT u.id as user_id, u.name, u.phone FROM users u WHERE u.game_id = ? AND (u.team_id IS NULL) ORDER BY u.name',
                    (g_row['id'],),
                ).fetchall()
            else:
                plist = g.db.execute(
                    'SELECT u.id as user_id, u.name, u.phone, t.id as team_id, t.name as team_name, CASE WHEN u.id = t.leader_user_id THEN 1 ELSE 0 END as is_leader FROM users u JOIN teams t ON t.id = u.team_id WHERE t.game_id = ? ORDER BY t.name, is_leader DESC, u.name',
                    (g_row['id'],),
                ).fetchall()
            game_participants[g_row['id']] = plist
            game_member_counts[g_row['id']] = len(plist)

        # Overview stats per game
        overview_stats: List[Dict[str, Any]] = []
        total_games = len(games)
        total_slots = 0
        total_filled = 0
        for g_row in games:
            slots = int(g_row['slots'])
            if g_row['type'] == 'single':
                filled = g.db.execute('SELECT COUNT(1) FROM users WHERE game_id = ? AND (team_id IS NULL)', (g_row['id'],)).fetchone()[0]
            else:
                filled = g.db.execute('SELECT COUNT(1) FROM teams WHERE game_id = ?', (g_row['id'],)).fetchone()[0]
            remaining = max(0, slots - int(filled))
            overview_stats.append({
                'id': g_row['id'],
                'name': g_row['name'],
                'type': g_row['type'],
                'slots': slots,
                'filled': int(filled),
                'remaining': remaining,
            })
            total_slots += slots
            total_filled += int(filled)

        # All participants overview (admin visibility)
        participants_overview = g.db.execute(
            'SELECT u.id AS user_id, u.name, u.phone, u.password, g.name AS game_name, g.type AS game_type, t.name AS team_name, '
            'CASE WHEN t.leader_user_id IS NOT NULL AND u.id = t.leader_user_id THEN 1 ELSE 0 END AS is_leader '
            'FROM users u '
            'JOIN games g ON g.id = u.game_id '
            'LEFT JOIN teams t ON t.id = u.team_id '
            'ORDER BY g.name, team_name, u.name'
        ).fetchall()

        # Allowed users (credentials list)
        allowed_list = g.db.execute('SELECT * FROM allowed_users ORDER BY name').fetchall()

        return render_template(
            'admin.html',
            games=games,
            single_participants=single_participants,
            teams=teams,
            members_map=members_map,
            game_participants=game_participants,
            game_member_counts=game_member_counts,
            overview_stats=overview_stats,
            total_games=total_games,
            total_slots=total_slots,
            total_filled=total_filled,
            participants_overview=participants_overview,
            allowed_list=allowed_list,
            game_to_teams=game_to_teams,
        )

    @app.route('/admin/export')
    def admin_export():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        # Export CSV dynamically
        import csv
        from io import StringIO, BytesIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Type', 'Game', 'Team', 'Participant Name', 'Phone'])

        # Single participants
        for row in g.db.execute(
            'SELECT g.name AS game, u.name, u.phone FROM users u JOIN games g ON g.id = u.game_id WHERE g.type = "single" ORDER BY g.name, u.name'
        ):
            writer.writerow(['single', row['game'], '', row['name'], row['phone']])

        # Team participants
        for t in g.db.execute('SELECT t.id, t.name, g.name AS game FROM teams t JOIN games g ON g.id = t.game_id ORDER BY g.name, t.name'):
            for m in g.db.execute(
            'SELECT u.name, u.phone FROM team_members tm JOIN users u ON u.id = tm.user_id WHERE tm.team_id = ? ORDER BY u.name',
            (t['id'],),
        ):
                writer.writerow(['team', t['game'], t['name'], m['name'], m['phone']])

        mem = BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        filename = f"participants_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(mem, mimetype='text/csv', as_attachment=True, download_name=filename)

    @app.route('/admin/team/create', methods=['POST'])
    def admin_create_team():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        team_name = request.form.get('team_name', '').strip()
        game_id = int(request.form.get('game_id') or 0)
        leader_phone = request.form.get('leader_phone', '').strip()
        members_text = request.form.get('members', '').strip()
        member_phones = [p.strip() for p in members_text.split('\n') if p.strip()]
        # Validate game
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
        if not game or game['type'] != 'team':
            flash('Select a valid team game.', 'danger')
            return redirect(url_for('dashboard'))
        # Enforce team size if configured (including leader)
        if game['team_size'] is not None:
            expected = int(game['team_size'])
            if 1 + len(member_phones) != expected:
                need = expected - 1
                flash(f'This game requires exactly {expected} members per team (leader + {need}).', 'danger')
                return redirect(url_for('dashboard'))
        # Validate leader
        leader = g.db.execute('SELECT * FROM users WHERE phone = ?', (leader_phone,)).fetchone()
        if not leader:
            flash('Leader phone not found. Ensure the user has signed up.', 'danger')
            return redirect(url_for('dashboard'))
        if is_registered_elsewhere(leader):
            flash('Leader is already registered in another game.', 'danger')
            return redirect(url_for('dashboard'))
        # Validate members
        members: List[sqlite3.Row] = []
        for phone in member_phones:
            row = g.db.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
            if not row:
                flash(f'Member with phone {phone} not found. Ask them to sign up first.', 'danger')
                return redirect(url_for('dashboard'))
            if is_registered_elsewhere(row):
                flash(f'Member {row["name"]} is already registered in another game.', 'danger')
                return redirect(url_for('dashboard'))
            members.append(row)
        # Check team slots
        if get_available_slots(game_id) <= 0:
            flash('No team slots available for this game.', 'warning')
            return redirect(url_for('dashboard'))
        # Create team and assign
        cur = g.db.cursor()
        team_code = generate_team_code()
        cur.execute('INSERT INTO teams (name, leader_user_id, game_id, team_code) VALUES (?,?,?,?)', (team_name, leader['id'], game_id, team_code))
        team_id = cur.lastrowid
        # Assign leader
        cur.execute('UPDATE users SET game_id = ?, team_id = ? WHERE id = ?', (game_id, team_id, leader['id']))
        # Add members
        for m in members:
            cur.execute('INSERT INTO team_members (team_id, user_id) VALUES (?,?)', (team_id, m['id']))
            cur.execute('UPDATE users SET game_id = ?, team_id = ? WHERE id = ?', (game_id, team_id, m['id']))
        g.db.commit()
        flash('Team created successfully.', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/admin/single/add', methods=['POST'])
    def admin_add_single():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        game_id = int(request.form.get('single_game_id') or 0)
        phone = request.form.get('single_phone', '').strip()
        # Validate game
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
        if not game or game['type'] != 'single':
            flash('Select a valid single game.', 'danger')
            return redirect(url_for('dashboard'))
        # Validate user
        target = g.db.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
        if not target:
            flash('User phone not found. Ensure the user has signed up.', 'danger')
            return redirect(url_for('dashboard'))
        if is_registered_elsewhere(target):
            flash('User is already registered in another game.', 'danger')
            return redirect(url_for('dashboard'))
        if get_available_slots(game_id) <= 0:
            flash('No slots available for this game.', 'warning')
            return redirect(url_for('dashboard'))
        g.db.execute('UPDATE users SET game_id = ?, team_id = NULL WHERE id = ?', (game_id, target['id']))
        g.db.commit()
        flash('Participant added to the game.', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/admin/team/add-member', methods=['POST'])
    def admin_add_team_member():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        team_code = request.form.get('team_code', '').strip().upper()
        member_phone = request.form.get('member_phone', '').strip()
        
        # Find team by code
        team = g.db.execute('SELECT * FROM teams WHERE team_code = ?', (team_code,)).fetchone()
        if not team:
            flash('Invalid team code.', 'danger')
            return redirect(url_for('admin'))
        
        # Get game info
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (team['game_id'],)).fetchone()
        if not game:
            flash('Game not found.', 'danger')
            return redirect(url_for('admin'))
        
        # Validate member
        member = g.db.execute('SELECT * FROM users WHERE phone = ?', (member_phone,)).fetchone()
        if not member:
            flash('User phone not found. Ensure the user has signed up.', 'danger')
            return redirect(url_for('admin'))
        
        if is_registered_elsewhere(member):
            flash('User is already registered in another game.', 'danger')
            return redirect(url_for('admin'))
        
        # Check if team is full (if team size is configured)
        if game['team_size'] is not None:
            current_members = g.db.execute('SELECT COUNT(1) FROM team_members WHERE team_id = ?', (team['id'],)).fetchone()[0]
            leader_count = 1  # Leader is always counted
            if current_members + leader_count >= int(game['team_size']):
                flash('This team is full.', 'warning')
                return redirect(url_for('admin'))
        
        # Add member to team
        cur = g.db.cursor()
        cur.execute('INSERT INTO team_members (team_id, user_id) VALUES (?,?)', (team['id'], member['id']))
        cur.execute('UPDATE users SET game_id = ?, team_id = ? WHERE id = ?', (team['game_id'], team['id'], member['id']))
        g.db.commit()
        flash(f'Successfully added {member["name"]} to team "{team["name"]}".', 'success')
        return redirect(url_for('admin'))

    @app.route('/admin/user/remove/<int:user_id>', methods=['POST'])
    def admin_remove_user(user_id: int):
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
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
        flash('Participant removed.', 'success')
        return redirect(url_for('admin'))
        
    @app.route('/admin/api-complete-remove-user/<int:user_id>', methods=['GET', 'POST'])
    def api_complete_remove_user(user_id: int):
        """Local version of the complete user removal API endpoint"""
        user = fetch_current_user()
        if not user or not user['is_admin']:
            return {"error": "Admin access required"}, 401
            
        try:
            # First get the user to get their phone
            user_to_remove = g.db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if not user_to_remove:
                return {"error": "User not found"}, 404
                
            phone = user_to_remove['phone']
            
            # If user is leader of a team, delete team and unassign all members
            team = g.db.execute('SELECT * FROM teams WHERE leader_user_id = ?', (user_id,)).fetchone()
            if team:
                member_ids = [r['user_id'] for r in g.db.execute('SELECT user_id FROM team_members WHERE team_id = ?', (team['id'],)).fetchall()]
                for mid in member_ids:
                    g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (mid,))
                g.db.execute('DELETE FROM team_members WHERE team_id = ?', (team['id'],))
                g.db.execute('DELETE FROM teams WHERE id = ?', (team['id'],))
            
            # Delete from team_members if they're a member
            g.db.execute('DELETE FROM team_members WHERE user_id = ?', (user_id,))
            
            # Now delete from users and allowed_users tables
            g.db.execute('DELETE FROM users WHERE id = ?', (user_id,))
            g.db.execute('DELETE FROM allowed_users WHERE phone = ?', (phone,))
            
            g.db.commit()
            return {"success": True}
        except Exception as e:
            import traceback
            return {"error": str(e), "details": traceback.format_exc()}, 500

    @app.route('/admin/team/delete/<int:team_id>', methods=['POST'])
    def admin_delete_team(team_id: int):
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        leader = g.db.execute('SELECT leader_user_id FROM teams WHERE id = ?', (team_id,)).fetchone()
        if leader:
            g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (leader['leader_user_id'],))
        for row in g.db.execute('SELECT user_id FROM team_members WHERE team_id = ?', (team_id,)).fetchall():
            g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE id = ?', (row['user_id'],))
        g.db.execute('DELETE FROM team_members WHERE team_id = ?', (team_id,))
        g.db.execute('DELETE FROM teams WHERE id = ?', (team_id,))
        g.db.commit()
        flash('Team deleted.', 'success')
        return redirect(url_for('admin'))

    @app.route('/admin/game/delete/<int:game_id>', methods=['POST'])
    def admin_delete_game(game_id: int):
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL WHERE game_id = ?', (game_id,))
        team_ids = [r['id'] for r in g.db.execute('SELECT id FROM teams WHERE game_id = ?', (game_id,)).fetchall()]
        for tid in team_ids:
            g.db.execute('DELETE FROM team_members WHERE team_id = ?', (tid,))
        g.db.execute('DELETE FROM teams WHERE game_id = ?', (game_id,))
        g.db.execute('DELETE FROM games WHERE id = ?', (game_id,))
        g.db.commit()
        flash('Game deleted.', 'success')
        return redirect(url_for('admin'))

    # Disable public signup; keep route for compatibility
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        flash('Signup is disabled. Please use credentials provided by admin.', 'info')
        return redirect(url_for('login'))


app = create_app()

if __name__ == '__main__':
    # Local dev run: python app.py
    app.run(host='0.0.0.0', port=5000, debug=True)


