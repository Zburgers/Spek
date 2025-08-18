// Login Application JavaScript
class SpekAuth {
    constructor() {
        this.currentTab = 'login';
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupPasswordStrength();
        this.setupPasswordToggles();
    }

    bindEvents() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Form submissions
        document.getElementById('loginForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        document.getElementById('registerForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleRegister();
        });

        // Password confirmation validation
        document.getElementById('confirmPassword').addEventListener('input', () => {
            this.validatePasswordConfirmation();
        });

        // Continue button in success modal
        document.getElementById('continueBtn').addEventListener('click', () => {
            window.location.href = 'chat.html';
        });

        // Social login buttons
        document.querySelector('.social-btn.google').addEventListener('click', () => {
            this.handleSocialLogin('google');
        });

        document.querySelector('.social-btn.github').addEventListener('click', () => {
            this.handleSocialLogin('github');
        });
    }

    // Tab switching
    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // Update forms
        document.querySelectorAll('.auth-form').forEach(form => {
            form.classList.toggle('active', form.id === `${tabName}Form`);
        });

        this.currentTab = tabName;
        this.clearFormErrors();
    }

    // Password strength checking
    setupPasswordStrength() {
        const passwordInput = document.getElementById('registerPassword');
        const strengthFill = document.getElementById('strengthFill');
        const strengthText = document.getElementById('strengthText');

        passwordInput.addEventListener('input', () => {
            const password = passwordInput.value;
            const strength = this.calculatePasswordStrength(password);
            
            this.updatePasswordStrength(strength, strengthFill, strengthText);
        });
    }

    calculatePasswordStrength(password) {
        let score = 0;
        
        if (password.length >= 8) score += 1;
        if (password.match(/[a-z]/)) score += 1;
        if (password.match(/[A-Z]/)) score += 1;
        if (password.match(/[0-9]/)) score += 1;
        if (password.match(/[^a-zA-Z0-9]/)) score += 1;
        
        if (score <= 1) return 'weak';
        if (score <= 3) return 'medium';
        if (score <= 4) return 'strong';
        return 'very-strong';
    }

    updatePasswordStrength(strength, strengthFill, strengthText) {
        // Remove all existing classes
        strengthFill.className = 'strength-fill';
        
        // Add appropriate class and update text
        switch (strength) {
            case 'weak':
                strengthFill.classList.add('weak');
                strengthText.textContent = 'Weak';
                strengthText.style.color = '#ef4444';
                break;
            case 'medium':
                strengthFill.classList.add('medium');
                strengthText.textContent = 'Medium';
                strengthText.style.color = '#f59e0b';
                break;
            case 'strong':
                strengthFill.classList.add('strong');
                strengthText.textContent = 'Strong';
                strengthText.style.color = '#10b981';
                break;
            case 'very-strong':
                strengthFill.classList.add('very-strong');
                strengthText.textContent = 'Very Strong';
                strengthText.style.color = '#059669';
                break;
        }
    }

    // Password visibility toggle
    setupPasswordToggles() {
        document.querySelectorAll('.toggle-password').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetId = e.target.closest('.toggle-password').dataset.target;
                const input = document.getElementById(targetId);
                const icon = e.target.closest('.toggle-password').querySelector('i');
                
                if (input.type === 'password') {
                    input.type = 'text';
                    icon.className = 'fas fa-eye-slash';
                } else {
                    input.type = 'password';
                    icon.className = 'fas fa-eye';
                }
            });
        });
    }

    // Form validation
    validatePasswordConfirmation() {
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const confirmWrapper = document.getElementById('confirmPassword').closest('.input-wrapper');
        
        if (confirmPassword && password !== confirmPassword) {
            this.showFieldError(confirmWrapper, 'Passwords do not match');
        } else {
            this.clearFieldError(confirmWrapper);
        }
    }

    showFieldError(wrapper, message) {
        wrapper.classList.add('error');
        
        // Remove existing error message
        const existingError = wrapper.parentNode.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        // Add new error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message visible';
        errorDiv.textContent = message;
        wrapper.parentNode.appendChild(errorDiv);
    }

    clearFieldError(wrapper) {
        wrapper.classList.remove('error');
        const errorMessage = wrapper.parentNode.querySelector('.error-message');
        if (errorMessage) {
            errorMessage.remove();
        }
    }

    clearFormErrors() {
        document.querySelectorAll('.input-wrapper').forEach(wrapper => {
            this.clearFieldError(wrapper);
        });
    }

    // Form submission handlers
    async handleLogin() {
        const form = document.getElementById('loginForm');
        const submitBtn = form.querySelector('button[type="submit"]');
        
        // Get form data
        const email = document.getElementById('loginEmail').value.trim();
        const password = document.getElementById('loginPassword').value;
        const rememberMe = document.getElementById('rememberMe').checked;
        
        // Basic validation
        if (!email || !password) {
            alert('Please fill in all required fields');
            return;
        }
        
        // Show loading state
        this.setFormLoading(form, true);
        
        try {
            // Call login API
            const response = await this.loginUser(email, password, rememberMe);
            
            // Store tokens
            this.storeAuthTokens(response);
            
            // Redirect to chat
            window.location.href = 'chat.html';
            
        } catch (error) {
            console.error('Login error:', error);
            alert(error.message || 'Login failed. Please try again.');
        } finally {
            this.setFormLoading(form, false);
        }
    }

    async handleRegister() {
        const form = document.getElementById('registerForm');
        const submitBtn = form.querySelector('button[type="submit"]');
        
        // Get form data
        const name = document.getElementById('registerName').value.trim();
        const username = document.getElementById('registerUsername').value.trim();
        const email = document.getElementById('registerEmail').value.trim();
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const agreeTerms = document.getElementById('agreeTerms').checked;
        
        // Validation
        if (!name || !username || !email || !password || !confirmPassword) {
            alert('Please fill in all required fields');
            return;
        }
        
        if (password !== confirmPassword) {
            alert('Passwords do not match');
            return;
        }
        
        if (!agreeTerms) {
            alert('Please agree to the Terms of Service and Privacy Policy');
            return;
        }
        
        if (password.length < 8) {
            alert('Password must be at least 8 characters long');
            return;
        }
        
        // Show loading state
        this.setFormLoading(form, true);
        
        try {
            // Call register API
            const response = await this.registerUser(name, username, email, password);
            
            // Show success modal
            this.showSuccessModal('Your account has been created successfully!');
            
        } catch (error) {
            console.error('Registration error:', error);
            alert(error.message || 'Registration failed. Please try again.');
        } finally {
            this.setFormLoading(form, false);
        }
    }

    // Loading states
    setFormLoading(form, loading) {
        const submitBtn = form.querySelector('button[type="submit"]');
        
        if (loading) {
            form.classList.add('form-loading');
            submitBtn.classList.add('loading');
        } else {
            form.classList.remove('form-loading');
            submitBtn.classList.remove('loading');
        }
    }

    // Success modal
    showSuccessModal(message) {
        document.getElementById('successMessage').textContent = message;
        document.getElementById('successModal').classList.add('visible');
    }

    hideSuccessModal() {
        document.getElementById('successModal').classList.remove('visible');
    }

    // Social login
    handleSocialLogin(provider) {
        // For demo purposes, show alert
        // In production, this would redirect to OAuth provider
        alert(`${provider.charAt(0).toUpperCase() + provider.slice(1)} login coming soon!`);
    }

    // API calls
    async loginUser(email, password, rememberMe) {
        // For demo purposes, return mock response
        // In production, this would call your FastAPI backend
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                // Simulate API call
                if (email && password) {
                    resolve({
                        access_token: 'mock_access_token_' + Date.now(),
                        token_type: 'bearer',
                        user: {
                            id: 1,
                            name: 'Demo User',
                            email: email,
                            username: email.split('@')[0]
                        }
                    });
                } else {
                    reject(new Error('Invalid credentials'));
                }
            }, 1000);
        });
    }

    async registerUser(name, username, email, password) {
        // For demo purposes, return mock response
        // In production, this would call your FastAPI backend
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                // Simulate API call
                if (name && username && email && password) {
                    resolve({
                        user: {
                            id: 1,
                            name: name,
                            email: email,
                            username: username
                        },
                        message: 'User created successfully'
                    });
                } else {
                    reject(new Error('Registration failed'));
                }
            }, 1000);
        });
    }

    // Token storage
    storeAuthTokens(response) {
        if (response.access_token) {
            localStorage.setItem('spek_access_token', response.access_token);
            localStorage.setItem('spek_user', JSON.stringify(response.user));
        }
    }

    // Utility functions
    validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    validateUsername(username) {
        return username.length >= 3 && /^[a-zA-Z0-9_]+$/.test(username);
    }
}

// Initialize auth when page loads
document.addEventListener('DOMContentLoaded', () => {
    new SpekAuth();
});

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('successModal');
    if (e.target === modal) {
        modal.classList.remove('visible');
    }
});
