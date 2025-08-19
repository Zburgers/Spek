// Main Application Entry Point - Shared across all pages
class SpekApp {
    constructor() {
        this.currentUser = null;
        this.isAuthenticated = false;
        this.apiClient = new APIClient();
        this.notifications = new NotificationManager();
        this.pageInitializers = []; // <-- Add this
        window.spekApp = this; // Expose global instance
    }

    async init() {
        await this.checkAuthStatus();
        this.updateUIForAuth();
        console.log('Spek App initialized');

        for (const initializer of this.pageInitializers) {
            initializer();
        }
    }

    onReady(callback) {
        this.pageInitializers.push(callback);
    }

    async checkAuthStatus() {
        const token = localStorage.getItem('access_token');
        if (token) {
            try {
                const user = await this.apiClient.getCurrentUser();
                this.setUser(user);
            } catch (error) {
                console.log('Token invalid, clearing auth');
                this.clearAuth();
            }
        } else {
            this.clearAuth();
        }
    }

    setUser(user) {
        this.currentUser = user;
        this.isAuthenticated = true;
    }

    clearAuth() {
        this.currentUser = null;
        this.isAuthenticated = false;
        localStorage.removeItem('access_token');
    }
    
    // Updates UI elements present on all pages (e.g., nav bar)
    updateUIForAuth() {
        const authButtonsContainer = document.querySelector('.auth-buttons');
        if (!authButtonsContainer) return;

        if (this.isAuthenticated) {
            authButtonsContainer.innerHTML = `
                <a href="/chat" class="btn btn-primary">Go to Chat</a>
                <button id="nav-logout-btn" class="btn btn-secondary">Logout</button>
            `;
            document.getElementById('nav-logout-btn').addEventListener('click', async () => {
                await this.apiClient.logout();
                this.clearAuth();
                window.location.href = '/';
            });
        } else {
            authButtonsContainer.innerHTML = `
                <a href="/login" class="btn btn-secondary">Sign In</a>
                <a href="/login?mode=register" class="btn btn-primary">Get Started</a>
            `;
        }
    }
}

// API Client Class
class APIClient {
    constructor() {
        this.baseURL = '/api/v1';
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        
        const token = localStorage.getItem('access_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const config = { ...options, headers };

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: `HTTP error! status: ${response.status}` }));
                throw new Error(errorData.detail);
            }
            return response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${this.baseURL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
            throw new Error(errorData.detail);
        }

        const tokens = await response.json();
        localStorage.setItem('access_token', tokens.access_token);
        return tokens;
    }

    async register(userData) {
        return this.request('/user', {
            method: 'POST',
            body: JSON.stringify(userData),
        });
    }

    async logout() {
        try {
            await this.request('/logout', { method: 'POST' });
        } catch (error) {
            console.error('Logout API call failed, but clearing client-side session anyway.', error);
        } finally {
            window.spekApp.clearAuth();
        }
    }

    async getCurrentUser() {
        return this.request('/user/me/');
    }

    async sendMessage(message) {
        return this.request('/chat/text', {
            method: 'POST',
            body: JSON.stringify({ message }),
        });
    }
}

// Simple Notification Manager
class NotificationManager {
    error(message) {
        // You can implement a more sophisticated notification system here
        alert(`Error: ${message}`);
    }
    success(message) {
        alert(`Success: ${message}`);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new SpekApp();
    app.init();
});