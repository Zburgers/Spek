// Main Application Entry Point
class SpekApp {
    constructor() {
        this.currentUser = null;
        this.isAuthenticated = false;
        this.apiClient = new APIClient();
        this.router = new Router();
        this.notifications = new NotificationManager();
        
        this.init();
    }

    async init() {
        // Check authentication status
        await this.checkAuthStatus();
        
        // Initialize router
        this.router.init();
        
        // Setup global event listeners
        this.setupEventListeners();
        
        // Initialize components
        this.initializeComponents();
        
        console.log('Spek App initialized');
    }

    async checkAuthStatus() {
        const token = localStorage.getItem('access_token');
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
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        this.updateUIForAuth();
    }

    updateUIForAuth() {
        // Update navigation and UI based on auth status
        const authButtons = document.querySelectorAll('[data-auth-required]');
        const publicButtons = document.querySelectorAll('[data-auth-public]');
        
        authButtons.forEach(btn => {
            btn.style.display = this.isAuthenticated ? 'block' : 'none';
        });
        
        publicButtons.forEach(btn => {
            btn.style.display = this.isAuthenticated ? 'none' : 'block';
        });
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
                    throw new Error('Authentication failed');
                }
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            return data;
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
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
        }
        
        return false;
    }

    // Auth endpoints
    async login(username, password) {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        return this.request('/login', {
            method: 'POST',
            headers: {}, // Let browser set content-type for FormData
            body: formData
        });
    }

    async register(userData) {
        return this.request('/user', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    }

    async logout() {
        return this.request('/logout', {
            method: 'POST'
        });
    }

    async getCurrentUser() {
        return this.request('/users/user/me/');
    }

    // Chat endpoints
    async sendTextMessage(message, sessionId = null, model = 'gpt-4') {
        return this.request('/chat/text', {
            method: 'POST',
            body: JSON.stringify({
                message,
                session_id: sessionId,
                model
            })
        });
    }

    async getChatHistory(sessionId) {
        return this.request(`/chat/history/${sessionId}`);
    }

    async sendVoiceMessage(audioData, sessionId = null, model = 'gpt-4') {
        return this.request('/chat/voice', {
            method: 'POST',
            body: JSON.stringify({
                audio_data: audioData,
                session_id: sessionId,
                model
            })
        });
    }

    // Voice endpoints
    async speechToText(audioData, language = 'en-US') {
        return this.request('/stt', {
            method: 'POST',
            body: JSON.stringify({
                audio_data: audioData,
                language
            })
        });
    }

    async textToSpeech(text, voice = 'alloy', language = 'en-US') {
        return this.request('/tts', {
            method: 'POST',
            body: JSON.stringify({
                text,
                voice,
                language
            })
        });
    }

    // Document endpoints
    async uploadDocument(fileName, fileType, fileSize, content) {
        return this.request('/documents/upload', {
            method: 'POST',
            body: JSON.stringify({
                file_name: fileName,
                file_type: fileType,
                file_size: fileSize,
                content
            })
        });
    }

    async getDocuments() {
        return this.request('/documents');
    }

    async getDocument(docId) {
        return this.request(`/documents/${docId}`);
    }

    async queryDocument(documentId, query, sessionId = null) {
        return this.request('/documents/query', {
            method: 'POST',
            body: JSON.stringify({
                document_id: documentId,
                query,
                session_id: sessionId
            })
        });
    }

    // System endpoints
    async getModels() {
        return this.request('/models');
    }

    async getHealth() {
        return this.request('/health');
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
