"""
TarFixer Complete Backend API - Simplified Version
Test version without YOLO model requirement
"""

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3

# ---------------------------------------------------------
# Flask Initialization
# ---------------------------------------------------------
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app, supports_credentials=True, origins=["*"])

# ---------------------------------------------------------
# Database Setup
# ---------------------------------------------------------
DATABASE = "tarfixer.db"

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL,
            name TEXT,
            created_at TEXT,
            last_login TEXT
        )
    ''')
    
    # Whitelist table
    c.execute('''
        CREATE TABLE IF NOT EXISTS whitelist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            user_type TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT
        )
    ''')
    
    # Sessions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            email TEXT,
            user_type TEXT,
            created_at TEXT,
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Reports table
    c.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            location TEXT,
            latitude REAL,
            longitude REAL,
            damage_percentage REAL,
            severity TEXT,
            detection_count INTEGER,
            description TEXT,
            annotated_image TEXT,
            original_image TEXT,
            status TEXT DEFAULT 'pending',
            assigned_worker TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    # Audit log table
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            email TEXT,
            details TEXT,
            timestamp TEXT,
            ip_address TEXT
        )
    ''')
    
    conn.commit()
    
    # Insert default whitelisted accounts
    default_whitelist = [
        ('admin@officer.com', 'officer', 'system'),
        ('supervisor@officer.com', 'officer', 'system'),
        ('manager@office.com', 'officer', 'system'),
        ('worker1@worker.com', 'worker', 'system'),
        ('worker2@worker.com', 'worker', 'system'),
        ('contractor@worker.com', 'worker', 'system'),
    ]
    
    for email, user_type, approved_by in default_whitelist:
        c.execute('INSERT OR IGNORE INTO whitelist (email, user_type, approved_by, approved_at) VALUES (?, ?, ?, ?)',
                  (email, user_type, approved_by, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

# ---------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------
def hash_password(password, email):
    """Hash password with email-specific salt"""
    salt = f"TARFIXER_SALT_2025_SECURE_{email.lower()}"
    return hashlib.sha256((password + salt).encode()).hexdigest()

def log_audit(event_type, email, details=None):
    """Log audit event"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO audit_log (event_type, email, details, timestamp, ip_address)
                     VALUES (?, ?, ?, ?, ?)''',
                  (event_type, email, json.dumps(details or {}), 
                   datetime.now().isoformat(), request.remote_addr))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit log error: {e}")

def require_auth(user_types=None):
    """Decorator to require authentication"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            
            if not token:
                return jsonify({'error': 'No token provided'}), 401
            
            conn = get_db()
            c = conn.cursor()
            c.execute('''SELECT * FROM sessions WHERE token = ? AND datetime(expires_at) > datetime('now')''', (token,))
            session_data = c.fetchone()
            conn.close()
            
            if not session_data:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            if user_types and session_data['user_type'] not in user_types:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            request.current_user = dict(session_data)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------------------------------------------------------
# Authentication Routes
# ---------------------------------------------------------
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """User registration"""
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    # Determine user type
    user_type = 'user'
    if '@officer.com' in email or '@office.com' in email:
        user_type = 'officer'
    elif '@worker.com' in email:
        user_type = 'worker'
    
    # Check whitelist for privileged accounts
    conn = get_db()
    c = conn.cursor()
    
    if user_type in ['officer', 'worker']:
        c.execute('SELECT * FROM whitelist WHERE email = ?', (email,))
        if not c.fetchone():
            conn.close()
            log_audit('SIGNUP_BLOCKED', email, {'reason': 'not_whitelisted'})
            return jsonify({'error': 'This email requires administrator approval'}), 403
    
    # Check if user exists
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Account already exists'}), 400
    
    # Create user
    password_hash = hash_password(password, email)
    name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
    
    c.execute('''INSERT INTO users (email, password_hash, user_type, name, created_at)
                 VALUES (?, ?, ?, ?, ?)''',
              (email, password_hash, user_type, name, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    log_audit('SIGNUP_SUCCESS', email, {'user_type': user_type})
    
    return jsonify({
        'message': 'Account created successfully',
        'email': email,
        'user_type': user_type
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login"""
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # Get user
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        log_audit('LOGIN_FAILED', email, {'reason': 'account_not_found'})
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Verify password
    password_hash = hash_password(password, email)
    if user['password_hash'] != password_hash:
        conn.close()
        log_audit('LOGIN_FAILED', email, {'reason': 'incorrect_password'})
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Create session token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=24)
    
    c.execute('''INSERT INTO sessions (token, user_id, email, user_type, created_at, expires_at)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (token, user['id'], email, user['user_type'], 
               datetime.now().isoformat(), expires_at.isoformat()))
    
    # Update last login
    c.execute('UPDATE users SET last_login = ? WHERE id = ?',
              (datetime.now().isoformat(), user['id']))
    
    conn.commit()
    conn.close()
    
    log_audit('LOGIN_SUCCESS', email, {'user_type': user['user_type']})
    
    return jsonify({
        'token': token,
        'email': email,
        'user_type': user['user_type'],
        'name': user['name'],
        'expires_at': expires_at.isoformat()
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
@require_auth()
def logout():
    """User logout"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM sessions WHERE token = ?', (token,))
    conn.commit()
    conn.close()
    
    log_audit('LOGOUT', request.current_user['email'])
    
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/auth/validate', methods=['GET'])
@require_auth()
def validate_session():
    """Validate current session"""
    return jsonify({
        'valid': True,
        'user': {
            'email': request.current_user['email'],
            'user_type': request.current_user['user_type']
        }
    }), 200

# ---------------------------------------------------------
# Mock Detection Route (for testing without YOLO)
# ---------------------------------------------------------
@app.route('/api/detect', methods=['POST'])
@require_auth()
def detect():
    """Mock damage detection for testing"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    log_audit('DETECTION_RUN', request.current_user['email'], {'status': 'mock'})
    
    # Return mock data
    return jsonify({
        "damage_percentage": 42.5,
        "annotated_image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
        "detection_count": 3,
        "severity_label": "Moderate"
    })

# ---------------------------------------------------------
# Report Management Routes
# ---------------------------------------------------------
@app.route('/api/reports', methods=['POST'])
@require_auth()
def create_report():
    """Submit a road damage report"""
    data = request.get_json()
    
    required_fields = ['location', 'latitude', 'longitude', 'damage_percentage', 'severity']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''INSERT INTO reports 
                 (user_email, location, latitude, longitude, damage_percentage, severity, 
                  detection_count, description, annotated_image, original_image, created_at, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (request.current_user['email'], data['location'], data['latitude'], data['longitude'],
               data['damage_percentage'], data['severity'], data.get('detection_count', 0),
               data.get('description', ''), data.get('annotated_image', ''), 
               data.get('original_image', ''), datetime.now().isoformat(), datetime.now().isoformat()))
    
    report_id = c.lastrowid
    conn.commit()
    conn.close()
    
    log_audit('REPORT_CREATED', request.current_user['email'], {'report_id': report_id})
    
    return jsonify({
        'message': 'Report submitted successfully',
        'report_id': report_id
    }), 201

@app.route('/api/reports', methods=['GET'])
@require_auth(['officer', 'worker'])
def get_reports():
    """Get all reports (for officers/workers)"""
    status_filter = request.args.get('status', None)
    
    conn = get_db()
    c = conn.cursor()
    
    if status_filter:
        c.execute('SELECT * FROM reports WHERE status = ? ORDER BY created_at DESC', (status_filter,))
    else:
        c.execute('SELECT * FROM reports ORDER BY created_at DESC')
    
    reports = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(reports), 200

@app.route('/api/reports/my', methods=['GET'])
@require_auth()
def get_my_reports():
    """Get current user's reports"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM reports WHERE user_email = ? ORDER BY created_at DESC', 
              (request.current_user['email'],))
    reports = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(reports), 200

@app.route('/api/reports/<int:report_id>/assign', methods=['POST'])
@require_auth(['officer'])
def assign_report(report_id):
    """Assign report to worker (officer only)"""
    data = request.get_json()
    worker_email = data.get('worker_email')
    
    if not worker_email:
        return jsonify({'error': 'Worker email required'}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''UPDATE reports SET assigned_worker = ?, status = 'assigned', updated_at = ?
                 WHERE id = ?''',
              (worker_email, datetime.now().isoformat(), report_id))
    conn.commit()
    conn.close()
    
    log_audit('REPORT_ASSIGNED', request.current_user['email'], {
        'report_id': report_id,
        'worker': worker_email
    })
    
    return jsonify({'message': 'Report assigned successfully'}), 200

@app.route('/api/reports/<int:report_id>/status', methods=['PUT'])
@require_auth(['officer', 'worker'])
def update_report_status(report_id):
    """Update report status"""
    data = request.get_json()
    status = data.get('status')
    
    if status not in ['pending', 'assigned', 'in_progress', 'completed', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE reports SET status = ?, updated_at = ? WHERE id = ?',
              (status, datetime.now().isoformat(), report_id))
    conn.commit()
    conn.close()
    
    log_audit('REPORT_STATUS_UPDATED', request.current_user['email'], {
        'report_id': report_id,
        'status': status
    })
    
    return jsonify({'message': 'Status updated successfully'}), 200

# ---------------------------------------------------------
# Worker Routes
# ---------------------------------------------------------
@app.route('/api/workers/tasks', methods=['GET'])
@require_auth(['worker'])
def get_worker_tasks():
    """Get tasks assigned to current worker"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM reports WHERE assigned_worker = ? ORDER BY created_at DESC',
              (request.current_user['email'],))
    tasks = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(tasks), 200

# ---------------------------------------------------------
# Admin Routes
# ---------------------------------------------------------
@app.route('/api/admin/users', methods=['GET'])
@require_auth(['officer'])
def get_users():
    """Get all users (officer only)"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, email, user_type, name, created_at, last_login FROM users ORDER BY created_at DESC')
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(users), 200

@app.route('/api/admin/audit', methods=['GET'])
@require_auth(['officer'])
def get_audit_log():
    """Get audit log (officer only)"""
    limit = request.args.get('limit', 100, type=int)
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?', (limit,))
    logs = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(logs), 200

# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': False,
        'mode': 'test_mode_without_yolo',
        'timestamp': datetime.now().isoformat()
    }), 200

# ---------------------------------------------------------
# Run the App
# ---------------------------------------------------------
if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🚀 TarFixer Backend Server Starting (TEST MODE)...")
    print("=" * 60)
    print(f"📍 API Base URL: http://localhost:5000/api")
    print(f"🔐 Authentication: Token-based")
    print(f"🗄️  Database: SQLite (tarfixer.db)")
    print(f"⚠️  YOLO Model: Disabled (Mock mode)")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
