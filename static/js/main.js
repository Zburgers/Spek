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

    async getDocuments() {
        return this.request('/documents', {
            method: 'GET',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        });
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