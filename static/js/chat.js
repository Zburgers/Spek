// Logic for the /chat.html page
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
            // Protect the route: redirect to login if not authenticated
            if (!window.spekApp || !window.spekApp.isAuthenticated) {
                window.location.href = '/login';
                return;
            }
        });

        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('messageInput');
        const chatMessages = document.getElementById('chatMessages');
        const logoutBtn = document.getElementById('logout-btn');

        chatInput.focus();

        // Handle message submission
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = chatInput.value.trim();
            if (!message) return;

            addMessage(message, 'user');
            chatInput.value = '';
            chatInput.style.height = 'auto'; // Reset height after sending

            const typingIndicator = addTypingIndicator();

            try {
                const response = await window.spekApp.apiClient.sendMessage(message);
                addMessage(response.response || 'Sorry, I could not process that request.', 'ai');
            } catch (error) {
                console.error('Chat error:', error);
                addMessage('Sorry, an error occurred. Please try again.', 'ai');
            } finally {
                typingIndicator.remove();
            }
        });

        // Handle logout
        logoutBtn.addEventListener('click', async () => {
            await window.spekApp.apiClient.logout();
            window.location.href = '/login';
        });

        // Auto-resize textarea
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = `${chatInput.scrollHeight}px`;
        });

        // Helper to add a message to the UI
        function addMessage(content, sender) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender === 'user' ? 'user-message' : 'ai-message'}`;
            
            const avatarHtml = sender === 'ai' 
                ? `<div class="message-avatar"><i class="fas fa-robot"></i></div>` 
                : '';

            const textContent = content.replace(/\n/g, '<br>'); // Preserve newlines
            
            messageDiv.innerHTML = `
                ${avatarHtml}
                <div class="message-content">
                    <div class="message-text">${textContent}</div>
                    <div class="message-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                </div>
            `;
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Helper to show a typing indicator
        function addTypingIndicator() {
            const typingDiv = document.createElement('div');
            typingDiv.className = 'message ai-message typing-indicator';
            typingDiv.innerHTML = `
                <div class="message-avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content">
                    <div class="message-text">
                        <div class="typing-dots"><span></span><span></span><span></span></div>
                    </div>
                </div>
            `;
            
            chatMessages.appendChild(typingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return typingDiv;
        }
    });
});