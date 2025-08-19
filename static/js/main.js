// Main Application Entry Point
class SpekApp {
    constructor() {
        this.currentUser = null;
        this.isAuthenticated = false;
        this.apiClient = new APIClient();
        this.router = new Router();
        this.notifications = new NotificationManager();
        this.tokenManager = new SecureTokenManager(); // Secure token storage
        window.spekApp = this; // Expose for router auth checks
        this.init();
    }

    async init() {
        // Check authentication status
        await this.checkAuthStatus();
        // Initialize router (hash-based)
        this.router.init();
        // Setup global event listeners
        this.setupEventListeners();
        // Initialize components
        this.initializeComponents();
        console.log('Spek App initialized');
    }

    async checkAuthStatus() {
        // Try to get a valid token (will attempt refresh if needed)
        const token = await this.tokenManager.getValidToken();
        if (token) {
            try {
                // Verify token with server
                const user = await this.apiClient.getCurrentUser();
                this.setUser(user);
            } catch (error) {
                console.log('Token invalid, clearing auth');
                this.clearAuth();
            }
        }
    }

    setUser(user) {
        this.currentUser = user;
        this.isAuthenticated = true;
        this.updateUIForAuth();
    }

    clearAuth() {
        this.currentUser = null;
        this.isAuthenticated = false;
        this.tokenManager.clearTokens(); // Clear tokens from memory
        this.updateUIForAuth();
    }

    updateUIForAuth() {
        // Update navigation and UI based on auth status
        const authButtons = document.querySelector('.auth-buttons');
        
        if (authButtons) {
            if (this.isAuthenticated) {
                authButtons.innerHTML = `
                    <a href="#/chat" class="btn btn-primary" data-link>Chat</a>
                    <button id="nav-logout-btn" class="btn btn-outline">Logout</button>
                `;
                
                // Add logout handler
                const logoutBtn = document.getElementById('nav-logout-btn');
                if (logoutBtn) {
                    logoutBtn.addEventListener('click', async () => {
                        try {
                            await this.apiClient.logout();
                            this.clearAuth();
                            this.notifications.success('Successfully logged out');
                            this.router.navigateTo('#/');
                        } catch (error) {
                            console.error('Logout error:', error);
                            this.clearAuth();
                            this.router.navigateTo('#/');
                        }
                    });
                }
            } else {
                authButtons.innerHTML = `
                    <a href="#/login" class="btn btn-outline" data-link>Sign In</a>
                    <a href="#/login?mode=register" class="btn btn-primary" data-link>Get Started</a>
                `;
            }
        }
        
        // Update Try Now link
        const tryNowLinks = document.querySelectorAll('a[href="#/chat"]');
        tryNowLinks.forEach(link => {
            if (!this.isAuthenticated) {
                link.href = '#/login';
                link.textContent = link.textContent.includes('Try') ? 'Try Now' : link.textContent;
            } else {
                link.href = '#/chat';
            }
        });
        
        // Re-render current view if it's the home view to update content
        if (this.router && this.router.currentRoute === '#/') {
            this.router.loadView('home');
        }
    }

    setupEventListeners() {
        // Global error handler
        window.addEventListener('error', (event) => {
            console.error('Global error:', event.error);
            this.notifications.error('An unexpected error occurred');
        });

        // Handle navigation clicks
        document.addEventListener('click', (event) => {
            const link = event.target.closest('a[href]');
            if (link && link.href.startsWith(window.location.origin)) {
                const url = new URL(link.href);
                if (url.pathname !== window.location.pathname) {
                    event.preventDefault();
                    this.router.navigate(url.pathname + url.search);
                }
            }
        });

        // Handle mobile navigation toggle
        const navToggle = document.querySelector('.nav-toggle');
        const navMenu = document.querySelector('.nav-menu');
        
        if (navToggle && navMenu) {
            navToggle.addEventListener('click', () => {
                navMenu.classList.toggle('active');
            });
        }
    }

    initializeComponents() {
        // Initialize any page-specific components
        this.initializeCurrentPage();
    }

    initializeCurrentPage() {
        const path = window.location.pathname;
        
        switch (path) {
            case '/':
                this.initializeLandingPage();
                break;
            case '/auth.html':
                this.initializeAuthPage();
                break;
            case '/chat.html':
                this.initializeChatPage();
                break;
            case '/documents.html':
                this.initializeDocumentsPage();
                break;
            case '/dashboard.html':
                this.initializeDashboard();
                break;
            default:
                console.log('No specific initialization for:', path);
        }
    }

    initializeLandingPage() {
        // Smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });

        // Animate hero stats on scroll
        this.animateOnScroll();
    }

    initializeAuthPage() {
        if (typeof AuthManager !== 'undefined') {
            new AuthManager(this);
        }
    }

    initializeChatPage() {
        if (!this.isAuthenticated) {
            this.router.navigate('/auth.html');
            return;
        }
        
        if (typeof ChatManager !== 'undefined') {
            new ChatManager(this);
        }
    }

    initializeDocumentsPage() {
        if (!this.isAuthenticated) {
            this.router.navigate('/auth.html');
            return;
        }
        
        if (typeof DocumentManager !== 'undefined') {
            new DocumentManager(this);
        }
    }

    initializeDashboard() {
        if (!this.isAuthenticated) {
            this.router.navigate('/auth.html');
            return;
        }
        
        if (typeof DashboardManager !== 'undefined') {
            new DashboardManager(this);
        }
    }

    animateOnScroll() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                }
            });
        }, observerOptions);

        // Observe elements that should animate on scroll
        document.querySelectorAll('.feature-card, .stat-card, .about-stats').forEach(el => {
            observer.observe(el);
        });
    }

    showLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('hidden');
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
    }
}

// API Client Class
class APIClient {
    constructor() {
        this.baseURL = '/api/v1';
        this.defaultHeaders = {
            'Content-Type': 'application/json',
        };
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: { ...this.defaultHeaders },
            credentials: 'include', // Include cookies for refresh token
            ...options
        };

        // Add auth token if available
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, config);
            
            // Handle token refresh if needed
            if (response.status === 401) {
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    config.headers.Authorization = `Bearer ${localStorage.getItem('access_token')}`;
                    return fetch(url, config);
                } else {
                    // Refresh failed - clear auth and redirect to login
                    window.spekApp?.clearAuth();
                    window.spekApp?.router.navigateTo('#/login');
                    throw new Error('Authentication failed');
                }
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async refreshToken() {
        try {
            const response = await fetch('/api/v1/refresh', {
                method: 'POST',
                credentials: 'include', // Include cookies for refresh token
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access_token);
                return true;
            } else {
                return false;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
            return false;
        }
    }

    async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch('/api/v1/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData,
            credentials: 'include'
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Login failed');
        }

        const tokens = await response.json();
        localStorage.setItem('access_token', tokens.access_token);
        return tokens;
    }

    async register(userData) {
        const response = await fetch('/api/v1/user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData),
            credentials: 'include'
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            
            let errorMessage = 'Registration failed';
            
            if (errorData.detail) {
                if (Array.isArray(errorData.detail)) {
                    // Handle validation errors (422)
                    errorMessage = errorData.detail.map(err => err.msg).join(', ');
                } else if (typeof errorData.detail === 'string') {
                    // Handle simple string errors
                    errorMessage = errorData.detail;
                }
            }
            
            throw new Error(errorMessage);
        }

        return await response.json();
    }

    async logout() {
        try {
            await fetch('/api/v1/logout', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });
        } catch (error) {
            console.error('Logout API call failed:', error);
        } finally {
            // Clear local storage regardless
            localStorage.removeItem('access_token');
        }
    }

    async getCurrentUser() {
        return await this.request('/user/me/');
    }

    // Chat API methods
    async sendMessage(message) {
        return await this.request('/chat/text', {
            method: 'POST',
            body: JSON.stringify({ message })
        });
    }

}

// Notification Manager
class NotificationManager {
    constructor() {
        this.container = this.createContainer();
        this.notifications = [];
    }

    createContainer() {
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                max-width: 400px;
            `;
            document.body.appendChild(container);
        }
        return container;
    }

    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} notification-item`;
        notification.style.cssText = `
            margin-bottom: 10px;
            animation: slideInRight 0.3s ease-out;
            position: relative;
        `;

        const iconMap = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        notification.innerHTML = `
            <div class="alert-icon">
                <i class="${iconMap[type] || iconMap.info}"></i>
            </div>
            <div class="alert-content">
                <div class="alert-message">${message}</div>
            </div>
            <button class="alert-dismiss">
                <i class="fas fa-times"></i>
            </button>
        `;

        // Add dismiss functionality
        const dismissBtn = notification.querySelector('.alert-dismiss');
        dismissBtn.addEventListener('click', () => this.dismiss(notification));

        this.container.appendChild(notification);
        this.notifications.push(notification);

        // Auto dismiss
        if (duration > 0) {
            setTimeout(() => this.dismiss(notification), duration);
        }

        return notification;
    }

    dismiss(notification) {
        if (notification && notification.parentNode) {
            notification.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
                const index = this.notifications.indexOf(notification);
                if (index > -1) {
                    this.notifications.splice(index, 1);
                }
            }, 300);
        }
    }

    success(message, duration = 5000) {
        return this.show(message, 'success', duration);
    }

    error(message, duration = 7000) {
        return this.show(message, 'danger', duration);
    }

    warning(message, duration = 6000) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration = 5000) {
        return this.show(message, 'info', duration);
    }

    clear() {
        this.notifications.forEach(notification => this.dismiss(notification));
    }
}

// Add notification animations to global styles
const notificationStyles = document.createElement('style');
notificationStyles.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }

    .animate-in {
        animation: slideIn 0.6s ease-out;
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(notificationStyles);

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.spekApp = new SpekApp();
});

// Export for use in other modules
window.APIClient = APIClient;
window.NotificationManager = NotificationManager;
