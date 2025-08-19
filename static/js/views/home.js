// Home view module
export function render() {
    const app = document.getElementById('app');
    if (app) {
        const isAuthenticated = window.spekApp?.isAuthenticated;
        const user = window.spekApp?.currentUser;
        
        app.innerHTML = `
            <section class="home-view" style="max-width: 800px; margin: 2rem auto; padding: 2rem; background: white; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); text-align: center;">
                <div class="welcome-content">
                    ${isAuthenticated ? `
                        <h2>Welcome back, ${user?.username || 'User'}! 👋</h2>
                        <p style="color: #666; margin-bottom: 2rem;">Ready to continue your AI conversations?</p>
                        <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                            <a href="#/chat" data-link class="btn btn-primary" 
                               style="padding: 1rem 2rem; background: #667eea; color: white; text-decoration: none; border-radius: 25px; font-weight: 500; transition: all 0.3s;">
                                Continue Chatting
                            </a>
                            <button id="logout-home-btn" class="btn btn-outline" 
                                    style="padding: 1rem 2rem; background: transparent; color: #dc3545; border: 1px solid #dc3545; border-radius: 25px; font-weight: 500; cursor: pointer; transition: all 0.3s;">
                                Logout
                            </button>
                        </div>
                    ` : `
                        <h2>Welcome to Spek AI Platform 🤖</h2>
                        <p style="color: #666; margin-bottom: 2rem;">Experience the future of AI interaction with our multimodal platform. Chat with text, voice, and documents seamlessly.</p>
                        
                        <div class="features-preview" style="margin: 2rem 0;">
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
                                <div style="padding: 1rem; border-radius: 10px; background: #f8f9fa; text-align: center;">
                                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">💬</div>
                                    <h4>Text Chat</h4>
                                    <p style="font-size: 0.9rem; color: #666;">Intelligent conversations</p>
                                </div>
                                <div style="padding: 1rem; border-radius: 10px; background: #f8f9fa; text-align: center;">
                                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">🎙️</div>
                                    <h4>Voice Chat</h4>
                                    <p style="font-size: 0.9rem; color: #666;">Natural speech interaction</p>
                                </div>
                                <div style="padding: 1rem; border-radius: 10px; background: #f8f9fa; text-align: center;">
                                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">📄</div>
                                    <h4>Document Analysis</h4>
                                    <p style="font-size: 0.9rem; color: #666;">AI-powered document chat</p>
                                </div>
                            </div>
                        </div>
                        
                        <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                            <a href="#/login" data-link class="btn btn-primary" 
                               style="padding: 1rem 2rem; background: #667eea; color: white; text-decoration: none; border-radius: 25px; font-weight: 500; transition: all 0.3s;">
                                Get Started
                            </a>
                            <a href="#/login" data-link class="btn btn-outline" 
                               style="padding: 1rem 2rem; background: transparent; color: #667eea; border: 1px solid #667eea; text-decoration: none; border-radius: 25px; font-weight: 500; transition: all 0.3s;">
                                Sign In
                            </a>
                        </div>
                    `}
                </div>
            </section>
        `;

        // Add event listeners for authenticated users
        if (isAuthenticated) {
            const logoutBtn = document.getElementById('logout-home-btn');
            if (logoutBtn) {
                logoutBtn.addEventListener('click', async () => {
                    try {
                        await window.spekApp.apiClient.logout();
                        window.spekApp.clearAuth();
                        window.spekApp.notifications.success('Successfully logged out');
                        // Re-render home view to show login options
                        render();
                    } catch (error) {
                        console.error('Logout error:', error);
                        // Clear auth anyway
                        window.spekApp.clearAuth();
                        render();
                    }
                });
            }
        }

        // Add hover effects
        const buttons = app.querySelectorAll('.btn');
        buttons.forEach(btn => {
            btn.addEventListener('mouseenter', () => {
                btn.style.transform = 'translateY(-2px)';
                btn.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
            });
            btn.addEventListener('mouseleave', () => {
                btn.style.transform = 'translateY(0)';
                btn.style.boxShadow = 'none';
            });
        });
    }
}
