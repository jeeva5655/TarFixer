/**
 * TarFixer Authentication System
 * Handles Google Sign-In and automatic dashboard routing based on email domain
 */

// Configuration
const AUTH_CONFIG = {
    // User type mappings based on email patterns
    userTypes: {
        officer: ['@officer.com', '@office.com'],
        worker: ['@worker.com'],
        user: ['@user.com', '@gmail.com', '@yahoo.com', '@outlook.com'] // General users
    },
    
    // Dashboard routes
    dashboards: {
        officer: '../Dashboard/Officer.HTML',
        worker: '../Dashboard/Worker.HTML',
        user: '../Dashboard/User.HTML'
    }
};

// Local Storage Keys
const STORAGE_KEYS = {
    AUTH_TOKEN: 'tarfixer_auth_token',
    USER_DATA: 'tarfixer_user_data',
    USER_TYPE: 'tarfixer_user_type'
};

/**
 * Initialize Google Sign-In
 */
function initGoogleAuth() {
    // Load Google Identity Services
    if (typeof google !== 'undefined' && google.accounts) {
        google.accounts.id.initialize({
            client_id: 'YOUR_GOOGLE_CLIENT_ID', // Replace with actual client ID
            callback: handleGoogleCallback,
            auto_select: false
        });
        
        // Render the Google Sign-In button
        const googleBtn = document.querySelector('.google-btn');
        if (googleBtn) {
            googleBtn.onclick = () => {
                google.accounts.id.prompt();
            };
        }
    }
}

/**
 * Handle Google Sign-In callback
 */
function handleGoogleCallback(response) {
    try {
        // Decode JWT token
        const credential = response.credential;
        const payload = parseJwt(credential);
        
        const email = payload.email;
        const name = payload.name;
        const picture = payload.picture;
        
        // Determine user type based on email
        const userType = determineUserType(email);
        
        if (!userType) {
            showError('Unable to determine account type. Please use a valid email domain.');
            return;
        }
        
        // Store authentication data
        storeAuthData({
            email,
            name,
            picture,
            userType,
            token: credential,
            timestamp: new Date().toISOString()
        });
        
        // Redirect to appropriate dashboard
        redirectToDashboard(userType);
        
    } catch (error) {
        console.error('Authentication error:', error);
        showError('Authentication failed. Please try again.');
    }
}

/**
 * Parse JWT token
 */
function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (error) {
        throw new Error('Invalid token format');
    }
}

/**
 * Determine user type based on email domain
 */
function determineUserType(email) {
    if (!email) return null;
    
    const emailLower = email.toLowerCase();
    
    // Check for officer domains
    for (const domain of AUTH_CONFIG.userTypes.officer) {
        if (emailLower.includes(domain)) {
            return 'officer';
        }
    }
    
    // Check for worker domains
    for (const domain of AUTH_CONFIG.userTypes.worker) {
        if (emailLower.includes(domain)) {
            return 'worker';
        }
    }
    
    // Check for user domains (catch-all for common email providers)
    for (const domain of AUTH_CONFIG.userTypes.user) {
        if (emailLower.includes(domain)) {
            return 'user';
        }
    }
    
    // Default to user type if none matched
    return 'user';
}

/**
 * Store authentication data
 */
function storeAuthData(data) {
    try {
        localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, data.token);
        localStorage.setItem(STORAGE_KEYS.USER_DATA, JSON.stringify(data));
        localStorage.setItem(STORAGE_KEYS.USER_TYPE, data.userType);
    } catch (error) {
        console.error('Failed to store auth data:', error);
    }
}

/**
 * Get stored authentication data
 */
function getAuthData() {
    try {
        const userData = localStorage.getItem(STORAGE_KEYS.USER_DATA);
        return userData ? JSON.parse(userData) : null;
    } catch (error) {
        console.error('Failed to retrieve auth data:', error);
        return null;
    }
}

/**
 * Check if user is authenticated
 */
function isAuthenticated() {
    const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    const userData = getAuthData();
    return !!(token && userData);
}

/**
 * Get current user type
 */
function getUserType() {
    return localStorage.getItem(STORAGE_KEYS.USER_TYPE);
}

/**
 * Redirect to appropriate dashboard
 */
function redirectToDashboard(userType) {
    const dashboardUrl = AUTH_CONFIG.dashboards[userType];
    if (dashboardUrl) {
        window.location.href = dashboardUrl;
    } else {
        console.error('Invalid user type:', userType);
        showError('Unable to redirect to dashboard.');
    }
}

/**
 * Logout user
 */
function logout() {
    localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER_DATA);
    localStorage.removeItem(STORAGE_KEYS.USER_TYPE);
    window.location.href = '../Login/Choose_login.html';
}

/**
 * Show error message
 */
function showError(message) {
    const errorDiv = document.getElementById('loginEmailError') || 
                     document.getElementById('regEmailError') || 
                     document.getElementById('error');
    
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorDiv.textContent = '';
            errorDiv.style.display = 'none';
        }, 5000);
    } else {
        alert(message);
    }
}

/**
 * Manual login with email and password
 * (Simulated - validates email pattern and stores data)
 */
async function manualLogin(email, password) {
    if (!email || !password) {
        showError('Please enter both email and password.');
        return false;
    }
    
    // Validate email format
    if (!isValidEmail(email)) {
        showError('Please enter a valid email address.');
        return false;
    }
    
    // Simulate authentication delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Determine user type
    const userType = determineUserType(email);
    
    if (!userType) {
        showError('Unable to determine account type. Please use a valid email domain.');
        return false;
    }
    
    // Extract name from email
    const name = email.split('@')[0].replace(/[._]/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
    
    // Store authentication data
    storeAuthData({
        email,
        name,
        picture: null,
        userType,
        token: 'manual_auth_' + Date.now(),
        timestamp: new Date().toISOString()
    });
    
    // Redirect to appropriate dashboard
    redirectToDashboard(userType);
    return true;
}

/**
 * Validate email format
 */
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Manual signup with email and password
 * (Simulated - validates and stores data)
 */
async function manualSignup(email, password, confirmPassword) {
    if (!email || !password || !confirmPassword) {
        showError('Please fill in all fields.');
        return false;
    }
    
    // Validate email format
    if (!isValidEmail(email)) {
        showError('Please enter a valid email address.');
        return false;
    }
    
    // Validate password strength
    if (!isStrongPassword(password)) {
        showError('Password must include A-Z, a-z, 0-9, symbol & 8+ chars');
        return false;
    }
    
    // Validate password match
    if (password !== confirmPassword) {
        showError('Passwords do not match.');
        return false;
    }
    
    // Simulate signup delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Determine user type
    const userType = determineUserType(email);
    
    if (!userType) {
        showError('Unable to determine account type. Please use a valid email domain.');
        return false;
    }
    
    // Extract name from email
    const name = email.split('@')[0].replace(/[._]/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
    
    // Store authentication data
    storeAuthData({
        email,
        name,
        picture: null,
        userType,
        token: 'manual_auth_' + Date.now(),
        timestamp: new Date().toISOString()
    });
    
    // Redirect to appropriate dashboard
    redirectToDashboard(userType);
    return true;
}

/**
 * Validate password strength
 */
function isStrongPassword(password) {
    return /[A-Z]/.test(password) &&
           /[a-z]/.test(password) &&
           /[0-9]/.test(password) &&
           /[\W_]/.test(password) &&
           password.length >= 8;
}

/**
 * Protect dashboard pages
 * Call this function at the start of each dashboard HTML
 */
function protectDashboard(requiredUserType) {
    if (!isAuthenticated()) {
        // Not logged in, redirect to login
        window.location.href = '../Login/Choose_login.html';
        return false;
    }
    
    const currentUserType = getUserType();
    
    if (requiredUserType && currentUserType !== requiredUserType) {
        // Wrong dashboard for user type, redirect to correct one
        redirectToDashboard(currentUserType);
        return false;
    }
    
    return true;
}

/**
 * Get current user info for dashboard display
 */
function getCurrentUser() {
    const userData = getAuthData();
    if (!userData) return null;
    
    return {
        name: userData.name || 'User',
        email: userData.email || '',
        userType: userData.userType || 'user',
        picture: userData.picture || null,
        initials: getInitials(userData.name || userData.email || 'U')
    };
}

/**
 * Get user initials
 */
function getInitials(name) {
    if (!name) return 'U';
    const parts = name.trim().split(/\s+/);
    let result = parts[0].charAt(0) || '';
    if (parts.length > 1) result += parts[1].charAt(0);
    return result.toUpperCase();
}

// Export functions for use in HTML files
if (typeof window !== 'undefined') {
    window.TarFixerAuth = {
        initGoogleAuth,
        manualLogin,
        manualSignup,
        logout,
        isAuthenticated,
        getUserType,
        getCurrentUser,
        protectDashboard,
        determineUserType
    };
}
