# Deploying TarFixer to Hugging Face Spaces

Since Render's free tier (512MB RAM) is too small for running the YOLO AI model, we will move the **entire backend** to Hugging Face Spaces, which offers **16GB RAM** for free.

## Step 1: Create a Space
1.  Log in to [Hugging Face](https://huggingface.co/).
2.  Go to **New Space** (click your profile icon -> New Space).
3.  **Owner**: `Jeeva5655` (or your username).
4.  **Space Name**: `tarfixer-backend` (or similar).
5.  **License**: `MIT` (optional).
6.  **SDK**: Select **Docker**. (This is important! Do not select Streamlit or Gradio).
7.  **Hardware**: `Default (CPU basic · 2 vCPU · 16 GB · Free)`.
8.  Click **Create Space**.

## Step 2: Upload Files
You need to upload the following files to your new Space. You can do this via the "Files" tab on the Hugging Face website (Drag & Drop) or via Git.

**Required Files:**
1.  `Dockerfile` (The one I just created for you)
2.  `requirements.txt`
3.  `backend/` folder (The entire folder containing `server.py`, `model/`, etc.)
4.  `tarfixer.db` (Your database file)

> **Note:** Make sure the `backend/model/best.pt` file is inside the uploaded `backend/` folder!

## Step 3: Update api-client-v2.js
Once your Space is "Running", Hugging Face will give you a "Direct URL" (usually found by clicking the "Embed this space" button or looking at the browser URL, typically `https://jeeva5655-tarfixer-backend.hf.space`).

You need to update your `api-client-v2.js` file:
```javascript
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE_URL = isLocal 
    ? 'http://localhost:5000/api' 
    : 'https://jeeva5655-tarfixer-backend.hf.space/api'; // <--- REPLACE THIS WITH YOUR NEW HF URL
```

## Step 4: Verify
1.  Your backend is now running on a high-RAM server!
2.  The `/api/detect` endpoint should now work fast and without crashing.
