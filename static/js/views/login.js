// Login view module
export function render(queryString = null) {
    // Parse query parameters
    const params = new URLSearchParams(queryString || '');
    const mode = params.get('mode') || 'login'; // Default to login mode
    const app = document.getElementById('app');
    if (app) {
        app.innerHTML = `
            <section class="login-view" style="max-width: 500px; margin: 2rem auto; padding: 2rem; background: white; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.1);">
                <div class="auth-header" style="text-align: center; margin-bottom: 2rem;">
                    <h2>Welcome to Spek</h2>
                    <p style="color: #666;">Sign in to your account or create a new one</p>
                </div>

                <div class="auth-tabs" style="display: flex; margin-bottom: 2rem; border-bottom: 1px solid #e9ecef;">
                    <button class="tab-btn ${mode === 'login' ? 'active' : ''}" data-tab="login" style="flex: 1; padding: 1rem; border: none; background: none; cursor: pointer; border-bottom: 2px solid ${mode === 'login' ? '#667eea' : 'transparent'}; color: ${mode === 'login' ? '#667eea' : '#666'}; font-weight: 500;">Sign In</button>
                    <button class="tab-btn ${mode === 'register' ? 'active' : ''}" data-tab="register" style="flex: 1; padding: 1rem; border: none; background: none; cursor: pointer; border-bottom: 2px solid ${mode === 'register' ? '#667eea' : 'transparent'}; color: ${mode === 'register' ? '#667eea' : '#666'};">Create Account</button>
                </div>

                <div id="login-error" style="color: #dc3545; margin-bottom: 1rem; text-align: center;"></div>

                <!-- Login Form -->
                <form class="auth-form ${mode === 'login' ? 'active' : ''}" id="loginForm" style="display: ${mode === 'login' ? 'block' : 'none'};">
                    <div class="form-group" style="margin-bottom: 1rem;">
                        <label for="loginEmail" style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Email or Username</label>
                        <input type="text" id="loginEmail" name="username" required 
                               style="width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 5px; font-size: 1rem;"
                               placeholder="Enter your email or username">
                    </div>
                    <div class="form-group" style="margin-bottom: 1.5rem;">
                        <label for="loginPassword" style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Password</label>
                        <input type="password" id="loginPassword" name="password" required 
                               style="width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 5px; font-size: 1rem;"
                               placeholder="Enter your password">
                    </div>
                    <button type="submit" id="loginBtn" 
                            style="width: 100%; padding: 0.75rem; background: #667eea; color: white; border: none; border-radius: 5px; font-size: 1rem; cursor: pointer; margin-bottom: 1rem;">
                        Sign In
                    </button>
                </form>

                <!-- Register Form -->
                <form class="auth-form ${mode === 'register' ? 'active' : ''}" id="registerForm" style="display: ${mode === 'register' ? 'block' : 'none'};">
                    <div class="form-group" style="margin-bottom: 1rem;">
                        <label for="registerName" style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Full Name</label>
                        <input type="text" id="registerName" name="name" required 
                               style="width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 5px; font-size: 1rem;"
                               placeholder="Enter your full name">
                    </div>
                    <div class="form-group" style="margin-bottom: 1rem;">
                        <label for="registerUsername" style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Username</label>
                        <input type="text" id="registerUsername" name="username" required 
                               style="width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 5px; font-size: 1rem;"
                               placeholder="Choose a username">
                    </div>
                    <div class="form-group" style="margin-bottom: 1rem;">
                        <label for="registerEmail" style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Email</label>
                        <input type="email" id="registerEmail" name="email" required 
                               style="width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 5px; font-size: 1rem;"
                               placeholder="Enter your email">
                    </div>
                    <div class="form-group" style="margin-bottom: 1.5rem;">
                        <label for="registerPassword" style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Password</label>
                        <input type="password" id="registerPassword" name="password" required 
                               style="width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 5px; font-size: 1rem;"
                               placeholder="Create a password (min 8 characters)">
                    </div>
                    <button type="submit" id="registerBtn" 
                            style="width: 100%; padding: 0.75rem; background: #4CAF50; color: white; border: none; border-radius: 5px; font-size: 1rem; cursor: pointer; margin-bottom: 1rem;">
                        Create Account
                    </button>
                </form>

                <div style="text-align: center; margin-top: 1rem;">
                    <a href="#/" data-link style="color: #667eea; text-decoration: none;">← Back to Home</a>
                </div>
            </section>
        `;

        // Add event listeners
        setupLoginEventListeners();
    }
}

function setupLoginEventListeners() {
    // Tab switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            
            // Update tab styling
            tabBtns.forEach(b => {
                b.classList.remove('active');
                b.style.borderBottomColor = 'transparent';
                b.style.color = '#666';
            });
            btn.classList.add('active');
            btn.style.borderBottomColor = '#667eea';
            btn.style.color = '#667eea';
            
            // Show/hide forms
            if (tab === 'login') {
                loginForm.style.display = 'block';
                registerForm.style.display = 'none';
            } else {
                loginForm.style.display = 'none';
                registerForm.style.display = 'block';
            }
        });
    });

    // Login form submission
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(loginForm);
        const username = formData.get('username');
        const password = formData.get('password');

        try {
            const loginBtn = document.getElementById('loginBtn');
            loginBtn.textContent = 'Signing in...';
            loginBtn.disabled = true;

            const tokens = await window.spekApp.apiClient.login(username, password);
            
            // Get user info
            const user = await window.spekApp.apiClient.getCurrentUser();
            window.spekApp.setUser(user);
            
            // Clear error and redirect
            document.getElementById('login-error').textContent = '';
            window.spekApp.notifications.success('Successfully logged in!');
            window.spekApp.router.navigateTo('#/chat');

        } catch (error) {
            console.error('Login error:', error);
            document.getElementById('login-error').textContent = error.message || 'Login failed. Please try again.';
        } finally {
            const loginBtn = document.getElementById('loginBtn');
            loginBtn.textContent = 'Sign In';
            loginBtn.disabled = false;
        }
    });

    // Register form submission
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(registerForm);
        const userData = {
            name: formData.get('name'),
            username: formData.get('username'),
            email: formData.get('email'),
            password: formData.get('password')
        };

        try {
            const registerBtn = document.getElementById('registerBtn');
            registerBtn.textContent = 'Creating account...';
            registerBtn.disabled = true;

            await window.spekApp.apiClient.register(userData);
            
            // Auto login after registration
            const tokens = await window.spekApp.apiClient.login(userData.username, userData.password);
            const user = await window.spekApp.apiClient.getCurrentUser();
            window.spekApp.setUser(user);
            
            // Clear error and redirect
            document.getElementById('login-error').textContent = '';
            window.spekApp.notifications.success('Account created successfully!');
            window.spekApp.router.navigateTo('#/chat');

        } catch (error) {
            console.error('Registration error:', error);
            document.getElementById('login-error').textContent = error.message || 'Registration failed. Please try again.';
        } finally {
            const registerBtn = document.getElementById('registerBtn');
            registerBtn.textContent = 'Create Account';
            registerBtn.disabled = false;
        }
    });
}
