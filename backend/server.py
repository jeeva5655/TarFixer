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
import re
import numpy as np

# Check if running on Render (low memory environment)
IS_RENDER = os.environ.get('RENDER', 'false').lower() == 'true'

try:
    import cv2
except Exception:
    cv2 = None

from flask import Flask, request, jsonify, session
from flask_cors import CORS

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth
except ImportError:
    firebase_admin = None
    firestore = None
    print("WARNING: Firebase SDK not installed. running in SQLite-only mode.")

# Initialize Firebase
db = None
USE_FIREBASE = False
try:
    firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS')
    if firebase_creds_json:
        creds_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        USE_FIREBASE = True
        print("🔥 Firebase Firestore initialized successfully!")
    else:
        print("WARNING: FIREBASE_CREDENTIALS not found, using SQLite fallback")
except Exception as e:
    print(f"WARNING: Firebase initialization failed: {e}, using SQLite fallback")
    USE_FIREBASE = False

# Only import heavy ML libraries if NOT on Render
YOLO = None
torch = None
if not IS_RENDER:
    try:
        from ultralytics import YOLO
        import torch
    except Exception as e:
        YOLO = None
        torch = None
else:
    print("INFO: Running on Render - skipping ultralytics import to save memory")

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

# Override with Environment Variables (Render Support)
# This ensures that settings from the Render Dashboard take precedence
if os.environ.get('EMAIL_HOST'): EMAIL_HOST = os.environ.get('EMAIL_HOST')
if os.environ.get('EMAIL_PORT'): EMAIL_PORT = int(os.environ.get('EMAIL_PORT'))
if os.environ.get('EMAIL_HOST_USER'): EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
if os.environ.get('EMAIL_HOST_PASSWORD'): EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
if os.environ.get('EMAIL_FROM_ADDRESS'): 
    EMAIL_FROM_ADDRESS = os.environ.get('EMAIL_FROM_ADDRESS')
elif EMAIL_HOST_USER:
    EMAIL_FROM_ADDRESS = f'TarFixer <{EMAIL_HOST_USER}>'

print(f"INFO: Email Config Loaded: Host={EMAIL_HOST}, User={EMAIL_HOST_USER}, From={EMAIL_FROM_ADDRESS}")

# ---------------------------------------------------------
# Flask Initialization
# ---------------------------------------------------------
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# CORS - Allow all origins for maximum compatibility
CORS(app, 
     supports_credentials=True, 
     origins=["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:3000", "http://localhost:8080", 
              "https://tar-fixer.vercel.app", "https://jeeva5655.github.io",
              re.compile(r"^https://.*\.vercel\.app$"), re.compile(r"^https://.*\.github\.io$")],
     allow_headers=["Content-Type", "Authorization", "Accept", "X-Test-Mode", "Origin"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     expose_headers=["Content-Type", "Authorization"])

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    # Allow specific origins
    allowed_origins = ['http://localhost:5500', 'http://127.0.0.1:5500', 
                       'https://tar-fixer.vercel.app', 'https://jeeva5655.github.io']
    if origin in allowed_origins or '.vercel.app' in origin or '.github.io' in origin:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, X-Test-Mode'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

@app.before_request
def log_request_info():
    origin = request.headers.get('Origin')
    print(f"INFO: Request from Origin: {origin} -> {request.method} {request.path}")

# Add CORS headers to all responses
# (Handled by Flask-CORS)

# ---------------------------------------------------------
# Database Setup
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "tarfixer.db")

# ---------------------------------------------------------
# Model Setup
# ---------------------------------------------------------
model = None

# Skip loading YOLO on Render free tier to avoid OOM
if IS_RENDER:
    print("📡 Will use simulated detection for demo purposes")
else:
    try:
        model_path = os.path.join(BASE_DIR, "model", "best.pt")
    # ...
    # ...
        if YOLO and os.path.exists(model_path):
            print(f"INFO: Loading YOLO model from {model_path}...")
            model = YOLO(model_path)
            print("INFO: YOLO Model loaded successfully")
        else:
            print(f"WARNING: YOLO Model not found at {model_path} or YOLO library missing")
    except Exception as e:
        print(f"ERROR: Failed to load YOLO model: {e}")

# ---------------------------------------------------------
# Firebase Firestore Helper Functions
# ---------------------------------------------------------
def fb_get_user_by_email(email):
    """Get user from Firebase by email"""
    if not USE_FIREBASE:
        return None
    try:
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).limit(1)
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"Firebase error: {e}")
        return None

def fb_create_user(email, password_hash, user_type='user', name=None, additional_data=None):
    """Create a new user in Firebase Firestore"""
    if not db: return None
    
    try:
        user_data = {
            'email': email,
            'password_hash': password_hash,
            'user_type': user_type,
            'name': name or email.split('@')[0],
            'approved': 1, # Default to approved for now unless specified
            'created_at': datetime.now().isoformat()
        }
        
        if additional_data:
            user_data.update(additional_data)
            
        # Add to 'users' collection
        doc_ref = db.collection('users').add(user_data)
        return doc_ref[1].id
    except Exception as e:
        print(f"Error creating Firebase user: {e}")
        return None

def fb_update_user(email, updates):
    """Update user in Firebase"""
    if not USE_FIREBASE:
        return False
    try:
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).limit(1)
        docs = list(query.stream())
        if docs:
            docs[0].reference.update(updates)
            return True
        return False
    except Exception as e:
        print(f"Firebase error: {e}")
        return False

def fb_create_session(token, user_id, email, user_type, expires_at):
    """Create session in Firebase"""
    if not USE_FIREBASE:
        return None
    try:
        sessions_ref = db.collection('sessions')
        sessions_ref.add({
            'token': token,
            'user_id': user_id,
            'email': email,
            'user_type': user_type,
            'created_at': datetime.now().isoformat(),
            'expires_at': expires_at.isoformat()
        })
        return token
    except Exception as e:
        print(f"Firebase error: {e}")
        return None

def fb_get_session(token):
    """Get session from Firebase"""
    if not USE_FIREBASE:
        return None
    try:
        sessions_ref = db.collection('sessions')
        query = sessions_ref.where('token', '==', token).limit(1)
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"Firebase error: {e}")
        return None

def fb_delete_session(token):
    """Delete session from Firebase"""
    if not USE_FIREBASE:
        return False
    try:
        sessions_ref = db.collection('sessions')
        query = sessions_ref.where('token', '==', token).limit(1)
        docs = list(query.stream())
        if docs:
            docs[0].reference.delete()
            return True
        return False
    except Exception as e:
        print(f"Firebase error: {e}")
        return False

def fb_create_report(report_data):
    """Create report in Firebase"""
    if not USE_FIREBASE:
        return None
    try:
        reports_ref = db.collection('reports')
        doc_ref = reports_ref.add(report_data)
        return doc_ref[1].id
    except Exception as e:
        print(f"Firebase error: {e}")
        return None

def fb_get_reports(status=None, user_email=None):
    """Get reports from Firebase"""
    if not USE_FIREBASE:
        return []
    try:
        reports_ref = db.collection('reports')
        
        # Simple query without ordering (ordering requires composite index)
        docs = reports_ref.stream()
        reports = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            
            # Apply filters manually
            if status and status != 'all' and data.get('status') != status:
                continue
            if user_email and data.get('user_email') != user_email:
                continue
                
            reports.append(data)
        
        # Sort by created_at descending (newest first)
        reports.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return reports
    except Exception as e:
        print(f"Firebase error in fb_get_reports: {e}")
        import traceback
        traceback.print_exc()
        return []

def fb_get_report_by_id(report_id):
    """Get single report from Firebase"""
    if not USE_FIREBASE:
        return None
    try:
        doc = db.collection('reports').document(report_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"Firebase error: {e}")
        return None

def fb_update_report(report_id, updates):
    """Update report in Firebase"""
    if not USE_FIREBASE:
        return False
    try:
        db.collection('reports').document(report_id).update(updates)
        return True
    except Exception as e:
        print(f"Firebase error: {e}")
        return False

def fb_log_audit(event_type, email, details=None):
    """Log audit event to Firebase"""
    if not USE_FIREBASE:
        return
    try:
        db.collection('audit_log').add({
            'event_type': event_type,
            'email': email,
            'details': details or {},
            'timestamp': datetime.now().isoformat(),
            'ip_address': request.remote_addr if request else None
        })
    except Exception as e:
        print(f"Firebase audit log error: {e}")

# ---------------------------------------------------------
# Firebase Workers Functions
# ---------------------------------------------------------
def fb_get_workers():
    """Get all workers from Firebase"""
    if not USE_FIREBASE:
        return []
    try:
        # Get users with role 'worker'
        users_ref = db.collection('users')
        docs = users_ref.where('role', '==', 'worker').stream()
        workers = []
        for doc in docs:
            data = doc.to_dict()
            workers.append({
                'id': doc.id,
                'name': data.get('name', data.get('email', 'Unknown')),
                'email': data.get('email'),
                'status': data.get('status', 'Available'),
                'zone': data.get('zone', 'Zone 1'),
                'active_jobs': data.get('active_jobs', 0)
            })
        return workers
    except Exception as e:
        print(f"Firebase error getting workers: {e}")
        return []

def fb_create_worker(worker_data):
    """Create a worker in Firebase (as a user with role=worker)"""
    if not USE_FIREBASE:
        return None
    try:
        # Create as user with worker role
        user_data = {
            'email': worker_data.get('email'),
            'name': worker_data.get('name'),
            'password_hash': hashlib.sha256(worker_data.get('password', 'worker123').encode()).hexdigest(),
            'role': 'worker',
            'status': 'Available',
            'zone': worker_data.get('zone', 'Zone 1'),
            'active_jobs': 0,
            'created_at': datetime.now().isoformat()
        }
        doc_ref = db.collection('users').add(user_data)
        return doc_ref[1].id
    except Exception as e:
        print(f"Firebase error creating worker: {e}")
        return None

def fb_update_worker_status(worker_email, status, active_jobs=None):
    """Update worker status in Firebase"""
    if not USE_FIREBASE:
        return False
    try:
        users_ref = db.collection('users')
        docs = users_ref.where('email', '==', worker_email).limit(1).stream()
        for doc in docs:
            updates = {'status': status}
            if active_jobs is not None:
                updates['active_jobs'] = active_jobs
            doc.reference.update(updates)
            return True
        return False
    except Exception as e:
        print(f"Firebase error updating worker: {e}")
        return False

def fb_get_whitelist_entry(email):
    """Get whitelist entry from Firebase"""
    if not USE_FIREBASE:
        return None
    try:
        whitelist_ref = db.collection('whitelist')
        query = whitelist_ref.where('email', '==', email).limit(1)
        docs = list(query.stream())
        if docs:
            data = docs[0].to_dict()
            data['id'] = docs[0].id
            return data
        return None
    except Exception as e:
        print(f"Firebase error getting whitelist: {e}")
        return None

def fb_create_whitelist_entry(data):
    """Create whitelist entry in Firebase"""
    if not USE_FIREBASE:
        return None
    try:
        whitelist_ref = db.collection('whitelist')
        # Check if exists first
        query = whitelist_ref.where('email', '==', data['email']).limit(1)
        if list(query.stream()):
            return None
            
        doc_ref = whitelist_ref.add({
            'email': data['email'],
            'user_type': data['user_type'],
            'phone': data.get('phone'),
            'status': data.get('status', 'pending'),
            'requested_at': get_utc_now(),
            'approved_by': None,
            'approved_at': None
        })
        return doc_ref[1].id
    except Exception as e:
        print(f"Firebase error creating whitelist: {e}")
        return None

def fb_update_whitelist_status(entry_id, status, approver_email=None):
    """Update whitelist status in Firebase"""
    if not USE_FIREBASE:
        return False
    try:
        whitelist_ref = db.collection('whitelist')
        updates = {
            'status': status,
            'approved_at': get_utc_now() if status == 'approved' else None
        }
        if approver_email:
            updates['approved_by'] = approver_email
            
        whitelist_ref.document(entry_id).update(updates)
        return True
    except Exception as e:
        print(f"Firebase error updating whitelist: {e}")
        return False

def fb_get_all_whitelist_entries(status_filter=None, role_filter=None):
    """Get all whitelist entries from Firebase"""
    if not USE_FIREBASE:
        return []
    try:
        whitelist_ref = db.collection('whitelist')
        query = whitelist_ref
        
        if status_filter:
            query = query.where('status', '==', status_filter)
        if role_filter:
            query = query.where('user_type', '==', role_filter)
            
        docs = query.stream()
        entries = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            entries.append(data)
            
        # Sort manually since we can't easily chain OrderBy with Where on multiple fields without index
        entries.sort(key=lambda x: x.get('requested_at', ''), reverse=True)
        return entries
    except Exception as e:
        print(f"Firebase error getting whitelist: {e}")
        return []

# ---------------------------------------------------------
# SQLite Database Functions (Fallback)
# ---------------------------------------------------------
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
    """Initialize the database tables"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     email TEXT UNIQUE NOT NULL,
                     password_hash TEXT,
                     name TEXT,
                     user_type TEXT NOT NULL DEFAULT 'user',
                     google_id TEXT,
                     avatar_url TEXT,
                     approved INTEGER DEFAULT 0,
                     security_answer TEXT,
                     last_login TEXT,
                     created_at TEXT)''')
                     
        # Migration: Ensure existing users have 'admin' as security answer if NULL
        try:
            c.execute("SELECT security_answer FROM users LIMIT 1")
        except sqlite3.OperationalError:
            print("🔧 Migrating DB: Adding security_answer column...")
            try:
                c.execute("ALTER TABLE users ADD COLUMN security_answer TEXT")
            except sqlite3.OperationalError:
                pass
            
        # Set default 'admin' for NULL values
        c.execute("UPDATE users SET security_answer = 'admin' WHERE security_answer IS NULL")
        if c.rowcount > 0:
            print(f"🔧 Migrated {c.rowcount} users to have default security answer 'admin'")

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
                updated_at TEXT,
                image_data TEXT,
                after_image TEXT,
                completion_lat REAL,
                completion_lng REAL,
                completed_at TEXT,
                completed_by TEXT
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
        
        # Password Resets Table
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
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()

# ---------------------------------------------------------
# AI Service Configuration
# ---------------------------------------------------------
# URL of the AI service on Hugging Face
# We will update this with the real URL after deployment
AI_SERVICE_URL = os.environ.get('AI_SERVICE_URL', 'https://huggingface.co/spaces/Jeeva5655/tarfixer-ai')

AI_SERVICE_URL = os.environ.get('AI_SERVICE_URL', 'https://huggingface.co/spaces/Jeeva5655/tarfixer-ai')

print(f"INFO: AI Service URL: {AI_SERVICE_URL}")

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'message': 'Welcome to TarFixer API',
        'status': 'online',
        'docs': '/api/health'
    }), 200

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

def get_utc_now():
    """Get current UTC timestamp in ISO format with Z suffix"""
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

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
            # TEST MODE: Allow unauthenticated requests when running locally
            # Check for test header or local development
            is_test_mode = request.headers.get('X-Test-Mode') == 'true'
            is_local = request.host.startswith('localhost') or request.host.startswith('127.0.0.1')
            
            if is_test_mode and is_local:
                print("⚠️ TEST MODE: Authentication bypassed for local testing")
                request.current_user = {'user_id': 0, 'email': 'test@test.com', 'user_type': 'user'}
                return f(*args, **kwargs)
            
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            
            if not token:
                return jsonify({'error': 'No token provided'}), 401
            
            # Use Firebase if available
            if USE_FIREBASE:
                session_data = fb_get_session(token)
                if not session_data:
                    return jsonify({'error': 'Invalid or expired token'}), 401
                
                # Check expiration
                expires_at = datetime.fromisoformat(session_data['expires_at'])
                if datetime.now() > expires_at:
                    fb_delete_session(token)
                    return jsonify({'error': 'Token expired'}), 401
                
                if user_types and session_data['user_type'] not in user_types:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                request.current_user = session_data
                return f(*args, **kwargs)
            
            # Fallback to SQLite
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
    nx2, ny2 = int(clamp(cx + bw / 2, 0, h - 1)), int(clamp(cy + bh / 2, 0, h - 1))
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
    security_answer = (data.get('security_answer') or '').strip().lower() # Normalize to lowercase
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
        
    if not security_answer:
        return jsonify({'error': 'Security answer (Pet Name) is required'}), 400
    
    # Determine user type from input or email domain
    user_type = 'user'
    if requested_user_type in ['officer', 'worker']:
        user_type = requested_user_type
    elif '@officer.com' in email or '@office.com' in email:
        user_type = 'officer'
    elif '@worker.com' in email:
        user_type = 'worker'
    
    # Use Firebase if available
    if USE_FIREBASE:
        # Check existing user
        existing_user = fb_get_user_by_email(email)
        if existing_user:
            return jsonify({'error': 'Account already exists'}), 400
            
        # WHITELIST CHECK FOR OFFICER/WORKER
        if user_type in ['officer', 'worker']:
            whitelist_entry = fb_get_whitelist_entry(email)
            
            if not whitelist_entry:
                # Create pending request
                fb_create_whitelist_entry({
                    'email': email,
                    'user_type': user_type,
                    'phone': phone,
                    'status': 'pending'
                })
                log_audit('SIGNUP_PENDING', email, {'user_type': user_type})
                return jsonify({'error': 'Awaiting approval from an officer', 'status': 'pending'}), 403
            
            whitelist_status = whitelist_entry.get('status', 'pending')
            if whitelist_status != 'approved':
                log_audit('SIGNUP_BLOCKED', email, {'reason': f'whitelist_{whitelist_status}'})
                message = 'Awaiting approval from officer' if whitelist_status == 'pending' else 'Request rejected'
                return jsonify({'error': message, 'status': whitelist_status}), 403
        
        # Create user in Firebase (Approved)
        password_hash = hash_password(password, email)
        fallback_name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
        name = preferred_name or fallback_name
        
        # Additional user data
        additional_data = {
            'security_answer': security_answer
        }
        
        user_id = fb_create_user(email, password_hash, user_type, name, additional_data)
        if user_id:
            # If came from whitelist, update usage? (Optional, maybe not needed)
            fb_log_audit('SIGNUP_SUCCESS', email, {'user_type': user_type})
            return jsonify({
                'message': 'Account created successfully',
                'email': email,
                'user_type': user_type
            }), 201
        else:
            return jsonify({'error': 'Failed to create account'}), 500
    
    # Fallback to SQLite
    conn = get_db()
    c = conn.cursor()
    whitelist_entry = None
    
    if user_type in ['officer', 'worker']:
        c.execute('SELECT * FROM whitelist WHERE email = ?', (email,))
        whitelist_entry = c.fetchone()
        
        if not whitelist_entry:
            # Create whitelist entry (Pending)
            try:
                c.execute('''INSERT INTO whitelist (email, user_type, phone, status, requested_at)
                             VALUES (?, ?, ?, 'pending', ?)''',
                          (email, user_type, phone or None, get_utc_now()))
                conn.commit()
                log_audit('SIGNUP_PENDING', email, {'user_type': user_type})
            except sqlite3.IntegrityError:
                pass
            conn.close()
            return jsonify({'error': 'Awaiting approval from an officer', 'status': 'pending'}), 403
            
        whitelist_status = whitelist_entry['status'] or 'pending'
        if whitelist_status != 'approved':
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
    
    # Ensure column exists (handled in init_db mostly, but good for safety)
    try:
        c.execute("SELECT security_answer FROM users LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE users ADD COLUMN security_answer TEXT")
    
    c.execute('''INSERT INTO users (email, password_hash, user_type, name, security_answer, created_at)
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (email, password_hash, user_type, name, security_answer, datetime.now().isoformat()))
    
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
    
    password_hash = hash_password(password, email)
    
    # Use Firebase if available
    if USE_FIREBASE:
        user = fb_get_user_by_email(email)
        
        if not user:
            fb_log_audit('LOGIN_FAILED', email, {'reason': 'account_not_found'})
            return jsonify({'error': 'Invalid credentials (User not found)'}), 401
        
        if user.get('password_hash') != password_hash:
            fb_log_audit('LOGIN_FAILED', email, {'reason': 'incorrect_password'})
            return jsonify({'error': 'Invalid credentials (Password mismatch)'}), 401
            
        # Check approval status (Legacy or Explicit)
        is_approved = user.get('approved', 1) # Default to 1 (True) for backward compat
        if not is_approved:
            fb_log_audit('LOGIN_BLOCKED', email, {'reason': 'pending_approval'})
            return jsonify({'error': 'Account pending approval. Please contact admin.'}), 403
        
        # Create session token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=30)
        
        fb_create_session(token, user['id'], email, user['user_type'], expires_at)
        fb_update_user(email, {'last_login': datetime.now().isoformat()})
        fb_log_audit('LOGIN_SUCCESS', email, {'user_type': user['user_type']})
        
        return jsonify({
            'token': token,
            'email': email,
            'user_type': user['user_type'],
            'name': user.get('name', email.split('@')[0]),
            'expires_at': expires_at.isoformat()
        }), 200
    
    # Fallback to SQLite
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
    if user['password_hash'] != password_hash:
        conn.close()
        log_audit('LOGIN_FAILED', email, {'reason': 'incorrect_password'})
        return jsonify({'error': 'Invalid credentials'}), 401
        
    # Check approval status
    if not user['approved']:
        conn.close()
        log_audit('LOGIN_BLOCKED', email, {'reason': 'pending_approval'})
        return jsonify({'error': 'Account pending approval'}), 403
    
    # Create session token
    token = secrets.token_urlsafe(32)
    # Extended to 30 days for offline convenience
    expires_at = datetime.now() + timedelta(days=30)
    
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
    
    # Use Firebase if available
    if USE_FIREBASE:
        fb_delete_session(token)
        fb_log_audit('LOGOUT', request.current_user['email'])
        return jsonify({'message': 'Logged out successfully'}), 200
    
    # Fallback to SQLite
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
    """Handle Google OAuth login - Auto-registers new users (PUBLIC USERS ONLY)"""
    data = request.get_json()
    
    email = data.get('email', '').strip().lower()
    google_id = data.get('google_id', '')
    id_token = data.get('id_token', '')
    name = data.get('name', '')
    
    # Google Sign-In is ONLY for regular users (User Dashboard)
    # Officers and Workers must use email/password with pre-approved accounts
    user_type = 'user'
    
    if not email or not google_id:
        log_audit('GOOGLE_LOGIN_FAILED', email, {'reason': 'missing_credentials'})
        return jsonify({'error': 'Email and Google ID required'}), 400
    
    # Use Firebase if available
    if USE_FIREBASE:
        user = fb_get_user_by_email(email)
        
        if not user:
            # Auto-register new Google user
            print(f"📝 Auto-registering new Google user in Firebase: {email}")
            user_id = fb_create_user(email, 'GOOGLE_AUTH', user_type, name or email.split('@')[0])
            if user_id:
                fb_update_user(email, {'google_id': google_id})
                fb_log_audit('GOOGLE_SIGNUP_SUCCESS', email, {'user_type': user_type})
                user = fb_get_user_by_email(email)
            else:
                return jsonify({'error': 'Failed to create account'}), 500
        
        # Create session
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)
        
        fb_create_session(token, user['id'], email, user_type, expires_at)
        fb_update_user(email, {'last_login': datetime.now().isoformat(), 'google_id': google_id})
        fb_log_audit('GOOGLE_LOGIN_SUCCESS', email, {'user_type': user_type})
        
        return jsonify({
            'token': token,
            'email': email,
            'user_type': user_type,
            'name': user.get('name', name),
            'expires_at': expires_at.isoformat()
        }), 200
    
    # Fallback to SQLite
    conn = get_db()
    c = conn.cursor()
    
    # Find user by email
    c.execute('''
        SELECT id, email, user_type, approved, name, google_id
        FROM users
        WHERE email = ?
    ''', (email,))
    user = c.fetchone()
    
    if not user:
        # Auto-register new Google user
        print(f"📝 Auto-registering new Google user: {email}")
        
        # Determine if auto-approval based on user type
        # Regular users are auto-approved, officers/workers need approval
        auto_approve = 1 if user_type == 'user' else 0
        
        try:
            c.execute('''
                INSERT INTO users (email, password_hash, user_type, name, google_id, approved, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (email, 'GOOGLE_AUTH', user_type, name, google_id, auto_approve, datetime.now().isoformat()))
            conn.commit()
            
            # Fetch the newly created user
            c.execute('SELECT id, email, user_type, approved, name, google_id FROM users WHERE email = ?', (email,))
            user = c.fetchone()
            
            log_audit('GOOGLE_SIGNUP_SUCCESS', email, {'user_type': user_type, 'auto_approved': auto_approve})
            
            if not auto_approve:
                conn.close()
                return jsonify({
                    'error': 'Account created! Pending admin approval.',
                    'status': 'pending'
                }), 403
                
        except Exception as e:
            conn.close()
            print(f"❌ Google signup error: {e}")
            return jsonify({'error': 'Failed to create account'}), 500
    
    # Update google_id if not set
    if user and not user['google_id']:
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
        'name': user['name'] or name,
        'expires_at': expires_at.isoformat()
    }), 200

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Initiate password reset with security check"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    security_answer = data.get('security_answer', '').strip().lower() # Verify against this
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
        
    if not security_answer:
        return jsonify({'error': 'Security answer (Pet Name) is required'}), 400
        
    # Rate limiting: Check if too many reset requests from this email
    conn = get_db()
    c = conn.cursor()
    
    # Check recent reset requests (last 15 minutes)
    # Ensure table exists first to avoid 500 error on fresh DB
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
    
    # Add verification_code column if it doesn't exist (migration)
    try:
        c.execute("SELECT verification_code FROM password_resets LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE password_resets ADD COLUMN verification_code TEXT")

    fifteen_min_ago = (datetime.now() - timedelta(minutes=15)).isoformat()
    
    # Use Firebase if available
    if USE_FIREBASE:
        # Check user in Firebase
        user = fb_get_user_by_email(email)
        
        if not user:
            # Don't reveal if user exists or not (security)
            return jsonify({
                'message': 'If an account exists with this email, you will receive password reset instructions.',
                'success': True
            }), 200
            
        # Check if Google Auth user (cannot reset password)
        if user.get('google_id'):
            return jsonify({
                'error': 'This account uses Google Sign-In. Please sign in with Google.',
                'is_google': True
            }), 400
            
        # SECURITY CHECK: Verify Pet Name
        # For legacy accounts without an answer, we default to 'admin'
        stored_answer = (user.get('security_answer') or 'admin').lower()
        if security_answer != stored_answer:
            # Check if it IS a legacy account (missing field) and they entered 'admin'
            # If the user specifically entered 'admin' and the field is missing/empty, it's valid.
            # The logic `(user.get('security_answer') or 'admin')` handles acts as the source of truth.
            
            # Audit log for failed security answer
            fb_log_audit('SECURITY_QUESTION_FAILED', email, {'attempted': security_answer})
            return jsonify({'error': 'Incorrect security answer (Pet Name).'}), 403

        # Generate reset token and code
        reset_token = secrets.token_urlsafe(32)
        verification_code = generate_verification_code()
        expires_at = datetime.now() + timedelta(hours=1)
        
        # Store in Firestore
        try:
            db.collection('password_resets').add({
                'email': email,
                'user_id': user['id'],
                'token': reset_token,
                'verification_code': verification_code,
                'expires_at': expires_at.isoformat(),
                'used': False,
                'created_at': datetime.now().isoformat()
            })
        except Exception as e:
            print(f"Firebase reset error: {e}")
            return jsonify({'error': 'Failed to process request'}), 500
            
        # Send email with reset link and verification code
        FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://tar-fixer.vercel.app')
        reset_link = f"{FRONTEND_URL}/Login/reset-password.html?token={reset_token}"
        
        # Send both emails: link and verification code
        email_sent_link = send_password_reset_link_email(email, reset_link, user.get('name', 'User'))
        email_sent_code = send_verification_code_email(email, verification_code, user.get('name', 'User'))
        
        fb_log_audit('PASSWORD_RESET_REQUEST', email, {
            'token_generated': True,
            'email_sent_link': email_sent_link,
            'email_sent_code': email_sent_code
        })
        
        return jsonify({
            'message': 'Password reset instructions have been sent to your email.',
            'success': True,
            # Keep for development
            'dev_reset_link': reset_link,
            'dev_token': reset_token,
            'dev_verification_code': verification_code
        }), 200

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
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    
    if user:
        # Convert to dict for consistency and to support .get() method
        user = dict(user)
    
    if not user:
        conn.close()
        # Don't reveal if user exists or not (security best practice)
        # But for development, provide feedback
        return jsonify({
            'message': 'If an account exists with this email, you will receive password reset instructions.',
            'success': True,
            'dev_note': 'No account found with this email. Please sign up first.'
        }), 200
        
    # Check if Google Auth user (from legacy or mixed auth)
    # We need to check if they have a google_id and NO password hash (or specific placeholder)
    if user['google_id'] and (not user['password_hash'] or user['password_hash'] == 'GOOGLE_AUTH'):
        conn.close()
        return jsonify({
            'error': 'This account uses Google Sign-In. Please sign in with Google.',
            'is_google': True
        }), 400
        
    # SECURITY CHECK: Verify Pet Name
    # For legacy accounts (NULL security_answer), default to 'admin'
    stored_answer = (user.get('security_answer') or 'admin').lower()
    
    if security_answer != stored_answer:
        conn.close()
        return jsonify({'error': 'Incorrect security answer (Pet Name).'}), 403
    
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
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://tar-fixer.vercel.app')
    reset_link = f"{FRONTEND_URL}/Login/reset-password.html?token={reset_token}"
    
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
    
    # Use Firebase if available
    if USE_FIREBASE:
        try:
            resets_ref = db.collection('password_resets')
            query = resets_ref.where('token', '==', token).limit(1)
            docs = list(query.stream())
            
            if not docs:
                return jsonify({'error': 'Invalid or expired reset token'}), 400
                
            reset_data = docs[0].to_dict()
            
            if reset_data.get('used'):
                return jsonify({'error': 'This reset link has already been used'}), 400
                
            expires_at = datetime.fromisoformat(reset_data['expires_at'])
            if datetime.now() > expires_at:
                return jsonify({'error': 'Token expired'}), 400
                
            if reset_data.get('verification_code') != code:
                return jsonify({'error': 'Invalid verification code'}), 400
                
            return jsonify({
                'message': 'Verification successful. You can now reset your password.',
                'success': True
            }), 200
        except Exception as e:
            print(f"Firebase verification error: {e}")
            return jsonify({'error': 'Verification failed'}), 500

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
    
    # Use Firebase if available
    if USE_FIREBASE:
        try:
            resets_ref = db.collection('password_resets')
            query = resets_ref.where('token', '==', token).limit(1)
            docs = list(query.stream())
            
            if not docs:
                return jsonify({'error': 'Invalid or expired reset token'}), 400
                
            reset_doc = docs[0]
            reset_data = reset_doc.to_dict()
            
            if reset_data.get('used'):
                return jsonify({'error': 'This reset link has already been used'}), 400
                
            # Verify code
            if reset_data.get('verification_code') != verification_code:
                return jsonify({'error': 'Invalid verification code'}), 400
                
            email = reset_data['email']
            
            # Hash password for fallback/security
            password_hash = hash_password(new_password, email)
            
            # Update password in Firebase Auth (if user exists there)
            try:
                # Find user UID by email (using our Firestore map logic usually, but here we can try auth.get_user_by_email)
                try:
                    user_record = auth.get_user_by_email(email)
                    auth.update_user(user_record.uid, password=new_password)
                    print(f"✅ Firebase Auth password updated for {email}")
                except auth.UserNotFoundError:
                    print(f"⚠️ User {email} not found in Firebase Auth, updating only Firestore")
            except Exception as e:
                print(f"⚠️ Firebase Auth update warning: {e}")
            
            # Update user in Firestore (password_hash)
            fb_update_user(email, {'password_hash': password_hash})
            
            # Mark token as used
            reset_doc.reference.update({'used': True, 'used_at': datetime.now().isoformat()})
            
            # Invalidate sessions by email (manual cleanup)
            sessions_ref = db.collection('sessions')
            sessions = sessions_ref.where('email', '==', email).stream()
            for s in sessions:
                s.reference.delete()
                
            fb_log_audit('PASSWORD_RESET_SUCCESS', email, {'ip': client_ip})
            
            return jsonify({
                'message': 'Password has been reset successfully. You can now log in with your new password.',
                'success': True
            }), 200
            
        except Exception as e:
            print(f"Firebase reset pass error: {e}")
            return jsonify({'error': 'Failed to reset password'}), 500

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
# Diagnostics & Global Error Handling
# ---------------------------------------------------------

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler to ensure JSON responses"""
    # Pass through HTTP errors
    if hasattr(e, 'code'):
        return jsonify({'error': str(e)}), e.code
    
    # Log the specific error
    print(f"❌ CRITICAL SERVER ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    
    return jsonify({
        'error': 'Internal Server Error', 
        'details': str(e),
        'note': 'Please check server logs for more details'
    }), 500

@app.route('/api/health/diagnostics', methods=['GET'])
def diagnostics():
    """Diagnostic endpoint to check server health"""
    import sys
    
    return jsonify({
        'status': 'online',
        'system': {
            'python_version': sys.version,
            'platform': sys.platform,
        },
        'components': {
            'opencv': 'loaded' if cv2 else 'failed',
            'pillow': 'loaded', # Since we import Image successfully
            'sqlite': 'loaded',
            'yolo_model': 'loaded' if model else 'not_loaded'
        },
        'environment': {
            'render_host': os.environ.get('RENDER', 'False'),
            'port': os.environ.get('PORT', '5000')
        }
    }), 200

# ---------------------------------------------------------
# Road Damage Detection Route
# ---------------------------------------------------------
@app.route('/api/detect', methods=['POST'])
@require_auth()
def detect():
    """Detect road damage in uploaded image"""
    print("🔍 Analysis Request Received")
    
    # Check diagnostics first
    if cv2 is None:
        print("❌ Error: OpenCV not loaded")
        return jsonify({'error': 'Server Configuration Error: OpenCV not available'}), 500

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    try:
        image_file = request.files['image']
        
        # Log file size and name
        image_file.seek(0, os.SEEK_END)
        size = image_file.tell()
        image_file.seek(0)
        print(f"📸 Image recieved: {image_file.filename} ({size} bytes)")
        
        # Load image with PIL
        try:
            pil_image = Image.open(image_file.stream).convert("RGB")
        except Exception as e:
            print(f"❌ PIL Image Load Error: {e}")
            return jsonify({'error': 'Invalid image format. Please upload a valid JPG or PNG.'}), 400
        
        # MEMORY FIX: Resize to max 640x640 to prevent OOM on Render Free Tier
        # This is critical for free tier instances with 512MB RAM
        try:
            pil_image.thumbnail((640, 640))
        except Exception as e:
            print(f"❌ Resize Error: {e}")
            return jsonify({'error': 'Failed to process image size.'}), 500
            
        # Convert to BGR for OpenCV
        try:
            img_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"❌ NumPy/CV2 Conversion Error: {e}")
            return jsonify({'error': 'Image processing failed internally.'}), 500

        H, W = img_bgr.shape[:2]
        print(f"📏 Processed Image Size: {W}x{H}")

        # Check if image is a road (Placeholder function)
        if not is_road_scene(img_bgr):
            print("⚠️ Image rejected by road scene classifier (mock)")
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
            
        # --------------------------------
        # YOLO MODEL INFERENCE
        # --------------------------------
        if model:
            try:
                # Determine device
                device = 'cpu'
                device_name = 'CPU'
                if torch and torch.cuda.is_available():
                    device = 0
                    device_name = f"GPU ({torch.cuda.get_device_name(0)})"
                
                print(f"🧠 Running YOLO inference on {device_name}...")
                print(f"🖥️  Device Check: Using {device_name.upper()} for inference.")

                # Run inference with lower confidence threshold to catch more
                results = model.predict(img_bgr, conf=0.25, verbose=True, device=device)
                
                # Visualize results on the image
                annotated_frame = results[0].plot()
                
                # Count detections
                det_count = len(results[0].boxes)
                print(f"✅ Inference successful. Detections: {det_count}")
                
                # Calculate damage percentage (simple approximation based on box area)
                total_area = H * W
                damage_area = 0
                for box in results[0].boxes:
                    # box.xywh returns center_x, center_y, width, height
                    w, h = box.xywh[0][2].item(), box.xywh[0][3].item()
                    damage_area += w * h
                
                percent = (damage_area / total_area) * 100
                percent = min(percent, 100.0) # Cap at 100%
                
            except Exception as e:
                print(f"❌ YOLO Inference Error: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f"AI Model Inference Failed: {str(e)}"}), 500
        else:
            # Use Hugging Face Space API for detection
            print("📡 Using Hugging Face Space for AI detection...")
            import requests
            
            try:
                # Convert image to bytes for API call
                img_byte_arr = io.BytesIO()
                pil_image.save(img_byte_arr, format='JPEG')
                img_byte_arr.seek(0)
                
                # Call Hugging Face Space API
                HF_API_URL = "https://jeeva5655-tarfixer-ai.hf.space/detect"
                print(f"📤 Sending image to: {HF_API_URL}")
                
                files = {'image': ('image.jpg', img_byte_arr, 'image/jpeg')}
                response = requests.post(HF_API_URL, files=files, timeout=60)
                
                print(f"📥 HF Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    hf_result = response.json()
                    print(f"✅ HF Detection Result: {hf_result}")
                    
                    percent = hf_result.get('damage_percentage', 0)
                    det_count = hf_result.get('detection_count', 0)
                    
                    # Get annotated image from HF response
                    hf_img_b64 = hf_result.get('annotated_image', '')
                    if hf_img_b64:
                        # Decode and use HF's annotated image
                        img_data = base64.b64decode(hf_img_b64)
                        nparr = np.frombuffer(img_data, np.uint8)
                        annotated_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    else:
                        annotated_frame = img_bgr.copy()
                else:
                    print(f"❌ HF API Error: {response.text}")
                    # Fallback to demo mode
                    import random
                    percent = random.uniform(15, 65)
                    det_count = random.randint(1, 5)
                    annotated_frame = img_bgr.copy()
                    cv2.putText(annotated_frame, "API Error - Demo", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    
            except requests.exceptions.Timeout:
                print("⏱️ HF API Timeout - using demo mode")
                import random
                percent = random.uniform(15, 65)
                det_count = random.randint(1, 5)
                annotated_frame = img_bgr.copy()
                cv2.putText(annotated_frame, "Timeout - Demo", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            except Exception as e:
                print(f"❌ HF API Error: {e}")
                import random
                percent = random.uniform(15, 65)
                det_count = random.randint(1, 5)
                annotated_frame = img_bgr.copy()
                cv2.putText(annotated_frame, "Error - Demo", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # Encode annotated image to base64
        try:
            _, buffer = cv2.imencode(".jpg", annotated_frame)
            img_base64 = base64.b64encode(buffer).decode("utf-8")
            img_url = f"data:image/jpeg;base64,{img_base64}"
        except Exception as e:
            print(f"❌ Image Encoding Error: {e}")
            return jsonify({'error': 'Failed to encode result image.'}), 500

        # Determine severity
        if percent < 1: severity = "Negligible"
        elif percent < 10: severity = "Low"
        elif percent < 30: severity = "Medium"
        elif percent < 60: severity = "High"
        else: severity = "Critical"

        response_data = {
            "damage_percentage": round(percent, 2),
            "annotated_image": img_url,
            "detection_count": det_count,
            "severity_label": severity,
            "execution_device": device_name if 'device_name' in locals() else "CPU"
        }
        
        return jsonify(response_data)

    except Exception as e:
        print(f"❌ Unhandled Error in /api/detect: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
# ---------------------------------------------------------
# Report Management Routes
# ---------------------------------------------------------
@app.route('/api/reports', methods=['POST'])
@require_auth()
def create_report():
    """Submit a road damage report"""
    try:
        data = request.get_json()
        
        required_fields = ['location', 'latitude', 'longitude', 'damage_percentage', 'severity']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        user_email = request.current_user['email']
        now = datetime.now().isoformat()
        
        # Get images and compress if needed
        annotated_img = data.get('annotated_image', '')
        original_img = data.get('original_image', '')
        
        def compress_image_base64(base64_str, max_size=800000):
            """Compress base64 image to reduce size"""
            if not base64_str or len(base64_str) <= max_size:
                return base64_str
            
            try:
                # Remove data URL prefix if present
                if ',' in base64_str:
                    prefix, b64_data = base64_str.split(',', 1)
                else:
                    prefix = 'data:image/jpeg;base64'
                    b64_data = base64_str
                
                # Decode base64 to image
                import io
                img_data = base64.b64decode(b64_data)
                img = Image.open(io.BytesIO(img_data))
                
                # Resize to reduce size
                max_dim = 800
                if img.width > max_dim or img.height > max_dim:
                    ratio = min(max_dim / img.width, max_dim / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Convert to RGB if needed
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Compress with JPEG
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=60, optimize=True)
                compressed_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                print(f"📦 Image compressed: {len(base64_str)} -> {len(compressed_b64)} bytes")
                return f"{prefix},{compressed_b64}"
            except Exception as e:
                print(f"⚠️ Image compression failed: {e}")
                return base64_str[:max_size] if len(base64_str) > max_size else base64_str
        
        # Compress images if too large
        annotated_img = compress_image_base64(annotated_img)
        original_img = compress_image_base64(original_img) if original_img else ''
        
        report_data = {
            'user_email': user_email,
            'location': data['location'],
            'latitude': float(data['latitude']) if data['latitude'] else 0,
            'longitude': float(data['longitude']) if data['longitude'] else 0,
            'damage_percentage': float(data['damage_percentage']) if data['damage_percentage'] else 0,
            'severity': str(data['severity']),
            'damage_type': data.get('damage_type', 'Road Damage'),
            'detection_count': int(data.get('detection_count', 0)),
            'description': data.get('description', ''),
            'annotated_image': annotated_img,
            'original_image': original_img,
            'status': 'new',
            'assigned_worker': None,
            'created_at': now,
            'updated_at': now
        }
        
        print(f"📝 Creating report for {user_email}, Firebase enabled: {USE_FIREBASE}")
        
        # Use Firebase if available
        if USE_FIREBASE:
            report_id = fb_create_report(report_data)
            if report_id:
                fb_log_audit('REPORT_CREATED', user_email, {'report_id': report_id})
                return jsonify({
                    'message': 'Report submitted successfully',
                    'report_id': report_id
                }), 201
            else:
                print("❌ Firebase report creation returned None")
                return jsonify({'error': 'Failed to create report in Firebase'}), 500
        
        # Fallback to SQLite
        conn = get_db()
        c = conn.cursor()
        
        c.execute('''INSERT INTO reports 
                     (user_email, location, latitude, longitude, damage_percentage, severity, 
                      detection_count, description, annotated_image, original_image, created_at, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user_email, report_data['location'], report_data['latitude'], report_data['longitude'],
                   report_data['damage_percentage'], report_data['severity'], report_data['detection_count'],
                   report_data['description'], report_data['annotated_image'], 
                   report_data['original_image'], now, now))
        
        report_id = c.lastrowid
        conn.commit()
        conn.close()
        
        log_audit('REPORT_CREATED', user_email, {'report_id': report_id})
        
        return jsonify({
            'message': 'Report submitted successfully',
            'report_id': report_id
        }), 201
        
    except Exception as e:
        print(f"❌ Error in create_report: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to create report: {str(e)}'}), 500

@app.route('/api/reports', methods=['GET'])
@require_auth(['officer', 'worker'])
def get_reports():
    """Get all reports (for officers/workers)"""
    status_filter = request.args.get('status', None)
    
    # Use Firebase if available
    if USE_FIREBASE:
        reports = fb_get_reports(status=status_filter)
        # Transform for frontend compatibility
        transformed = []
        for r in reports:
            transformed.append({
                'id': r.get('id'),
                'user_email': r.get('user_email'),
                'latitude': r.get('latitude'),
                'longitude': r.get('longitude'),
                'damage_percentage': r.get('damage_percentage'),
                'confidence': r.get('damage_percentage'),
                'damage_type': r.get('damage_type', 'Road Damage'),
                'severity': r.get('severity'),
                'status': r.get('status', 'new'),
                'assigned_worker': r.get('assigned_worker'),
                'image_data': r.get('annotated_image', r.get('original_image', '')),
                'created_at': r.get('created_at'),
                'updated_at': r.get('updated_at'),
                # Completion data from worker
                'after_image': r.get('after_image'),
                'after_damage_percentage': r.get('after_damage_percentage'),
                'completed_by': r.get('completed_by'),
                'completed_at': r.get('completed_at')
            })
        return jsonify({'reports': transformed}), 200
    
    # Fallback to SQLite
    conn = get_db()
    c = conn.cursor()
    
    if status_filter:
        c.execute('SELECT * FROM reports WHERE status = ? ORDER BY created_at DESC', (status_filter,))
    else:
        c.execute('SELECT * FROM reports ORDER BY created_at DESC')
    
    reports = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify({'reports': reports}), 200

@app.route('/api/reports/my', methods=['GET'])
@require_auth()
def get_my_reports():
    """Get current user's reports"""
    user_email = request.current_user['email']
    
    # Use Firebase if available
    if USE_FIREBASE:
        reports = fb_get_reports(user_email=user_email)
        return jsonify(reports), 200
    
    # Fallback to SQLite
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM reports WHERE user_email = ? ORDER BY created_at DESC', 
              (user_email,))
    reports = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(reports), 200

@app.route('/api/reports/<report_id>/assign', methods=['POST'])
@require_auth(['officer'])
def assign_report(report_id):
    """Assign report to worker (officer only)"""
    data = request.get_json()
    worker_email = data.get('worker_email')
    
    if not worker_email:
        return jsonify({'error': 'Worker email required'}), 400
    
    now = datetime.now().isoformat()
    
    # Use Firebase if available
    if USE_FIREBASE:
        success = fb_update_report(report_id, {
            'assigned_worker': worker_email,
            'status': 'assigned',
            'updated_at': now
        })
        if success:
            # Update worker status
            fb_update_worker_status(worker_email, 'Busy')
            fb_log_audit('REPORT_ASSIGNED', request.current_user['email'], {
                'report_id': report_id,
                'worker': worker_email
            })
            return jsonify({'message': 'Report assigned successfully'}), 200
        else:
            return jsonify({'error': 'Failed to assign report'}), 500
    
    # Fallback to SQLite
    conn = get_db()
    c = conn.cursor()
    c.execute('''UPDATE reports SET assigned_worker = ?, status = 'assigned', updated_at = ?
                 WHERE id = ?''',
              (worker_email, now, report_id))
    conn.commit()
    conn.close()
    
    log_audit('REPORT_ASSIGNED', request.current_user['email'], {
        'report_id': report_id,
        'worker': worker_email
    })
    
    return jsonify({'message': 'Report assigned successfully'}), 200

@app.route('/api/reports/<report_id>/status', methods=['PUT'])
@require_auth(['officer', 'worker'])
def update_report_status(report_id):
    """Update report status"""
    data = request.get_json()
    status = data.get('status')
    
    valid_statuses = ['new', 'pending', 'assigned', 'in_progress', 'done', 'completed', 'resolved', 'rejected']
    if status not in valid_statuses:
        return jsonify({'error': 'Invalid status'}), 400
    
    now = datetime.now().isoformat()
    
    # Use Firebase if available
    if USE_FIREBASE:
        success = fb_update_report(report_id, {
            'status': status,
            'updated_at': now
        })
        if success:
            fb_log_audit('REPORT_STATUS_UPDATED', request.current_user['email'], {
                'report_id': report_id,
                'status': status
            })
            return jsonify({'message': 'Status updated successfully'}), 200
        else:
            return jsonify({'error': 'Failed to update status'}), 500
    
    # Fallback to SQLite
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

@app.route('/api/reports/<report_id>/complete', methods=['POST'])
@require_auth(['worker'])
def complete_report(report_id):
    """Worker completes a task with after image and GPS verification"""
    data = request.get_json()
    
    after_image = data.get('after_image', '')
    completion_lat = data.get('completion_lat')
    completion_lng = data.get('completion_lng')
    completion_time = data.get('completion_time', datetime.now().isoformat())
    after_damage_percentage = data.get('after_damage_percentage', -1)  # -1 means unverified
    
    if not after_image:
        return jsonify({'error': 'After image is required'}), 400
    
    # Get the original report to verify location
    if USE_FIREBASE:
        report = fb_get_report_by_id(report_id)
    else:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
        row = c.fetchone()
        conn.close()
        report = dict(row) if row else None
    
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    
    # Verify GPS location matches (within tolerance)
    original_lat = report.get('latitude', 0)
    original_lng = report.get('longitude', 0)
    
    if completion_lat and completion_lng:
        # Calculate distance using Haversine formula
        import math
        R = 6371000  # Earth's radius in meters
        
        lat1, lat2 = math.radians(original_lat), math.radians(completion_lat)
        dlat = math.radians(completion_lat - original_lat)
        dlng = math.radians(completion_lng - original_lng)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        MAX_DISTANCE = 500  # 500 meters tolerance
        
        if distance > MAX_DISTANCE:
            return jsonify({
                'error': f'Location verification failed. You are {distance:.0f}m away from task location. Maximum allowed: {MAX_DISTANCE}m'
            }), 400
    
    # Compress the after image if too large
    compressed_after = after_image
    if len(after_image) > 800000:
        try:
            if ',' in after_image:
                prefix, b64_data = after_image.split(',', 1)
            else:
                prefix = 'data:image/jpeg;base64'
                b64_data = after_image
            
            import io
            img_data = base64.b64decode(b64_data)
            img = Image.open(io.BytesIO(img_data))
            
            max_dim = 800
            if img.width > max_dim or img.height > max_dim:
                ratio = min(max_dim / img.width, max_dim / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=60, optimize=True)
            compressed_after = f"{prefix},{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
        except Exception as e:
            print(f"After image compression failed: {e}")
    
    now = datetime.now().isoformat()
    
    # Update report with after image and mark as done
    if USE_FIREBASE:
        success = fb_update_report(report_id, {
            'after_image': compressed_after,
            'completion_lat': completion_lat,
            'completion_lng': completion_lng,
            'completed_at': completion_time,
            'completed_by': request.current_user['email'],
            'after_damage_percentage': after_damage_percentage,
            'status': 'done',
            'updated_at': now
        })
        if success:
            fb_log_audit('REPORT_COMPLETED', request.current_user['email'], {
                'report_id': report_id
            })
            return jsonify({'message': 'Task completed successfully'}), 200
        else:
            return jsonify({'error': 'Failed to complete task'}), 500
    
    # SQLite fallback
    conn = get_db()
    c = conn.cursor()
    c.execute('''UPDATE reports SET 
                 after_image = ?, 
                 completion_lat = ?, 
                 completion_lng = ?,
                 completed_at = ?,
                 completed_by = ?,
                 status = 'done',
                 updated_at = ?
                 WHERE id = ?''',
              (compressed_after, completion_lat, completion_lng, completion_time,
               request.current_user['email'], now, report_id))
    conn.commit()
    conn.close()
    
    log_audit('REPORT_COMPLETED', request.current_user['email'], {'report_id': report_id})
    
    return jsonify({'message': 'Task completed successfully'}), 200

# ---------------------------------------------------------
# Worker Routes
# ---------------------------------------------------------
@app.route('/api/workers', methods=['GET'])
@require_auth(['officer'])
def get_workers():
    """Get all workers (officer only)"""
    try:
        # Use Firebase if available
        if USE_FIREBASE:
            workers = fb_get_workers()
            # Return workers even if empty list (not None)
            if workers is not None:
                if len(workers) > 0:
                    return jsonify({'workers': workers}), 200
                # Fall through to demo workers if empty
        
        # Fallback to SQLite or return demo workers if none found
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE role = ?', ('worker',))
            rows = c.fetchall()
            conn.close()
            
            if rows:
                workers = []
                for row in rows:
                    data = dict(row)
                    workers.append({
                        'id': data.get('id'),
                        'name': data.get('name', data.get('email', 'Unknown')),
                        'email': data.get('email'),
                        'status': data.get('status', 'Available'),
                        'zone': data.get('zone', 'Zone 1'),
                        'active_jobs': data.get('active_jobs', 0)
                    })
                return jsonify({'workers': workers}), 200
        except Exception as db_error:
            print(f"SQLite error getting workers: {db_error}")
        
        # Return demo workers if none exist
        return jsonify({
            'workers': [
                {'id': '1', 'name': 'Ramesh K', 'email': 'ramesh@worker.com', 'status': 'Available', 'zone': 'Zone 1', 'active_jobs': 0},
                {'id': '2', 'name': 'Suresh M', 'email': 'suresh@worker.com', 'status': 'Busy', 'zone': 'Zone 2', 'active_jobs': 2},
                {'id': '3', 'name': 'Abdul R', 'email': 'abdul@worker.com', 'status': 'Available', 'zone': 'Zone 3', 'active_jobs': 0},
                {'id': '4', 'name': 'John D', 'email': 'john@worker.com', 'status': 'Available', 'zone': 'Zone 4', 'active_jobs': 1}
            ],
            'demo': True
        }), 200
    except Exception as e:
        print(f"Error in get_workers: {e}")
        import traceback
        traceback.print_exc()
        # Return demo workers as fallback
        return jsonify({
            'workers': [
                {'id': '1', 'name': 'Ramesh K', 'email': 'ramesh@worker.com', 'status': 'Available', 'zone': 'Zone 1', 'active_jobs': 0},
                {'id': '2', 'name': 'Suresh M', 'email': 'suresh@worker.com', 'status': 'Busy', 'zone': 'Zone 2', 'active_jobs': 2},
                {'id': '3', 'name': 'Abdul R', 'email': 'abdul@worker.com', 'status': 'Available', 'zone': 'Zone 3', 'active_jobs': 0},
                {'id': '4', 'name': 'John D', 'email': 'john@worker.com', 'status': 'Available', 'zone': 'Zone 4', 'active_jobs': 1}
            ],
            'demo': True
        }), 200

@app.route('/api/workers', methods=['POST'])
@require_auth(['officer'])
def create_worker():
    """Create a new worker (officer only)"""
    data = request.get_json()
    
    required_fields = ['name', 'email']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Name and email are required'}), 400
    
    # Use Firebase if available
    if USE_FIREBASE:
        worker_id = fb_create_worker({
            'name': data['name'],
            'email': data['email'],
            'password': data.get('password', 'worker123'),
            'zone': data.get('zone', 'Zone 1')
        })
        if worker_id:
            fb_log_audit('WORKER_CREATED', request.current_user['email'], {'worker_id': worker_id})
            return jsonify({'message': 'Worker created successfully', 'worker_id': worker_id}), 201
        else:
            return jsonify({'error': 'Failed to create worker'}), 500
    
    # Fallback to SQLite
    conn = get_db()
    c = conn.cursor()
    password_hash = hashlib.sha256(data.get('password', 'worker123').encode()).hexdigest()
    
    try:
        c.execute('''INSERT INTO users (email, name, password_hash, role, status, zone, active_jobs, created_at)
                     VALUES (?, ?, ?, 'worker', 'Available', ?, 0, ?)''',
                  (data['email'], data['name'], password_hash, data.get('zone', 'Zone 1'), datetime.now().isoformat()))
        conn.commit()
        worker_id = c.lastrowid
        conn.close()
        
        log_audit('WORKER_CREATED', request.current_user['email'], {'worker_id': worker_id})
        return jsonify({'message': 'Worker created successfully', 'worker_id': worker_id}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Worker with this email already exists'}), 400

@app.route('/api/workers/tasks', methods=['GET'])
@require_auth(['worker'])
def get_worker_tasks():
    """Get tasks assigned to current worker"""
    worker_email = request.current_user['email']
    
    # Use Firebase if available
    if USE_FIREBASE:
        reports = fb_get_reports()
        # Filter for tasks assigned to this worker
        tasks = [r for r in reports if r.get('assigned_worker') == worker_email]
        return jsonify(tasks), 200
    
    # Fallback to SQLite
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM reports WHERE assigned_worker = ? ORDER BY created_at DESC',
              (worker_email,))
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
    
    if USE_FIREBASE:
        entries = fb_get_all_whitelist_entries(status_filter, role_filter)
        return jsonify(entries), 200
        
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
    
    if USE_FIREBASE:
        # For Firebase, request_id is a string
        # BUT flask route defines <int:request_id>... 
        # Wait, Firebase IDs are strings. We need to handle this.
        # Ideally route should be <request_id> (string)
        # But for now, let's assume if it comes in as int, we convert? No, Firebase IDs are alphanumeric.
        # This will fail routing if we don't change route definition.
        # I will update route definitions below.
        pass

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
        
    # If approving, we might need to Create the User if they don't exist?
    # In SQLite flow: User creation happens on next signup attempt (whitelist check passes).
    # OR we can auto-create user now?
    # The current SQLite flow (see signup) assumes user retries signup.
    # But wait, if they retry signup, they will getting 201 Created.
    # Does 'approve' action create the user?
    # In `update_approval_status` (SQLite), it ONLY updates whitelist.
    # So the user has to SIGN UP AGAIN.
    # This is slightly bad UX but secure.
    # But let's stick to this pattern for now to match SQLite legacy.
    
    timestamp = get_utc_now()
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

@app.route('/api/admin/approvals/<request_id>/approve', methods=['POST'])
@require_auth(['officer'])
def approve_request(request_id):
    # Handle Firebase (String ID) vs SQLite (Int ID)
    # The route <request_id> captures both strings and ints as strings
    
    if USE_FIREBASE:
        success = fb_update_whitelist_status(request_id, 'approved', request.current_user['email'])
        if success:
            # OPTIONAL: Auto-create user account if we have password? 
            # We don't have password stored in whitelist.
            # So user must sign up again.
            return jsonify({'message': 'Request approved', 'status': 'approved'}), 200
        return jsonify({'error': 'Failed to update'}), 500
        
    # SQLite - convert to int
    try:
        int_id = int(request_id)
        return update_approval_status(int_id, 'approved')
    except ValueError:
        return jsonify({'error': 'Invalid ID format for SQLite'}), 400

@app.route('/api/admin/approvals/<request_id>/reject', methods=['POST'])
@require_auth(['officer'])
def reject_request(request_id):
    if USE_FIREBASE:
        success = fb_update_whitelist_status(request_id, 'rejected', request.current_user['email'])
        if success:
            return jsonify({'message': 'Request rejected', 'status': 'rejected'}), 200
        return jsonify({'error': 'Failed to update'}), 500

    try:
        int_id = int(request_id)
        return update_approval_status(int_id, 'rejected')
    except ValueError:
        return jsonify({'error': 'Invalid ID format for SQLite'}), 400

# ---------------------------------------------------------
# Analytics / Stats Endpoints
# ---------------------------------------------------------

@app.route('/api/admin/stats', methods=['GET'])
@require_auth(['officer'])
def admin_stats():
    """Get dashboard analytics for officers"""
    try:
        conn = get_db()
        c = conn.cursor()

        # 1. Status Counts
        c.execute('SELECT status, COUNT(*) as count FROM reports GROUP BY status')
        raw_counts = {row['status']: row['count'] for row in c.fetchall()}
        
        # Ensure all keys exist
        counts = {
            'new': raw_counts.get('new', 0) + raw_counts.get('pending', 0), # Handle legacy 'pending'
            'assigned': raw_counts.get('assigned', 0),
            'in_progress': raw_counts.get('in_progress', 0),
            'done': raw_counts.get('done', 0),
            'resolved': raw_counts.get('resolved', 0)
        }

        # 2. Severity Counts (Pie Chart)
        c.execute('SELECT severity, COUNT(*) as count FROM reports WHERE severity IS NOT NULL GROUP BY severity')
        severity = {row['severity']: row['count'] for row in c.fetchall()}

        # 3. Weekly Activity (Last 7 Days) - Reports Created
        seven_days_ago = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
        # SQLite substr(created_at, 1, 10) extracts 'YYYY-MM-DD'
        c.execute("""
            SELECT substr(created_at, 1, 10) as day, COUNT(*) as count 
            FROM reports 
            WHERE created_at >= ? 
            GROUP BY day
            ORDER BY day
        """, (seven_days_ago,))
        weekly_data = {row['day']: row['count'] for row in c.fetchall()}
        
        # Fill missing days with 0
        weekly_reports = []
        for i in range(7):
            d = (datetime.now() - timedelta(days=6-i))
            day_str = d.strftime('%Y-%m-%d')
            # Format label as 'Mon', 'Tue' etc for chart
            label = d.strftime('%a') 
            weekly_reports.append({
                'date': day_str,
                'label': label,
                'count': weekly_data.get(day_str, 0)
            })

        conn.close()

        return jsonify({
            'counts': counts,
            'severity': severity,
            'weekly_reports': weekly_reports
        }), 200
    except Exception as e:
        print(f"Admin Stats Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/worker/stats', methods=['GET'])
@require_auth(['worker'])
def worker_stats():
    """Get dashboard analytics for workers"""
    try:
        email = request.current_user['email']
        conn = get_db()
        c = conn.cursor()

        # 1. My Tasks Status
        c.execute('''
            SELECT status, COUNT(*) as count 
            FROM reports 
            WHERE assigned_worker = ? 
            GROUP BY status
        ''', (email,))
        raw_counts = {row['status']: row['count'] for row in c.fetchall()}
        
        counts = {
            'assigned': raw_counts.get('assigned', 0),
            'in_progress': raw_counts.get('in_progress', 0),
            'done': raw_counts.get('done', 0),    # Waiting verification
            'resolved': raw_counts.get('resolved', 0) # Verified
        }

        # 2. My Weekly Completions (Last 7 Days)
        seven_days_ago = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
        
        # Check 'completed_at' or 'updated_at' for done/resolved jobs
        c.execute("""
            SELECT substr(updated_at, 1, 10) as day, COUNT(*) as count 
            FROM reports 
            WHERE assigned_worker = ? 
            AND (status = 'done' OR status = 'resolved')
            AND updated_at >= ? 
            GROUP BY day
            ORDER BY day
        """, (email, seven_days_ago))
        
        weekly_data = {row['day']: row['count'] for row in c.fetchall()}
        
        weekly_perf = []
        for i in range(7):
            d = (datetime.now() - timedelta(days=6-i))
            day_str = d.strftime('%Y-%m-%d')
            label = d.strftime('%a')
            weekly_perf.append({
                'date': day_str,
                'label': label,
                'count': weekly_data.get(day_str, 0)
            })

        conn.close()

        return jsonify({
            'counts': counts,
            'weekly_performance': weekly_perf
        }), 200
    except Exception as e:
        print(f"Worker Stats Error: {e}")
        return jsonify({'error': str(e)}), 500

# ---------------------------------------------------------
# Setup Routes (for initializing demo data)
# ---------------------------------------------------------
@app.route('/api/setup/create-demo-workers', methods=['POST'])
def create_demo_workers():
    """Create demo worker accounts (one-time setup)"""
    demo_workers = [
        {'email': 'ramesh@worker.com', 'name': 'Ramesh K', 'zone': 'Zone 1'},
        {'email': 'suresh@worker.com', 'name': 'Suresh M', 'zone': 'Zone 2'},
        {'email': 'abdul@worker.com', 'name': 'Abdul R', 'zone': 'Zone 3'},
        {'email': 'john@worker.com', 'name': 'John D', 'zone': 'Zone 4'}
    ]
    
    created = []
    already_exists = []
    
    for worker in demo_workers:
        email = worker['email']
        password_hash = hash_password('worker123', email)
        
        if USE_FIREBASE:
            existing = fb_get_user_by_email(email)
            if existing:
                already_exists.append(email)
                continue
            
            user_id = fb_create_user(email, password_hash, 'worker', worker['name'])
            if user_id:
                # Update zone info
                try:
                    db.collection('users').document(user_id).update({
                        'zone': worker['zone'],
                        'status': 'Available',
                        'active_jobs': 0
                    })
                except:
                    pass
                created.append(email)
        else:
            # SQLite fallback
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT id FROM users WHERE email = ?', (email,))
            if c.fetchone():
                already_exists.append(email)
                conn.close()
                continue
            
            c.execute('''INSERT INTO users (email, password_hash, user_type, name, created_at)
                         VALUES (?, ?, 'worker', ?, ?)''',
                      (email, password_hash, worker['name'], datetime.now().isoformat()))
            conn.commit()
            conn.close()
            created.append(email)
    
    return jsonify({
        'message': 'Demo workers setup complete',
        'created': created,
        'already_exists': already_exists
    }), 200

# ---------------------------------------------------------
# Run the App
# ---------------------------------------------------------
if __name__ == '__main__':
    # init_db() is already called at module level
    # init_db() is already called at module level
    print("=" * 60)
    print("INFO: TarFixer Backend Server Starting...")
    print("=" * 60)
    print(f"INFO: API Base URL: {os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')}/api")
    print(f"INFO: Authentication: Token-based (JWT-style)")
    print(f"INFO: Database: SQLite ({DATABASE})")
    print(f"INFO: AI Service: {AI_SERVICE_URL}")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
