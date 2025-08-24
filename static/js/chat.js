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

        // Cache DOM elements
        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('messageInput');
        const chatMessages = document.getElementById('chatMessages');
        const logoutBtn = document.getElementById('logout-btn');
        const chatSidebar = document.getElementById('chatSidebar');
        const menuBtn = document.getElementById('menuBtn');
        const sidebarToggle = document.getElementById('sidebarToggle');
        const newChatBtn = document.getElementById('newChatBtn');
        const chatList = document.getElementById('chatList');
        const attachBtn = document.getElementById('attachBtn');
        const voiceBtn = document.getElementById('voiceBtn');
        const moreBtn = document.getElementById('moreBtn');

        // Store current session ID for the chat
        let currentSessionId = null;
        let chatSessions = [];
        let hasShownWelcomeMessage = false;

        // Initialize the app
        init();

        async function init() {
            chatInput.focus();
            initializeSidebar();
            initializeEventListeners();
            await loadChatSessions();
        }

        function initializeEventListeners() {
            // Handle message submission
            chatForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await sendMessage();
            });

            // Add Enter key handler for message input
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    chatForm.dispatchEvent(new Event('submit'));
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

            // Tool button event listeners
            if (attachBtn) {
                attachBtn.addEventListener('click', () => {
                    alert('File attachment feature coming soon!');
                });
            }

            if (voiceBtn) {
                voiceBtn.addEventListener('click', () => {
                    alert('Voice message feature coming soon!');
                });
            }

            if (moreBtn) {
                moreBtn.addEventListener('click', () => {
                    alert('More options coming soon!');
                });
            }
        }

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

                await handleStreamingResponse(response, aiMessageDiv);

            } catch (error) {
                console.error('Chat error:', error);
                handleChatError(error, aiMessageDiv);
            }
        }

        async function handleStreamingResponse(response, aiMessageDiv) {
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
                                    // Validate session_id format (assuming UUID)
                                    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
                                    if (!uuidRegex.test(data.session_id)) {
                                        console.error('Invalid session ID format received:', data.session_id);
                                        throw new Error('Invalid session ID received from server');
                                    }
                                    // Update session ID for new chats
                                    currentSessionId = data.session_id;
                                    updateUrlWithSessionId(data.session_id);
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
        }

        function handleChatError(error, aiMessageDiv) {
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

        function updateUrlWithSessionId(sessionId) {
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('session_id', sessionId);
            window.history.replaceState(null, '', newUrl);
        }

        // Helper to add a message to the UI
        function addMessage(content, sender, timestamp = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender === 'user' ? 'user-message' : 'ai-message'}`;

            const avatarHtml = sender === 'ai'
                ? `<div class="message-avatar"><i class="fas fa-robot"></i></div>`
                : '';

            // Format content based on sender type
            const formattedContent = sender === 'ai' 
                ? parseMarkdown(content)
                : content.replace(/\n/g, '<br>');

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
            formatted = formatted.replace(/(^|[^*])\*([^*]+?)\*(?!\*)/g, '$1<em>$2</em>');
            formatted = formatted.replace(/(^|[^_])_([^_]+?)_(?!_)/g, '$1<em>$2</em>');

            // Code blocks (```code```)
            formatted = formatted.replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>');

            // Inline code (`code`)
            formatted = formatted.replace(/`([^`]+?)`/g, '<code>$1</code>');

            // Process lists line by line for better control
            formatted = processLists(formatted);

            // Line breaks (after list processing)
            formatted = formatted.replace(/\n/g, '<br>');

            return formatted;
        }

        function processLists(text) {
            const lines = text.split('\n');
            let inUl = false, inOl = false;
            const processedLines = [];

            for (let line of lines) {
                if (/^[\-\*]\s/.test(line)) {
                    if (!inUl) {
                        if (inOl) {
                            processedLines.push('</ol>');
                            inOl = false;
                        }
                        processedLines.push('<ul>');
                        inUl = true;
                    }
                    processedLines.push(line.replace(/^[\-\*]\s(.+)$/, '<li>$1</li>'));
                } else if (/^\d+\.\s/.test(line)) {
                    if (!inOl) {
                        if (inUl) {
                            processedLines.push('</ul>');
                            inUl = false;
                        }
                        processedLines.push('<ol>');
                        inOl = true;
                    }
                    processedLines.push(line.replace(/^\d+\.\s(.+)$/, '<li>$1</li>'));
                } else {
                    if (inUl) {
                        processedLines.push('</ul>');
                        inUl = false;
                    }
                    if (inOl) {
                        processedLines.push('</ol>');
                        inOl = false;
                    }
                    processedLines.push(line);
                }
            }

            // Close any remaining open lists
            if (inUl) processedLines.push('</ul>');
            if (inOl) processedLines.push('</ol>');

            return processedLines.join('\n');
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
                hasShownWelcomeMessage = false;

                // Add messages from history
                if (response.messages && response.messages.length > 0) {
                    response.messages.forEach(msg => {
                        addMessage(
                            msg.content,
                            msg.message_type === 'user' ? 'user' : 'ai',
                            msg.created_at
                        );
                    });
                } else if (!hasShownWelcomeMessage) {
                    // Only show welcome message if no history and haven't shown it yet
                    showWelcomeMessage();
                }

            } catch (error) {
                console.error('Error loading chat history:', error);
                // Only show welcome message on error if we haven't shown it yet
                if (!hasShownWelcomeMessage) {
                    showWelcomeMessage();
                }
            }
        }

        function showWelcomeMessage() {
            if (!hasShownWelcomeMessage) {
                addMessage("Hello! I'm your AI assistant powered by Google's Gemini. How can I help you today?", 'ai');
                hasShownWelcomeMessage = true;
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
                    menuBtn && !menuBtn.contains(e.target) &&
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
                    await loadChatHistory(currentSessionId);
                    markSessionAsActive(currentSessionId);
                } else if (!hasShownWelcomeMessage) {
                    // Show welcome message for new chat only if we haven't shown it yet
                    showWelcomeMessage();
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
                const chatItem = createChatItem(session);
                chatList.appendChild(chatItem);
            });
        }

        function createChatItem(session) {
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

            // Add event listeners
            const mainArea = chatItem.querySelector('.chat-item-main');
            const editBtn = chatItem.querySelector('.edit-btn');
            const deleteBtn = chatItem.querySelector('.delete-btn');

            mainArea.addEventListener('click', () => switchToSession(session.uuid));
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                startInlineEdit(session.uuid, session.title || 'Untitled Chat');
            });
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteChatSession(session.uuid);
            });

            return chatItem;
        }

        // Create a new chat session
        async function createNewChat() {
            try {
                console.log('DEBUG: Creating new chat session...');
                const response = await window.spekApp.apiClient.request('/chat/sessions', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ title: 'New Chat' })
                });

                console.log('DEBUG: Created new session:', response.uuid);

                // Add the new session to the list
                chatSessions.unshift(response);
                renderChatSessions();

                // Switch to the new session
                switchToSession(response.uuid);

                // Close sidebar on mobile
                closeSidebarOnMobile();

            } catch (error) {
                console.error('Error creating new chat:', error);
                alert('Failed to create new chat. Please try again.');
            }
        }

        function closeSidebarOnMobile() {
            if (window.innerWidth <= 768) {
                chatSidebar.classList.add('hidden');
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
            closeSidebarOnMobile();
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

            // Handle save on Enter or blur
            const saveEdit = async () => {
                const newTitle = input.value.trim();
                if (newTitle && newTitle !== currentTitle) {
                    await saveInlineEdit(sessionId, newTitle, titleElement, originalContent);
                } else {
                    titleElement.innerHTML = originalContent;
                }
                input.removeEventListener('blur', saveEdit);
            };

            input.addEventListener('keydown', async (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    await saveEdit();
                } else if (e.key === 'Escape') {
                    // Cancel edit
                    titleElement.innerHTML = originalContent;
                    input.removeEventListener('blur', saveEdit);
                }
            });

            input.addEventListener('blur', saveEdit);
        }

        async function saveInlineEdit(sessionId, newTitle, titleElement, originalContent) {
            try {
                console.log('DEBUG: Updating chat title:', sessionId, newTitle);
                await window.spekApp.apiClient.request(`/chat/sessions/${sessionId}/title`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
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
            if (!confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
                return;
            }

            // Backup in case subsequent UI updates fail
            const originalSessionsList = [...chatSessions];

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
                    hasShownWelcomeMessage = false;
                    showWelcomeMessage();
                }

                console.log('DEBUG: Successfully deleted chat session');
            } catch (error) {
                console.error('Error deleting chat session:', error);
                // Restore the original state
                chatSessions = originalSessionsList;
                renderChatSessions();
                alert('Failed to delete chat session. Please try again.');
            }
        }
    });
});