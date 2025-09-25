/**
 * @file main.js
 * @description This is the primary entry point for the Spek application's client-side logic.
 * It initializes the main application controller (`SpekApp`), handles user authentication,
 * and provides a centralized API client (`APIClient`) for all backend communication.
 * This script is shared across all pages of the application.
 *
 * @version 1.0.0
 * @date 2025-09-25
 */

// ===================================================================================
//                                  OVERVIEW
// ===================================================================================
//
// The script is structured around two main classes:
//
// 1. SpekApp: The core application class. It acts as a singleton controller, managing
//    the application's state, such as authentication status and the current user. It
//    also handles the initialization sequence and updates common UI elements (like the navbar).
//    An instance is exposed globally as `window.spekApp` for easy access from other scripts.
//
// 2. APIClient: A dedicated class that abstracts all communication with the backend API.
//    All HTTP requests should be routed through this client. It handles adding the
//    authentication token to requests and standardizing error handling.
//
// The application initializes when the DOM is fully loaded, ensuring all page elements
// are available for manipulation.
//
// ===================================================================================
//                               CLASS: SpekApp
// ===================================================================================
//
// Manages the overall state and lifecycle of the front-end application.
//
// --- Properties ---
// - currentUser: (Object|null) Stores the logged-in user's data.
// - isAuthenticated: (boolean) A flag indicating if a user is currently logged in.
// - apiClient: (APIClient) An instance of the API client for making server requests.
// - notifications: (NotificationManager) An instance to handle UI notifications.
// - pageInitializers: (Array<Function>) A queue for page-specific initialization
//   functions, which are executed after the main app initialization is complete.
//
// --- Key Methods ---
// - init(): The main initialization method. It checks the user's authentication
//   status and runs all registered page-specific initializers.
// - onReady(callback): A public method allowing other scripts (e.g., chat.js, login.js)
//   to register their own initialization logic. This keeps page-specific code
//   decoupled from this main file.
// - checkAuthStatus(): Checks for an auth token in localStorage and validates it with
//   the server to set the user's session.
// - updateUIForAuth(): Updates shared UI components, like the navigation bar, to
//   reflect the current authentication state (e.g., showing "Login" vs. "Logout").
//
// ===================================================================================
//                              CLASS: APIClient
// ===================================================================================
//
// A wrapper for all backend API endpoints. It centralizes request logic,
// token management, and error handling.
//
// --- Core Method ---
// - request(endpoint, options): The base method for all API calls. It automatically
//   attaches the JWT token from localStorage to the `Authorization` header.
//
// --- Endpoint Groups ---
// - Authentication: login(), register(), logout().
// - User: getCurrentUser().
// - Chat: sendMessage().
// - Document Management: getDocuments(), uploadDocument(), deleteDocument(), etc. Handles
//   both general and chat-specific document operations.
// - Chat-Document Association: Methods to link/unlink documents to a specific chat,
//   such as `getChatDocuments()` and `associateDocumentsWithChat()`.
//
// ===================================================================================
//                          CONTRIBUTION GUIDELINES ✍️
// ===================================================================================
//
// To maintain code quality and consistency, please follow these simple guidelines:
//
// 1.  **Centralize API Calls**: All new interactions with the backend API must be
//     added as methods within the `APIClient` class. Do not use `fetch()` directly
//     in page-specific scripts.
//
// 2.  **Manage State in SpekApp**: Any global state (e.g., user information,
//     authentication status) should be managed within the `SpekApp` class.
//
// 3.  **Use `onReady` for Page Logic**: For JavaScript that needs to run on a
//     specific page (e.g., initializing the chat interface on `/chat`), add your
//     code inside a `window.spekApp.onReady(() => { ... });` block in that page's
//     specific JS file. This ensures your code runs after the main app is initialized.
//
// 4.  **Keep it Clean**: Avoid adding page-specific DOM manipulations or logic directly
//     into this file. This file is for shared, global functionality only.
//
// ===================================================================================

// Main Application Entry Point - Shared across all pages
import NotificationManager from './notifications.js';

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
                        .map(err => err.msg || err.message || 'Validation error')
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

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new SpekApp();
    app.init();
});