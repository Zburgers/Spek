// Client-side Router for SPA-like navigation
class Router {
    constructor() {
        this.routes = new Map();
        this.currentRoute = null;
        this.setupRoutes();
    }

    init() {
        // Handle browser back/forward
        window.addEventListener('popstate', () => {
            this.handleRoute(window.location.pathname + window.location.search);
        });

        // Handle initial route
        this.handleRoute(window.location.pathname + window.location.search);
    }

    setupRoutes() {
        // Define routes and their handlers
        this.routes.set('/', {
            title: 'Spek - Multimodal AI Platform',
            handler: () => this.loadPage('/static/index.html')
        });

        // Explicit route for canonical landing page
        this.routes.set('/index.html', {
            title: 'Spek - Multimodal AI Platform',
            handler: () => this.loadPage('/static/index.html')
        });

        this.routes.set('/auth.html', {
            title: 'Sign In - Spek',
            handler: () => this.loadPage('/static/auth.html')
        });

        this.routes.set('/chat.html', {
            title: 'Chat - Spek',
            handler: () => this.loadPage('/static/chat.html'),
            requiresAuth: true
        });

        this.routes.set('/documents.html', {
            title: 'Documents - Spek',
            handler: () => this.loadPage('/static/documents.html'),
            requiresAuth: true
        });

        this.routes.set('/dashboard.html', {
            title: 'Dashboard - Spek',
            handler: () => this.loadPage('/static/dashboard.html'),
            requiresAuth: true
        });

        this.routes.set('/profile.html', {
            title: 'Profile - Spek',
            handler: () => this.loadPage('/static/profile.html'),
            requiresAuth: true
        });
    }

    async handleRoute(path) {
        // Extract pathname from full path
        const url = new URL(path, window.location.origin);
        const pathname = url.pathname;
        
        // Find matching route
        let route = this.routes.get(pathname);
        
        // Handle special cases
        if (!route) {
            // Check if it's an HTML file request
            if (pathname.endsWith('.html')) {
                route = this.routes.get(pathname);
            }
        }

        // If still no route found, redirect to canonical index page
        if (!route) {
            console.log('Route not found:', pathname, 'redirecting to /index.html');
            this.navigate('/index.html');
            return;
        }

        // Check authentication requirement
        if (route.requiresAuth && !window.spekApp?.isAuthenticated) {
            console.log('Route requires auth, redirecting to login');
            this.navigate('/auth.html');
            return;
        }

        // Update current route
        this.currentRoute = { path: pathname, route };

        // Update document title
        document.title = route.title;

        // Execute route handler
        try {
            await route.handler();
        } catch (error) {
            console.error('Route handler error:', error);
            window.spekApp?.notifications?.error('Failed to load page');
        }
    }

    async loadPage(pagePath) {
        try {
            // Show loading
            window.spekApp?.showLoading();

            // Check if we're at the root and trying to load index.html
            if (window.location.pathname === '/' && pagePath === '/static/index.html') {
                // We're already at the root, which serves index.html, no need to redirect
                window.spekApp?.hideLoading();
                return;
            }
            
            // For other pages, redirect if needed
            if (window.location.pathname !== pagePath.replace('/static', '')) {
                window.location.href = pagePath.replace('/static', '');
                return;
            }

            // Page is already loaded, just hide loading
            window.spekApp?.hideLoading();
        } catch (error) {
            console.error('Failed to load page:', error);
            window.spekApp?.hideLoading();
            throw error;
        }
    }

    navigate(path, replace = false) {
        if (replace) {
            window.history.replaceState(null, '', path);
        } else {
            window.history.pushState(null, '', path);
        }
        this.handleRoute(path);
    }

    back() {
        window.history.back();
    }

    forward() {
        window.history.forward();
    }

    getCurrentRoute() {
        return this.currentRoute;
    }

    isCurrentRoute(path) {
        return this.currentRoute?.path === path;
    }
}

// Utility functions for URL management
class URLUtils {
    static getQueryParams() {
        const params = new URLSearchParams(window.location.search);
        const result = {};
        for (const [key, value] of params) {
            result[key] = value;
        }
        return result;
    }

    static getQueryParam(name, defaultValue = null) {
        const params = new URLSearchParams(window.location.search);
        return params.get(name) || defaultValue;
    }

    static setQueryParam(name, value) {
        const url = new URL(window.location);
        url.searchParams.set(name, value);
        window.history.replaceState(null, '', url.toString());
    }

    static removeQueryParam(name) {
        const url = new URL(window.location);
        url.searchParams.delete(name);
        window.history.replaceState(null, '', url.toString());
    }

    static updateQueryParams(params) {
        const url = new URL(window.location);
        Object.entries(params).forEach(([key, value]) => {
            if (value === null || value === undefined) {
                url.searchParams.delete(key);
            } else {
                url.searchParams.set(key, value);
            }
        });
        window.history.replaceState(null, '', url.toString());
    }
}

// Export classes
window.Router = Router;
window.URLUtils = URLUtils;
