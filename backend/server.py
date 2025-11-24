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
import numpy as np
try:
    import cv2
except Exception:  # pragma: no cover - best effort import on limited envs
    cv2 = None
from flask import Flask, request, jsonify, session
from flask_cors import CORS
try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - allow server to run without YOLO weights
    YOLO = None
from PIL import Image
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
# Load YOLO Model
# ---------------------------------------------------------
MODEL_PATH = r"C:\Users\ninje\Downloads\Road damage\runs\detect\train22\weights\best.pt"
if YOLO is None:
    model = None
    print("⚠️ Ultralytics not installed. Detection endpoint will be disabled.")
else:
    try:
        model = YOLO(MODEL_PATH)
        print("✅ YOLOv11 model loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load YOLO model: {e}")
        model = None

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
    """Returns False if image is unlikely to be a road"""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    total = H * W

    brightness = np.mean(gray)
    contrast = gray.std()

    if brightness < 30 or brightness > 230 or contrast < 20:
        return False

    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 70, 130)
    edge_ratio = np.sum(edges > 0) / total
    texture_var = np.var(gray) / 255.0

    avg_color = np.mean(image_bgr, axis=(0, 1))
    avg_brightness = np.mean(avg_color)

    if edge_ratio < 0.018 or texture_var < 0.07 or avg_brightness > 160:
        return False

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

    # YOLO Detection
    results = model.predict(source=pil_image, conf=0.25, iou=0.45, save=False)
    det_count, damage_pct, severity = 0, 0.0, "No Damage"

    if results and results[0].boxes is not None:
        r = results[0]
        det_count = len(r.boxes)
        avg_conf = 0.0
        union_mask = np.zeros((H, W), dtype=np.uint8)

        for box in r.boxes:
            conf = float(box.conf) if box.conf is not None else 1.0
            avg_conf += conf
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            expand_factor = 0.2 if conf < 0.5 else 0.12
            x1, y1, x2, y2 = expand_box(x1, y1, x2, y2, W, H, expand_factor)
            cv2.rectangle(union_mask, (x1, y1), (x2, y2), 255, -1)

        avg_conf /= max(det_count, 1)
        union_pixels = np.count_nonzero(union_mask)
        union_ratio = union_pixels / total_pixels

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 70, 130)
        dark_mask = (gray < 90).astype(np.uint8) * 255

        dark_ratio = np.sum(dark_mask > 0) / total_pixels
        edge_ratio = np.sum(edges > 0) / total_pixels

        visual_weight = (dark_ratio * 0.25 + edge_ratio * 0.75)
        raw_ratio = (union_ratio * 0.8) + (visual_weight * 0.2)
        raw_ratio *= (1.0 + (det_count * 0.25))

        if avg_conf < 0.45:
            raw_ratio *= 1.1

        if det_count <= 1:
            raw_ratio = min(raw_ratio, 0.70)
        else:
            raw_ratio = min(raw_ratio, 1.0)

        damage_pct = round(clamp(raw_ratio, 0.0, 1.0) * 100.0, 2)

        if damage_pct < 30:
            severity = "Minor"
        elif damage_pct <= 60:
            severity = "Moderate"
        else:
            severity = "Severe"

    # Annotate and encode image
    annotated = results[0].plot()
    ann_pil = Image.fromarray(annotated[..., ::-1])
    buf = io.BytesIO()
    ann_pil.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    ann_url = f"data:image/jpeg;base64,{img_b64}"

    log_audit('DETECTION_RUN', request.current_user['email'], {
        'damage_percentage': damage_pct,
        'severity': severity,
        'detection_count': det_count
    })

    return jsonify({
        "damage_percentage": damage_pct,
        "annotated_image": ann_url,
        "detection_count": det_count,
        "severity_label": severity
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
# Health Check
# ---------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'timestamp': datetime.now().isoformat()
    }), 200

# ---------------------------------------------------------
# Run the App
# ---------------------------------------------------------
if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🚀 TarFixer Backend Server Starting...")
    print("=" * 60)
    print(f"📍 API Base URL: http://localhost:5000/api")
    print(f"🔐 Authentication: Token-based (JWT-style)")
    print(f"🗄️  Database: SQLite ({DATABASE})")
    print(f"🤖 YOLO Model: {'✅ Loaded' if model else '❌ Not Loaded'}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
