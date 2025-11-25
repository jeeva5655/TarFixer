# Email Configuration Template for TarFixer
# 
# SETUP INSTRUCTIONS:
# 1. Copy this file to 'email_config.py' (same directory)
# 2. Replace the placeholder values below with your actual credentials
# 3. Never commit email_config.py to git (it's in .gitignore)

# =============================================================================
# GMAIL SETUP (Recommended for Development)
# =============================================================================
# 
# Step-by-step guide to get Gmail working:
# 
# 1. Go to Google Account Security:
#    https://myaccount.google.com/security
# 
# 2. Enable 2-Step Verification:
#    - Scroll to "How you sign in to Google"
#    - Click "2-Step Verification"
#    - Follow the setup wizard
# 
# 3. Generate App Password:
#    - Go to https://myaccount.google.com/apppasswords
#    - Select app: "Mail"
#    - Select device: "Windows Computer" (or Other)
#    - Click "Generate"
#    - Copy the 16-character password (remove spaces)
# 
# 4. Update the values below:
#    - EMAIL_HOST_USER: Your Gmail address
#    - EMAIL_HOST_PASSWORD: The 16-character app password
#    - EMAIL_FROM_ADDRESS: Your Gmail (or custom sender name)
#

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'  # ← Replace with your Gmail
EMAIL_HOST_PASSWORD = 'xxxxxxxxxxxxxxxx'  # ← Replace with 16-char app password
EMAIL_FROM_ADDRESS = 'TarFixer <your-email@gmail.com>'  # ← Replace with your Gmail


# =============================================================================
# ALTERNATIVE EMAIL SERVICES
# =============================================================================

# SendGrid:
# ----------
# EMAIL_HOST = 'smtp.sendgrid.net'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'apikey'
# EMAIL_HOST_PASSWORD = 'SG.your-sendgrid-api-key'
# EMAIL_FROM_ADDRESS = 'TarFixer <noreply@yourdomain.com>'

# AWS SES:
# ---------
# EMAIL_HOST = 'email-smtp.us-east-1.amazonaws.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-aws-smtp-username'
# EMAIL_HOST_PASSWORD = 'your-aws-smtp-password'
# EMAIL_FROM_ADDRESS = 'TarFixer <noreply@yourdomain.com>'

# Outlook/Office365:
# -------------------
# EMAIL_HOST = 'smtp.office365.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@outlook.com'
# EMAIL_HOST_PASSWORD = 'your-outlook-password'
# EMAIL_FROM_ADDRESS = 'TarFixer <your-email@outlook.com>'


# =============================================================================
# TESTING WITHOUT EMAIL
# =============================================================================
# If you leave EMAIL_HOST_USER or EMAIL_HOST_PASSWORD empty, the system will
# still work but will print email content to console instead of sending.
# Useful for development/testing without email setup.
