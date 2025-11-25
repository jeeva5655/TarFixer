# Firebase Google OAuth Setup Guide for TarFixer

This guide will help you set up Firebase Google Authentication for your TarFixer application.

## Step 1: Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project" or "Create a project"
3. Enter project name: **TarFixer** (or your preferred name)
4. Accept terms and click "Continue"
5. Disable Google Analytics (optional, you can enable it if you want)
6. Click "Create project"
7. Wait for project creation and click "Continue"

## Step 2: Register Your Web App

1. In the Firebase console, click the **Web icon** (</>) to add a web app
2. Enter app nickname: **TarFixer Web**
3. Check "Also set up Firebase Hosting" (optional)
4. Click "Register app"
5. Copy the Firebase configuration object (you'll need this later)
6. Click "Continue to console"

## Step 3: Enable Google Authentication

1. In the left sidebar, click **Build** → **Authentication**
2. Click "Get started" button
3. Click on the **"Sign-in method"** tab
4. Click on **"Google"** from the providers list
5. Toggle the **Enable** switch to ON
6. Set project support email (your email)
7. Click **"Save"**

## Step 4: Configure Firebase in Your Project

1. Open `firebase-config.js` in your project
2. Replace the placeholder values with your Firebase configuration:

```javascript
const firebaseConfig = {
  apiKey: "YOUR_API_KEY_HERE",              // Replace with your actual API key
  authDomain: "YOUR_PROJECT_ID.firebaseapp.com",  // Replace with your project ID
  projectId: "YOUR_PROJECT_ID",             // Replace with your project ID
  storageBucket: "YOUR_PROJECT_ID.appspot.com",   // Replace with your project ID
  messagingSenderId: "YOUR_MESSAGING_SENDER_ID",  // Replace with your sender ID
  appId: "YOUR_APP_ID"                      // Replace with your app ID
};
```

**Example (with fake values):**
```javascript
const firebaseConfig = {
  apiKey: "AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  authDomain: "tarfixer-abc123.firebaseapp.com",
  projectId: "tarfixer-abc123",
  storageBucket: "tarfixer-abc123.appspot.com",
  messagingSenderId: "123456789012",
  appId: "1:123456789012:web:abcdef123456"
};
```

## Step 5: Add Authorized Domains (for Production)

1. In Firebase Console, go to **Authentication** → **Settings** tab
2. Scroll down to **Authorized domains**
3. Add your domains:
   - `localhost` (already included by default)
   - Your production domain (e.g., `tarfixer.com`)
   - Your GitHub Pages domain (if using, e.g., `jeeva5655.github.io`)

## Step 6: Test the Integration

1. Make sure both servers are running:
   ```powershell
   # Backend (Terminal 1)
   .venv\Scripts\python.exe backend\server.py
   
   # Frontend (Terminal 2)
   .venv\Scripts\python.exe -m http.server 8000
   ```

2. Open `http://localhost:8000/Login/Choose_login.html`
3. Click **"Continue with Google"** button
4. Select your Google account
5. Grant permissions
6. You should be automatically signed in and redirected to the appropriate dashboard

## How It Works

### User Flow:
1. User clicks "Continue with Google" button
2. Firebase opens Google Sign-In popup
3. User selects Google account and grants permissions
4. Firebase returns user info (email, name, Google ID, ID token)
5. Frontend sends this info to backend API (`/api/auth/google-login` or `/api/auth/google-signup`)
6. Backend checks if user exists:
   - **Existing user:** Creates session and returns token
   - **New user:** Creates account (with approval check for officers/workers)
7. Frontend stores token and redirects to dashboard

### User Type Determination:
- **Officer accounts:** `*@officer.com` or `*@office.com` → Requires whitelist approval
- **Worker accounts:** `*@worker.com` → Requires whitelist approval  
- **Public users:** All other emails (gmail.com, yahoo.com, etc.) → Auto-approved as "user"

### Whitelist System:
- Officers and workers **MUST** be on the whitelist to access the system
- Public users (Gmail, Yahoo, etc.) are automatically approved
- Pending accounts can be reviewed in the Officer Dashboard → "Access Requests"

## Troubleshooting

### Popup Blocked Error
- **Solution:** Allow popups for localhost in your browser settings
- **Alternative:** The code can fall back to redirect method if needed

### "Firebase not initialized" Error
- **Solution:** Make sure you've added your Firebase configuration to `firebase-config.js`
- Check browser console for detailed error messages

### "Account requires approval" Message
- **Expected:** This is normal for officer/worker accounts
- The account will be visible in Officer Dashboard for approval

### CORS Errors
- **Solution:** Backend already has CORS enabled for all origins
- For production, update CORS settings in `backend/server.py`

## Security Notes

1. **API Key Security:**
   - Firebase API keys are safe to include in client-side code
   - They are restricted by domain in Firebase Console
   - They only allow Firebase services, not full Google Cloud access

2. **ID Token Verification:**
   - Backend receives Google ID token for verification
   - Can add server-side verification using Firebase Admin SDK (optional)

3. **Session Security:**
   - Backend generates its own secure session tokens
   - Tokens stored in localStorage with 7-day expiration
   - Users can sign out to invalidate tokens

## Next Steps

1. **Add Firebase Admin SDK** (Optional - for server-side token verification):
   ```bash
   pip install firebase-admin
   ```

2. **Deploy to Production:**
   - Add production domain to Firebase Authorized Domains
   - Update CORS settings in backend
   - Use environment variables for sensitive config

3. **Enhance Security:**
   - Implement rate limiting for auth endpoints
   - Add CAPTCHA for signup (Firebase App Check)
   - Enable MFA (Multi-Factor Authentication)

## Support

If you encounter issues:
1. Check Firebase Console → Authentication → Users (to see registered users)
2. Check browser Developer Console for errors
3. Check backend terminal for API logs
4. Review Firebase documentation: https://firebase.google.com/docs/auth/web/google-signin

---

**Your Firebase Google OAuth authentication is now ready! 🎉**

Users can now sign in with their Google accounts seamlessly.
