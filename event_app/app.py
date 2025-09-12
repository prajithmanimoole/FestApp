import os
import sqlite3
import random
import string
import sys
import zipfile
import tempfile
import logging
from contextlib import closing
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urlparse

from flask import Flask, g, render_template, request, redirect, url_for, session, flash, send_file
import secrets
from io import BytesIO

# Set up logging for database operations
logging.basicConfig(level=logging.INFO)
db_logger = logging.getLogger('database_operations')

def log_database_operation(operation: str, table: str, details: str = ""):
    """Log database operations for debugging"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db_logger.info(f"[{timestamp}] {operation} on {table}: {details}")

def safe_db_execute(query: str, params: tuple = (), operation_desc: str = ""):
    """Execute database query with error handling and logging"""
    try:
        log_database_operation("EXECUTE", "query", f"{operation_desc}: {query[:50]}...")
        result = g.db.execute(query, params)
        return result
    except Exception as e:
        log_database_operation("ERROR", "query", f"{operation_desc} failed: {str(e)}")
        raise

# Local import for certificate generation
try:
    # When imported as a module
    from .certificate_html_generator import generate_certificate_pdf, generate_html_certificate, generate_dual_certificates
except (ImportError, ValueError):
    # When run directly
    try:
        from certificate_html_generator import generate_certificate_pdf, generate_html_certificate, generate_dual_certificates
    except ImportError:
        # If the certificate generator isn't available, provide a stub function
        def generate_certificate_pdf(student_name, event_name, event_date, class_section=None):
            buffer = BytesIO()
            buffer.write(b"Certificate generation failed - Required libraries not installed")
            buffer.seek(0)
            return buffer
        
        def generate_html_certificate(student_name, event_name, event_date, class_section=None):
            return "<html><body><h1>Certificate generation failed - Required libraries not installed</h1></body></html>"
        
        def generate_dual_certificates(student_name, event_name, event_date, class_section=None):
            buffer = BytesIO()
            buffer.write(b"Certificate generation failed - Required libraries not installed")
            buffer.seek(0)
            return buffer

# Check if running on Railway (DATABASE_URL environment variable will be set)
DATABASE_URL = os.environ.get('DATABASE_URL')
# Local/default database path for SQLite
DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'database.db'))

# Flag to determine if we're using PostgreSQL
USING_POSTGRES = DATABASE_URL is not None and DATABASE_URL.startswith('postgres')

# Helper function to get the appropriate placeholder for SQL queries
def get_placeholder():
    return '%s' if USING_POSTGRES else '?'


def get_db():
    """Connect to the database and return a connection object with row factory"""
    if USING_POSTGRES:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Parse DATABASE_URL to get connection parameters
        url = urlparse(DATABASE_URL)
        dbname = url.path[1:]
        user = url.username
        password = url.password
        host = url.hostname
        port = url.port
        
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
            cursor_factory=RealDictCursor
        )
        # Don't use autocommit mode to ensure transaction safety
        # conn.autocommit = True  # Removed - causes data loss issues
        return conn
    else:
        # SQLite connection
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


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
            if USING_POSTGRES:
                with g.db.cursor() as cursor:
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'allowed_users'")
                    exists = cursor.fetchone()
            else:
                exists = g.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='allowed_users'").fetchone()
            
            if not exists:
                ensure_schema_and_seed()
            else:
                # Run integrity check periodically (every 100th request roughly)
                import random
                if random.randint(1, 100) == 1:
                    check_database_integrity()
                    
        except Exception as e:
            print(f"Database setup error: {e}", file=sys.stderr)
            ensure_schema_and_seed()

    @app.teardown_request
    def teardown_request(exception: Optional[BaseException]) -> None:  # noqa: ARG001
        db = g.pop('db', None)
        if db is not None:
            try:
                # If there was an exception, rollback any pending transactions
                if exception is not None and hasattr(db, 'rollback'):
                    db.rollback()
                # For successful requests, ensure commit is called
                elif hasattr(db, 'commit'):
                    db.commit()
            except Exception as e:
                print(f"Database teardown error: {e}", file=sys.stderr)
                if hasattr(db, 'rollback'):
                    try:
                        db.rollback()
                    except:
                        pass
            finally:
                db.close()

    ensure_schema_and_seed()

    register_routes(app)
    return app


def ensure_schema_and_seed() -> None:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    with closing(get_db()) as db:
        if USING_POSTGRES:
            with db.cursor() as cur:
                # Users
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        phone TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        name TEXT NOT NULL,
                        class_section TEXT,
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
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        slots INTEGER NOT NULL,
                        type TEXT NOT NULL CHECK(type IN ('single','team')),
                        team_size INTEGER
                    )
                    """
                )
                # Teams
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS teams (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        game_id INTEGER NOT NULL,
                        leader_user_id INTEGER,
                        team_code TEXT UNIQUE NOT NULL
                    )
                    """
                )
                # Team Members (linking table)
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS team_members (
                        id SERIAL PRIMARY KEY,
                        team_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        UNIQUE(team_id, user_id)
                    )
                    """
                )
                # Allowed Users (login whitelist)
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS allowed_users (
                        id SERIAL PRIMARY KEY,
                        phone TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        name TEXT NOT NULL,
                        class_section TEXT
                    )
                    """
                )
                # Phone Whitelist
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS whitelist_phones (
                        id SERIAL PRIMARY KEY,
                        phone TEXT UNIQUE NOT NULL
                    )
                    """
                )
                
                # Certificate settings
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS certificate_settings (
                        id SERIAL PRIMARY KEY,
                        certificates_enabled INTEGER NOT NULL DEFAULT 0,
                        event_date TEXT
                    )
                    """
                )
                
                # Certificate downloads tracking
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS certificate_downloads (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        download_date TEXT NOT NULL,
                        UNIQUE(user_id)
                    )
                    """
                )
                db.commit()
        else:
            cur = db.cursor()
            # Users
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    name TEXT NOT NULL,
                    class_section TEXT,
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
        # Whitelist phones (admin-preloaded allowed phone numbers)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS whitelist_phones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL
            )
            """
        )
        
        # Certificate settings
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS certificate_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                certificates_enabled INTEGER NOT NULL DEFAULT 0,
                event_date TEXT
            )
            """
        )
        
        # Certificate downloads tracking
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS certificate_downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                download_date TEXT NOT NULL,
                UNIQUE(user_id)
            )
            """
        )
        db.commit()

        # Seed minimal data if empty: only admin user, no games
        user_count = cur.execute('SELECT COUNT(1) FROM users').fetchone()[0]
        if user_count == 0:
            cur.execute(
                'INSERT INTO users (phone, password, name, class_section, is_admin) VALUES (?,?,?,?,?)',
                ('9990001111', 'admin123', 'Admin User', 'ADMIN', 1),
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
                log_database_operation("INSERT", "allowed_users", f"Migrating user {row[0]}")
                cur.execute(
                    'INSERT INTO allowed_users (phone, password, name, is_admin) VALUES (?,?,?,?)',
                    (row[0], row[1], row[2], row[3]),
                )
        
        # Add integrity check - ensure we don't lose the admin user
        admin_in_users = cur.execute('SELECT 1 FROM users WHERE phone = ?', ('9990001111',)).fetchone()
        admin_in_allowed = cur.execute('SELECT 1 FROM allowed_users WHERE phone = ?', ('9990001111',)).fetchone()
        
        if not admin_in_users or not admin_in_allowed:
            log_database_operation("RECOVERY", "users", "Re-adding missing admin user")
            if not admin_in_users:
                cur.execute(
                    'INSERT OR REPLACE INTO users (phone, password, name, class_section, is_admin) VALUES (?,?,?,?,?)',
                    ('9990001111', 'admin123', 'Admin User', 'ADMIN', 1),
                )
            if not admin_in_allowed:
                cur.execute(
                    'INSERT OR REPLACE INTO allowed_users (phone, password, name, is_admin) VALUES (?,?,?,1)',
                    ('9990001111', 'admin123', 'Admin User'),
                )
        
        db.commit()

        # Add class_section column to users if missing (migration for existing DBs)
        try:
            cols = [r[1] for r in cur.execute('PRAGMA table_info(users)').fetchall()]
            if 'class_section' not in cols:
                cur.execute('ALTER TABLE users ADD COLUMN class_section TEXT')
                db.commit()
        except Exception:
            pass


def check_database_integrity():
    """Perform database integrity checks and repair if needed"""
    try:
        with closing(get_db()) as db:
            cur = db.cursor()
            
            # Check 1: Ensure admin user exists
            admin_count = cur.execute('SELECT COUNT(*) FROM users WHERE phone = ? AND is_admin = 1', ('9990001111',)).fetchone()[0]
            if admin_count == 0:
                log_database_operation("REPAIR", "users", "Adding missing admin user")
                cur.execute(
                    'INSERT INTO users (phone, password, name, class_section, is_admin) VALUES (?,?,?,?,?)',
                    ('9990001111', 'admin123', 'Admin User', 'ADMIN', 1),
                )
            
            # Check 2: Ensure admin exists in allowed_users
            allowed_admin = cur.execute('SELECT 1 FROM allowed_users WHERE phone = ?', ('9990001111',)).fetchone()
            if not allowed_admin:
                log_database_operation("REPAIR", "allowed_users", "Adding missing admin to allowed_users")
                cur.execute(
                    'INSERT INTO allowed_users (phone, password, name, is_admin) VALUES (?,?,?,1)',
                    ('9990001111', 'admin123', 'Admin User'),
                )
            
            # Check 3: Sync users and allowed_users tables
            users_without_allowed = cur.execute('''
                SELECT u.phone, u.password, u.name, u.is_admin 
                FROM users u 
                LEFT JOIN allowed_users a ON u.phone = a.phone 
                WHERE a.phone IS NULL
            ''').fetchall()
            
            for user in users_without_allowed:
                log_database_operation("REPAIR", "allowed_users", f"Syncing missing user {user[0]}")
                cur.execute(
                    'INSERT INTO allowed_users (phone, password, name, is_admin) VALUES (?,?,?,?)',
                    (user[0], user[1], user[2], user[3]),
                )
            
            # Check 4: Remove orphaned data
            orphaned_team_members = cur.execute('''
                SELECT tm.id FROM team_members tm 
                LEFT JOIN users u ON tm.user_id = u.id 
                WHERE u.id IS NULL
            ''').fetchall()
            
            if orphaned_team_members:
                log_database_operation("CLEANUP", "team_members", f"Removing {len(orphaned_team_members)} orphaned team members")
                for orphan in orphaned_team_members:
                    cur.execute('DELETE FROM team_members WHERE id = ?', (orphan[0],))
            
            db.commit()
            log_database_operation("SUCCESS", "integrity_check", "Database integrity check completed")
            return True
            
    except Exception as e:
        log_database_operation("ERROR", "integrity_check", f"Integrity check failed: {str(e)}")
        return False


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
            # First, check against users table
            user_row = g.db.execute('SELECT * FROM users WHERE phone = ? AND password = ?', (phone, password)).fetchone()
            if user_row:
                session['user_id'] = user_row['id']
                flash('Signed in successfully.', 'success')
                return redirect(url_for('dashboard'))
            # Backwards compatibility: allow login using allowed_users to auto-create user
            allowed = g.db.execute('SELECT * FROM allowed_users WHERE phone = ? AND password = ?', (phone, password)).fetchone()
            if allowed:
                cur = g.db.cursor()
                cur.execute(
                    'INSERT OR IGNORE INTO users (phone, password, name, class_section, is_admin) VALUES (?,?,?,?,?)',
                    (allowed['phone'], allowed['password'], allowed['name'], None, allowed['is_admin'])
                )
                g.db.commit()
                user_row = g.db.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
                if user_row:
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

    @app.route('/opponents')
    def opponents():
        user = fetch_current_user()
        if not user:
            return redirect(url_for('login'))
        if not user['game_id']:
            flash('Join an event first to see opponents.', 'warning')
            return redirect(url_for('dashboard'))

        # Use the appropriate placeholder based on database type
        placeholder = '%s' if USING_POSTGRES else '?'
        
        game = g.db.execute(f'SELECT * FROM games WHERE id = {placeholder}', (user['game_id'],)).fetchone()
        if not game:
            flash('Game not found.', 'danger')
            return redirect(url_for('dashboard'))

        if game['type'] == 'single':
            opponents_list = g.db.execute(
                f'SELECT u.* FROM users u WHERE u.game_id = {placeholder} AND (u.team_id IS NULL) AND u.id != {placeholder} ORDER BY u.name',
                (user['game_id'], user['id']),
            ).fetchall()
            return render_template('opponents.html', game=game, view_type='single', opponents=opponents_list)

        # Team game: list other teams and their members
        placeholder = '%s' if USING_POSTGRES else '?'
        
        my_team = g.db.execute(f'SELECT * FROM teams WHERE id = {placeholder}', (user['team_id'],)).fetchone()
        if not my_team:
            flash('Your team was not found.', 'danger')
            return redirect(url_for('dashboard'))

        other_teams = g.db.execute(
            f'SELECT t.*, u.name AS leader_name, u.phone AS leader_phone '
            f'FROM teams t JOIN users u ON u.id = t.leader_user_id '
            f'WHERE t.game_id = {placeholder} AND t.id != {placeholder} ORDER BY t.name',
            (my_team['game_id'], my_team['id']),
        ).fetchall()

        # Build members map for all other teams
        team_ids = [t['id'] for t in other_teams]
        members_map: Dict[int, List[sqlite3.Row]] = {}
        
        # Use a more compatible approach that works with both SQLite and PostgreSQL
        placeholder = '%s' if USING_POSTGRES else '?'
        
        for team_id in team_ids:
            rows = g.db.execute(
                f'SELECT tm.team_id, u.* FROM team_members tm JOIN users u ON u.id = tm.user_id '
                f'WHERE tm.team_id = {placeholder} ORDER BY u.name',
                (team_id,)
            ).fetchall()
            for r in rows:
                members_map.setdefault(r['team_id'], []).append(r)

        return render_template(
            'opponents.html',
            game=game,
            view_type='team',
            my_team=my_team,
            teams=other_teams,
            members_map=members_map,
        )

    @app.route('/admin', methods=['GET', 'POST'])
    def admin():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        # Determine which tab should be active
        active_tab = request.args.get('tab') or 'overview'

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
                active_tab = 'addgame'
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
                # stay on overview (credentials accordion)
                active_tab = 'overview'

        # Handle Whitelist add (single)
        if request.method == 'POST' and request.form.get('form_type') == 'add_whitelist':
            wphone = request.form.get('wl_phone', '').strip()
            if not wphone:
                flash('Phone is required for whitelist.', 'danger')
            else:
                try:
                    g.db.execute('INSERT INTO whitelist_phones (phone) VALUES (?)', (wphone,))
                    g.db.commit()
                    flash('Phone added to whitelist.', 'success')
                except Exception:
                    flash('Phone already exists in whitelist.', 'warning')
            active_tab = 'whitelist'

        # Handle Whitelist bulk add (textarea with newline-separated phones)
        if request.method == 'POST' and request.form.get('form_type') == 'bulk_whitelist':
            phones_text = request.form.get('wl_phones', '').strip()
            if not phones_text:
                flash('Provide one or more phone numbers.', 'danger')
            else:
                phones = [p.strip() for p in phones_text.split('\n') if p.strip()]
                inserted = 0
                for p in phones:
                    try:
                        g.db.execute('INSERT INTO whitelist_phones (phone) VALUES (?)', (p,))
                        inserted += 1
                    except Exception:
                        pass
                g.db.commit()
                flash(f'Whitelist updated. Added {inserted} new phone(s).', 'success')
            active_tab = 'whitelist'

        # Handle Whitelist remove
        if request.method == 'POST' and request.form.get('form_type') == 'remove_whitelist':
            rphone = request.form.get('wl_phone_remove', '').strip()
            if not rphone:
                flash('Phone is required.', 'danger')
            else:
                try:
                    # Check if phone exists before deleting
                    exists = g.db.execute('SELECT 1 FROM whitelist_phones WHERE phone = ?', (rphone,)).fetchone()
                    if exists:
                        g.db.execute('DELETE FROM whitelist_phones WHERE phone = ?', (rphone,))
                        g.db.commit()
                        flash(f'Phone {rphone} removed from whitelist.', 'info')
                    else:
                        flash(f'Phone {rphone} was not found in whitelist.', 'warning')
                except Exception as e:
                    g.db.rollback() if hasattr(g.db, 'rollback') else None
                    print(f"Error removing phone from whitelist: {e}", file=sys.stderr)
                    flash('Error removing phone from whitelist. Please try again.', 'danger')
            active_tab = 'whitelist'

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
        # This query needs to handle users who are not in any game yet
        participants_overview = g.db.execute(
            """
            SELECT 
                u.id AS user_id, 
                u.name, 
                u.phone, 
                u.password, 
                g.name AS game_name, 
                g.type AS game_type, 
                t.name AS team_name,
                CASE 
                    WHEN t.leader_user_id IS NOT NULL AND u.id = t.leader_user_id THEN 1 
                    ELSE 0 
                END AS is_leader
            FROM users u
            LEFT JOIN games g ON g.id = u.game_id
            LEFT JOIN teams t ON t.id = u.team_id
            ORDER BY u.name
            """
        ).fetchall()

        # Allowed users (credentials list)
        allowed_list = g.db.execute('SELECT * FROM allowed_users ORDER BY name').fetchall()
        whitelist_list = g.db.execute('SELECT * FROM whitelist_phones ORDER BY phone').fetchall()

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
            whitelist_list=whitelist_list,
            game_to_teams=game_to_teams,
            active_tab=active_tab,
            cert_settings=g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone(),
            certificate_downloads=g.db.execute('''
                SELECT cd.download_date, u.name, u.phone, u.class_section, g.name as game_name
                FROM certificate_downloads cd
                JOIN users u ON u.id = cd.user_id
                LEFT JOIN games g ON g.id = u.game_id
                ORDER BY cd.download_date DESC
                LIMIT 50
            ''').fetchall(),
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

    @app.route('/admin/export/<int:game_id>')
    def admin_export_game(game_id: int):
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        # Get game
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
        if not game:
            flash('Game not found.', 'danger')
            return redirect(url_for('admin', tab='gamesctl'))

        import csv
        from io import StringIO, BytesIO

        output = StringIO()
        writer = csv.writer(output)

        if game['type'] == 'single':
            writer.writerow(['Game', 'Participant Name', 'Phone', 'Class/Section'])
            rows = g.db.execute(
                'SELECT u.name, u.phone, u.class_section FROM users u WHERE u.game_id = ? AND (u.team_id IS NULL) ORDER BY u.name',
                (game_id,),
            ).fetchall()
            for r in rows:
                writer.writerow([game['name'], r['name'], r['phone'], r['class_section'] or ''])
        else:
            writer.writerow(['Game', 'Team', 'Team Code', 'Role', 'Name', 'Phone', 'Class/Section'])
            # Leader rows
            for t in g.db.execute(
                'SELECT t.id, t.name AS team_name, t.team_code, u.name AS leader_name, u.phone AS leader_phone, u.class_section AS leader_class_section '
                'FROM teams t JOIN users u ON u.id = t.leader_user_id WHERE t.game_id = ? ORDER BY t.name',
                (game_id,),
            ):
                writer.writerow([game['name'], t['team_name'], t['team_code'], 'Leader', t['leader_name'], t['leader_phone'], t['leader_class_section'] or ''])
                # Member rows
                for m in g.db.execute(
                    'SELECT u.name, u.phone, u.class_section FROM team_members tm JOIN users u ON u.id = tm.user_id WHERE tm.team_id = ? ORDER BY u.name',
                    (t['id'],),
                ):
                    writer.writerow([game['name'], t['team_name'], t['team_code'], 'Member', m['name'], m['phone'], m['class_section'] or ''])

        mem = BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        safe_name = str(game['name']).replace(' ', '_')
        filename = f"{safe_name}_participants_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
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
        # Enforce upper-bound team size if configured (including leader)
        if game['team_size'] is not None:
            expected = int(game['team_size'])
            if 1 + len(member_phones) > expected:
                max_additional = expected - 1
                flash(f'This game allows at most {expected} members per team (leader + up to {max_additional}).', 'danger')
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
        
        if USING_POSTGRES:
            cur.execute('INSERT INTO teams (name, leader_user_id, game_id, team_code) VALUES (%s,%s,%s,%s) RETURNING id', 
                      (team_name, leader['id'], game_id, team_code))
            team_id = cur.fetchone()['id']
        else:
            cur.execute('INSERT INTO teams (name, leader_user_id, game_id, team_code) VALUES (?,?,?,?)', 
                      (team_name, leader['id'], game_id, team_code))
            team_id = cur.lastrowid
        # Assign leader
        cur.execute('UPDATE users SET game_id = ?, team_id = ? WHERE id = ?', (game_id, team_id, leader['id']))
        # Add members
        for m in members:
            cur.execute('INSERT INTO team_members (team_id, user_id) VALUES (?,?)', (team_id, m['id']))
            cur.execute('UPDATE users SET game_id = ?, team_id = ? WHERE id = ?', (game_id, team_id, m['id']))
        g.db.commit()
        flash(f'Team created successfully. Team Code: {team_code}', 'success')
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
        return redirect(url_for('admin', tab='addmember'))

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
        # Preserve tab if provided (e.g., gamesctl)
        tab = request.args.get('tab') or 'overview'
        return redirect(url_for('admin', tab=tab))

    @app.route('/api/remove-user/<int:user_id>', methods=['POST'])
    def api_remove_user(user_id: int):
        user = fetch_current_user()
        if not user or not user['is_admin']:
            return {"error": "Admin access required"}, 401
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
            g.db.rollback()
            return {"error": str(e)}, 500
        
    @app.route('/admin/api-complete-remove-user/<int:user_id>', methods=['GET', 'POST'])
    @app.route('/api/complete-remove-user/<int:user_id>', methods=['POST'])
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
            try:
                g.db.execute('DELETE FROM team_members WHERE user_id = ?', (user_id,))
                
                # Now delete from users and allowed_users tables
                # Verify user exists before deletion
                user_exists = g.db.execute('SELECT phone FROM users WHERE id = ?', (user_id,)).fetchone()
                if user_exists:
                    phone = user_exists['phone']
                    g.db.execute('DELETE FROM users WHERE id = ?', (user_id,))
                    # Only delete from allowed_users if it exists
                    allowed_exists = g.db.execute('SELECT 1 FROM allowed_users WHERE phone = ?', (phone,)).fetchone()
                    if allowed_exists:
                        g.db.execute('DELETE FROM allowed_users WHERE phone = ?', (phone,))
                    
                    g.db.commit()
                    return {"success": True, "message": f"User {phone} deleted successfully"}
                else:
                    return {"error": "User not found"}, 404
                    
            except Exception as deletion_error:
                g.db.rollback() if hasattr(g.db, 'rollback') else None
                print(f"Error during user deletion: {deletion_error}", file=sys.stderr)
                return {"error": f"Database error during deletion: {str(deletion_error)}"}, 500
        except Exception as e:
            import traceback
            return {"error": str(e), "details": traceback.format_exc()}, 500

    @app.route('/admin/user/edit/<int:user_id>', methods=['POST'])
    def admin_edit_user(user_id: int):
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        name = request.form.get('edit_name', '').strip()
        phone = request.form.get('edit_phone', '').strip()
        password = request.form.get('edit_password', '').strip()
        class_section = request.form.get('edit_class_section', '').strip() or None
        original_phone = request.form.get('original_phone', '').strip()
        if not name or not phone or not password:
            flash('Name, phone and password are required.', 'danger')
            return redirect(url_for('admin'))
        try:
            # Ensure phone uniqueness if changed
            exists = g.db.execute('SELECT id FROM users WHERE phone = ? AND id != ?', (phone, user_id)).fetchone()
            if exists:
                flash('Another user already has this phone number.', 'danger')
                return redirect(url_for('admin'))
            g.db.execute('UPDATE users SET name = ?, phone = ?, password = ?, class_section = ? WHERE id = ?', (name, phone, password, class_section, user_id))
            # Sync allowed_users. If there is a row for original_phone, update it; else upsert by new phone
            row = g.db.execute('SELECT id FROM allowed_users WHERE phone = ?', (original_phone or phone,)).fetchone()
            if row:
                g.db.execute('UPDATE allowed_users SET name = ?, phone = ?, password = ? WHERE id = ?', (name, phone, password, row['id']))
            else:
                # insert if not exists for new phone
                exists_new = g.db.execute('SELECT id FROM allowed_users WHERE phone = ?', (phone,)).fetchone()
                if not exists_new:
                    g.db.execute('INSERT INTO allowed_users (name, phone, password, is_admin) VALUES (?,?,?,0)', (name, phone, password))
            g.db.commit()
            flash('User updated.', 'success')
        except Exception as e:
            g.db.rollback()
            flash(f'Failed to update user: {e}', 'danger')
        return redirect(url_for('admin'))

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
        tab = request.args.get('tab') or 'gamesctl'
        return redirect(url_for('admin', tab=tab))

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
        tab = request.args.get('tab') or 'gamesctl'
        return redirect(url_for('admin', tab=tab))

    @app.route('/admin/remove-participants', methods=['POST'])
    def admin_remove_participants():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        try:
            # Remove team memberships and teams
            g.db.execute('DELETE FROM team_members')
            g.db.execute('DELETE FROM teams')
            # Delete all non-admin users
            g.db.execute('DELETE FROM users WHERE is_admin = 0')
            g.db.commit()
            flash('All participants removed. Admin accounts preserved. Games/whitelist unchanged.', 'success')
        except Exception as e:
            g.db.rollback()
            flash(f'Failed to remove participants: {e}', 'danger')
        return redirect(url_for('admin'))

    @app.route('/admin/clear-all', methods=['POST'])
    def admin_clear_all():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        try:
            # Remove all team memberships and teams
            g.db.execute('DELETE FROM team_members')
            g.db.execute('DELETE FROM teams')
            # Unassign any remaining users from games/teams just in case
            g.db.execute('UPDATE users SET game_id = NULL, team_id = NULL')
            # Remove all games
            g.db.execute('DELETE FROM games')
            # Remove all non-admin users
            g.db.execute('DELETE FROM users WHERE is_admin = 0')
            # Keep only admin rows in allowed_users
            g.db.execute('DELETE FROM allowed_users WHERE is_admin = 0')
            # Clear whitelist entirely
            g.db.execute('DELETE FROM whitelist_phones')
            g.db.commit()
            flash('All data cleared except admin accounts.', 'success')
        except Exception as e:
            g.db.rollback()
            flash(f'Failed to clear data: {e}', 'danger')
        return redirect(url_for('admin'))

    @app.route('/admin/participants')
    def admin_participants_list():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))

        games = g.db.execute('SELECT * FROM games ORDER BY name').fetchall()
        per_game: Dict[int, Dict[str, Any]] = {}
        for gr in games:
            entry: Dict[str, Any] = {'game': gr}
            if gr['type'] == 'single':
                participants = g.db.execute(
                    'SELECT u.name, u.phone, u.class_section FROM users u WHERE u.game_id = ? AND (u.team_id IS NULL) ORDER BY u.name',
                    (gr['id'],),
                ).fetchall()
                entry['participants'] = participants
            else:
                teams = g.db.execute(
                    'SELECT t.id, t.name, t.team_code, u.name AS leader_name, u.phone AS leader_phone, u.class_section AS leader_class_section '
                    'FROM teams t JOIN users u ON u.id = t.leader_user_id WHERE t.game_id = ? ORDER BY t.name',
                    (gr['id'],),
                ).fetchall()
                # members per team
                team_ids = [t['id'] for t in teams]
                members_map: Dict[int, List[sqlite3.Row]] = {}
                if team_ids:
                    # Use a more compatible approach for both SQLite and PostgreSQL
                    placeholder = '%s' if USING_POSTGRES else '?'
                    
                    for team_id in team_ids:
                        rows = g.db.execute(
                            f'SELECT tm.team_id, u.name, u.phone, u.class_section FROM team_members tm JOIN users u ON u.id = tm.user_id '
                            f'WHERE tm.team_id = {placeholder} ORDER BY u.name',
                            (team_id,)
                        ).fetchall()
                        for r in rows:
                            members_map.setdefault(r['team_id'], []).append(r)
                entry['teams'] = teams
                entry['members_map'] = members_map
            per_game[gr['id']] = entry

        return render_template('participants_print.html', games=games, per_game=per_game)

    @app.route('/admin/export-pdf')
    def admin_export_pdf():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))

        try:
            # Lazy import to avoid requirement when unused
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib import colors
        except Exception:
            flash('PDF generation library not installed. Please install reportlab.', 'danger')
            return redirect(url_for('admin'))

        games = g.db.execute('SELECT * FROM games ORDER BY name').fetchall()

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=16*mm, bottomMargin=16*mm)
        styles = getSampleStyleSheet()
        elements: List[Any] = []

        title_style = styles['Title']
        subtitle_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], spaceAfter=6)
        table_header_bg = colors.Color(0.92, 0.92, 0.92)

        elements.append(Paragraph('Participants List (by Game)', title_style))
        elements.append(Spacer(1, 6))
        generated_on = datetime.now().strftime('%Y-%m-%d %H:%M')
        elements.append(Paragraph(f'Generated on: {generated_on}', styles['Normal']))
        elements.append(Spacer(1, 12))

        for idx_game, gr in enumerate(games):
            # Game header
            subtitle = f"{gr['name']}  —  {gr['type'].upper()}"
            elements.append(Paragraph(subtitle, subtitle_style))

            if gr['type'] == 'single':
                rows = [["#", "Name", "Phone", "Class/Section"]]
                participants = g.db.execute(
                    'SELECT u.name, u.phone, u.class_section FROM users u WHERE u.game_id = ? AND (u.team_id IS NULL) ORDER BY u.name',
                    (gr['id'],),
                ).fetchall()
                for idx, p in enumerate(participants, start=1):
                    rows.append([str(idx), p['name'], p['phone'], p['class_section'] or '-'])
                if len(rows) == 1:
                    rows.append(['-', 'No participants', '', ''])
                table = Table(rows, repeatRows=1, colWidths=[12*mm, None, 32*mm, 32*mm])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), table_header_bg),
                    ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                    ('ALIGN', (0,0), (0,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 10))
            else:
                # Team game
                teams = g.db.execute(
                    'SELECT t.id, t.name, t.team_code, u.name AS leader_name, u.phone AS leader_phone, u.class_section AS leader_class_section '
                    'FROM teams t JOIN users u ON u.id = t.leader_user_id WHERE t.game_id = ? ORDER BY t.name',
                    (gr['id'],),
                ).fetchall()
                if not teams:
                    rows = [["-", "No teams", "", "", ""]]
                    table = Table(rows, colWidths=[12*mm, None, 28*mm, 28*mm, 28*mm])
                    elements.append(table)
                    elements.append(Spacer(1, 8))
                else:
                    # Render each team with its own members table for clarity
                    for t_idx, t in enumerate(teams, start=1):
                        header = f"{t_idx}. Team: {t['name']}  (Code: {t['team_code']})"
                        elements.append(Paragraph(header, styles['Heading3']))

                        leader_rows = [["Leader", t['leader_name'], t['leader_phone'], t['leader_class_section'] or '-']]
                        leader_table = Table(leader_rows, colWidths=[20*mm, None, 32*mm, 32*mm])
                        leader_table.setStyle(TableStyle([
                            ('BACKGROUND', (0,0), (0,0), table_header_bg),
                            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                            ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold'),
                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ]))
                        elements.append(leader_table)

                        member_header = [["#", "Member Name", "Phone", "Class/Section"]]
                        members = g.db.execute(
                            'SELECT u.name, u.phone, u.class_section FROM team_members tm JOIN users u ON u.id = tm.user_id WHERE tm.team_id = ? ORDER BY u.name',
                            (t['id'],),
                        ).fetchall()
                        member_rows = list(member_header)
                        for midx, m in enumerate(members, start=1):
                            member_rows.append([str(midx), m['name'], m['phone'], m['class_section'] or '-'])
                        if len(member_rows) == 1:
                            member_rows.append(['-', 'No members yet', '', ''])
                        member_table = Table(member_rows, repeatRows=1, colWidths=[12*mm, None, 32*mm, 32*mm])
                        member_table.setStyle(TableStyle([
                            ('BACKGROUND', (0,0), (-1,0), table_header_bg),
                            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                            ('ALIGN', (0,0), (0,-1), 'CENTER'),
                            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ]))
                        elements.append(member_table)
                        elements.append(Spacer(1, 8))

            # Page break between games for cleaner print, except after the last
            if idx_game < len(games) - 1:
                elements.append(PageBreak())

        doc.build(elements)
        buf.seek(0)
        filename = f"participants_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)

    @app.route('/admin/export-pdf/<int:game_id>')
    def admin_export_game_pdf(game_id: int):
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
        except Exception:
            flash('PDF generation library not installed. Please install reportlab.', 'danger')
            return redirect(url_for('admin'))

        game = g.db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
        if not game:
            flash('Game not found.', 'danger')
            return redirect(url_for('admin', tab='gamesctl'))

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=16*mm, bottomMargin=16*mm)
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        subtitle_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], spaceAfter=6)
        table_header_bg = colors.Color(0.92, 0.92, 0.92)

        elements: List[Any] = []
        elements.append(Paragraph('Participants List (Single Game)', title_style))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"Game: {game['name']} ({game['type'].upper()})", subtitle_style))
        elements.append(Spacer(1, 8))

        if game['type'] == 'single':
            rows = [["#", "Name", "Phone", "Class/Section"]]
            participants = g.db.execute(
                'SELECT u.name, u.phone, u.class_section FROM users u WHERE u.game_id = ? AND (u.team_id IS NULL) ORDER BY u.name',
                (game_id,),
            ).fetchall()
            for idx, p in enumerate(participants, start=1):
                rows.append([str(idx), p['name'], p['phone'], p['class_section'] or '-'])
            if len(rows) == 1:
                rows.append(['-', 'No participants', '', ''])
            table = Table(rows, repeatRows=1, colWidths=[12*mm, None, 32*mm, 32*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), table_header_bg),
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('ALIGN', (0,0), (0,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ]))
            elements.append(table)
        else:
            teams = g.db.execute(
                'SELECT t.id, t.name, t.team_code, u.name AS leader_name, u.phone AS leader_phone, u.class_section AS leader_class_section '
                'FROM teams t JOIN users u ON u.id = t.leader_user_id WHERE t.game_id = ? ORDER BY t.name',
                (game_id,),
            ).fetchall()
            if not teams:
                elements.append(Paragraph('No teams.', styles['Normal']))
            else:
                for t_idx, t in enumerate(teams, start=1):
                    header = f"{t_idx}. Team: {t['name']}  (Code: {t['team_code']})"
                    elements.append(Paragraph(header, styles['Heading3']))
                    leader_rows = [["Leader", t['leader_name'], t['leader_phone'], t['leader_class_section'] or '-']]
                    leader_table = Table(leader_rows, colWidths=[20*mm, None, 32*mm, 32*mm])
                    leader_table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (0,0), table_header_bg),
                        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                        ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold'),
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ]))
                    elements.append(leader_table)

                    member_header = [["#", "Member Name", "Phone", "Class/Section"]]
                    members = g.db.execute(
                        'SELECT u.name, u.phone, u.class_section FROM team_members tm JOIN users u ON u.id = tm.user_id WHERE tm.team_id = ? ORDER BY u.name',
                        (t['id'],),
                    ).fetchall()
                    member_rows = list(member_header)
                    for midx, m in enumerate(members, start=1):
                        member_rows.append([str(midx), m['name'], m['phone'], m['class_section'] or '-'])
                    if len(member_rows) == 1:
                        member_rows.append(['-', 'No members yet', '', ''])
                    member_table = Table(member_rows, repeatRows=1, colWidths=[12*mm, None, 32*mm, 32*mm])
                    member_table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), table_header_bg),
                        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                        ('ALIGN', (0,0), (0,-1), 'CENTER'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ]))
                    elements.append(member_table)
                    elements.append(Spacer(1, 8))

        doc.build(elements)
        buf.seek(0)
        safe_name = str(game['name']).replace(' ', '_')
        filename = f"{safe_name}_participants_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


    # Public signup with whitelist enforcement
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            class_section = request.form.get('class_section', '').strip()
            phone = request.form.get('phone', '').strip()
            password = request.form.get('password', '').strip()

            if not name or not phone or not password or not class_section:
                flash('All fields are required.', 'danger')
                return render_template('signup.html')

            # Check whitelist
            wl = g.db.execute('SELECT 1 FROM whitelist_phones WHERE phone = ?', (phone,)).fetchone()
            if not wl:
                flash('Phone number is not whitelisted. Contact admin.', 'danger')
                return render_template('signup.html')

            # Check if already registered
            exists = g.db.execute('SELECT 1 FROM users WHERE phone = ?', (phone,)).fetchone()
            if exists:
                flash('This phone is already registered. Please login.', 'warning')
                return redirect(url_for('login'))

            # Create user
            g.db.execute(
                'INSERT INTO users (phone, password, name, class_section, is_admin) VALUES (?,?,?,?,0)',
                (phone, password, name, class_section)
            )
            g.db.commit()
            flash('Signup successful. You can now login.', 'success')
            return redirect(url_for('login'))

        return render_template('signup.html')
        
    # Certificate routes
    @app.route('/certificate')
    def certificate():
        user = fetch_current_user()
        if not user:
            flash('Please login to access your certificate.', 'warning')
            return redirect(url_for('login'))
            
        # Get user's game information
        user_game = None
        if user['game_id']:
            user_game = g.db.execute('SELECT * FROM games WHERE id = ?', (user['game_id'],)).fetchone()
        
        # Get certificate settings
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        certificates_enabled = settings and settings['certificates_enabled'] == 1
        
        return render_template(
            'certificate.html',
            certificates_enabled=certificates_enabled,
            user_game=user_game,
            preview_only=True
        )
        
    @app.route('/certificate/preview/event')
    def preview_event_certificate():
        user = fetch_current_user()
        if not user:
            flash('Please login to preview your certificate.', 'warning')
            return redirect(url_for('login'))
            
        # Check if certificates are enabled by admin
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        certificates_enabled = settings and settings['certificates_enabled'] == 1
        
        if not certificates_enabled:
            flash('Certificate preview is currently disabled by the administrator.', 'info')
            return redirect(url_for('certificate'))
        
        # Get user's game information
        if not user['game_id']:
            flash('You are not registered for any event. Please contact the administrator.', 'warning')
            return redirect(url_for('certificate'))
            
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (user['game_id'],)).fetchone()
        
        # Get certificate settings
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        
        # Get event date from settings
        event_date = settings['event_date'] if settings and settings['event_date'] else datetime.now().strftime('%B %d, %Y')
        
        # Generate HTML certificate for event
        try:
            certificate_html = generate_html_certificate(
                student_name=user['name'],
                event_name=game['name'],
                event_date=event_date,
                class_section=user['class_section'],
                certificate_type='event'
            )
            return certificate_html
        except Exception as e:
            print(f"Error generating event certificate preview: {e}")
            flash('Error generating certificate preview. Please contact administrator.', 'danger')
            return redirect(url_for('certificate'))
    
    @app.route('/certificate/preview/seminar')
    def preview_seminar_certificate():
        user = fetch_current_user()
        if not user:
            flash('Please login to preview your certificate.', 'warning')
            return redirect(url_for('login'))
            
        # Check if certificates are enabled by admin
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        certificates_enabled = settings and settings['certificates_enabled'] == 1
        
        if not certificates_enabled:
            flash('Certificate preview is currently disabled by the administrator.', 'info')
            return redirect(url_for('certificate'))
        
        # Get user's game information (for consistency, though seminar doesn't need specific game)
        if not user['game_id']:
            flash('You are not registered for any event. Please contact the administrator.', 'warning')
            return redirect(url_for('certificate'))
            
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (user['game_id'],)).fetchone()
        
        # Get certificate settings
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        
        # Get event date from settings
        event_date = settings['event_date'] if settings and settings['event_date'] else datetime.now().strftime('%B %d, %Y')
        
        # Generate HTML certificate for seminar
        try:
            certificate_html = generate_html_certificate(
                student_name=user['name'],
                event_name=game['name'],  # This will be overridden for seminar type
                event_date=event_date,
                class_section=user['class_section'],
                certificate_type='seminar'
            )
            return certificate_html
        except Exception as e:
            print(f"Error generating seminar certificate preview: {e}")
            flash('Error generating certificate preview. Please contact administrator.', 'danger')
            return redirect(url_for('certificate'))
        
    @app.route('/admin/certificates', methods=['GET'])
    def admin_certificates():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
            
        # Get certificate settings
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        
        # Get download records
        downloads = g.db.execute('''
            SELECT cd.download_date, u.name, u.phone, u.class_section, g.name as game_name
            FROM certificate_downloads cd
            JOIN users u ON u.id = cd.user_id
            LEFT JOIN games g ON g.id = u.game_id
            ORDER BY cd.download_date DESC
        ''').fetchall()
        
        return render_template(
            'admin_certificates.html',
            settings=settings,
            downloads=downloads
        )
        
    @app.route('/admin/certificates/settings', methods=['POST'])
    def admin_update_certificate_settings():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
            
        event_date = request.form.get('event_date', '')
        certificates_enabled = 1 if request.form.get('certificates_enabled') else 0
        
        # Check if settings already exist
        settings = g.db.execute('SELECT 1 FROM certificate_settings LIMIT 1').fetchone()
        
        if settings:
            g.db.execute(
                'UPDATE certificate_settings SET certificates_enabled = ?, event_date = ?',
                (certificates_enabled, event_date)
            )
        else:
            g.db.execute(
                'INSERT INTO certificate_settings (certificates_enabled, event_date) VALUES (?, ?)',
                (certificates_enabled, event_date)
            )
            
        g.db.commit()
        flash('Certificate settings updated successfully.', 'success')
        return redirect(url_for('admin', tab='certificates'))
    
    @app.route('/admin/database/integrity-check', methods=['POST'])
    def admin_database_integrity_check():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
            
        try:
            success = check_database_integrity()
            if success:
                flash('Database integrity check completed successfully. Check logs for details.', 'success')
            else:
                flash('Database integrity check encountered issues. Check logs for details.', 'warning')
        except Exception as e:
            flash(f'Database integrity check failed: {str(e)}', 'danger')
            
        return redirect(url_for('admin', tab='overview'))
    
    @app.route('/certificate/preview')
    @app.route('/certificate/preview/<certificate_type>')
    def preview_certificate(certificate_type='event'):
        user = fetch_current_user()
        if not user:
            flash('Please login to preview your certificate.', 'warning')
            return redirect(url_for('login'))
            
        # Check if certificates are enabled
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        certificates_enabled = settings and settings['certificates_enabled'] == 1
        
        if not certificates_enabled:
            flash('Certificates are not yet available. Please check back later.', 'info')
            return redirect(url_for('certificate'))
            
        # Get user's game information
        if not user['game_id']:
            flash('You are not registered for any event. Please contact the administrator.', 'warning')
            return redirect(url_for('certificate'))
            
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (user['game_id'],)).fetchone()
        
        # Get event date from settings
        event_date = settings['event_date'] if settings and settings['event_date'] else datetime.now().strftime('%B %d, %Y')
        
        # Validate certificate type
        if certificate_type not in ['event', 'seminar']:
            certificate_type = 'event'
        
        # Generate HTML certificate for preview
        try:
            certificate_html = generate_html_certificate(
                student_name=user['name'],
                event_name=game['name'],
                event_date=event_date,
                class_section=user['class_section'],
                certificate_type=certificate_type
            )
            
            # Add navigation and download buttons to the preview
            navigation_html = f'''
            <div style="position: fixed; top: 10px; left: 10px; z-index: 1000; background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); font-family: Arial, sans-serif;">
                <h5 style="margin: 0 0 10px 0; color: #333;">Certificate Preview</h5>
                <div style="margin-bottom: 10px;">
                    <a href="{url_for('preview_certificate', certificate_type='event')}" 
                       style="padding: 5px 10px; margin-right: 5px; text-decoration: none; background: {'#007bff' if certificate_type == 'event' else '#6c757d'}; color: white; border-radius: 4px; font-size: 12px;">Event Certificate</a>
                    <a href="{url_for('preview_certificate', certificate_type='seminar')}" 
                       style="padding: 5px 10px; text-decoration: none; background: {'#007bff' if certificate_type == 'seminar' else '#6c757d'}; color: white; border-radius: 4px; font-size: 12px;">Seminar Certificate</a>
                </div>
                <div>
                    <a href="{url_for('download_single_certificate', certificate_type=certificate_type)}" 
                       style="padding: 8px 15px; text-decoration: none; background: #28a745; color: white; border-radius: 4px; font-size: 12px; display: inline-block;">
                       📥 Download This Certificate
                    </a>
                </div>
                <div style="margin-top: 8px;">
                    <a href="{url_for('certificate')}" 
                       style="padding: 5px 10px; text-decoration: none; background: #6c757d; color: white; border-radius: 4px; font-size: 11px;">
                       ← Back to Certificates
                    </a>
                </div>
            </div>
            '''
            
            return navigation_html + certificate_html
        except Exception as e:
            print(f"Error generating certificate preview: {e}")
            flash('Error generating certificate preview. Please contact administrator.', 'danger')
            return redirect(url_for('certificate'))
    
    @app.route('/certificate/download/<certificate_type>')
    def download_single_certificate(certificate_type='event'):
        user = fetch_current_user()
        if not user:
            flash('Please login to download your certificate.', 'warning')
            return redirect(url_for('login'))
            
        # Check if certificates are enabled
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        certificates_enabled = settings and settings['certificates_enabled'] == 1
        
        if not certificates_enabled:
            flash('Certificates are not yet available. Please check back later.', 'info')
            return redirect(url_for('certificate'))
            
        # Get user's game information
        if not user['game_id']:
            flash('You are not registered for any event. Please contact the administrator.', 'warning')
            return redirect(url_for('certificate'))
            
        game = g.db.execute('SELECT * FROM games WHERE id = ?', (user['game_id'],)).fetchone()
        
        # Get event date from settings
        event_date = settings['event_date'] if settings and settings['event_date'] else datetime.now().strftime('%B %d, %Y')
        
        # Validate certificate type
        if certificate_type not in ['event', 'seminar']:
            certificate_type = 'event'
        
        # Generate single certificate PDF
        try:
            certificate_buffer = generate_certificate_pdf(
                student_name=user['name'],
                event_name=game['name'],
                event_date=event_date,
                class_section=user['class_section'],
                certificate_type=certificate_type
            )
        except Exception as e:
            print(f"Error generating certificate: {e}")
            flash('Error generating certificate. Please contact administrator.', 'danger')
            return redirect(url_for('certificate'))
        
        # Record the download
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        download_record = g.db.execute('SELECT 1 FROM certificate_downloads WHERE user_id = ?', (user['id'],)).fetchone()
        
        if not download_record:
            g.db.execute(
                'INSERT INTO certificate_downloads (user_id, download_date) VALUES (?, ?)',
                (user['id'], now)
            )
            g.db.commit()
        
        # Determine filename based on certificate type
        cert_type_name = 'Event' if certificate_type == 'event' else 'Seminar'
        filename = f"{user['name'].replace(' ', '_')}_{cert_type_name}_Certificate.pdf"
        
        # Send the certificate
        return send_file(
            certificate_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    @app.route('/admin/certificates/bulk-generate')
    def admin_bulk_generate_certificates():
        user = fetch_current_user()
        if not user or not user['is_admin']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
            
        # Get certificate settings
        settings = g.db.execute('SELECT * FROM certificate_settings LIMIT 1').fetchone()
        event_date = settings['event_date'] if settings and settings['event_date'] else datetime.now().strftime('%B %d, %Y')
        
        # Create a temporary directory to store certificates
        with tempfile.TemporaryDirectory() as temp_dir:
            # Get all participants
            participants = g.db.execute('''
                SELECT u.id, u.name, u.class_section, g.name as game_name
                FROM users u
                LEFT JOIN games g ON g.id = u.game_id
                WHERE u.game_id IS NOT NULL AND u.is_admin = 0
                ORDER BY u.name
            ''').fetchall()
            
            if not participants:
                flash('No participants found to generate certificates for.', 'warning')
                return redirect(url_for('admin', tab='certificates'))
                
            # Generate certificates for each participant
            certificate_files = []
            for p in participants:
                if not p['game_name']:
                    continue
                    
                file_name = f"certificate_{p['id']}_{p['name'].replace(' ', '_')}.pdf"
                file_path = os.path.join(temp_dir, file_name)
                
                try:
                    # Generate dual certificates for each participant
                    dual_cert_buffer = generate_dual_certificates(
                        student_name=p['name'],
                        event_name=p['game_name'],
                        event_date=event_date,
                        class_section=p['class_section']
                    )
                    
                    # Change file extension to .zip since we're now generating dual certificates
                    file_name = f"certificates_{p['id']}_{p['name'].replace(' ', '_')}.zip"
                    file_path = os.path.join(temp_dir, file_name)
                    
                    # Write to file
                    with open(file_path, 'wb') as f:
                        f.write(dual_cert_buffer.getvalue())
                except Exception as e:
                    print(f"Error generating certificates for {p['name']}: {e}")
                    continue
                
                certificate_files.append(file_path)
                
            # Create a zip file containing all certificates
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for file_path in certificate_files:
                    file_name = os.path.basename(file_path)
                    zip_file.write(file_path, file_name)
                    
            zip_buffer.seek(0)
            
            # Send the zip file
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f"all_certificates_{datetime.now().strftime('%Y%m%d')}.zip"
            )


app = create_app()

if __name__ == '__main__':
    # Local dev run: python app.py
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)


