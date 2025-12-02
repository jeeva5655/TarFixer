# Deployment Walkthrough

I have prepared your backend for deployment to Render.

## 1. Code Preparation
- **Updated `server.py`**:
    - Modified to use relative paths for the model file.
    - Added dynamic port configuration (`os.environ.get('PORT')`) for cloud hosting.
    - Added database initialization on startup.
- **Created Configuration Files**:
    - `Procfile`: Tells Render how to start the app (`gunicorn backend.server:app`).
    - `requirements.txt`: Lists all Python dependencies.
    - `render.yaml`: Blueprint for Render services.
- **Model File**:
    - Copied `best.pt` to `backend/model/` so it's included in the git repository.

## 2. Git Deployment
- **Committed Changes**: All new files and changes have been committed.
- **Pushed to GitHub**: Successfully pushed to `https://github.com/jeeva5655/TarFixer`.

## 3. Next Steps (Action Required)
Since you are not logged in to Render, I could not complete the automated setup.

1.  **Log in to Render**: Go to [dashboard.render.com](https://dashboard.render.com/) and sign in (use GitHub if possible).
2.  **Create Service**:
    - Click **New +** -> **Web Service**.
    - Connect your GitHub repo `jeeva5655/TarFixer`.
    - Render should auto-detect the settings from `render.yaml` or you can manually set:
        - **Runtime**: Python 3
        - **Build Command**: `pip install -r requirements.txt`
        - **Start Command**: `gunicorn backend.server:app`
3.  **Update Frontend**:
    - Once deployed, copy the Render URL (e.g., `https://tarfixer-backend.onrender.com`).
    - Update `api-client.js` in your local code with this new URL.
    - Push the change to GitHub to update your Vercel frontend.
