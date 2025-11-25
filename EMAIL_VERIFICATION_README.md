# Email Verification System - Password Reset

## Overview
The password reset feature now includes **two-factor email verification** for enhanced security:

1. **Email with Reset Link** - User clicks link to access reset page
2. **6-Digit Verification Code** - Sent via separate email, required to complete reset

## Features Implemented

### 🔒 Security Features
- **Rate Limiting**: 3 requests per 15 minutes per email
- **Brute-Force Protection**: 10 failed attempts per hour per IP
- **Verification Codes**: 6-digit codes expire in 10 minutes
- **Session Invalidation**: All active sessions terminated on password reset
- **Audit Logging**: All security events logged with IP addresses

### 📧 Email System
- Professional HTML email templates
- Fallback text versions for all emails
- Gmail, SendGrid, AWS SES, Outlook support
- Development mode (prints to console if not configured)

## Setup Instructions

### 1. Configure Email Service

Copy the example config:
```bash
cd backend
copy email_config.example.py email_config.py
```

Edit `backend/email_config.py` with your credentials:

#### For Gmail (Recommended):
1. Go to https://myaccount.google.com/security
2. Enable **2-Step Verification**
3. Go to https://myaccount.google.com/apppasswords
4. Create app password for "TarFixer"
5. Copy the 16-character password

Update in `email_config.py`:
```python
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-16-char-app-password'
EMAIL_FROM_ADDRESS = 'TarFixer <your-email@gmail.com>'
```

### 2. Test the System

#### Without Email Config (Development):
- Backend will print emails to console
- You can see the verification code in terminal output
- Reset links still work normally

#### With Email Config:
- Actual emails will be sent
- Check spam folder if not received
- Verification codes expire in 10 minutes

## User Flow

### Password Reset Process:

1. **User clicks "Forgot Password"**
   - Enters their email address
   - Clicks "Send Reset Link"

2. **System sends 2 emails:**
   - **Email 1**: Password reset link with clickable button
   - **Email 2**: 6-digit verification code

3. **User opens reset link:**
   - Redirected to reset password page
   - Must enter verification code from email
   - Creates new password

4. **Security validations:**
   - Verification code must match
   - Code must not be expired (10 min)
   - Password must meet strength requirements
   - All active sessions are terminated

## API Endpoints

### POST `/api/auth/forgot-password`
Request password reset
```json
{
  "email": "user@example.com"
}
```

### POST `/api/auth/verify-code`
Verify 6-digit code (optional pre-check)
```json
{
  "token": "reset-token-from-url",
  "code": "123456"
}
```

### POST `/api/auth/reset-password`
Complete password reset
```json
{
  "token": "reset-token-from-url",
  "code": "123456",
  "password": "NewSecurePassword123!"
}
```

## Database Schema

### `password_resets` table:
```sql
- token TEXT UNIQUE          -- URL token
- verification_code TEXT     -- 6-digit code
- expires_at TEXT           -- Expiration timestamp
- used INTEGER              -- 0=unused, 1=used
- created_at TEXT           -- Creation timestamp
```

### `reset_attempts` table:
```sql
- ip_address TEXT           -- Client IP
- attempted_at TEXT         -- Attempt timestamp
```

## Security Best Practices

✅ **Implemented:**
- Rate limiting by email and IP
- Verification codes expire quickly (10 min)
- Session invalidation on password change
- Audit logging with IP tracking
- Strong password requirements
- Token single-use enforcement

⚠️ **Production Recommendations:**
- Use HTTPS in production
- Remove `dev_*` fields from API responses
- Set up proper email domain (no Gmail in production)
- Consider adding CAPTCHA for forgot password
- Monitor audit logs for suspicious activity

## Troubleshooting

### Emails not sending?
1. Check `email_config.py` credentials
2. For Gmail: Ensure App Password (not regular password)
3. For Gmail: 2-Step Verification must be enabled
4. Check backend console for error messages
5. Test with development mode first (empty credentials)

### Verification code not working?
1. Check code hasn't expired (10 min limit)
2. Ensure code matches exactly (6 digits)
3. Check for typos or spaces
4. Request new reset link if expired

### Rate limit errors?
- Wait 15 minutes before requesting again
- Max 3 requests per email per 15 minutes
- Max 10 failed attempts per IP per hour

## File Structure

```
backend/
├── server.py                    # Main backend with email functions
├── email_config.py             # Your email credentials (gitignored)
└── email_config.example.py     # Template for email setup

Login/
├── Choose_login.html           # Login page with "Forgot Password" button
└── reset-password.html         # Password reset form with code input

.gitignore                      # Excludes email_config.py
```

## Email Templates

Both emails include:
- Professional HTML design with gradients
- TarFixer branding
- Clear instructions
- Expiration warnings
- Plain text fallback

### Email 1: Reset Link
- Large "Reset Password" button
- Copy-paste link fallback
- 1-hour expiration notice

### Email 2: Verification Code
- Large centered code (easy to read)
- Letter-spaced for clarity
- 10-minute expiration notice
- Security reminders

## Testing Checklist

- [ ] Email config properly set up
- [ ] Forgot password sends 2 emails
- [ ] Reset link opens correct page
- [ ] Verification code validates correctly
- [ ] Invalid code shows error
- [ ] Expired code rejected
- [ ] Password strength validated
- [ ] Successful reset redirects to login
- [ ] Rate limiting works (3 per 15min)
- [ ] Brute-force protection works (10 per hour)

## Support

For issues or questions:
1. Check backend console for detailed error messages
2. Verify email configuration
3. Check audit logs in database
4. Test with development mode first
