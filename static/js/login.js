// Logic for the /login.html page
document.addEventListener('DOMContentLoaded', () => {
    // Wait for window.spekApp to be defined before proceeding
    function waitForSpekApp(callback) {
        if (window.spekApp) {
            callback();
        } else {
            setTimeout(() => waitForSpekApp(callback), 20);
        }
    }

    waitForSpekApp(() => {
        window.spekApp.onReady(() => {
            // Redirect if already logged in
            if (window.spekApp && window.spekApp.isAuthenticated) {
                window.location.href = '/chat';
                return;
            }
            });
        });

        const tabBtns = document.querySelectorAll('.tab-btn');
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const authError = document.getElementById('auth-error');

    // Handle tab switching
    const switchTab = (tab) => {
        authError.style.display = 'none';
        
        const isLogin = tab === 'login';
        tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
        loginForm.style.display = isLogin ? 'block' : 'none';
        registerForm.style.display = isLogin ? 'none' : 'block';

        const params = new URLSearchParams(window.location.search);
        params.set('mode', tab);
        window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
    };
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Initialize tabs based on URL parameter
    const initialMode = new URLSearchParams(window.location.search).get('mode') || 'login';
    switchTab(initialMode);

    // Login form submission
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(loginForm);
        const username = formData.get('username');
        const password = formData.get('password');
        authError.style.display = 'none';

        try {
            await window.spekApp.apiClient.login(username, password);
            window.location.href = '/chat';
        } catch (error) {
            authError.textContent = error.message || 'Login failed. Please try again.';
            authError.style.display = 'block';
        }
    });

    // Register form submission
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(registerForm);
        const userData = Object.fromEntries(formData.entries());
        authError.style.display = 'none';

        try {
            await window.spekApp.apiClient.register(userData);
            // Auto login after successful registration
            await window.spekApp.apiClient.login(userData.username, userData.password);
            window.location.href = '/chat';
        } catch (error) {
            authError.textContent = error.message || 'Registration failed. Please try again.';
            authError.style.display = 'block';
        }
    });
});