// Logic for the /chat.html page

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded event fired');
    
    // Use helper function for waiting for SpekApp
    window.AppUtils.waitForSpekApp(() => {
        console.log('Inside waitForSpekApp callback');
        
        window.spekApp.onReady(() => {
            // Protect the route: redirect to login if not authenticated
            if (!window.spekApp || !window.spekApp.isAuthenticated) {
                window.location.href = '/login';
                return;
            }
        });

        console.log('Past authentication check');

        // Cache DOM elements
        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('messageInput');
        const chatMessages = document.getElementById('chatMessages');
        const documentChipsContainer = document.getElementById('documentChipsContainer');
        const attachFileBtn = document.getElementById('attachFileBtn');
        const chatFileUpload = document.getElementById('chatFileUpload');
        const logoutBtn = document.getElementById('logout-btn');
        const chatSidebar = document.getElementById('chatSidebar');
        const menuBtn = document.getElementById('menuBtn');
        const sidebarToggle = document.getElementById('sidebarToggle');
        const newChatBtn = document.getElementById('newChatBtn');
        const chatList = document.getElementById('chatList');
        const voiceBtn = document.getElementById('voiceBtn');
        const moreBtn = document.getElementById('moreBtn');

        // Debug DOM elements
        console.log('DEBUG: DOM elements found:');
        console.log('  - attachFileBtn:', attachFileBtn);
        console.log('  - documentSelectorOverlay:', document.getElementById('documentSelectorOverlay'));
        console.log('  - documentSelectorPopup:', document.getElementById('documentSelectorPopup'));
        console.log('  - appWideDocuments:', document.getElementById('appWideDocuments'));
        console.log('  - chatSpecificDocuments:', document.getElementById('chatSpecificDocuments'));

        // Store current session ID for the chat
        let currentSessionId = null;
        let chatSessions = [];
        let hasShownWelcomeMessage = false;

        // ==============================================
        // DOCUMENT MANAGEMENT INTEGRATION
        // ==============================================
        
        async function initializeDocumentManagement() {
            console.log('📁 Initializing document management integration...');
            
            if (!window.documentManager) {
                console.warn('⚠️ Document manager not found, retrying...');
                setTimeout(initializeDocumentManagement, 100);
                return;
            }
            
            await window.documentManager.initialize();
            
            // NEW: Connect attach button to hidden file input
            if (attachFileBtn && chatFileUpload) {
                attachFileBtn.addEventListener('click', () => chatFileUpload.click());
                chatFileUpload.addEventListener('change', handleChatFileUpload);
                console.log('✅ Attach button connected to file input.');
            } else {
                console.error('❌ Attach button or file upload input not found');
            }

            // Listen for clicks on the remove button of document chips
            if (documentChipsContainer) {
                documentChipsContainer.addEventListener('click', (e) => {
                    if (e.target.classList.contains('document-chip-remove')) {
                        const chip = e.target.closest('.document-chip');
                        if (chip) {
                            chip.remove();
                            updateSelectedDocumentsForMessage();
                        }
                    }
                });
            }
            
            // Connect docs manager button to document modal (for full management)
            const docsMgrBtn = document.getElementById('docsMgrBtn');
            if (docsMgrBtn) {
                docsMgrBtn.addEventListener('click', () => {
                    console.log('📁 Docs manager button clicked - opening document modal');
                    window.documentManager.openModal();
                });
                console.log('✅ Docs manager button connected to document modal');
            }
            
            console.log('✅ Document management integration complete');
        }

        // NEW: Handle file uploads from the chat input
        async function handleChatFileUpload(event) {
            const files = event.target.files;
            if (!files.length) return;

            for (const file of files) {
                try {
                    // Upload as chat-specific document
                    const doc = await window.documentManager.uploadFile(file, 'chat_specific');
                    if (doc) {
                        addDocumentChip(doc);
                        updateSelectedDocumentsForMessage();
                    }
                } catch (error) {
                    console.error('Error uploading file:', error);
                    // Provide more specific error messages
                    let errorMessage = `Failed to upload ${file.name}`;
                    if (error.message?.includes('size')) {
                        errorMessage = `${file.name} exceeds maximum file size`;
                    } else if (error.message?.includes('type')) {
                        errorMessage = `${file.name} is not a supported file type`;
                    }
                    window.documentManager.showNotification(errorMessage, 'error');
                }
            }
            // Reset file input to allow re-uploading the same file
            event.target.value = '';
        }

        // NEW: Add a document chip to the UI using helper function
        function addDocumentChip(doc) {
            if (!documentChipsContainer) return;
            console.log('DEBUG: Adding document chip for doc:', doc);
            const chip = window.UIHelpers.createDocumentChip(doc);
            documentChipsContainer.appendChild(chip);
        }

        // NEW: Get currently selected documents from chips
        function getSelectedDocumentsFromChips() {
            const chips = document.querySelectorAll('.document-chip');
            console.log('DEBUG: Found chips:', chips.length, chips);
            const documents = [];
            chips.forEach(chip => {
                console.log('DEBUG: Chip dataset:', chip.dataset);
                documents.push({
                    id: chip.dataset.docId,
                    filename: chip.querySelector('.document-chip-name').textContent
                });
            });
            return documents;
        }
        
        // NEW: Function to update the documents associated with the current message
        function updateSelectedDocumentsForMessage() {
            // This function can be expanded if we need to maintain a more complex state
            // For now, getSelectedDocumentsFromChips is sufficient
        }
        
        // Update document manager when chat session changes
        function updateDocumentManagerForSession(sessionId) {
            console.log('📁 Updating document manager for session:', sessionId);
            if (window.documentManager) {
                window.documentManager.setChatId(sessionId);
            }
        }

        // Initialize the app
        init();

        async function init() {
            chatInput.focus();
            initializeSidebar();
            initializeEventListeners();
            await initializeDocumentManagement();
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
            
            // Debug: Check if documentChipsContainer exists and has children
            console.log('DEBUG SEND: documentChipsContainer:', documentChipsContainer);
            console.log('DEBUG SEND: documentChipsContainer.children.length:', documentChipsContainer ? documentChipsContainer.children.length : 'container not found');
            
            const selectedDocuments = getSelectedDocumentsFromChips();
            console.log('DEBUG SEND: selectedDocuments from chips:', selectedDocuments);
            
            // Only send valid UUIDs for selected documents
            const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            const selectedDocumentIds = selectedDocuments
                .map(d => {
                    console.log('DEBUG SEND: Mapping document:', d, 'id:', d.id);
                    return d.id;
                })
                .filter(id => {
                    const isValid = uuidRegex.test(id);
                    console.log('DEBUG SEND: Filtering ID:', id, 'valid:', isValid);
                    return isValid;
                });
            
            console.log('DEBUG SEND: Final selectedDocumentIds:', selectedDocumentIds);

            // Add user message to UI
            addMessage(message, 'user', null, selectedDocuments);
            
            chatInput.value = '';
            chatInput.style.height = 'auto';
            documentChipsContainer.innerHTML = ''; // Clear chips after sending

            // Create a placeholder for the AI response
            const aiMessageDiv = createStreamingMessage();

            try {
                // Using filtered UUIDs for selected documents
                console.log('📎 Sending message with selected documents:', selectedDocumentIds);

                 const requestPayload = {
                     message: message,
                     session_id: currentSessionId,
                     selected_document_ids: selectedDocumentIds
                  };
                  
                console.log('DEBUG SEND: Full request payload:', requestPayload);

                // Use streaming endpoint
                const response = await fetch('/api/v1/chat/text/stream', {
                    method: 'POST',
                    headers:
                     {
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
                                    updateDocumentManagerForSession(data.session_id);
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
            window.AppUtils.updateUrlParameter('session_id', sessionId);
        }

        // Helper to add a message to the UI
        function addMessage(content, sender, timestamp = null, documents = []) {
            console.log('DEBUG: addMessage called:', {
                sender,
                documentsCount: documents.length,
                documents: documents
            });

            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender === 'user' ? 'user-message' : 'ai-message'}`;

            const avatarHtml = sender === 'ai'
                ? `<div class="message-avatar"><i class="fas fa-robot"></i></div>`
                : '';

            // Format content based on sender type
            const formattedContent = sender === 'ai' 
                ? window.MarkdownUtils.parseMarkdown(content)
                : content.replace(/\n/g, '<br>');

            // Use provided timestamp or current time
            const messageTime = timestamp
                ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            // Create document icons if documents are present using helper function
            const documentIcons = window.UIHelpers.createDocumentIconsForMessage(documents);
            console.log('DEBUG: Document icons created:', documentIcons);

            messageDiv.innerHTML = `
                ${avatarHtml}
                <div class="message-content">
                    ${documentIcons ? documentIcons.outerHTML : ''}
                    <div class="message-text">${formattedContent}</div>
                    <div class="message-time">${messageTime}</div>
                </div>
            `;

            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            console.log('DEBUG: Message added to DOM with document icons:', !!documentIcons);
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
            const formattedContent = window.MarkdownUtils.parseMarkdown(content);
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
            console.log('DEBUG: loadChatHistory function called with sessionId:', sessionId);
            try {
                console.log('DEBUG: Loading chat history for session:', sessionId);
                console.log('DEBUG: About to make API request to:', `/chat/history/${sessionId}`);
                
                const response = await window.spekApp.apiClient.request(`/chat/history/${sessionId}`, {
                    method: 'GET'
                });

                console.log('DEBUG: Chat history response:', response);

                // Clear existing messages
                chatMessages.innerHTML = '';
                hasShownWelcomeMessage = false;

                // Add messages from history
                if (response.messages && response.messages.length > 0) {
                    console.log('DEBUG: Processing', response.messages.length, 'messages from history');
                    response.messages.forEach((msg, index) => {
                        console.log(`DEBUG: Message ${index + 1}:`, {
                            content: msg.content.substring(0, 50) + '...',
                            type: msg.message_type,
                            documents: msg.documents,
                            documentsCount: msg.documents ? msg.documents.length : 0
                        });
                        addMessage(
                            msg.content,
                            msg.message_type === 'user' ? 'user' : 'ai',
                            msg.created_at,
                            msg.documents || [] // Include document information
                        );
                    });
                } else if (!hasShownWelcomeMessage) {
                    console.log('DEBUG: No messages in history, showing welcome message');
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

        /**
         * Loads and displays all chat sessions for the authenticated user.
         * Fetches sessions from the API, renders them in the sidebar, and handles URL-based session loading.
         * 
         * This function:
         * - Fetches all user chat sessions from /chat/sessions endpoint
         * - Sorts sessions by creation date (newest first) on the frontend as backup
         * - Renders sessions in the sidebar chat list
         * - Handles URL parameters to load specific sessions
         * - Shows welcome message for new users or empty states
         * 
         * @async
         * @function loadChatSessions
         * @returns {Promise<void>} Resolves when sessions are loaded and rendered
         * 
         * @example
         * // Load and display all chat sessions
         * await loadChatSessions();
         * // Sessions will appear in sidebar ordered by newest first
         * 
         * @throws {Error} If API request fails or sessions cannot be loaded
         */
        async function loadChatSessions() {
            try {
                console.log('DEBUG: Loading chat sessions...');
                const response = await window.spekApp.apiClient.request('/chat/sessions', {
                    method: 'GET'
                });

                chatSessions = response || [];
                
                // Sort sessions by creation date (newest first) as backup to backend sorting
                chatSessions.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                
                console.log(`DEBUG: Loaded ${chatSessions.length} chat sessions`);
                renderChatSessions();

                // Check for session_id in URL after loading sessions
                const urlParams = new URLSearchParams(window.location.search);
                const sessionIdFromUrl = urlParams.get('session_id');
                
                if (sessionIdFromUrl) {
                    currentSessionId = sessionIdFromUrl;
                    updateDocumentManagerForSession(sessionIdFromUrl);
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

        /**
         * Renders the list of chat sessions in the sidebar.
         * Creates interactive chat items with click handlers for navigation and management.
         * 
         * This function:
         * - Clears the existing chat list
         * - Creates DOM elements for each session
         * - Attaches event listeners for navigation and actions
         * - Handles empty state display
         * 
         * @function renderChatSessions
         * @returns {void}
         * 
         * @example
         * // After loading sessions from API
         * chatSessions = [...]; // array of session objects
         * renderChatSessions(); // Will display all sessions in sidebar
         */
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
            
            // Debug: Verify event listeners are attached
            console.log(`DEBUG: Rendered ${chatSessions.length} chat items with event listeners`);
            const clickableItems = chatList.querySelectorAll('.chat-item-main');
            console.log(`DEBUG: Found ${clickableItems.length} clickable chat items`);
        }

        /**
         * Creates a clickable chat item DOM element for the sidebar.
         * Generates the complete chat item with title, preview, actions, and event listeners.
         * 
         * This function:
         * - Creates the HTML structure for a chat session item
         * - Formats the creation date for display
         * - Attaches click handlers for navigation, editing, and deletion
         * - Prevents event bubbling for action buttons
         * 
         * @function createChatItem
         * @param {Object} session - The chat session object from the API
         * @param {string} session.uuid - Unique identifier for the session
         * @param {string} session.title - Display title for the chat
         * @param {string} session.created_at - ISO date string of session creation
         * @returns {HTMLElement} Complete DOM element ready for insertion into chat list
         * 
         * @example
         * const session = {
         *   uuid: "123e4567-e89b-12d3-a456-426614174000",
         *   title: "My Chat Session",
         *   created_at: "2025-09-03T12:00:00Z"
         * };
         * const chatItem = createChatItem(session);
         * chatList.appendChild(chatItem);
         */
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

            // Add event listeners with proper error handling
            const mainArea = chatItem.querySelector('.chat-item-main');
            const editBtn = chatItem.querySelector('.edit-btn');
            const deleteBtn = chatItem.querySelector('.delete-btn');

            // Main click handler for switching to session
            if (mainArea) {
                mainArea.addEventListener('click', (e) => {
                    e.preventDefault();
                    console.log('DEBUG: Chat item clicked, switching to session:', session.uuid);
                    switchToSession(session.uuid);
                });
                mainArea.style.cursor = 'pointer'; // Visual feedback for clickability
            } else {
                console.error('ERROR: Main area not found for session:', session.uuid);
            }

            // Edit button handler
            if (editBtn) {
                editBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    console.log('DEBUG: Edit button clicked for session:', session.uuid);
                    startInlineEdit(session.uuid, session.title || 'Untitled Chat');
                });
            } else {
                console.error('ERROR: Edit button not found for session:', session.uuid);
            }

            // Delete button handler
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    console.log('DEBUG: Delete button clicked for session:', session.uuid);
                    deleteChatSession(session.uuid);
                });
            } else {
                console.error('ERROR: Delete button not found for session:', session.uuid);
            }

            return chatItem;
        }

        /**
         * Creates a new chat session and switches to it.
         * Sends API request to create session, updates local state, and navigates to new chat.
         * 
         * This function:
         * - Sends POST request to create a new chat session
         * - Adds the new session to the beginning of the sessions list (newest first)
         * - Re-renders the chat list to show the new session
         * - Automatically switches to the new session
         * - Closes mobile sidebar for better UX
         * 
         * @async
         * @function createNewChat
         * @returns {Promise<void>} Resolves when new chat is created and loaded
         * 
         * @example
         * // Create a new chat session
         * await createNewChat();
         * // New session will appear at top of sidebar and become active
         * 
         * @throws {Error} If chat creation fails or API request errors
         */
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

                // Add the new session to the beginning of the list (newest first)
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

        /**
         * Switches the active chat session and updates the UI accordingly.
         * Handles session navigation, URL updates, and chat history loading.
         * 
         * This function:
         * - Sets the new session as current
         * - Updates browser URL with session parameter
         * - Loads chat history for the session
         * - Updates document manager context
         * - Manages visual active state
         * - Handles mobile sidebar closing
         * 
         * @function switchToSession
         * @param {string} sessionId - UUID of the session to switch to
         * @returns {void}
         * 
         * @example
         * // Switch to a specific chat session
         * switchToSession("123e4567-e89b-12d3-a456-426614174000");
         * // Browser URL will update to include ?session_id=123e4567...
         * // Chat history will load and session will be marked as active
         */
        function switchToSession(sessionId) {
            console.log('DEBUG: Switching to session:', sessionId);

            currentSessionId = sessionId;

            // Update document manager for new session
            updateDocumentManagerForSession(sessionId);

            // Update URL
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('session_id', sessionId);
            window.history.pushState(null, '', newUrl);

            // Mark session as active
            markSessionAsActive(sessionId);

            // Load chat history
            console.log('DEBUG: About to call loadChatHistory for session:', sessionId);
            console.log('DEBUG: typeof loadChatHistory:', typeof loadChatHistory);
            console.log('DEBUG: loadChatHistory function:', loadChatHistory);
            try {
                const result = loadChatHistory(sessionId);
                console.log('DEBUG: loadChatHistory call result:', result);
                if (result && result.then) {
                    console.log('DEBUG: loadChatHistory returned a promise');
                    result.catch(error => {
                        console.error('DEBUG: loadChatHistory promise rejected:', error);
                    });
                }
                console.log('DEBUG: loadChatHistory call completed');
            } catch (error) {
                console.error('DEBUG: Error calling loadChatHistory:', error);
                console.error('DEBUG: Error stack:', error.stack);
            }

            // Close sidebar on mobile
            closeSidebarOnMobile();
        }

        /**
         * Marks a specific chat session as active in the sidebar.
         * Updates visual indicators to show which session is currently selected.
         * 
         * This function:
         * - Removes active class from all chat items
         * - Adds active class to the specified session
         * - Provides visual feedback for the current session
         * 
         * @function markSessionAsActive
         * @param {string} sessionId - UUID of the session to mark as active
         * @returns {void}
         * 
         * @example
         * // Mark a session as active (visually selected)
         * markSessionAsActive("123e4567-e89b-12d3-a456-426614174000");
         * // The corresponding chat item will show active styling
         */
        function markSessionAsActive(sessionId) {
            // Remove active class from all sessions
            chatList.querySelectorAll('.chat-item').forEach(item => {
                item.classList.remove('active');
            });

            // Add active class to current session
            const activeItem = chatList.querySelector(`[data-session-id="${sessionId}"]`);
            if (activeItem) {
                activeItem.classList.add('active');
                console.log('DEBUG: Marked session as active:', sessionId);
            } else {
                console.warn('WARNING: Could not find chat item to mark as active:', sessionId);
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

        // Make functions available globally for onclick handlers
        window.switchToSession = switchToSession;
        window.deleteChatSession = deleteChatSession;

        console.log('✅ Chat initialization complete');
    });
});