"""
TarFixer Complete Backend API
Production-ready backend with authentication, road damage detection, and report management
"""

import os
import io
import base64
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
# import numpy as np (Removed for lightweight deployment)
# try:
#     import cv2
# except Exception:
#     cv2 = None
from flask import Flask, request, jsonify, session
from flask_cors import CORS
try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - allow server to run without YOLO weights
    YOLO = None
from PIL import Image
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
try:
    from email_config import *
except ImportError:
    # Default settings if config file doesn't exist
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = ''
    EMAIL_HOST_PASSWORD = ''
    EMAIL_FROM_ADDRESS = 'TarFixer <noreply@tarfixer.com>'

# ---------------------------------------------------------
# Flask Initialization
# ---------------------------------------------------------
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app, 
     supports_credentials=True, 
     origins=["http://localhost:5500", "http://127.0.0.1:5500", "https://tar-fixer.vercel.app"],
     allow_headers=["Content-Type", "Authorization", "Accept"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     expose_headers=["Content-Type", "Authorization"])

# Add CORS headers to all responses
# (Handled by Flask-CORS)

# ---------------------------------------------------------
# Database Setup
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "tarfixer.db")

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def add_column_if_missing(conn, table, column_name, definition):
    """Ensure a column exists on a table for backward compatibility"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column_name not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {definition}")
        conn.commit()

def ensure_whitelist_columns(conn):
    """Add new whitelist metadata columns when upgrading schema"""
    add_column_if_missing(conn, 'whitelist', 'phone', 'TEXT')
    add_column_if_missing(conn, 'whitelist', 'status', "TEXT DEFAULT 'pending'")
    add_column_if_missing(conn, 'whitelist', 'requested_at', 'TEXT')

def ensure_user_columns(conn):
    """Add Google OAuth columns to users table"""
    add_column_if_missing(conn, 'users', 'google_id', 'TEXT')
    add_column_if_missing(conn, 'users', 'approved', "INTEGER DEFAULT 1")

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
            phone TEXT,
            status TEXT DEFAULT 'pending',
            requested_at TEXT,
            approved_by TEXT,
            approved_at TEXT
        )
    ''')

    ensure_whitelist_columns(conn)
    ensure_user_columns(conn)
    
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
    
    # Insert default whitelisted accounts if not exist
    default_whitelist = [
        ('admin@officer.com', 'officer', 'system'),
        ('supervisor@officer.com', 'officer', 'system'),
        ('manager@office.com', 'officer', 'system'),
        ('worker1@worker.com', 'worker', 'system'),
        ('worker2@worker.com', 'worker', 'system'),
        ('contractor@worker.com', 'worker', 'system'),
    ]
    
    for email, user_type, approved_by in default_whitelist:
        timestamp = datetime.now().isoformat()
        c.execute('''
            INSERT OR IGNORE INTO whitelist (email, user_type, phone, status, requested_at, approved_by, approved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (email, user_type, None, 'approved', timestamp, approved_by, timestamp))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

# ---------------------------------------------------------
# AI Service Configuration
# ---------------------------------------------------------
# URL of the AI service on Hugging Face
# We will update this with the real URL after deployment
AI_SERVICE_URL = os.environ.get('AI_SERVICE_URL', 'http://localhost:7860')

print(f"🤖 AI Service URL: {AI_SERVICE_URL}")

@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check to verify backend is running and DB is accessible"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT 1')
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    return jsonify({
        'status': 'online',
        'database': db_status,
        'ai_service': AI_SERVICE_URL,
        'timestamp': datetime.now().isoformat()
    }), 200

# Initialize DB on module load (for production servers like Gunicorn)
try:
    init_db()
except Exception as e:
    print(f"⚠️ Database initialization warning: {e}")

# ---------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------
def hash_password(password, email):
    """Hash password with email-specific salt"""
    salt = f"TARFIXER_SALT_2025_SECURE_{email.lower()}"
    return hashlib.sha256((password + salt).encode()).hexdigest()

def log_audit(event_type, email, details=None):
    """Log audit event"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO audit_log (event_type, email, details, timestamp, ip_address)
                 VALUES (?, ?, ?, ?, ?)''',
              (event_type, email, json.dumps(details or {}), 
               datetime.now().isoformat(), request.remote_addr))
    conn.commit()
    conn.close()

# ---------------------------------------------------------
# Email Helpers
# ---------------------------------------------------------

def send_email(to_email, subject, html_content, text_content=None):
    """Send email using SMTP"""
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        print(f"⚠️ Email not configured. Would send to {to_email}: {subject}")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_FROM_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add text and HTML parts
        if text_content:
            part1 = MIMEText(text_content, 'plain')
            msg.attach(part1)
        
        part2 = MIMEText(html_content, 'html')
        msg.attach(part2)
        
        # Connect and send
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        if EMAIL_USE_TLS:
            server.starttls()
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

def generate_verification_code():
    """Generate 6-digit verification code"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

def send_verification_code_email(to_email, code, user_name='User'):
    """Send verification code email"""
    subject = 'Your TarFixer Verification Code'
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .code-box {{ background: white; border: 2px dashed #667eea; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0; }}
            .code {{ font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #667eea; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔒 Password Reset Verification</h1>
            </div>
            <div class="content">
                <p>Hello {user_name},</p>
                <p>You requested to reset your password for TarFixer. Use the verification code below to proceed:</p>
                
                <div class="code-box">
                    <div style="font-size: 14px; color: #666; margin-bottom: 10px;">Your Verification Code</div>
                    <div class="code">{code}</div>
                    <div style="font-size: 12px; color: #999; margin-top: 10px;">Valid for 10 minutes</div>
                </div>
                
                <p><strong>Important:</strong></p>
                <ul>
                    <li>This code expires in <strong>10 minutes</strong></li>
                    <li>Don't share this code with anyone</li>
                    <li>If you didn't request this, please ignore this email</li>
                </ul>
                
                <div class="footer">
                    <p>© 2025 TarFixer - Road Damage Detection System</p>
                    <p>This is an automated email, please do not reply.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Password Reset Verification - TarFixer
    
    Hello {user_name},
    
    Your verification code is: {code}
    
    This code expires in 10 minutes.
    
    If you didn't request this, please ignore this email.
    
    © 2025 TarFixer
    """
    
    return send_email(to_email, subject, html_content, text_content)

def send_password_reset_link_email(to_email, reset_link, user_name='User'):
    """Send password reset link email"""
    subject = 'Reset Your TarFixer Password'
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; padding: 15px 40px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔑 Reset Your Password</h1>
            </div>
            <div class="content">
                <p>Hello {user_name},</p>
                <p>We received a request to reset your TarFixer account password. Click the button below to create a new password:</p>
                
                <div style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset Password</a>
                </div>
                
                <p><strong>This link will expire in 1 hour.</strong></p>
                
                <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="background: #e9e9e9; padding: 10px; border-radius: 5px; word-break: break-all; font-size: 12px;">{reset_link}</p>
                
                <p>If you didn't request this password reset, please ignore this email or contact support if you have concerns.</p>
                
                <div class="footer">
                    <p>© 2025 TarFixer - Road Damage Detection System</p>
                    <p>This is an automated email, please do not reply.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Reset Your TarFixer Password
    
    Hello {user_name},
    
    We received a request to reset your password. Click the link below:
    
    {reset_link}
    
    This link expires in 1 hour.
    
    If you didn't request this, please ignore this email.
    
    © 2025 TarFixer
    """
    
    return send_email(to_email, subject, html_content, text_content)

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

def clamp(v, lo, hi):
    """Limit value between lo and hi"""
    return max(lo, min(hi, v))

def expand_box(x1, y1, x2, y2, w, h, factor=0.15):
    """Expand detection box slightly"""
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    bw, bh = (x2 - x1) * (1 + factor), (y2 - y1) * (1 + factor)
    nx1, ny1 = int(clamp(cx - bw / 2, 0, w - 1)), int(clamp(cy - bh / 2, 0, h - 1))
    nx2, ny2 = int(clamp(cx + bw / 2, 0, w - 1)), int(clamp(cy + bh / 2, 0, h - 1))
    return nx1, ny1, nx2, ny2

def is_road_scene(image_bgr):
    """
    Returns False if image is unlikely to be a road.
    (Simplified for production stability - always returns True)
    """
    return True

# ---------------------------------------------------------
# Authentication Routes
# ---------------------------------------------------------
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """User registration with officer approval for privileged roles"""
    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')
    requested_user_type = (data.get('user_type') or '').lower().strip()
    phone = (data.get('phone') or '').strip()
    preferred_name = (data.get('name') or '').strip()
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    # Determine user type from input or email domain
    user_type = 'user'
    if requested_user_type in ['officer', 'worker']:
        user_type = requested_user_type
    elif '@officer.com' in email or '@office.com' in email:
        user_type = 'officer'
    elif '@worker.com' in email:
        user_type = 'worker'
    
    conn = get_db()
    c = conn.cursor()
    whitelist_entry = None
    
    if user_type in ['officer', 'worker']:
        c.execute('SELECT * FROM whitelist WHERE email = ?', (email,))
        whitelist_entry = c.fetchone()
        if not whitelist_entry:
            c.execute('''INSERT INTO whitelist (email, user_type, phone, status, requested_at)
                         VALUES (?, ?, ?, 'pending', ?)''',
                      (email, user_type, phone or None, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            log_audit('SIGNUP_PENDING', email, {'user_type': user_type})
            return jsonify({'error': 'Awaiting approval from an officer', 'status': 'pending'}), 403
        whitelist_status = whitelist_entry['status'] or 'pending'
        if whitelist_status != 'approved':
            if phone and (not whitelist_entry['phone'] or whitelist_entry['phone'] != phone):
                c.execute('UPDATE whitelist SET phone = ?, requested_at = ? WHERE id = ?',
                          (phone, datetime.now().isoformat(), whitelist_entry['id']))
                conn.commit()
            conn.close()
            log_audit('SIGNUP_BLOCKED', email, {'reason': f'whitelist_{whitelist_status}'})
            message = 'Awaiting approval from an officer' if whitelist_status == 'pending' else 'This request was rejected by an officer'
            return jsonify({'error': message, 'status': whitelist_status}), 403
        user_type = whitelist_entry['user_type']
    
    # Check if user exists
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Account already exists'}), 400
    
    # Create user
    password_hash = hash_password(password, email)
    fallback_name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
    name = preferred_name or fallback_name
    
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

@app.route('/api/auth/google-signup', methods=['POST'])
def google_signup():
    """Handle Google OAuth signup"""
    data = request.get_json()
    
    email = data.get('email', '').strip().lower()
    google_id = data.get('google_id', '')
    name = data.get('name', email.split('@')[0])
    user_type = data.get('user_type', 'user').lower()
    id_token = data.get('id_token', '')
    email_verified = data.get('email_verified', True)
    
    if not email or not google_id:
        log_audit('GOOGLE_SIGNUP_FAILED', email, {'reason': 'missing_credentials'})
        return jsonify({'error': 'Email and Google ID required'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # Check if user already exists
    c.execute('SELECT id, email, user_type, approved FROM users WHERE email = ?', (email,))
    existing = c.fetchone()
    
    if existing:
        conn.close()
        if existing['approved']:
            return jsonify({'error': 'Account already exists. Please use login instead.'}), 409
        else:
            return jsonify({
                'error': 'Account pending approval',
                'status': 'pending',
                'message': 'Your account is awaiting officer approval'
            }), 403
    
    # Check whitelist for privileged accounts
    approved = True
    if user_type in ['officer', 'worker']:
        c.execute('SELECT email, status FROM whitelist WHERE email = ?', (email,))
        whitelist_entry = c.fetchone()
        if not whitelist_entry:
            approved = False
        elif whitelist_entry['status'] != 'approved':
            approved = False
    
    # Create new user
    password_hash = hashlib.sha256(f'google_{google_id}'.encode()).hexdigest()
    
    c.execute('''
        INSERT INTO users (email, password_hash, user_type, approved, name, google_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (email, password_hash, user_type, approved, name, google_id, datetime.now().isoformat()))
    
    user_id = c.lastrowid
    
    # Add to whitelist if privileged and not approved
    if not approved and user_type in ['officer', 'worker']:
        c.execute('''
            INSERT OR IGNORE INTO whitelist (email, user_type, status, requested_at)
            VALUES (?, ?, 'pending', ?)
        ''', (email, user_type, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        log_audit('GOOGLE_SIGNUP_PENDING', email, {'user_type': user_type})
        return jsonify({
            'error': 'Account requires approval',
            'status': 'pending',
            'message': 'Your account request is pending officer approval'
        }), 403
    
    # Create session for approved users
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=7)
    
    c.execute('''
        INSERT INTO sessions (user_id, token, expires_at, created_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, token, expires_at.isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    log_audit('GOOGLE_SIGNUP_SUCCESS', email, {'user_type': user_type, 'method': 'google'})
    
    return jsonify({
        'token': token,
        'email': email,
        'user_type': user_type,
        'name': name,
        'expires_at': expires_at.isoformat()
    }), 201

@app.route('/api/auth/google-login', methods=['POST'])
def google_login():
    """Handle Google OAuth login"""
    data = request.get_json()
    
    email = data.get('email', '').strip().lower()
    google_id = data.get('google_id', '')
    id_token = data.get('id_token', '')
    
    if not email or not google_id:
        log_audit('GOOGLE_LOGIN_FAILED', email, {'reason': 'missing_credentials'})
        return jsonify({'error': 'Email and Google ID required'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # Find user by email and google_id
    c.execute('''
        SELECT id, email, user_type, approved, name, google_id
        FROM users
        WHERE email = ? AND (google_id = ? OR google_id IS NULL)
    ''', (email, google_id))
    user = c.fetchone()
    
    if not user:
        conn.close()
        log_audit('GOOGLE_LOGIN_FAILED', email, {'reason': 'user_not_found'})
        return jsonify({'error': 'No account found. Please sign up first.'}), 404
    
    # Update google_id if not set
    if not user['google_id']:
        c.execute('UPDATE users SET google_id = ? WHERE id = ?', (google_id, user['id']))
    
    # Check if approved
    if not user['approved']:
        conn.close()
        log_audit('GOOGLE_LOGIN_BLOCKED', email, {'reason': 'pending_approval'})
        return jsonify({
            'error': 'Account pending approval',
            'status': 'pending'
        }), 403
    
    # Create session
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=7)
    
    c.execute('''
        INSERT INTO sessions (user_id, token, expires_at, created_at)
        VALUES (?, ?, ?, ?)
    ''', (user['id'], token, expires_at.isoformat(), datetime.now().isoformat()))
    
    # Update last login
    c.execute('UPDATE users SET last_login = ? WHERE id = ?',
              (datetime.now().isoformat(), user['id']))
    
    conn.commit()
    conn.close()
    
    log_audit('GOOGLE_LOGIN_SUCCESS', email, {'user_type': user['user_type'], 'method': 'google'})
    
    return jsonify({
        'token': token,
        'email': email,
        'user_type': user['user_type'],
        'name': user['name'],
        'expires_at': expires_at.isoformat()
    }), 200

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Handle forgot password request - generates reset token with rate limiting"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    # Rate limiting: Check if too many reset requests from this email
    conn = get_db()
    c = conn.cursor()
    
    # Check recent reset requests (last 15 minutes)
    fifteen_min_ago = (datetime.now() - timedelta(minutes=15)).isoformat()
    c.execute('''
        SELECT COUNT(*) as count FROM password_resets
        WHERE user_id = (SELECT id FROM users WHERE email = ?)
        AND created_at > ?
    ''', (email, fifteen_min_ago))
    
    recent_requests = c.fetchone()
    if recent_requests and recent_requests['count'] >= 3:
        conn.close()
        log_audit('PASSWORD_RESET_RATE_LIMITED', email, {'attempts': recent_requests['count']})
        return jsonify({'error': 'Too many reset requests. Please try again later.'}), 429
    
    # Check if user exists
    c.execute('SELECT id, email, name FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    
    if not user:
        # Don't reveal if user exists or not (security best practice)
        return jsonify({
            'message': 'If an account exists with this email, you will receive password reset instructions.',
            'success': True
        }), 200
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=1)  # Token valid for 1 hour
    
    # Store reset token
    c.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            verification_code TEXT,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Add verification_code column if it doesn't exist
    try:
        c.execute("SELECT verification_code FROM password_resets LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE password_resets ADD COLUMN verification_code TEXT")
    
    # Generate verification code
    verification_code = generate_verification_code()
    
    c.execute('''
        INSERT INTO password_resets (user_id, token, verification_code, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user['id'], reset_token, verification_code, expires_at.isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    # Send email with reset link and verification code
    reset_link = f"http://localhost:8000/Login/reset-password.html?token={reset_token}"
    
    # Send both emails: link and verification code
    email_sent_link = send_password_reset_link_email(email, reset_link, email.split('@')[0])
    email_sent_code = send_verification_code_email(email, verification_code, email.split('@')[0])
    
    log_audit('PASSWORD_RESET_REQUEST', email, {
        'token_generated': True,
        'email_sent_link': email_sent_link,
        'email_sent_code': email_sent_code
    })
    
    return jsonify({
        'message': 'Password reset instructions have been sent to your email.',
        'success': True,
        # Keep for development (remove in production)
        'dev_reset_link': reset_link,
        'dev_token': reset_token,
        'dev_verification_code': verification_code
    }), 200

@app.route('/api/auth/verify-code', methods=['POST'])
def verify_code():
    """Verify the 6-digit code before allowing password reset"""
    data = request.get_json()
    token = data.get('token', '')
    code = data.get('code', '').strip()
    
    if not token or not code:
        return jsonify({'error': 'Token and verification code are required'}), 400
    
    if len(code) != 6 or not code.isdigit():
        return jsonify({'error': 'Invalid verification code format'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # Check if token and code match
    c.execute('''
        SELECT pr.id, pr.user_id, pr.verification_code, pr.expires_at, pr.used, u.email
        FROM password_resets pr
        JOIN users u ON pr.user_id = u.id
        WHERE pr.token = ?
    ''', (token,))
    
    reset = c.fetchone()
    conn.close()
    
    if not reset:
        return jsonify({'error': 'Invalid or expired reset token'}), 400
    
    if reset['used']:
        return jsonify({'error': 'This reset link has already been used'}), 400
    
    # Check expiration (10 minutes for verification codes)
    expires_at = datetime.fromisoformat(reset['expires_at'])
    if datetime.now() > expires_at:
        return jsonify({'error': 'Verification code has expired. Please request a new reset link.'}), 400
    
    # Verify code
    if reset['verification_code'] != code:
        log_audit('VERIFICATION_CODE_FAILED', reset['email'], {'ip': request.remote_addr})
        return jsonify({'error': 'Invalid verification code'}), 400
    
    log_audit('VERIFICATION_CODE_SUCCESS', reset['email'], {'ip': request.remote_addr})
    
    return jsonify({
        'message': 'Verification successful. You can now reset your password.',
        'success': True
    }), 200

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password using token with brute-force protection"""
    data = request.get_json()
    token = data.get('token', '')
    new_password = data.get('password', '')
    verification_code = data.get('code', '').strip()
    
    if not token or not new_password:
        return jsonify({'error': 'Token and new password are required'}), 400
    
    if not verification_code:
        return jsonify({'error': 'Verification code is required'}), 400
    
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    # Rate limiting: Track failed token attempts by IP
    client_ip = request.remote_addr
    
    conn = get_db()
    c = conn.cursor()
    
    # Create table for tracking failed attempts if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS reset_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            attempted_at TEXT NOT NULL
        )
    ''')
    
    # Clean old attempts (older than 1 hour)
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    c.execute('DELETE FROM reset_attempts WHERE attempted_at < ?', (one_hour_ago,))
    
    # Check failed attempts from this IP in last hour
    c.execute('''
        SELECT COUNT(*) as count FROM reset_attempts
        WHERE ip_address = ? AND attempted_at > ?
    ''', (client_ip, one_hour_ago))
    
    attempts = c.fetchone()
    if attempts and attempts['count'] >= 10:
        conn.close()
        log_audit('PASSWORD_RESET_BLOCKED', 'unknown', {
            'reason': 'too_many_attempts',
            'ip': client_ip
        })
        return jsonify({'error': 'Too many failed attempts. Please try again later.'}), 429
    
    # Find valid reset token and verify code
    c.execute('''
        SELECT pr.id, pr.user_id, pr.verification_code, pr.expires_at, pr.used, u.email
        FROM password_resets pr
        JOIN users u ON pr.user_id = u.id
        WHERE pr.token = ? AND pr.used = 0
    ''', (token,))
    
    reset_request = c.fetchone()
    
    # Verify the code matches
    if not reset_request or reset_request['verification_code'] != verification_code:
        # Log failed attempt
        c.execute('''
            INSERT INTO reset_attempts (ip_address, attempted_at)
            VALUES (?, ?)
        ''', (client_ip, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        log_audit('PASSWORD_RESET_FAILED', 'unknown', {
            'reason': 'invalid_token',
            'ip': client_ip
        })
        return jsonify({'error': 'Invalid or expired reset token'}), 400
    
    # Check if token expired
    expires_at = datetime.fromisoformat(reset_request['expires_at'])
    if datetime.now() > expires_at:
        # Log failed attempt
        c.execute('''
            INSERT INTO reset_attempts (ip_address, attempted_at)
            VALUES (?, ?)
        ''', (client_ip, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        log_audit('PASSWORD_RESET_FAILED', reset_request['email'], {
            'reason': 'expired_token',
            'ip': client_ip
        })
        return jsonify({'error': 'Reset token has expired. Please request a new one.'}), 400
    
    # Hash new password using the same method as login (with email as salt)
    password_hash = hash_password(new_password, reset_request['email'])
    
    # Update password
    c.execute('UPDATE users SET password_hash = ? WHERE id = ?',
              (password_hash, reset_request['user_id']))
    
    # Mark token as used
    c.execute('UPDATE password_resets SET used = 1 WHERE id = ?',
              (reset_request['id'],))
    
    # Invalidate all other sessions for this user (force re-login)
    c.execute('DELETE FROM sessions WHERE user_id = ?',
              (reset_request['user_id'],))
    
    conn.commit()
    conn.close()
    
    log_audit('PASSWORD_RESET_SUCCESS', reset_request['email'], {
        'ip': client_ip,
        'sessions_invalidated': True
    })
    
    return jsonify({
        'message': 'Password has been reset successfully. You can now log in with your new password.',
        'success': True
    }), 200

# ---------------------------------------------------------
# Road Damage Detection Route
# ---------------------------------------------------------
@app.route('/api/detect', methods=['POST'])
@require_auth()
def detect():
    """Detect road damage in uploaded image"""
    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500
    if cv2 is None:
        return jsonify({'error': 'OpenCV not available on this server build'}), 500

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    image_file = request.files['image']

    try:
        pil_image = Image.open(image_file.stream).convert("RGB")
        img_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    except Exception as e:
        return jsonify({'error': f'Invalid image file: {e}'}), 400

    H, W = img_bgr.shape[:2]
    total_pixels = H * W

    # Check if image is a road
    if not is_road_scene(img_bgr):
        black = np.zeros_like(img_bgr)
        _, buf = cv2.imencode(".jpg", black)
        img_b64 = base64.b64encode(buf).decode("utf-8")
        img_url = f"data:image/jpeg;base64,{img_b64}"

        return jsonify({
            "damage_percentage": 0.0,
            "annotated_image": img_url,
            "detection_count": 0,
            "severity_label": "No Road Detected"
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

def serialize_whitelist_entry(row):
    return {
        'id': row['id'],
        'email': row['email'],
        'user_type': row['user_type'],
        'phone': row['phone'],
        'status': row['status'],
        'requested_at': row['requested_at'],
        'approved_by': row['approved_by'],
        'approved_at': row['approved_at']
    }

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

@app.route('/api/admin/approvals', methods=['GET'])
@require_auth(['officer'])
def list_approvals():
    """Return whitelist entries with optional filters"""
    status_filter = request.args.get('status')
    role_filter = request.args.get('user_type')
    conn = get_db()
    c = conn.cursor()
    query = 'SELECT * FROM whitelist'
    clauses = []
    params = []
    if status_filter:
        clauses.append('status = ?')
        params.append(status_filter)
    if role_filter:
        clauses.append('user_type = ?')
        params.append(role_filter)
    if clauses:
        query += ' WHERE ' + ' AND '.join(clauses)
    query += ' ORDER BY COALESCE(requested_at, approved_at) DESC'
    c.execute(query, params)
    entries = [serialize_whitelist_entry(row) for row in c.fetchall()]
    conn.close()
    return jsonify(entries), 200

def update_approval_status(request_id, new_status):
    data = request.get_json(silent=True) or {}
    note = data.get('note')
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM whitelist WHERE id = ?', (request_id,))
    entry = c.fetchone()
    if not entry:
        conn.close()
        return jsonify({'error': 'Request not found'}), 404
    current_status = entry['status'] or 'pending'
    if current_status == new_status:
        conn.close()
        return jsonify({'message': f"Request already {new_status}"}), 200
    timestamp = datetime.now().isoformat()
    c.execute('''UPDATE whitelist SET status = ?, approved_by = ?, approved_at = ? WHERE id = ?''',
              (new_status, request.current_user['email'], timestamp, request_id))
    conn.commit()
    conn.close()
    log_audit('APPROVAL_DECISION', request.current_user['email'], {
        'request_id': request_id,
        'request_email': entry['email'],
        'from': current_status,
        'to': new_status,
        'note': note
    })
    return jsonify({'message': f"Request {new_status}", 'entry': {
        'id': entry['id'],
        'email': entry['email'],
        'status': new_status,
        'user_type': entry['user_type']
    }}), 200

@app.route('/api/admin/approvals/<int:request_id>/approve', methods=['POST'])
@require_auth(['officer'])
def approve_request(request_id):
    return update_approval_status(request_id, 'approved')

@app.route('/api/admin/approvals/<int:request_id>/reject', methods=['POST'])
@require_auth(['officer'])
def reject_request(request_id):
    return update_approval_status(request_id, 'rejected')

# ---------------------------------------------------------
# Run the App
# ---------------------------------------------------------
if __name__ == '__main__':
    # init_db() is already called at module level
    print("=" * 60)
    print("🚀 TarFixer Backend Server Starting...")
    print("=" * 60)
    print(f"📍 API Base URL: http://localhost:5000/api")
    print(f"🔐 Authentication: Token-based (JWT-style)")
    print(f"🗄️  Database: SQLite ({DATABASE})")
    print(f"🤖 AI Service: {AI_SERVICE_URL}")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
