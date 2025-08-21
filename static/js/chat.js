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
        
        // Sidebar elements
        const chatSidebar = document.getElementById('chatSidebar');
        const menuBtn = document.getElementById('menuBtn');
        const sidebarToggle = document.getElementById('sidebarToggle');
        const newChatBtn = document.getElementById('newChatBtn');
        const chatList = document.getElementById('chatList');

        // Store current session ID for the chat
        let currentSessionId = null;
        let chatSessions = [];

        chatInput.focus();

        // Initialize sidebar functionality
        initializeSidebar();

        // Load chat sessions and check for session_id in URL
        loadChatSessions();

        // Handle message submission
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await sendMessage();
        });

        // Add Enter key handler for message input
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Function to send message with streaming
        async function sendMessage() {
            const message = chatInput.value.trim();
            if (!message) return;

            addMessage(message, 'user');
            chatInput.value = '';
            chatInput.style.height = 'auto'; // Reset height after sending

            // Create a placeholder message for the AI response
            const aiMessageDiv = createStreamingMessage();

            try {
                const requestPayload = {
                    message: message,
                    session_id: currentSessionId
                };

                // Use streaming endpoint
                const response = await fetch('/api/v1/chat/text/stream', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${window.spekApp.getToken()}`
                    },
                    body: JSON.stringify(requestPayload)
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let aiResponseContent = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const dataStr = line.slice(6);
                            if (dataStr.trim()) {
                                try {
                                    const data = JSON.parse(dataStr);
                                    
                                    if (data.session_id && !currentSessionId) {
                                        // Update session ID for new chats
                                        currentSessionId = data.session_id;
                                        const newUrl = new URL(window.location);
                                        newUrl.searchParams.set('session_id', data.session_id);
                                        window.history.replaceState(null, '', newUrl);
                                        loadChatSessions(); // Refresh sidebar
                                    }
                                    
                                    if (data.chunk) {
                                        aiResponseContent += data.chunk;
                                        updateStreamingMessage(aiMessageDiv, aiResponseContent);
                                    }
                                    
                                    if (data.complete) {
                                        finalizeStreamingMessage(aiMessageDiv);
                                    }
                                    
                                    if (data.error) {
                                        throw new Error(data.error);
                                    }
                                } catch (parseError) {
                                    console.warn('Failed to parse SSE data:', parseError);
                                }
                            }
                        }
                    }
                }

            } catch (error) {
                console.error('Chat error:', error);
                let errorMessage = 'Sorry, an error occurred. Please try again.';
                
                if (error.message) {
                    if (error.message.includes('not configured')) {
                        errorMessage = 'AI service is not available right now. Please try again later.';
                    } else if (error.message.includes('unauthorized')) {
                        errorMessage = 'Your session has expired. Please log in again.';
                        setTimeout(() => {
                            window.location.href = '/login';
                        }, 2000);
                    } else {
                        errorMessage = error.message;
                    }
                }
                
                // Update the streaming message with error
                updateStreamingMessage(aiMessageDiv, errorMessage);
                finalizeStreamingMessage(aiMessageDiv);
            }
        }

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

        // Tool button event listeners
        const attachBtn = document.getElementById('attachBtn');
        const voiceBtn = document.getElementById('voiceBtn');
        const moreBtn = document.getElementById('moreBtn');

        if (attachBtn) {
            attachBtn.addEventListener('click', () => {
                // Placeholder for file attachment
                alert('File attachment feature coming soon!');
            });
        }

        if (voiceBtn) {
            voiceBtn.addEventListener('click', () => {
                // Placeholder for voice message
                alert('Voice message feature coming soon!');
            });
        }

        if (moreBtn) {
            moreBtn.addEventListener('click', () => {
                // Placeholder for more options
                alert('More options coming soon!');
            });
        }

        // Helper to add a message to the UI
        function addMessage(content, sender, timestamp = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender === 'user' ? 'user-message' : 'ai-message'}`;
            
            const avatarHtml = sender === 'ai' 
                ? `<div class="message-avatar"><i class="fas fa-robot"></i></div>` 
                : '';

            // Format content based on sender type
            let formattedContent;
            if (sender === 'ai') {
                // Apply markdown formatting for AI messages
                formattedContent = parseMarkdown(content);
            } else {
                // Preserve newlines for user messages
                formattedContent = content.replace(/\n/g, '<br>');
            }
            
            // Use provided timestamp or current time
            const messageTime = timestamp 
                ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            messageDiv.innerHTML = `
                ${avatarHtml}
                <div class="message-content">
                    <div class="message-text">${formattedContent}</div>
                    <div class="message-time">${messageTime}</div>
                </div>
            `;
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Parse markdown formatting
        function parseMarkdown(text) {
            let formatted = text;
            
            // Bold text (**text** or __text__)
            formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            formatted = formatted.replace(/__(.*?)__/g, '<strong>$1</strong>');
            
            // Italic text (*text* or _text_)
            formatted = formatted.replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<em>$1</em>');
            formatted = formatted.replace(/(?<!_)_([^_]+?)_(?!_)/g, '<em>$1</em>');
            
            // Code blocks (```code```)
            formatted = formatted.replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>');
            
            // Inline code (`code`)
            formatted = formatted.replace(/`([^`]+?)`/g, '<code>$1</code>');
            
            // Line breaks
            formatted = formatted.replace(/\n/g, '<br>');
            
            // Lists (- item or * item)
            formatted = formatted.replace(/^[\-\*]\s(.+)$/gm, '<li>$1</li>');
            formatted = formatted.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
            
            // Numbered lists (1. item)
            formatted = formatted.replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>');
            // Note: This is a simplified approach - a full parser would handle nested lists better
            
            return formatted;
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

        // Create a placeholder message for streaming
        function createStreamingMessage() {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ai-message streaming';
            
            const messageTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            messageDiv.innerHTML = `
                <div class="message-avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content">
                    <div class="message-text">
                        <div class="streaming-cursor">|</div>
                    </div>
                    <div class="message-time">${messageTime}</div>
                </div>
            `;
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return messageDiv;
        }

        // Update streaming message content
        function updateStreamingMessage(messageDiv, content) {
            const messageText = messageDiv.querySelector('.message-text');
            const formattedContent = parseMarkdown(content);
            messageText.innerHTML = formattedContent + '<div class="streaming-cursor">|</div>';
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Finalize streaming message
        function finalizeStreamingMessage(messageDiv) {
            const cursor = messageDiv.querySelector('.streaming-cursor');
            if (cursor) {
                cursor.remove();
            }
            messageDiv.classList.remove('streaming');
        }

        // Load chat history for a session
        async function loadChatHistory(sessionId) {
            try {
                const response = await window.spekApp.apiClient.request(`/chat/history/${sessionId}`, {
                    method: 'GET'
                });

                // Clear existing messages
                chatMessages.innerHTML = '';

                // Add messages from history
                if (response.messages && response.messages.length > 0) {
                    response.messages.forEach(msg => {
                        addMessage(
                            msg.content, 
                            msg.message_type === 'user' ? 'user' : 'ai',
                            msg.created_at
                        );
                    });
                } else {
                    // Add welcome message if no history
                    // addMessage("Hello! I'm your AI assistant. How can I help you today?", 'ai');
                }

            } catch (error) {
                console.error('Error loading chat history:', error);
                // Add welcome message on error
                addMessage("Hello! I'm your AI assistant. How can I help you today?", 'ai');
            }
        }

        // Initialize sidebar functionality
        function initializeSidebar() {
            // Toggle sidebar on mobile
            if (menuBtn) {
                menuBtn.addEventListener('click', () => {
                    chatSidebar.classList.toggle('hidden');
                });
            }

            if (sidebarToggle) {
                sidebarToggle.addEventListener('click', () => {
                    chatSidebar.classList.add('hidden');
                });
            }

            // New chat button
            if (newChatBtn) {
                newChatBtn.addEventListener('click', createNewChat);
            }

            // Close sidebar when clicking outside on mobile
            document.addEventListener('click', (e) => {
                if (window.innerWidth <= 768 && 
                    !chatSidebar.contains(e.target) && 
                    !menuBtn.contains(e.target) &&
                    !chatSidebar.classList.contains('hidden')) {
                    chatSidebar.classList.add('hidden');
                }
            });
        }

        // Load all chat sessions for the user
        async function loadChatSessions() {
            try {
                console.log('DEBUG: Loading chat sessions...');
                const response = await window.spekApp.apiClient.request('/chat/sessions', {
                    method: 'GET'
                });

                chatSessions = response || [];
                console.log(`DEBUG: Loaded ${chatSessions.length} chat sessions`);
                renderChatSessions();

                // Check for session_id in URL after loading sessions
                const urlParams = new URLSearchParams(window.location.search);
                const sessionIdFromUrl = urlParams.get('session_id');
                if (sessionIdFromUrl) {
                    currentSessionId = sessionIdFromUrl;
                    loadChatHistory(currentSessionId);
                    markSessionAsActive(currentSessionId);
                } else {
                    // Show welcome message for new chat
                    addMessage("Hello! I'm your AI assistant powered by Google's Gemini. How can I help you today?", 'ai');
                }

            } catch (error) {
                console.error('Error loading chat sessions:', error);
                chatList.innerHTML = '<div class="loading">Failed to load chat history</div>';
            }
        }

        // Render chat sessions in the sidebar
        function renderChatSessions() {
            if (chatSessions.length === 0) {
                chatList.innerHTML = '<div class="loading">No chat history yet</div>';
                return;
            }

            chatList.innerHTML = '';
            chatSessions.forEach(session => {
                const chatItem = document.createElement('div');
                chatItem.className = 'chat-item';
                chatItem.dataset.sessionId = session.uuid;
                
                // Format the created date
                const createdDate = new Date(session.created_at);
                const timeStr = createdDate.toLocaleDateString();
                
                chatItem.innerHTML = `
                    <div class="chat-item-main" data-session-id="${session.uuid}">
                        <div class="chat-item-content">
                            <div class="chat-item-title" id="title-${session.uuid}">${session.title || 'Untitled Chat'}</div>
                            <div class="chat-item-preview">Click to continue conversation</div>
                        </div>
                        <div class="chat-item-time">${timeStr}</div>
                    </div>
                    <div class="chat-item-actions">
                        <button class="action-btn edit-btn" title="Edit chat name" data-session-id="${session.uuid}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="action-btn delete-btn" title="Delete chat" data-session-id="${session.uuid}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                `;

                // Add click event to the main area only
                const mainArea = chatItem.querySelector('.chat-item-main');
                mainArea.addEventListener('click', () => switchToSession(session.uuid));
                
                // Add edit button event listener
                const editBtn = chatItem.querySelector('.edit-btn');
                editBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    startInlineEdit(session.uuid, session.title || 'Untitled Chat');
                });
                
                // Add delete button event listener
                const deleteBtn = chatItem.querySelector('.delete-btn');
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteChatSession(session.uuid);
                });
                
                chatList.appendChild(chatItem);
            });
        }

        // Create a new chat session
        async function createNewChat() {
            try {
                console.log('DEBUG: Creating new chat session...');
                const response = await window.spekApp.apiClient.request('/chat/sessions', {
                    method: 'POST',
                    body: JSON.stringify({ title: 'New Chat' })
                });

                console.log('DEBUG: Created new session:', response.uuid);
                
                // Add the new session to the list
                chatSessions.unshift(response);
                renderChatSessions();
                
                // Switch to the new session
                switchToSession(response.uuid);
                
                // Close sidebar on mobile
                if (window.innerWidth <= 768) {
                    chatSidebar.classList.add('hidden');
                }

            } catch (error) {
                console.error('Error creating new chat:', error);
                alert('Failed to create new chat. Please try again.');
            }
        }

        // Switch to a different chat session
        function switchToSession(sessionId) {
            console.log('DEBUG: Switching to session:', sessionId);
            
            currentSessionId = sessionId;
            
            // Update URL
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('session_id', sessionId);
            window.history.pushState(null, '', newUrl);
            
            // Mark session as active
            markSessionAsActive(sessionId);
            
            // Load chat history
            loadChatHistory(sessionId);
            
            // Close sidebar on mobile
            if (window.innerWidth <= 768) {
                chatSidebar.classList.add('hidden');
            }
        }

        // Mark a session as active in the sidebar
        function markSessionAsActive(sessionId) {
            // Remove active class from all sessions
            chatList.querySelectorAll('.chat-item').forEach(item => {
                item.classList.remove('active');
            });
            
            // Add active class to current session
            const activeItem = chatList.querySelector(`[data-session-id="${sessionId}"]`);
            if (activeItem) {
                activeItem.classList.add('active');
            }
        }

        // Inline editing functions
        function startInlineEdit(sessionId, currentTitle) {
            const titleElement = document.getElementById(`title-${sessionId}`);
            if (!titleElement) return;

            // Create input element
            const input = document.createElement('input');
            input.type = 'text';
            input.value = currentTitle;
            input.className = 'chat-title-input';
            input.maxLength = 100;

            // Replace title with input
            const originalContent = titleElement.innerHTML;
            titleElement.innerHTML = '';
            titleElement.appendChild(input);

            // Focus and select all text
            input.focus();
            input.select();

            // Handle save on Enter
            input.addEventListener('keydown', async (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    await saveInlineEdit(sessionId, input.value.trim(), titleElement, originalContent);
                } else if (e.key === 'Escape') {
                    // Cancel edit
                    titleElement.innerHTML = originalContent;
                }
            });

            // Handle save on blur
            input.addEventListener('blur', async () => {
                await saveInlineEdit(sessionId, input.value.trim(), titleElement, originalContent);
            });
        }

        async function saveInlineEdit(sessionId, newTitle, titleElement, originalContent) {
            if (!newTitle || newTitle.length === 0) {
                // Restore original if empty
                titleElement.innerHTML = originalContent;
                return;
            }

            try {
                console.log('DEBUG: Updating chat title for session:', sessionId);
                await window.spekApp.apiClient.request(`/chat/sessions/${sessionId}/title`, {
                    method: 'PUT',
                    body: JSON.stringify({ title: newTitle })
                });

                // Update the session in our local array
                const session = chatSessions.find(s => s.uuid === sessionId);
                if (session) {
                    session.title = newTitle;
                    titleElement.innerHTML = newTitle;
                }

                console.log('DEBUG: Successfully updated chat title');
            } catch (error) {
                console.error('Error updating chat title:', error);
                // Restore original content on error
                titleElement.innerHTML = originalContent;
                alert('Failed to update chat title. Please try again.');
            }
        }

        async function deleteChatSession(sessionId) {
            if (confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
                try {
                    console.log('DEBUG: Deleting chat session:', sessionId);
                    await window.spekApp.apiClient.request(`/chat/sessions/${sessionId}`, {
                        method: 'DELETE'
                    });

                    // Remove the session from our local array
                    chatSessions = chatSessions.filter(s => s.uuid !== sessionId);
                    renderChatSessions();

                    // If we deleted the current session, redirect to a new chat
                    if (currentSessionId === sessionId) {
                        currentSessionId = null;
                        const newUrl = new URL(window.location);
                        newUrl.searchParams.delete('session_id');
                        window.history.pushState(null, '', newUrl);
                        
                        // Clear chat messages and show welcome message
                        chatMessages.innerHTML = '';
                        addMessage("Hello! I'm your AI assistant powered by Google's Gemini. How can I help you today?", 'ai');
                    }

                    console.log('DEBUG: Successfully deleted chat session');
                } catch (error) {
                    console.error('Error deleting chat session:', error);
                    alert('Failed to delete chat session. Please try again.');
                }
            }
        };
    });
});