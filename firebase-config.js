/**
 * Firebase Configuration for TarFixer
 * Google OAuth Authentication
 */

// Firebase configuration - Your actual Firebase project credentials
const firebaseConfig = {
  apiKey: "AIzaSyClMMKj1_Vgm9El6NFNVz64p5DHpYLhHZw",
  authDomain: "road-damage-detection-824c4.firebaseapp.com",
  projectId: "road-damage-detection-824c4",
  storageBucket: "road-damage-detection-824c4.firebasestorage.app",
  messagingSenderId: "895762072407",
  appId: "1:895762072407:web:ffd74956409f8358bef412",
  measurementId: "G-PQERKYQFHM"
};

// Initialize Firebase
let auth = null;
let googleProvider = null;

// Load Firebase dynamically
function initializeFirebase() {
  return new Promise((resolve, reject) => {
    // Wait a bit for Firebase SDK to load
    const checkFirebase = () => {
      if (typeof firebase !== 'undefined') {
        try {
          // Initialize Firebase App
          if (!firebase.apps.length) {
            firebase.initializeApp(firebaseConfig);
          }
          
          // Initialize Firebase Auth
          auth = firebase.auth();
          googleProvider = new firebase.auth.GoogleAuthProvider();
          
          // Optional: Add custom parameters
          googleProvider.addScope('profile');
          googleProvider.addScope('email');
          
          // Optional: Force account selection
          googleProvider.setCustomParameters({
            prompt: 'select_account'
          });
          
          console.log('✅ Firebase initialized successfully');
          resolve(true);
        } catch (error) {
          console.error('❌ Firebase initialization error:', error);
          reject(error);
        }
      } else {
        console.warn('Waiting for Firebase SDK to load...');
        setTimeout(checkFirebase, 100);
      }
    };
    
    checkFirebase();
  });
}

// Sign in with Google Popup
async function signInWithGooglePopup() {
  try {
    if (!auth || !googleProvider) {
      throw new Error('Firebase not initialized. Call initializeFirebase() first.');
    }
    
    const result = await auth.signInWithPopup(googleProvider);
    
    // Get user info
    const user = result.user;
    const credential = result.credential;
    
    return {
      success: true,
      user: {
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
        photoURL: user.photoURL,
        emailVerified: user.emailVerified
      },
      credential: credential,
      idToken: await user.getIdToken()
    };
  } catch (error) {
    console.error('Google Sign-In Error:', error);
    
    // Handle specific error codes
    let errorMessage = 'Failed to sign in with Google';
    
    switch (error.code) {
      case 'auth/popup-closed-by-user':
        errorMessage = 'Sign-in popup was closed';
        break;
      case 'auth/popup-blocked':
        errorMessage = 'Sign-in popup was blocked by browser';
        break;
      case 'auth/cancelled-popup-request':
        errorMessage = 'Sign-in cancelled';
        break;
      case 'auth/account-exists-with-different-credential':
        errorMessage = 'An account already exists with the same email';
        break;
      default:
        errorMessage = error.message;
    }
    
    return {
      success: false,
      error: errorMessage,
      code: error.code
    };
  }
}

// Sign in with Google Redirect (alternative method)
async function signInWithGoogleRedirect() {
  try {
    if (!auth || !googleProvider) {
      throw new Error('Firebase not initialized');
    }
    
    await auth.signInWithRedirect(googleProvider);
  } catch (error) {
    console.error('Google Redirect Error:', error);
    throw error;
  }
}

// Get redirect result
async function getRedirectResult() {
  try {
    if (!auth) {
      throw new Error('Firebase not initialized');
    }
    
    const result = await auth.getRedirectResult();
    
    if (result.user) {
      return {
        success: true,
        user: {
          uid: result.user.uid,
          email: result.user.email,
          displayName: result.user.displayName,
          photoURL: result.user.photoURL,
          emailVerified: result.user.emailVerified
        },
        idToken: await result.user.getIdToken()
      };
    }
    
    return { success: false, error: 'No user found' };
  } catch (error) {
    console.error('Redirect Result Error:', error);
    return { success: false, error: error.message };
  }
}

// Sign out
async function signOutFirebase() {
  try {
    if (!auth) {
      throw new Error('Firebase not initialized');
    }
    
    await auth.signOut();
    console.log('✅ Signed out successfully');
    return { success: true };
  } catch (error) {
    console.error('Sign Out Error:', error);
    return { success: false, error: error.message };
  }
}

// Get current user
function getCurrentUser() {
  if (!auth) {
    return null;
  }
  return auth.currentUser;
}

// Listen to auth state changes
function onAuthStateChanged(callback) {
  if (!auth) {
    throw new Error('Firebase not initialized');
  }
  return auth.onAuthStateChanged(callback);
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    initializeFirebase,
    signInWithGooglePopup,
    signInWithGoogleRedirect,
    getRedirectResult,
    signOutFirebase,
    getCurrentUser,
    onAuthStateChanged
  };
}
