# TarFixer Authentication System

## Overview

The TarFixer application now has a complete authentication system that automatically routes users to the appropriate dashboard based on their email domain.

## How It Works

### 1. **Email-Based User Type Detection**

When a user logs in (via manual login or Google Sign-In), the system analyzes their email address to determine their role:

#### User Types & Email Patterns:

- **Officer Dashboard** (`@officer.com`, `@office.com`)
  - Example: `jeeva@officer.com`, `admin@office.com`
  - Access: Officer management dashboard

- **Worker Dashboard** (`@worker.com`)
  - Example: `ramesh@worker.com`
  - Access: Worker task management dashboard

- **User Dashboard** (All other emails including Gmail, Yahoo, Outlook, etc.)
  - Example: `jeeva@gmail.com`, `user@yahoo.com`, `anyone@example.com`
  - Access: Regular user dashboard for reporting road damage

### 2. **Authentication Flow**

```
User enters email → System analyzes domain → Determines user type → Redirects to appropriate dashboard
```

### 3. **Login Methods**

#### A. Manual Login (Email + Password)
- User enters email and password
- System validates email format
- System determines user type from email domain
- User is redirected to the correct dashboard

#### B. Google Sign-In
- User clicks "Continue with Google"
- Authenticates via Google
- System extracts email from Google account
- Automatically determines user type
- Redirects to appropriate dashboard

### 4. **Dashboard Protection**

Each dashboard is protected and will:
- Check if user is authenticated
- Verify user has correct role for that dashboard
- Redirect to login page if not authenticated
- Redirect to correct dashboard if user type doesn't match

## Usage Examples

### Example 1: Officer Login
```
Email: admin@officer.com
Password: (any password)
Result: → Redirected to Officer.HTML dashboard
```

### Example 2: Worker Login
```
Email: worker123@worker.com
Password: (any password)
Result: → Redirected to Worker.HTML dashboard
```

### Example 3: Regular User Login
```
Email: myemail@gmail.com
Password: (any password)
Result: → Redirected to User.HTML dashboard
```

### Example 4: Google Sign-In with Gmail
```
Google Account: anything@gmail.com
Result: → Automatically redirected to User.HTML dashboard
```

## Testing the System

### Test with Different Email Patterns:

1. **Test Officer Access:**
   - Email: `test@officer.com` or `admin@office.com`
   - Password: `Test@1234` (or any password meeting requirements)
   - Expected: Officer dashboard

2. **Test Worker Access:**
   - Email: `ramesh@worker.com`
   - Password: `Worker@123`
   - Expected: Worker dashboard

3. **Test User Access:**
   - Email: `yourname@gmail.com` or any other domain
   - Password: `User@1234`
   - Expected: User dashboard

## Features

### ✅ Automatic Role Detection
- No need to manually select user type
- System intelligently determines role from email

### ✅ Dashboard Protection
- Users cannot access dashboards they're not authorized for
- Automatic redirection to correct dashboard

### ✅ Persistent Sessions
- User stays logged in until they sign out
- Session data stored securely in browser

### ✅ User Information Display
- Each dashboard shows the logged-in user's name
- Shows email and user initials

### ✅ Multiple Login Methods
- Traditional email/password login
- Google Sign-In integration

## Technical Details

### Files Modified:
- `auth.js` - Core authentication system
- `Login/Choose_login.html` - Login page with auth integration
- `Dashboard/Officer.HTML` - Officer dashboard with protection
- `Dashboard/Worker.HTML` - Worker dashboard with protection
- `Dashboard/User.HTML` - User dashboard with protection

### Local Storage Keys:
- `tarfixer_auth_token` - Authentication token
- `tarfixer_user_data` - User profile data
- `tarfixer_user_type` - User role type

## Security Notes

⚠️ **Current Implementation:**
- This is a **client-side authentication system** for demonstration purposes
- Passwords are not actually verified (any password works)
- Real production use requires a backend server with proper authentication

🔒 **For Production:**
- Implement server-side authentication
- Use secure password hashing (bcrypt, argon2)
- Add JWT token validation
- Implement session management
- Add HTTPS/SSL
- Use environment variables for sensitive data

## Customization

### Adding New Email Domains

Edit `auth.js` and modify the `AUTH_CONFIG` object:

```javascript
userTypes: {
    officer: ['@officer.com', '@office.com', '@admin.com'], // Add more domains
    worker: ['@worker.com', '@contractor.com'], // Add more domains
    user: ['@user.com', '@gmail.com', '@yahoo.com'] // Add more domains
}
```

### Adding New User Types

1. Add new user type to `AUTH_CONFIG.userTypes`
2. Add dashboard route to `AUTH_CONFIG.dashboards`
3. Create new dashboard HTML file
4. Add protection using `TarFixerAuth.protectDashboard('newtype')`

## Troubleshooting

### Issue: Not redirecting to dashboard
**Solution:** Check browser console for errors, ensure auth.js is loaded

### Issue: Wrong dashboard loads
**Solution:** Check email domain mapping in auth.js

### Issue: Login button doesn't work
**Solution:** Ensure JavaScript is enabled and auth.js is properly loaded

### Issue: Google Sign-In not appearing
**Solution:** You need to set up Google OAuth credentials (see below)

## Google Sign-In Setup (Optional)

To enable real Google Sign-In:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Google Identity Services
4. Create OAuth 2.0 credentials
5. Replace `YOUR_GOOGLE_CLIENT_ID` in `auth.js` with your actual client ID
6. Add your domain to authorized domains

## Support

For issues or questions:
- Check browser console for error messages
- Verify all files are in correct directories
- Ensure relative paths are correct
- Test with different email patterns

---

**Note:** This system is designed for learning and demonstration. For production use, implement proper server-side authentication with a backend API.
