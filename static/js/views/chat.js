// Chat view module
export function render() {
    const app = document.getElementById('app');
    if (app) {
        app.innerHTML = `
            <section class="chat-view" style="max-width: 1000px; margin: 0 auto; height: 80vh; display: flex; flex-direction: column;">
                <div class="chat-header" style="background: white; padding: 1rem; border-radius: 10px 10px 0 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h2 style="margin: 0; color: #333;">Spek Chat</h2>
                            <span style="color: #28a745; font-size: 0.9rem;">● Connected</span>
                        </div>
                        <div>
                            <button id="logout-btn" style="padding: 0.5rem 1rem; background: #dc3545; color: white; border: none; border-radius: 5px; cursor: pointer;">
                                Logout
                            </button>
                        </div>
                    </div>
                </div>

                <div class="chat-container" style="flex: 1; background: white; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden;">
                    <div id="chat-messages" style="flex: 1; overflow-y: auto; padding: 1rem; background: #f8f9fa;">
                        <div class="message ai-message" style="margin-bottom: 1rem; padding: 1rem; border-radius: 10px; background: #e9ecef; margin-right: 20%;">
                            <strong>Spek AI:</strong> Hello! I'm your AI assistant. How can I help you today?
                        </div>
                    </div>
                    
                    <div class="chat-input-container" style="padding: 1rem; border-top: 1px solid #e9ecef; background: white;">
                        <form id="chat-form" style="display: flex; gap: 1rem;">
                            <input type="text" id="chat-input" placeholder="Type your message..." 
                                   style="flex: 1; padding: 0.75rem; border: 1px solid #ddd; border-radius: 25px; font-size: 1rem; outline: none;"
                                   autocomplete="off" />
                            <button type="submit" id="send-btn" 
                                    style="padding: 0.75rem 1.5rem; background: #667eea; color: white; border: none; border-radius: 25px; cursor: pointer; font-size: 1rem;">
                                Send
                            </button>
                        </form>
                    </div>
                </div>

                <div style="text-align: center; margin-top: 1rem;">
                    <a href="#/" data-link style="color: #667eea; text-decoration: none;">← Back to Home</a>
                </div>
            </section>
        `;

        // Add event listeners
        setupChatEventListeners();
    }
}

function setupChatEventListeners() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const logoutBtn = document.getElementById('logout-btn');

    // Focus input
    chatInput.focus();

    // Chat form submission
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage(message, 'user');
        chatInput.value = '';

        // Show typing indicator
        const typingIndicator = addTypingIndicator();

        try {
            // Send message to API
            const response = await window.spekApp.apiClient.sendMessage(message);
            
            // Remove typing indicator
            typingIndicator.remove();
            
            // Add AI response
            addMessage(response.message || response.response || 'Sorry, I could not process that request.', 'ai');
            
        } catch (error) {
            console.error('Chat error:', error);
            typingIndicator.remove();
            addMessage('Sorry, there was an error processing your message. Please try again.', 'ai');
            window.spekApp.notifications.error('Failed to send message');
        }
    });

    // Logout functionality
    logoutBtn.addEventListener('click', async () => {
        try {
            await window.spekApp.apiClient.logout();
            window.spekApp.clearAuth();
            window.spekApp.notifications.success('Successfully logged out');
            window.spekApp.router.navigateTo('#/login');
        } catch (error) {
            console.error('Logout error:', error);
            // Clear auth anyway
            window.spekApp.clearAuth();
            window.spekApp.router.navigateTo('#/login');
        }
    });

    function addMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const senderName = sender === 'user' ? 'You' : 'Spek AI';
        const messageStyle = sender === 'user' 
            ? 'margin-bottom: 1rem; padding: 1rem; border-radius: 10px; background: #667eea; color: white; margin-left: 20%;'
            : 'margin-bottom: 1rem; padding: 1rem; border-radius: 10px; background: #e9ecef; margin-right: 20%;';
        
        messageDiv.style.cssText = messageStyle;
        messageDiv.innerHTML = `<strong>${senderName}:</strong> ${content}`;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return messageDiv;
    }

    function addTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message ai-message typing-indicator';
        typingDiv.style.cssText = 'margin-bottom: 1rem; padding: 1rem; border-radius: 10px; background: #e9ecef; margin-right: 20%; opacity: 0.7;';
        typingDiv.innerHTML = '<strong>Spek AI:</strong> <em>typing...</em>';
        
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return typingDiv;
    }
}
