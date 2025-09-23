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

    getToken() {
        return localStorage.getItem('access_token');
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

    // Document Management Methods
    async uploadDocument(file, scope = 'app_wide') {
        // Validate file size (e.g., 10MB limit)
        const maxSize = 10 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
            throw new Error('File size exceeds 10MB limit');
        }
        
        // Validate file type (adjust based on your requirements)
        const allowedTypes = ['application/pdf', 'text/plain', 'application/msword', 
                              'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
        if (!allowedTypes.includes(file.type)) {
            throw new Error(`File type ${file.type} is not supported`);
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('scope', scope);

        const response = await fetch(`${this.baseURL}/documents/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: formData,
        });

        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                } else if (typeof errorData === 'string') {
                    errorMessage = errorData;
                }
            } catch (parseError) {
                console.warn('Failed to parse error response:', parseError);
                // Keep the default error message
            }
            throw new Error(errorMessage);
        }

        return response.json();
    }

    async deleteDocument(documentId) {
        return this.request(`/documents/${documentId}`, {
            method: 'DELETE',
        });
    }

    async updateDocumentStatus(documentId, status, message = null) {
        return this.request(`/documents/${documentId}/status`, {
            method: 'PATCH',
            body: JSON.stringify({
                status: status,
                message: message
            }),
        });
    }

    async getDocument(documentId) {
        return this.request(`/documents/${documentId}`, {
            method: 'GET',
        });
    }

    async queryDocument(documentId, query) {
        return this.request('/documents/query', {
            method: 'POST',
            body: JSON.stringify({
                document_id: documentId,
                query: query
            }),
        });
    }

    // Chat-Document Association Methods
    async getChatDocuments(chatId) {
        const response = await this.request(`/chats/${chatId}/documents`, {
            method: 'GET',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        });
        // The response is already in the correct format from the backend
        return response;
    }

    async addDocumentToChat(chatId, documentId) {
        // Use the bulk association endpoint for consistency
        return this.associateDocumentsWithChat(chatId, [documentId], true);
    }

    async removeDocumentFromChat(chatId, documentId) {
        return this.request(`/chats/${chatId}/documents/${documentId}`, {
            method: 'DELETE',
        });
    }

    // New method for bulk document association
    async associateDocumentsWithChat(chatId, documentIds, selected = true) {
        return this.request(`/chats/${chatId}/documents`, {
            method: 'POST',
            body: JSON.stringify({
                document_ids: documentIds,
                selected: selected
            }),
        });
    }

    // Chat-specific document upload using the dedicated endpoint
    async uploadChatDocument(chatId, file) {
        console.log('DEBUG: uploadChatDocument called with chatId:', chatId, 'file:', file.name);
        
        const formData = new FormData();
        formData.append('file', file);

        const uploadUrl = `${this.baseURL}/chats/${chatId}/documents/upload`;
        console.log('DEBUG: Upload URL:', uploadUrl);

        const response = await fetch(uploadUrl, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: formData,
        });

        console.log('DEBUG: Upload response status:', response.status);
        
        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                console.log('DEBUG: Error response data:', errorData);
                // If detail is an array of validation errors, extract messages
                if (Array.isArray(errorData.detail)) {
                    errorMessage = errorData.detail
                        .map(err => err.msg || JSON.stringify(err))
                        .join('; ');
                } else if (typeof errorData.detail === 'string') {
                    errorMessage = errorData.detail;
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                }
            } catch (parseError) {
                console.warn('Failed to parse error response:', parseError);
                // Keep default message
            }
            throw new Error(errorMessage);
        }

        const result = await response.json();
        console.log('DEBUG: Upload successful, result:', result);
        return result;
    }

    // Enhanced getDocuments with normalization
    async getDocuments() {
        const response = await this.request('/documents', {
            method: 'GET',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        });
        
        // Normalize the response format
        const documents = Array.isArray(response) ? response : (response.data || []);
        return {
            data: documents.map(doc => ({
                uuid: doc.uuid || doc.id,
                id: doc.uuid || doc.id,
                filename: doc.filename || doc.file_name || doc.title,
                file_name: doc.file_name || doc.filename || doc.title,
                title: doc.title || doc.filename || doc.file_name,
                file_type: doc.file_type,
                file_size: doc.file_size,
                processing_status: doc.processing_status || doc.status,
                status: doc.status || doc.processing_status,
                created_at: doc.created_at || doc.uploaded_at,
                uploaded_at: doc.uploaded_at || doc.created_at,
                scope: doc.scope || 'app_wide',
                chat_id: doc.chat_id || null
            }))
        };
    }
}

// Simple Notification Manager
class NotificationManager {
    constructor() {
        this.maxToasts = 5;
        this.defaultDuration = 3500;
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.setAttribute('aria-live', 'polite');
        this.container.setAttribute('aria-atomic', 'true');
        document.body.appendChild(this.container);
        this.toasts = new Set();
    }

    show(message, type = 'info', options = {}) {
        const { duration = this.defaultDuration, dismissible = true } = options;

        // Trim if exceeding max
        while (this.container.children.length >= this.maxToasts) {
            const oldest = this.container.firstElementChild;
            if (oldest) this._removeToast(oldest);
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'status');

        const iconMap = {
            success: '✅',
            error: '❌',
            info: 'ℹ️'
        };

        const icon = document.createElement('span');
        icon.className = 'toast-icon';
        icon.textContent = iconMap[type] || 'ℹ️';

        const content = document.createElement('div');
        content.className = 'toast-content';
        content.textContent = String(message);

        toast.appendChild(icon);
        toast.appendChild(content);

        if (dismissible) {
            const btn = document.createElement('button');
            btn.className = 'toast-dismiss';
            btn.setAttribute('aria-label', 'Dismiss notification');
            btn.innerHTML = '&times;';
            btn.addEventListener('click', () => this._removeToast(toast));
            toast.appendChild(btn);
        }

        // Auto dismiss
        let timerId = null;
        const startTimer = () => {
            if (duration > 0) {
                timerId = setTimeout(() => this._removeToast(toast), duration);
            }
        };
        const clearTimer = () => {
            if (timerId) {
                clearTimeout(timerId);
                timerId = null;
            }
        };

        toast.addEventListener('mouseenter', clearTimer);
        toast.addEventListener('mouseleave', startTimer);

        this.container.appendChild(toast);
        // Trigger animation
        requestAnimationFrame(() => toast.classList.add('show'));
        startTimer();
        this.toasts.add(toast);
        return toast;
    }

    success(message, options = {}) {
        return this.show(message, 'success', options);
    }

    error(message, options = {}) {
        return this.show(message, 'error', options);
    }

    info(message, options = {}) {
        return this.show(message, 'info', options);
    }

    clearAll() {
        Array.from(this.toasts).forEach(t => this._removeToast(t));
    }

    _removeToast(toast) {
        if (!toast || !toast.parentElement) return;
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => {
            if (toast.parentElement) toast.parentElement.removeChild(toast);
            this.toasts.delete(toast);
        }, 200);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new SpekApp();
    app.init();
});