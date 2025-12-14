/**
 * TarFixer API Client
 * Frontend integration with backend API
 */

const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE_URL = isLocal
    ? 'http://localhost:5000/api'
    : 'https://tarfixer-backend.onrender.com/api';
console.log('🚀 TarFixer API Client v2.0 Loaded - URL:', API_BASE_URL);
const TOKEN_KEY = 'tarfixer_auth_token';
const USER_KEY = 'tarfixer_user_data';

class TarFixerAPI {
    constructor() {
        this.baseURL = API_BASE_URL;
        this.token = localStorage.getItem(TOKEN_KEY);
        this.user = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    }

    // ==========================================
    // AUTHENTICATION
    // ==========================================

    async signup(email, password, options = {}) {
        try {
            const payload = {
                email,
                password
            };

            if (typeof options === 'string') {
                payload.user_type = options;
            } else if (options && typeof options === 'object') {
                if (options.userType) payload.user_type = options.userType;
                if (options.phone) payload.phone = options.phone;
                if (options.name) payload.name = options.name;
            }

            const response = await fetch(`${API_BASE_URL}/auth/signup`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                const error = new Error(data.error || 'Signup failed');
                error.status = response.status;
                error.response = data;
                throw error;
            }

            // Auto-login after signup
            return await this.login(email, password);
        } catch (error) {
            console.error('Signup error:', error);
            throw error;
        }
    }

    async login(email, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Login failed');
            }

            // Store token and user data
            this.token = data.token;
            this.user = {
                email: data.email,
                name: data.name,
                userType: data.user_type,
                expiresAt: data.expires_at
            };

            localStorage.setItem(TOKEN_KEY, this.token);
            localStorage.setItem(USER_KEY, JSON.stringify(this.user));

            return this.user;
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    }

    async logout() {
        try {
            if (this.token) {
                await fetch(`${API_BASE_URL}/auth/logout`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.token}`
                    }
                });
            }
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            // Clear local data
            this.token = null;
            this.user = null;
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
        }
    }

    async validateSession() {
        try {
            if (!this.token) {
                return null;
            }

            const response = await fetch(`${API_BASE_URL}/auth/validate`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            if (!response.ok) {
                throw new Error('Session invalid');
            }

            return await response.json();
        } catch (error) {
            console.error('Session validation error:', error);
            // Clear tokens but don't redirect from here
            this.token = null;
            this.user = null;
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
            return null;
        }
    }

    isAuthenticated() {
        return !!this.token && !!this.user;
    }

    getUserType() {
        return this.user?.userType || null;
    }

    getUser() {
        return this.user;
    }

    // ==========================================
    // ROAD DAMAGE DETECTION
    // ==========================================

    async detectDamage(imageFile) {
        try {
            const formData = new FormData();
            formData.append('image', imageFile);

            // Check for test mode (URL has ?test=true)
            const isTestMode = window.location.search.includes('test=true');
            const headers = {
                'Authorization': `Bearer ${this.token}`
            };
            if (isTestMode) {
                headers['X-Test-Mode'] = 'true';
                console.log('⚠️ Test mode detected, adding X-Test-Mode header');
            }

            const response = await fetch(`${API_BASE_URL}/detect`, {
                method: 'POST',
                headers: headers,
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                if (response.status === 401) {
                    console.warn('Session expired or invalid. Redirecting to login...');
                    this.logout();
                    window.location.href = '/Login/Choose_login.html';
                    throw new Error('Session expired. Please login again.');
                }
                throw new Error(data.error || 'Detection failed');
            }

            return data;
        } catch (error) {
            console.error('Detection error:', error);
            throw error;
        }
    }

    // ==========================================
    // REPORT MANAGEMENT
    // ==========================================

    async createReport(reportData) {
        try {
            const response = await fetch(`${API_BASE_URL}/reports`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(reportData)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Report submission failed');
            }

            return data;
        } catch (error) {
            console.error('Report creation error:', error);
            throw error;
        }
    }

    async getReports(status = null) {
        try {
            const url = status
                ? `${API_BASE_URL}/reports?status=${status}`
                : `${API_BASE_URL}/reports`;

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch reports');
            }

            return data;
        } catch (error) {
            console.error('Get reports error:', error);
            throw error;
        }
    }

    async getMyReports() {
        try {
            const response = await fetch(`${API_BASE_URL}/reports/my`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch reports');
            }

            return data;
        } catch (error) {
            console.error('Get my reports error:', error);
            throw error;
        }
    }

    async getWorkers() {
        try {
            const response = await fetch(`${API_BASE_URL}/workers`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch workers');
            }

            return data;
        } catch (error) {
            console.error('Get workers error:', error);
            throw error;
        }
    }

    async createWorker(name, email, password = 'worker123', zone = 'Zone 1') {
        try {
            const response = await fetch(`${API_BASE_URL}/workers`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name, email, password, zone })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to create worker');
            }

            return data;
        } catch (error) {
            console.error('Create worker error:', error);
            throw error;
        }
    }

    async assignReport(reportId, workerEmail) {
        try {
            const response = await fetch(`${API_BASE_URL}/reports/${reportId}/assign`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ worker_email: workerEmail })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Assignment failed');
            }

            return data;
        } catch (error) {
            console.error('Assign report error:', error);
            throw error;
        }
    }

    async updateReportStatus(reportId, status) {
        try {
            const response = await fetch(`${API_BASE_URL}/reports/${reportId}/status`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Status update failed');
            }

            return data;
        } catch (error) {
            console.error('Update status error:', error);
            throw error;
        }
    }

    // ==========================================
    // WORKER ROUTES
    // ==========================================

    async getWorkerTasks() {
        try {
            const response = await fetch(`${API_BASE_URL}/workers/tasks`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch tasks');
            }

            return data;
        } catch (error) {
            console.error('Get worker tasks error:', error);
            throw error;
        }
    }

    // ==========================================
    // ADMIN ROUTES
    // ==========================================

    async getUsers() {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/users`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch users');
            }

            return data;
        } catch (error) {
            console.error('Get users error:', error);
            throw error;
        }
    }

    async getApprovals(status = 'pending', userType = null) {
        try {
            const params = new URLSearchParams();
            if (status) params.append('status', status);
            if (userType) params.append('user_type', userType);
            const response = await fetch(`${API_BASE_URL}/admin/approvals?${params.toString()}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch approvals');
            }

            return data;
        } catch (error) {
            console.error('Get approvals error:', error);
            throw error;
        }
    }

    async approveRequest(requestId, note = '') {
        return this.updateApproval(requestId, 'approve', note);
    }

    async rejectRequest(requestId, note = '') {
        return this.updateApproval(requestId, 'reject', note);
    }

    async updateApproval(requestId, action, note) {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/approvals/${requestId}/${action}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ note })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to update approval');
            }

            return data;
        } catch (error) {
            console.error('Update approval error:', error);
            throw error;
        }
    }

    async getAuditLog(limit = 100) {
        try {
            const response = await fetch(`${API_BASE_URL}/admin/audit?limit=${limit}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch audit log');
            }

            return data;
        } catch (error) {
            console.error('Get audit log error:', error);
            throw error;
        }
    }

    // ==========================================
    // HEALTH CHECK
    // ==========================================

    async checkHealth() {
        try {
            const response = await fetch(`${API_BASE_URL}/health`, {
                method: 'GET'
            });

            return await response.json();
        } catch (error) {
            console.error('Health check error:', error);
            return { status: 'error', error: error.message };
        }
    }
}

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TarFixerAPI;
}

// Initialize global instance for browser usage
const API = new TarFixerAPI();
