# 🚀 TarFixer Complete Production Deployment Guide

## 📋 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      TARFIXER SYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   Frontend   │◄────►│   Backend    │                    │
│  │  (HTML/JS)   │ HTTP │  (Flask API) │                    │
│  └──────────────┘      └──────┬───────┘                    │
│                                │                             │
│                         ┌──────┴───────┐                    │
│                         │               │                    │
│                    ┌────▼────┐    ┌────▼────┐              │
│                    │  SQLite │    │  YOLO   │              │
│                    │Database │    │  Model  │              │
│                    └─────────┘    └─────────┘              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🗂️ Project Structure

```
Road damage/
├── backend/
│   ├── server.py           # Main Flask API server (NEW)
│   ├── run.py              # Old detection server
│   ├── app.py              # Legacy server
│   ├── tarfixer.db         # SQLite database (auto-created)
│   └── requirements.txt    # Python dependencies
│
├── Dashboard/
│   ├── Officer.HTML        # Officer management dashboard
│   ├── Worker.HTML         # Worker task dashboard
│   └── User.HTML           # User reporting dashboard
│
├── Login/
│   ├── Choose_login.html   # Login/Signup page (UPDATED)
│   ├── bg.jpg              # Background image
│   └── google.png          # Google icon
│
├── api-client.js           # Frontend API integration (NEW)
├── auth.js                 # Legacy auth (kept for fallback)
│
└── Documentation/
    ├── DEPLOYMENT_GUIDE.md # This file
    ├── API_DOCUMENTATION.md
    └── SECURITY_TESTS.md
```

## 🔧 Prerequisites

### Backend Requirements:
- **Python 3.8+**
- **Flask** web framework
- **YOLO Model** (`best.pt` trained model)
- **SQLite** (built-in with Python)

### Frontend Requirements:
- **Modern Web Browser** (Chrome, Firefox, Edge)
- **Local Web Server** or **File System Access**

## 📦 Installation Steps

### Step 1: Install Python Dependencies

```bash
cd "c:\Users\ninje\Downloads\Road damage\backend"

# Install requirements
pip install flask flask-cors ultralytics pillow opencv-python numpy sqlite3
```

### Step 2: Configure YOLO Model Path

Edit `backend/server.py` line 47:
```python
MODEL_PATH = r"E:\road-damage\runs\detect\train22\weights\best.pt"
```
Change to your actual model path.

### Step 3: Initialize Database

The database is auto-created on first run. Default whitelist includes:
- `admin@officer.com` (Officer)
- `supervisor@officer.com` (Officer)
- `manager@office.com` (Officer)
- `worker1@worker.com` (Worker)
- `worker2@worker.com` (Worker)
- `contractor@worker.com` (Worker)

### Step 4: Start Backend Server

```bash
cd backend
python server.py
```

Expected output:
```
============================================================
🚀 TarFixer Backend Server Starting...
============================================================
📍 API Base URL: http://localhost:5000/api
🔐 Authentication: Token-based (JWT-style)
🗄️  Database: SQLite (tarfixer.db)
🤖 YOLO Model: ✅ Loaded
============================================================
 * Running on http://0.0.0.0:5000
```

### Step 5: Configure Frontend API URL

If deploying to production, edit `api-client.js` line 6:
```javascript
const API_BASE_URL = 'http://localhost:5000/api';
```
Change to your production URL.

### Step 6: Open Frontend

Open in browser:
```
file:///c:/Users/ninje/Downloads/Road%20damage/Login/Choose_login.html
```

Or use a local server:
```bash
python -m http.server 8080
# Then visit: http://localhost:8080/Login/Choose_login.html
```

## 🔐 Authentication Flow

### 1. User Registration
```javascript
POST /api/auth/signup
Body: { "email": "user@example.com", "password": "SecurePass123!" }

Response: 
{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "email": "user@example.com",
    "user_type": "user",
    "name": "User",
    "expires_at": "2025-11-23T08:00:00"
}
```

### 2. User Login
```javascript
POST /api/auth/login
Body: { "email": "admin@officer.com", "password": "Admin@123" }

Response: Same as signup
```

### 3. Protected Routes
All API routes except `/health`, `/auth/signup`, `/auth/login` require:
```
Headers: {
    "Authorization": "Bearer <token>"
}
```

## 🛠️ API Endpoints

### Authentication
- `POST /api/auth/signup` - Create new account
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/validate` - Validate session

### Road Damage Detection
- `POST /api/detect` - Upload image for analysis
  - Requires: `multipart/form-data` with `image` file
  - Returns: damage percentage, severity, annotated image

### Report Management
- `POST /api/reports` - Submit road damage report
- `GET /api/reports` - Get all reports (Officer/Worker only)
- `GET /api/reports/my` - Get current user's reports
- `POST /api/reports/<id>/assign` - Assign to worker (Officer only)
- `PUT /api/reports/<id>/status` - Update report status

### Worker Routes
- `GET /api/workers/tasks` - Get assigned tasks (Worker only)

### Admin Routes
- `GET /api/admin/users` - List all users (Officer only)
- `GET /api/admin/audit` - View audit log (Officer only)

### Health Check
- `GET /api/health` - Server health status

## 🧪 Testing the System

### Test 1: Health Check
```bash
curl http://localhost:5000/api/health
```

### Test 2: Create User Account
```bash
curl -X POST http://localhost:5000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@gmail.com","password":"Test@123"}'
```

### Test 3: Login
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@gmail.com","password":"Test@123"}'
```

### Test 4: Road Damage Detection
```bash
curl -X POST http://localhost:5000/api/detect \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "image=@path/to/road_image.jpg"
```

### Test 5: Submit Report
```bash
curl -X POST http://localhost:5000/api/reports \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "location": "Main Street, City",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "damage_percentage": 45.50,
    "severity": "Moderate",
    "detection_count": 3,
    "description": "Large pothole near intersection"
  }'
```

## 🚀 Complete User Flow

### For Regular Users:
1. **Sign up** → `test@gmail.com` (auto-assigned as "user")
2. **Login** → Redirected to User Dashboard
3. **Upload image** → AI detects road damage
4. **Submit report** → Officer notified

### For Officers:
1. **Login** → `admin@officer.com` (whitelisted)
2. **View reports** → See all submitted reports
3. **Assign worker** → Select worker for repair task
4. **Track status** → Monitor progress

### For Workers:
1. **Login** → `worker1@worker.com` (whitelisted)
2. **View tasks** → See assigned repair jobs
3. **Update status** → Mark as in-progress/completed

## 📊 Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    user_type TEXT NOT NULL,  -- 'user', 'officer', 'worker'
    name TEXT,
    created_at TEXT,
    last_login TEXT
);
```

### Reports Table
```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY,
    user_email TEXT,
    location TEXT,
    latitude REAL,
    longitude REAL,
    damage_percentage REAL,
    severity TEXT,  -- 'Minor', 'Moderate', 'Severe'
    detection_count INTEGER,
    description TEXT,
    annotated_image TEXT,  -- Base64
    original_image TEXT,   -- Base64
    status TEXT DEFAULT 'pending',  -- 'pending', 'assigned', 'in_progress', 'completed'
    assigned_worker TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

### Sessions Table
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    user_id INTEGER,
    email TEXT,
    user_type TEXT,
    created_at TEXT,
    expires_at TEXT  -- 24 hours from creation
);
```

## 🔒 Security Features

✅ **Token-Based Authentication** - Secure session tokens  
✅ **Password Hashing** - SHA-256 with email-specific salt  
✅ **Whitelist System** - Pre-approved officer/worker emails  
✅ **Role-Based Access Control** - User type validation  
✅ **Session Expiration** - 24-hour token lifetime  
✅ **Audit Logging** - All actions tracked  
✅ **CORS Protection** - Configurable cross-origin requests  
✅ **SQL Injection Prevention** - Parameterized queries  

## 🐛 Troubleshooting

### Issue: Backend won't start
**Solution:**
```bash
# Check if port 5000 is in use
netstat -ano | findstr :5000

# Kill process if needed
taskkill /PID <process_id> /F

# Or use different port
# Edit server.py line last: app.run(host='0.0.0.0', port=5001)
```

### Issue: YOLO model not loading
**Solution:**
1. Verify model path in `server.py`
2. Check file exists: `E:\road-damage\runs\detect\train22\weights\best.pt`
3. Ensure ultralytics installed: `pip install ultralytics`

### Issue: CORS errors in browser
**Solution:**
```python
# In server.py, update CORS settings:
CORS(app, supports_credentials=True, origins=["http://localhost:8080"])
```

### Issue: Database locked
**Solution:**
```bash
# Close all connections
# Delete tarfixer.db
# Restart server (auto-recreates)
```

### Issue: Login fails with correct password
**Solution:**
- Backend must be running on `http://localhost:5000`
- Check browser console for errors
- Verify API_BASE_URL in `api-client.js`

## 📈 Performance Optimization

### Backend:
- Use production WSGI server (Gunicorn/uWSGI)
- Enable caching for frequent queries
- Move to PostgreSQL for scalability
- Add Redis for session management

### Frontend:
- Minify JavaScript files
- Compress images
- Enable browser caching
- Use CDN for static assets

## 🌐 Production Deployment

### Option 1: Local Network Deployment
```python
# server.py - Allow local network access
app.run(host='0.0.0.0', port=5000)

# Access from other devices:
# http://<your-ip>:5000/api
```

### Option 2: Cloud Deployment (Heroku/AWS/Azure)
1. Add `Procfile`:
```
web: gunicorn server:app
```

2. Update `requirements.txt`
3. Set environment variables
4. Deploy to cloud platform

### Option 3: Docker Deployment
```dockerfile
FROM python:3.9
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
CMD ["python", "server.py"]
```

## 📞 Support

### System Status:
- Backend Health: `GET /api/health`
- Database: SQLite at `backend/tarfixer.db`
- Logs: Console output

### Default Test Accounts:
- Officer: `admin@officer.com` / `Admin@123`
- Worker: `worker1@worker.com` / `Worker@123`
- User: Any Gmail address / Any password (auto-created)

## ✅ Deployment Checklist

- [ ] Python 3.8+ installed
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] YOLO model path configured
- [ ] Backend server running (`python server.py`)
- [ ] Database initialized (auto-created on first run)
- [ ] Frontend can access backend (check browser console)
- [ ] Test login with default accounts
- [ ] Test road damage detection
- [ ] Test report submission
- [ ] Verify officer can see reports
- [ ] Verify worker can see assigned tasks

## 🎉 System is Ready!

Your TarFixer system is now fully integrated with:
- ✅ Backend API with authentication
- ✅ SQLite database for persistent storage
- ✅ YOLO-based road damage detection
- ✅ Role-based dashboards (User/Worker/Officer)
- ✅ Report management system
- ✅ Worker task assignment
- ✅ Audit logging
- ✅ Production-ready security

**Start the backend and begin detecting road damage!** 🚗🕳️
