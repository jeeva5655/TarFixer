# 🚀 Deploying TarFixer Backend to Render

This guide will help you deploy your Flask backend and database to Render.com for free.

## ⚠️ Important Note About Database
Since we are using SQLite (`tarfixer.db`), the database is stored as a file. On Render's **Free Tier**, the file system is **ephemeral**, meaning **all data will be lost** every time the server restarts or you deploy new code.

**Options:**
1.  **Accept Data Reset**: Good for demos. The database will reset to empty (with default users) on every deploy.
2.  **Use Persistent Disk**: Upgrade to a paid Render plan ($7/mo) and add a Disk.
3.  **Migrate to PostgreSQL**: Render provides a managed PostgreSQL database (Free for 90 days). This requires code changes to migrate from SQLite to Postgres.

For now, we will proceed with **Option 1 (Free Tier)**.

## 📋 Prerequisites
1.  You have a GitHub account.
2.  The code is pushed to your GitHub repository: `https://github.com/jeeva5655/TarFixer`

## 🚀 Deployment Steps

### Step 1: Push Latest Changes
I have updated your code to be compatible with Render (added `Procfile`, `requirements.txt`, and fixed paths). You must push these changes to GitHub first.

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### Step 2: Create Service on Render
1.  Go to [dashboard.render.com](https://dashboard.render.com/).
2.  Click **New +** -> **Web Service**.
3.  Select **Build and deploy from a Git repository**.
4.  Connect your GitHub account and select `jeeva5655/TarFixer`.
5.  **Configure the service**:
    *   **Name**: `tarfixer-backend`
    *   **Region**: Closest to you (e.g., Singapore or Frankfurt)
    *   **Branch**: `main`
    *   **Runtime**: `Python 3`
    *   **Build Command**: `pip install -r requirements.txt` (should be auto-filled)
    *   **Start Command**: `gunicorn backend.server:app` (should be auto-filled from Procfile)
    *   **Instance Type**: `Free`

6.  Click **Create Web Service**.

### Step 3: Wait for Build
Render will start building your app. It may take a few minutes to install dependencies (especially `ultralytics` and `torch`).
*   **Note**: If the build fails due to memory (OOM), try to remove `ultralytics` from `requirements.txt` temporarily or upgrade to a paid plan. The free tier has 512MB RAM which is tight for YOLO.

### Step 4: Get Your Backend URL
Once deployed, you will see a URL like `https://tarfixer-backend.onrender.com`.
Copy this URL.

### Step 5: Update Frontend
Now you need to tell your Vercel frontend to talk to this new backend.

1.  Open `api-client.js` in your local code.
2.  Change line 6:
    ```javascript
    // OLD
    const API_BASE_URL = 'http://localhost:5000/api';
    
    // NEW (Replace with your actual Render URL)
    const API_BASE_URL = 'https://tarfixer-backend.onrender.com/api';
    ```
3.  Commit and push these changes to GitHub.
    ```bash
    git add api-client.js
    git commit -m "Update API URL to production"
    git push origin main
    ```
4.  Vercel should automatically redeploy your frontend with the new configuration.

## 🧪 Verification
1.  Open your Vercel app (`https://tar-fixer.vercel.app/`).
2.  Try to **Sign Up** (since the database is fresh).
3.  If it works, your backend is live!

## 🐛 Troubleshooting
*   **Database Reset**: Remember, if the site "forgets" your user, it's because the free server restarted.
*   **Cold Starts**: The free server sleeps after inactivity. The first request might take 50+ seconds.
*   **Build Failures**: Check the logs in Render dashboard.
