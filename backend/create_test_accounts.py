"""
Create test accounts in the TarFixer database
Run this script to create test accounts for development
"""

import sqlite3
import hashlib
from datetime import datetime

# Database path
DATABASE = "tarfixer.db"

def hash_password(password, email):
    """Hash password with email-specific salt (same as server.py)"""
    salt = f"TARFIXER_SALT_2025_SECURE_{email.lower()}"
    return hashlib.sha256((password + salt).encode()).hexdigest()

def create_test_accounts():
    """Create test accounts for all user types"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Test accounts data
    test_accounts = [
        # User accounts
        {
            'email': 'user@test.com',
            'password': 'password123',
            'user_type': 'user',
            'name': 'Test User',
            'approved': 1
        },
        {
            'email': 'john@gmail.com',
            'password': 'password123',
            'user_type': 'user',
            'name': 'John Doe',
            'approved': 1
        },
        # Officer accounts
        {
            'email': 'officer@test.com',
            'password': 'officer123',
            'user_type': 'officer',
            'name': 'Test Officer',
            'approved': 1
        },
        {
            'email': 'admin@officer.com',
            'password': 'admin123',
            'user_type': 'officer',
            'name': 'Admin Officer',
            'approved': 1
        },
        # Worker accounts
        {
            'email': 'worker@test.com',
            'password': 'worker123',
            'user_type': 'worker',
            'name': 'Test Worker',
            'approved': 1
        },
        {
            'email': 'ramesh@worker.com',
            'password': 'worker123',
            'user_type': 'worker',
            'name': 'Ramesh K',
            'approved': 1
        }
    ]
    
    print("Creating test accounts...")
    print("=" * 60)
    
    for account in test_accounts:
        email = account['email']
        password = account['password']
        user_type = account['user_type']
        name = account['name']
        approved = account['approved']
        
        # Hash the password
        password_hash = hash_password(password, email)
        
        try:
            # Check if user already exists
            c.execute('SELECT email FROM users WHERE email = ?', (email,))
            if c.fetchone():
                print(f"⚠️  {email} already exists - skipping")
                continue
            
            # Insert new user
            c.execute('''
                INSERT INTO users (email, password_hash, user_type, name, approved, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (email, password_hash, user_type, name, approved, datetime.now().isoformat()))
            
            conn.commit()
            print(f"✅ Created: {email} ({user_type}) - Password: {password}")
            
        except Exception as e:
            print(f"❌ Error creating {email}: {e}")
    
    conn.close()
    
    print("=" * 60)
    print("\n📋 TEST ACCOUNTS SUMMARY:")
    print("\nUSER ACCOUNTS (Can report road damage):")
    print("  • user@test.com / password123")
    print("  • john@gmail.com / password123")
    print("\nOFFICER ACCOUNTS (Can manage reports & assign workers):")
    print("  • officer@test.com / officer123")
    print("  • admin@officer.com / admin123")
    print("\nWORKER ACCOUNTS (Can view assigned tasks):")
    print("  • worker@test.com / worker123")
    print("  • ramesh@worker.com / worker123")
    print("\n✅ You can now login with any of these accounts!")

if __name__ == "__main__":
    create_test_accounts()
