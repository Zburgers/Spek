// Hash-based Router for SPA navigation
class Router {
    constructor() {
        this.routes = new Map();
        this.currentRoute = null;
        this.setupRoutes();
    }

    init() {
        // Listen for hash changes
        window.addEventListener('hashchange', () => {
            this.handleRoute(window.location.hash);
        });
        
        // Handle clicks on data-link elements
        document.addEventListener('click', (e) => {
            if (e.target.hasAttribute('data-link') || e.target.closest('[data-link]')) {
                e.preventDefault();
                const link = e.target.hasAttribute('data-link') ? e.target : e.target.closest('[data-link]');
                const href = link.getAttribute('href');
                if (href && href.startsWith('#/')) {
                    this.navigateTo(href);
                }
            }
        });
        
        // Handle initial route
        this.handleRoute(window.location.hash);
    }

    setupRoutes() {
        // Define hash routes and their handlers
        this.routes.set('#/', {
            title: 'Spek - Multimodal AI Platform',
            handler: () => this.loadView('home')
        });
        this.routes.set('#/login', {
            title: 'Sign In - Spek',
            handler: (queryString) => this.loadView('login', queryString)
        });
        this.routes.set('#/chat', {
            title: 'Chat - Spek',
            handler: () => this.loadView('chat'),
            requiresAuth: true
        });
        // Add more routes as needed
    }

    handleRoute(hash) {
        if (!hash || hash === '' || hash === '#') {
            hash = '#/';
        }
        
        // Separate path from query parameters
        const [path, queryString] = hash.split('?');
        const route = this.routes.get(path);
        
        if (route) {
            document.title = route.title;
            if (route.requiresAuth && !window.spekApp?.isAuthenticated) {
                this.navigateTo('#/login');
                return;
            }
            route.handler(queryString);
            this.currentRoute = hash;
        } else {
            // 404 fallback
            this.loadNotFound();
        }
    }

    navigateTo(hash) {
        if (window.location.hash !== hash) {
            window.location.hash = hash;
        } else {
            this.handleRoute(hash);
        }
    }

    loadView(viewName, queryString = null) {
        // Dynamically import and render the view
        import(`/static/js/views/${viewName}.js`).then(module => {
            if (module && typeof module.render === 'function') {
                module.render(queryString);
            }
        }).catch(() => {
            this.loadNotFound();
        });
    }

    loadNotFound() {
        const app = document.getElementById('app');
        if (app) {
            app.innerHTML = '<h2 style="color:red">404 - Page Not Found</h2>';
        }
        document.title = '404 - Not Found';
    }

    getCurrentRoute() {
        return this.currentRoute;
    }

    isCurrentRoute(hash) {
        return this.currentRoute === hash;
    }
}

// Export classes
window.Router = Router;
