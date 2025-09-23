/**
 * Centralized Document Manager
 * 
 * Handles all document operations for both app-wide and chat-specific contexts.
 * Provides a unified interface that replaces the two separate document systems.
 */

class DocumentManager {
    constructor() {
        // Operating modes
        this.MODES = {
            MODAL: 'modal',       // Full document management modal
            SELECTOR: 'selector'  // Document selection popup for chat
        };

        // Current state
        this.currentMode = null;
        this.currentChatId = null;
        this.isInitialized = false;

        // Cached data
        this.cachedDocuments = null;
        this.cachedChatDocuments = null;
        this.lastCacheTime = null;
        this.CACHE_DURATION = 30000; // 30 seconds

        this.selectedDocumentIds = new Set();
        this.tempSelectedDocumentIds = new Set();

        // DOM references (will be set during initialization)
        this.elements = {
            // Modal elements
            modal: null,
            modalCloseBtn: null,
            modalUploadArea: null,
            modalFileInput: null,
            modalUploadBtn: null,
            modalRefreshBtn: null,
            modalDocumentsList: null,
            modalDetailsModal: null,

            // Selector popup elements
            selectorOverlay: null,
            selectorPopup: null,
            selectorCloseBtn: null,
            selectorAppWideContainer: null,
            selectorChatContainer: null,
            selectorQuickUploadInput: null,
            selectorAppWideCount: null,
            selectorChatCount: null,
            selectorApplyBtn: null,
            selectorCancelBtn: null
        };

        // WebSocket connection for live status updates
        this.statusWebSocket = null;
        this.monitoredDocuments = new Set();
        
        // Event handlers
        this.eventHandlers = {
            modalOpen: () => this.openModal(),
            modalClose: () => this.closeModal(),
            selectorOpen: () => this.openSelector(),
            selectorClose: () => this.closeSelector(),
            refreshDocuments: () => this.refreshDocuments(),
            modalFileUpload: (e) => this.handleModalFileUpload(e),
            selectorFileUpload: (e) => this.handleSelectorFileUpload(e),
            modalFileDrop: (e) => this.handleModalFileDrop(e),
            modalFileDragOver: (e) => this.handleFileDragOver(e),
            modalFileDragLeave: (e) => this.handleFileDragLeave(e)
        };

        console.log('📁 Centralized DocumentManager initialized');
    }

    /**
     * Initialize the document manager with DOM elements and event listeners
     */
    async initialize() {
        if (this.isInitialized) {
            console.log('📁 DocumentManager already initialized');
            return;
        }

        console.log('📁 Initializing DocumentManager...');
        
        // Get DOM references
        this.setupDOMReferences();
        
        // Setup event listeners
        this.setupEventListeners();

        // Setup global window functions for backward compatibility
        this.setupGlobalFunctions();

        // Initialize WebSocket for live status updates
        this.initializeStatusWebSocket();

        this.isInitialized = true;
        console.log('✅ DocumentManager initialized successfully');
    }

    /**
     * Initialize WebSocket connection for live document status updates
     */
    initializeStatusWebSocket() {
        try {
            // Clear any existing heartbeat or planned reconnects
            if (this._wsHeartbeatInterval) {
                clearInterval(this._wsHeartbeatInterval);
            }
            if (this._wsPlannedReconnect) {
                clearTimeout(this._wsPlannedReconnect);
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const token = (window.spekApp && window.spekApp.getToken) ? window.spekApp.getToken() : localStorage.getItem('access_token');
            const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
            const wsUrl = `${protocol}//${window.location.host}/api/v1/documents/status-updates${tokenQuery}`;

            // Exponential backoff state
            this._wsAttempts = (this._wsAttempts || 0);
            const backoffBase = 1000; // 1s
            const maxBackoff = 15000; // 15s
            const backoff = Math.min(backoffBase * Math.pow(2, this._wsAttempts), maxBackoff) + Math.floor(Math.random() * 300);

            console.log(`📡 Connecting document status WebSocket (attempt ${this._wsAttempts + 1}, backoff ${backoff}ms if needed)...`);
            this.statusWebSocket = new WebSocket(wsUrl);

            this.statusWebSocket.onopen = () => {
                console.log('📡 Document status WebSocket connected');
                this._wsAttempts = 0; // reset attempts
                // Initial ping
                this.statusWebSocket.send('ping');
                // Heartbeat every 25s
                this._wsHeartbeatInterval = setInterval(() => {
                    if (this.statusWebSocket && this.statusWebSocket.readyState === WebSocket.OPEN) {
                        this.statusWebSocket.send('ping');
                    }
                }, 25000);
                // Re-subscribe to monitored documents
                this.monitoredDocuments.forEach(docId => {
                    try { this.statusWebSocket.send(docId); } catch (_) {}
                });
            };

            this.statusWebSocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.error) {
                        console.warn('📡 WebSocket error message:', data.error);
                        if (data.error === 'unauthorized') {
                            // Stop reconnecting permanently until user re-authenticates
                            this._wsAuthFailed = true;
                            this.cleanupWebSocket();
                            return;
                        }
                        return; // ignore other errors for now
                    }
                    if (data.document_id && data.status) {
                        this.handleStatusUpdate(data);
                    }
                } catch (error) {
                    // Non-JSON (e.g., pong)
                    if (event.data === 'pong') return;
                    console.log('WebSocket message (non-JSON):', event.data);
                }
            };

            this.statusWebSocket.onclose = (evt) => {
                console.log(`📡 Document status WebSocket disconnected (code=${evt.code}).`);
                this.cleanupWebSocket();
                if (this._wsAuthFailed) {
                    console.log('📡 Not reconnecting due to auth failure.');
                    return;
                }
                this._wsAttempts += 1;
                this._wsPlannedReconnect = setTimeout(() => this.initializeStatusWebSocket(), backoff);
            };

            this.statusWebSocket.onerror = (error) => {
                console.error('📡 WebSocket error:', error);
            };

        } catch (error) {
            console.error('Failed to initialize status WebSocket:', error);
        }
    }

    cleanupWebSocket() {
        if (this._wsHeartbeatInterval) {
            clearInterval(this._wsHeartbeatInterval);
            this._wsHeartbeatInterval = null;
        }
        if (this.statusWebSocket && this.statusWebSocket.readyState !== WebSocket.OPEN) {
            try { this.statusWebSocket.close(); } catch (_) {}
        }
    }

    /**
     * Handle real-time status updates from WebSocket
     */
    handleStatusUpdate(statusData) {
        const { document_id, status, filename, scope, updated_at } = statusData;
        
        console.log(`📊 Status update for ${filename}: ${status}`);
        
        // Update document in local storage
        const scopeType = scope === 'app_wide' ? 'app_wide' : 'chat_specific';
        const documents = this.documents[scopeType];
        
        const docIndex = documents.findIndex(doc => 
            (doc.uuid || doc.id) === document_id
        );
        
        if (docIndex !== -1) {
            documents[docIndex].status = status;
            documents[docIndex].processing_status = status;
            if (updated_at) {
                documents[docIndex].updated_at = updated_at;
            }
            
            // Update UI if document is currently visible
            this.updateDocumentStatusInUI(document_id, status);
            
            // Show notification for status changes
            this.showStatusNotification(filename, status);
        }
    }

    /**
     * Update document status in the current UI
     */
    updateDocumentStatusInUI(documentId, status) {
        // Update in document lists
        const documentItems = document.querySelectorAll(`.document-item[data-doc-id="${documentId}"]`);
        documentItems.forEach(item => {
            const statusElement = item.querySelector('.document-status');
            if (statusElement) {
                statusElement.textContent = this.formatStatus(status);
                statusElement.className = `document-status status-${this.getStatusClass(status)}`;
            }
        });
        
        // Update in modal details if open
        const detailsStatus = document.getElementById('docDetailsStatus');
        if (detailsStatus && detailsStatus.getAttribute('data-doc-id') === documentId) {
            detailsStatus.textContent = this.formatStatus(status);
            detailsStatus.className = `document-status status-${this.getStatusClass(status)}`;
        }
    }

    /**
     * Show status change notification
     */
    showStatusNotification(filename, status) {
        const statusMessages = {
            'processing': `🔄 Processing ${filename}...`,
            'completed': `✅ ${filename} processing completed!`,
            'processed': `✅ ${filename} processing completed!`,
            'failed': `❌ Failed to process ${filename}`,
            'error': `❌ Error processing ${filename}`
        };
        
        const message = statusMessages[status] || `📄 ${filename} status: ${status}`;
        this.showNotification(message, status === 'completed' || status === 'processed' ? 'success' : 
                             status === 'failed' || status === 'error' ? 'error' : 'info');
    }

    /**
     * Monitor a document for status updates
     */
    monitorDocumentStatus(documentId) {
        if (this.statusWebSocket && this.statusWebSocket.readyState === WebSocket.OPEN) {
            if (!this.monitoredDocuments.has(documentId)) {
                this.statusWebSocket.send(documentId);
                this.monitoredDocuments.add(documentId);
                console.log(`📊 Monitoring status for document: ${documentId}`);
            }
        }
    }

    /**
     * Stop monitoring a document
     */
    stopMonitoringDocument(documentId) {
        this.monitoredDocuments.delete(documentId);
    }

    /**
     * Set up DOM element references
     */
    setupDOMReferences() {
        // Modal elements
        this.elements.modal = document.getElementById('documentsModal');
        this.elements.modalCloseBtn = document.querySelector('#documentsModal .modal-close');
        this.elements.modalUploadArea = document.getElementById('uploadArea');
        this.elements.modalFileInput = document.getElementById('fileInput');
        this.elements.modalUploadBtn = document.getElementById('uploadBtn');
        this.elements.modalRefreshBtn = document.getElementById('refreshDocsBtn');
        this.elements.modalDocumentsList = document.getElementById('documentsList');
        this.elements.modalDetailsModal = document.getElementById('documentDetailsModal');
        this.elements.modalDetailsCloseBtn = document.getElementById('documentDetailsModalClose');

        console.log('📁 Document Details Modal Elements:', {
            modal: !!this.elements.modalDetailsModal,
            closeBtn: !!this.elements.modalDetailsCloseBtn,
            modalElement: this.elements.modalDetailsModal,
            closeBtnElement: this.elements.modalDetailsCloseBtn
        });

        // Selector popup elements
        this.elements.selectorOverlay = document.getElementById('documentSelectorOverlay');
        this.elements.selectorPopup = document.getElementById('documentSelectorPopup');
        this.elements.selectorCloseBtn = document.getElementById('closeSelectorBtn');
        this.elements.selectorAppWideContainer = document.getElementById('appWideDocuments');
        this.elements.selectorChatContainer = document.getElementById('chatSpecificDocuments');
        this.elements.selectorQuickUploadInput = document.getElementById('quickUploadInput');
        this.elements.selectorAppWideCount = document.getElementById('appWideCount');
        this.elements.selectorChatCount = document.getElementById('chatDocsCount');
        this.elements.selectorApplyBtn = document.getElementById('applySelectorBtn');
        this.elements.selectorCancelBtn = document.getElementById('cancelSelectorBtn');

        console.log('📁 DOM references set up', {
            modal: !!this.elements.modal,
            selectorOverlay: !!this.elements.selectorOverlay,
            allElementsFound: Object.values(this.elements).every(el => el !== null)
        });
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Tab event listeners
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.getAttribute('data-tab'));
            });
        });

        // Modal event listeners
        if (this.elements.modalCloseBtn) {
            this.elements.modalCloseBtn.addEventListener('click', this.eventHandlers.modalClose);
        }

        if (this.elements.modalRefreshBtn) {
            this.elements.modalRefreshBtn.addEventListener('click', this.eventHandlers.refreshDocuments);
        }

        if (this.elements.modalUploadArea) {
            this.elements.modalUploadArea.addEventListener('dragover', this.eventHandlers.modalFileDragOver);
            this.elements.modalUploadArea.addEventListener('dragleave', this.eventHandlers.modalFileDragLeave);
            this.elements.modalUploadArea.addEventListener('drop', this.eventHandlers.modalFileDrop);
            this.elements.modalUploadArea.addEventListener('click', () => {
                if (this.elements.modalFileInput) this.elements.modalFileInput.click();
            });
        }

        if (this.elements.modalFileInput) {
            this.elements.modalFileInput.addEventListener('change', this.eventHandlers.modalFileUpload);
        }

        if (this.elements.modalUploadBtn) {
            this.elements.modalUploadBtn.addEventListener('click', () => {
                if (this.elements.modalFileInput) this.elements.modalFileInput.click();
            });
        }

        // Document details modal close button
        if (this.elements.modalDetailsCloseBtn) {
            this.elements.modalDetailsCloseBtn.addEventListener('click', () => {
                console.log('📁 Document details close button clicked');
                this.closeDocumentDetails();
            });
            console.log('✅ Document details close button event listener added');
        } else {
            console.error('❌ Document details close button not found!');
        }

        // Close document details modal when clicking outside
        if (this.elements.modalDetailsModal) {
            this.elements.modalDetailsModal.addEventListener('click', (e) => {
                if (e.target === this.elements.modalDetailsModal) {
                    console.log('📁 Document details modal overlay clicked');
                    this.closeDocumentDetails();
                }
            });
            console.log('✅ Document details modal overlay click listener added');
        } else {
            console.error('❌ Document details modal not found!');
        }

        // Selector event listeners
        if (this.elements.selectorCloseBtn) {
            this.elements.selectorCloseBtn.addEventListener('click', this.eventHandlers.selectorClose);
        }

        if (this.elements.selectorCancelBtn) {
            this.elements.selectorCancelBtn.addEventListener('click', this.eventHandlers.selectorClose);
        }

        if (this.elements.selectorQuickUploadInput) {
            this.elements.selectorQuickUploadInput.addEventListener('change', this.eventHandlers.selectorFileUpload);
        }

        if (this.elements.selectorApplyBtn) {
            this.elements.selectorApplyBtn.addEventListener('click', () => this.applySelection());
        }

        // Upload area click handler for selector
        const selectorUploadArea = document.querySelector('#upload-section-content .upload-area');
        if (selectorUploadArea) {
            selectorUploadArea.addEventListener('click', () => {
                const uploadInput = document.getElementById('quickUploadInput');
                if (uploadInput) uploadInput.click();
            });
        }

        // Close on overlay click
        if (this.elements.modal) {
            this.elements.modal.addEventListener('click', (e) => {
                if (e.target === this.elements.modal) {
                    this.closeModal();
                }
            });
        }

        if (this.elements.selectorOverlay) {
            this.elements.selectorOverlay.addEventListener('click', (e) => {
                if (e.target === this.elements.selectorOverlay) {
                    this.closeSelector();
                }
            });
        }

        console.log('📁 Event listeners set up');
    }

    /**
     * Set up global window functions for backward compatibility
     */
    setupGlobalFunctions() {
        window.openDocumentSelector = () => this.openSelector();
        window.closeDocumentSelector = () => this.closeSelector();
        window.addDocumentToChat = (docId) => this.addDocumentToChat(docId);
        window.removeDocumentFromChat = (docId) => this.removeDocumentFromChat(docId);
        window.openDocumentModal = () => this.openModal();
        
        console.log('📁 Global window functions set up for backward compatibility');
    }

    /**
     * Set the current chat ID and update document manager state.
     * This method is called when switching between chat sessions to ensure
     * the document manager displays the correct documents for the active chat.
     * 
     * @param {string} chatId - The UUID of the chat session to switch to
     * 
     * @example
     * // Switch to a specific chat session
     * documentManager.setChatId('059991a4-f8bc-4336-bb76-df6d9b281512');
     * 
     * @use_case Loading chat-specific documents when user clicks on a chat history item
     */
    setChatId(chatId) {
        console.log('📁 Setting chat ID:', chatId);
        this.currentChatId = chatId;
        // Clear chat-specific cache when chat changes
        this.cachedChatDocuments = null;
        this.selectedDocumentIds.clear();
        this.tempSelectedDocumentIds.clear();
        // When a chat is loaded, we should probably fetch its selected docs
        if (chatId) {
            this.getChatDocuments().then(docs => {
                this.selectedDocumentIds = new Set(docs.selected_document_ids);
            }).catch(error => {
                console.error('❌ Error loading chat documents:', error);
            });
        }
    }

    /**
     * Get the currently selected document IDs for the active chat.
     */
    getSelectedDocumentIds() {
        return Array.from(this.selectedDocumentIds);
    }

    /**
     * Open document management modal
     */
    async openModal() {
        console.log('📁 Opening document management modal');
        this.currentMode = this.MODES.MODAL;

        if (this.elements.modal) {
            // Let CSS handle visibility/centering
            this.elements.modal.classList.add('active');
            await this.loadDocumentsForModal();
        } else {
            console.error('❌ Document modal not found');
        }
    }

    /**
     * Close document management modal
     */
    closeModal() {
        console.log('📁 Closing document management modal');
        if (this.elements.modal) {
            this.elements.modal.classList.remove('active');
        }
        this.currentMode = null;
    }

    /**
     * Open document selector popup
     */
    async openSelector() {
        console.log('📁 Opening document selector popup');
        this.currentMode = this.MODES.SELECTOR;

        if (this.elements.selectorOverlay) {
            // Let CSS handle it through the active class
            this.elements.selectorOverlay.classList.add('active');
            
            const chatDocs = await this.getChatDocuments();
            this.selectedDocumentIds = new Set(chatDocs.selected_document_ids || []);
            this.tempSelectedDocumentIds = new Set(this.selectedDocumentIds);
            
            await this.loadDocumentsForSelector();
            this.updateSelectedCount();
        } else {
            console.error('❌ Document selector overlay not found');
        }
    }

    /**
     * Close document selector popup
     */
    closeSelector() {
        console.log('📁 Closing document selector popup');
        if (this.elements.selectorOverlay) {
            this.elements.selectorOverlay.classList.remove('active');
        }
        this.currentMode = null;
    }

    /**
     * Close document details modal
     */
    closeDetails() {
        if (this.elements.modalDetailsModal) {
            this.elements.modalDetailsModal.classList.remove('active');
        }
    }

    /**
     * Check if cache is valid
     */
    isCacheValid() {
        return this.lastCacheTime && 
               (Date.now() - this.lastCacheTime) < this.CACHE_DURATION;
    }

    /**
     * Get documents from cache or API
     */
    async getDocuments(forceRefresh = false) {
        if (!forceRefresh && this.isCacheValid() && this.cachedDocuments) {
            console.log('📁 Using cached documents');
            return this.cachedDocuments;
        }

        console.log('📁 Fetching documents from API' + (forceRefresh ? ' (FORCE REFRESH)' : ''));
        try {
            const response = await window.spekApp.apiClient.getDocuments();
            console.log('📁 DEBUG: Documents API response:', response);
            
            // Extract the data array from the response
            const documents = response.data || response || [];
            console.log('📁 DEBUG: Documents count:', documents.length);
            
            this.cachedDocuments = documents;
            this.lastCacheTime = Date.now();
            return documents;
        } catch (error) {
            console.error('❌ Error fetching documents:', error);
            throw error;
        }
    }

    /**
     * Get chat documents (app-wide + chat-specific + selection state)
     */
    async getChatDocuments(forceRefresh = false) {
        if (!this.currentChatId) {
            console.warn('⚠️ No current chat ID set for getChatDocuments - returning empty chat documents');
            return { 
                app_wide_documents: [], 
                chat_specific_documents: [], 
                selected_document_ids: [] 
            };
        }

        const cacheKey = `chat_${this.currentChatId}`;
        if (!forceRefresh && this.cachedChatDocuments && this.cachedChatDocuments[cacheKey]) {
            console.log('📁 Using cached chat documents');
            return this.cachedChatDocuments[cacheKey];
        }

        console.log('📁 Fetching chat documents from API');
        try {
            const response = await window.spekApp.apiClient.getChatDocuments(this.currentChatId);
            
            if (!this.cachedChatDocuments) {
                this.cachedChatDocuments = {};
            }
            this.cachedChatDocuments[cacheKey] = response;
            
            return response;
        } catch (error) {
            console.error('❌ Error fetching chat documents:', error);
            throw error;
        }
    }

    /**
     * Load documents for modal display
     */
    async loadDocumentsForModal(forceRefresh = false) {
        if (!this.elements.modalDocumentsList) {
            console.error('❌ Modal documents list not found');
            return;
        }

        try {
            this.elements.modalDocumentsList.innerHTML = `
                <div class="loading">
                    <div class="loading-spinner"></div>
                    <div>Loading documents...</div>
                </div>
            `;
            
            const response = await this.getDocuments(forceRefresh);
            const documents = response || [];

            console.log('📁 DEBUG: Modal response from API:', response);
            console.log('📁 Loaded', documents.length, 'documents for modal');

            if (documents.length === 0) {
                this.elements.modalDocumentsList.innerHTML = `
                    <div class="no-documents">
                        <i class="fas fa-folder-open" style="font-size: 3rem; margin-bottom: 1rem; color: #cbd5e1;"></i>
                        <h3>No Documents Found</h3>
                        <p>Upload some documents to get started with your AI assistant.</p>
                    </div>
                `;
                return;
            }

            // Create grid container
            this.elements.modalDocumentsList.innerHTML = '<div class="documents-grid"></div>';
            const gridContainer = this.elements.modalDocumentsList.querySelector('.documents-grid');
            
            documents.forEach(doc => {
                const docElement = this.createModalDocumentElement(doc);
                gridContainer.appendChild(docElement);
            });

        } catch (error) {
            console.error('❌ Error loading documents for modal:', error);
            this.elements.modalDocumentsList.innerHTML = `
                <div class="error">
                    <i class="fas fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                    <h3>Failed to Load Documents</h3>
                    <p>Please try again or contact support if the problem persists.</p>
                </div>
            `;
        }
    }

    /**
     * Load documents for selector display
     */
    async loadDocumentsForSelector(forceRefresh = false) {
        try {
            if (this.elements.selectorAppWideContainer) {
                this.elements.selectorAppWideContainer.innerHTML = '<div class="loading-message">Loading app-wide documents...</div>';
            }
            if (this.elements.selectorChatContainer) {
                this.elements.selectorChatContainer.innerHTML = '<div class="loading-message">Loading chat documents...</div>';
            }

            // Load all documents and chat-specific data
            const [allDocuments, chatDocuments] = await Promise.all([
                this.getDocuments(forceRefresh),
                this.getChatDocuments(forceRefresh)
            ]);

            console.log('📁 DEBUG: Selector - allDocuments from API:', allDocuments);
            console.log('📁 DEBUG: Selector - chatDocuments from API:', chatDocuments);
            this.displaySelectorDocuments(allDocuments || [], chatDocuments);

        } catch (error) {
            console.error('❌ Error loading documents for selector:', error);
            this.showNotification('Failed to load documents', 'error');
        }
    }

    /**
     * Display documents in selector mode
     */
    displaySelectorDocuments(allDocuments, chatDocuments) {
        // Display app-wide documents
        if (this.elements.selectorAppWideContainer) {
            const appWideDocuments = allDocuments.filter(doc => doc.scope === 'app_wide');
            console.log('📁 All documents:', allDocuments);
            console.log('📁 App-wide documents after filtering:', appWideDocuments);
            
            // Create document category structure
            this.elements.selectorAppWideContainer.innerHTML = `
                <div class="document-category">
                    <div class="category-header" onclick="documentManager.toggleCategory('app-wide')">
                        <h3 class="category-title">
                            <i class="fas fa-globe"></i>
                            App-wide Documents
                            <span class="category-count">${appWideDocuments.length}</span>
                        </h3>
                        <button class="category-toggle" id="app-wide-toggle">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                    </div>
                    <div class="category-content" id="app-wide-content">
                        <div class="selector-documents-grid" id="app-wide-grid">
                            ${appWideDocuments.length === 0 ? 
                                `<div class="no-documents">
                                    <i class="fas fa-globe" style="font-size: 2rem; margin-bottom: 1rem; color: #cbd5e1;"></i>
                                    <p>No app-wide documents available</p>
                                </div>` : ''
                            }
                        </div>
                    </div>
                </div>
            `;
            
            if (appWideDocuments.length > 0) {
                const gridContainer = this.elements.selectorAppWideContainer.querySelector('#app-wide-grid');
                appWideDocuments.forEach(doc => {
                    const isSelected = this.tempSelectedDocumentIds.has(doc.uuid);
                    const docElement = this.createSelectorDocumentElement(doc, 'app_wide', isSelected);
                    gridContainer.appendChild(docElement);
                });
            }

            if (this.elements.selectorAppWideCount) {
                this.elements.selectorAppWideCount.textContent = appWideDocuments.length.toString();
            }
        }

        // Display chat-specific documents
        if (this.elements.selectorChatContainer) {
            const chatSpecificDocuments = allDocuments.filter(doc => doc.scope === 'chat_specific' && doc.chat_id === this.currentChatId);
            
            // Create document category structure
            this.elements.selectorChatContainer.innerHTML = `
                <div class="document-category">
                    <div class="category-header" onclick="documentManager.toggleCategory('chat-specific')">
                        <h3 class="category-title">
                            <i class="fas fa-comments"></i>
                            Chat-specific Documents
                            <span class="category-count">${chatSpecificDocuments.length}</span>
                        </h3>
                        <button class="category-toggle" id="chat-specific-toggle">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                    </div>
                    <div class="category-content" id="chat-specific-content">
                        <div class="selector-documents-grid" id="chat-specific-grid">
                            ${chatSpecificDocuments.length === 0 ? 
                                `<div class="no-documents">
                                    <i class="fas fa-comments" style="font-size: 2rem; margin-bottom: 1rem; color: #cbd5e1;"></i>
                                    <p>No chat-specific documents yet</p>
                                </div>` : ''
                            }
                        </div>
                    </div>
                </div>
            `;
            
            if (chatSpecificDocuments.length > 0) {
                const gridContainer = this.elements.selectorChatContainer.querySelector('#chat-specific-grid');
                chatSpecificDocuments.forEach(doc => {
                    const isSelected = this.tempSelectedDocumentIds.has(doc.uuid);
                    const docElement = this.createSelectorDocumentElement(doc, 'chat_specific', isSelected);
                    gridContainer.appendChild(docElement);
                });
            }

            if (this.elements.selectorChatCount) {
                this.elements.selectorChatCount.textContent = chatSpecificDocuments.length.toString();
            }
        }

        // Update selection count
        this.updateSelectedCount();
    }

    /**
     * Toggle collapsible document category
     */
    toggleCategory(categoryId) {
        const content = document.getElementById(`${categoryId}-content`);
        const toggle = document.getElementById(`${categoryId}-toggle`);
        
        if (content && toggle) {
            const isCollapsed = content.classList.contains('collapsed');
            
            if (isCollapsed) {
                content.classList.remove('collapsed');
                toggle.classList.remove('collapsed');
            } else {
                content.classList.add('collapsed');
                toggle.classList.add('collapsed');
            }
        }
    }

    /**
     * Switch between tabs in the document management modal
     */
    switchTab(targetTabId) {
        // Hide all tab panes
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        
        // Remove active class from all tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Show target tab pane
        const targetPane = document.getElementById(targetTabId);
        if (targetPane) {
            targetPane.classList.add('active');
        }
        
        // Add active class to clicked tab button
        const targetBtn = document.querySelector(`[data-tab="${targetTabId}"]`);
        if (targetBtn) {
            targetBtn.classList.add('active');
        }

        // If switching to manage tab, load documents
        if (targetTabId === 'manage-tab') {
            this.loadDocumentsForModal();
        }
    }

    /**
     * Create document element for modal display
     */
    createModalDocumentElement(doc) {
        const docDiv = document.createElement('div');
        docDiv.className = 'document-card';
        docDiv.setAttribute('data-doc-id', doc.uuid || doc.id);
        
        // Determine file icon based on extension
        const fileExtension = doc.filename.split('.').pop().toLowerCase();
        const fileIcon = this.getFileIcon(fileExtension);
        
        docDiv.innerHTML = `
            <div class="document-card-header">
                <div class="document-card-icon">
                    <i class="fas ${fileIcon}"></i>
                </div>
                <div class="document-card-info">
                    <div class="document-card-name" title="${doc.filename}">${doc.filename}</div>
                    <div class="document-card-meta">
                        <span class="document-card-size">
                            <i class="fas fa-hdd"></i>
                            ${this.formatFileSize(doc.file_size)}
                        </span>
                        <span class="document-card-date">
                            <i class="fas fa-calendar-alt"></i>
                            ${this.formatDate(doc.created_at)}
                        </span>
                    </div>
                </div>
            </div>
            <div class="document-card-status-row">
                <span class="document-status status-${this.getStatusClass(doc.processing_status)}">
                    <i class="fas ${this.getStatusIcon(doc.processing_status)}"></i>
                    ${this.formatStatus(doc.processing_status)}
                </span>
                <span class="document-scope scope-${doc.scope}">
                    <i class="fas ${doc.scope === 'app_wide' ? 'fa-globe' : 'fa-comments'}"></i>
                    ${doc.scope === 'app_wide' ? 'App-wide' : 'Chat-specific'}
                </span>
            </div>
            <div class="document-card-actions">
                <button class="document-action-btn view" onclick="documentManager.viewDocument('${doc.uuid}')" title="View Details">
                    <i class="fas fa-eye"></i>
                    View
                </button>
                <button class="document-action-btn delete" onclick="documentManager.deleteDocument('${doc.uuid}')" title="Delete">
                    <i class="fas fa-trash"></i>
                    Delete
                </button>
            </div>
        `;
        return docDiv;
    }

    /**
     * Create document element for selector display
     */
    createSelectorDocumentElement(doc, type, isSelected) {
        const div = document.createElement('div');
        div.className = `selector-document-card ${isSelected ? 'selected' : ''}`;
        const docId = doc.uuid || doc.id;
        const docName = doc.filename || doc.file_name;
        div.setAttribute('data-doc-id', docId);
        
        // Determine file icon based on extension
        const fileExtension = docName.split('.').pop().toLowerCase();
        const fileIcon = this.getFileIcon(fileExtension);
        
        div.innerHTML = `
            <div class="selector-card-header">
                <div class="selector-card-icon">
                    <i class="fas ${fileIcon}"></i>
                </div>
                <div class="selector-card-name" title="${docName}">${docName}</div>
            </div>
            <div class="selector-card-meta">
                <span class="selector-card-size">
                    <i class="fas fa-hdd"></i>
                    ${this.formatFileSize(doc.file_size)}
                </span>
                <span class="document-status status-${this.getStatusClass(doc.status || doc.processing_status)}">
                    <i class="fas ${this.getStatusIcon(doc.status || doc.processing_status)}"></i>
                    ${this.formatStatus(doc.status || doc.processing_status)}
                </span>
            </div>
            <button class="selector-card-select" onclick="documentManager.toggleDocumentSelection('${docId}', this.closest('.selector-document-card'))">
                ${isSelected ? 'Selected' : 'Select'}
            </button>
        `;
        
        // Add click event for the entire card
        div.addEventListener('click', (e) => {
            if (!e.target.closest('.selector-card-select')) {
                this.toggleDocumentSelection(docId, div);
            }
        });
        
        return div;
    }

    /**
     * Toggle document selection in the selector popup
     */
    toggleDocumentSelection(documentId, cardElement) {
        if (this.tempSelectedDocumentIds.has(documentId)) {
            this.tempSelectedDocumentIds.delete(documentId);
            cardElement.classList.remove('selected');
            const button = cardElement.querySelector('.selector-card-select');
            if (button) {
                button.textContent = 'Select';
            }
        } else {
            this.tempSelectedDocumentIds.add(documentId);
            cardElement.classList.add('selected');
            const button = cardElement.querySelector('.selector-card-select');
            if (button) {
                button.textContent = 'Selected';
            }
        }
        this.updateSelectedCount();
    }

    /**
     * Toggle document selection in the selector popup (legacy support)
     */
    toggleSelection(documentId, buttonElement) {
        const cardElement = buttonElement.closest('.selector-document-card') || buttonElement.closest('.document-item');
        this.toggleDocumentSelection(documentId, cardElement);
    }

    /**
     * Update the 'X documents selected' text
     */
    updateSelectedCount() {
        const count = this.tempSelectedDocumentIds.size;
        const countElement = document.getElementById('selectedCount');
        if (countElement) {
            countElement.textContent = `${count} document${count === 1 ? '' : 's'} selected`;
        }
    }

    /**
     * Apply the selection from the popup
     */
    async applySelection() {
        if (!this.currentChatId) {
            this.showNotification('Please start a chat session first', 'error');
            return;
        }

        try {
            const documentIds = Array.from(this.tempSelectedDocumentIds);
            await window.spekApp.apiClient.associateDocumentsWithChat(this.currentChatId, documentIds, true);
            
            this.selectedDocumentIds = new Set(this.tempSelectedDocumentIds);
            
            this.showNotification('Document selection applied successfully');
            this.closeSelector();

        } catch (error) {
            console.error('❌ Error applying document selection:', error);
            this.showNotification('Failed to apply document selection', 'error');
        }
    }

    /**
     * Add document to current chat
     */
    async addDocumentToChat(documentId) {
        if (!this.currentChatId) {
            this.showNotification('Please start a chat session first', 'error');
            return;
        }

        try {
            await window.spekApp.apiClient.addDocumentToChat(this.currentChatId, documentId);
            this.showNotification('Document added to chat successfully');
            
            // Clear cache and refresh if in selector mode
            this.cachedChatDocuments = null;
            if (this.currentMode === this.MODES.SELECTOR) {
                await this.loadDocumentsForSelector();
            }
        } catch (error) {
            console.error('❌ Error adding document to chat:', error);
            this.showNotification('Failed to add document to chat', 'error');
        }
    }

    /**
     * Remove document from current chat
     */
    async removeDocumentFromChat(documentId) {
        if (!this.currentChatId) {
            this.showNotification('No active chat session', 'error');
            return;
        }

        try {
            await window.spekApp.apiClient.removeDocumentFromChat(this.currentChatId, documentId);
            this.showNotification('Document removed from chat successfully');
            
            // Clear cache and refresh if in selector mode
            this.cachedChatDocuments = null;
            if (this.currentMode === this.MODES.SELECTOR) {
                await this.loadDocumentsForSelector();
            }
        } catch (error) {
            console.error('❌ Error removing document from chat:', error);
            this.showNotification('Failed to remove document from chat', 'error');
        }
    }

    /**
     * Handle file upload in modal
     */
    async handleModalFileUpload(event) {
        const files = Array.from(event.target.files);
        console.log('📄 DEBUG: DocumentManager.modal.handleFileUpload called with', files.length, 'files');
        
        if (files.length === 0) return;

        for (const file of files) {
            console.log('📄 DEBUG: Processing file:', file.name, 'Size:', file.size, 'Type:', file.type);
            await this.uploadFile(file, 'app_wide');
        }

        // Clear the input
        event.target.value = '';
        
        console.log('📄 DEBUG: Modal file upload completed successfully');
        
        // Refresh modal display
        if (this.currentMode === this.MODES.MODAL) {
            console.log('📄 DEBUG: Refreshing modal after upload...');
            await this.loadDocumentsForModal();
        }
    }

    /**
     * Handle file upload in selector
     */
    async handleSelectorFileUpload(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;

        // Check upload scope from radio buttons
        const scopeRadios = document.querySelectorAll('input[name="uploadScope"]');
        let scope = 'app_wide';
        for (const radio of scopeRadios) {
            if (radio.checked) {
                scope = radio.value;
                break;
            }
        }

        for (const file of files) {
            await this.uploadFile(file, scope);
        }

        // Clear the input
        event.target.value = '';
        
        // Refresh selector display
        if (this.currentMode === this.MODES.SELECTOR) {
            await this.loadDocumentsForSelector();
        }
    }

    /**
     * Handle file drop in modal
     */
    handleModalFileDrop(event) {
        event.preventDefault();
        this.elements.modalUploadArea.classList.remove('dragover');
        
        const files = Array.from(event.dataTransfer.files);
        console.log('📁 Files dropped:', files.length);
        
        files.forEach(file => this.uploadFile(file, 'app_wide'));
    }

    /**
     * Handle drag over
     */
    handleFileDragOver(event) {
        event.preventDefault();
        event.currentTarget.classList.add('dragover');
    }

    /**
     * Handle drag leave
     */
    handleFileDragLeave(event) {
        event.currentTarget.classList.remove('dragover');
    }

    /**
     * Upload a file
     */
    async uploadFile(file, scope = 'app_wide') {
        console.log('� DEBUG: DocumentManager.modal.uploadFile called with:', file.name);

        // Validate file
        if (!this.validateFile(file)) {
            return;
        }

        try {
            let response;
            if (scope === 'chat_specific' && this.currentChatId) {
                response = await window.spekApp.apiClient.uploadChatDocument(this.currentChatId, file);
            } else {
                response = await window.spekApp.apiClient.uploadDocument(file, scope);
            }

            console.log('📤 Upload successful:', response);
            console.log('📤 Uploaded document scope:', response.scope);
            
            this.showNotification(`Document "${file.name}" uploaded successfully`);
            
            // Start monitoring document status for real-time updates
            if (response && response.document_id) {
                this.monitorDocumentStatus(response.document_id);
            }
            
            // Clear relevant caches
            this.cachedDocuments = null;
            if (scope === 'chat_specific') {
                this.cachedChatDocuments = null;
            }

            console.log('📤 DEBUG: Caches cleared after upload');
            return response;
        } catch (error) {
            console.error('❌ Error uploading file:', error);
            this.showNotification(`Failed to upload "${file.name}"`, 'error');
            throw error;
        }
    }

    /**
     * Validate file before upload - Now using AppUtils helper
     */
    validateFile(file) {
        const result = window.AppUtils.validateFile(file);
        if (!result.success) {
            this.showNotification(result.error, 'error');
            return false;
        }
        return true;
    }

    /**
     * View document details
     */
    async viewDocument(docId) {
        try {
            const doc = await window.spekApp.apiClient.getDocument(docId);
            this.showDocumentDetails(doc);
        } catch (error) {
            console.error('❌ Error loading document details:', error);
            this.showNotification('Failed to load document details', 'error');
        }
    }

    /**
     * Show document details modal
     */
    showDocumentDetails(doc) {
        if (this.elements.modalDetailsModal) {
            // removed inline style manipulation
            this.elements.modalDetailsModal.classList.add('active');
        }
        const docId = doc.uuid || doc.id;
        document.getElementById('docDetailsTitle').textContent = doc.filename || doc.file_name;
        document.getElementById('docDetailsSize').textContent = this.formatFileSize(doc.file_size);
        document.getElementById('docDetailsDate').textContent = this.formatDate(doc.created_at || doc.uploaded_at);
        document.getElementById('docDetailsStatus').textContent = this.formatStatus(doc.processing_status || doc.status);
        document.getElementById('docDetailsStatus').className = `document-status status-${this.getStatusClass(doc.processing_status || doc.status)}`;
        document.getElementById('docDetailsStatus').setAttribute('data-doc-id', docId);
    }

    /**
     * Close document details modal
     */
    closeDocumentDetails() {
        console.log('📁 Closing document details modal');
        if (this.elements.modalDetailsModal) {
            this.elements.modalDetailsModal.classList.remove('active');
            console.log('✅ Document details modal closed');
        } else {
            console.error('❌ Document details modal element not found!');
        }
    }

    /**
     * Delete document
     */
    async deleteDocument(docId) {
        if (!confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
            return;
        }

        try {
            await window.spekApp.apiClient.deleteDocument(docId);
            this.showNotification('Document deleted successfully');
            
            // CRITICAL: Force clear all caches and refresh immediately
            this.cachedDocuments = null;
            this.cachedChatDocuments = null;
            this.lastCacheTime = null;
            
            // Force refresh current view with cache bypass
            if (this.currentMode === this.MODES.MODAL) {
                await this.loadDocumentsForModal(true); // Force refresh
            } else if (this.currentMode === this.MODES.SELECTOR) {
                await this.loadDocumentsForSelector(true); // Force refresh
            }
            
            // Also force refresh any cached data in API client
            if (window.spekApp.apiClient.clearDocumentCache) {
                window.spekApp.apiClient.clearDocumentCache();
            }
            
        } catch (error) {
            console.error('❌ Error deleting document:', error);
            this.showNotification('Failed to delete document', 'error');
        }
    }

    /**
     * Refresh documents
     */
    async refreshDocuments() {
        console.log('📁 Refreshing documents...');
        
        // Clear all caches
        this.cachedDocuments = null;
        this.cachedChatDocuments = null;
        this.lastCacheTime = null;

        // Reload current view
        if (this.currentMode === this.MODES.MODAL) {
            await this.loadDocumentsForModal();
        } else if (this.currentMode === this.MODES.SELECTOR) {
            await this.loadDocumentsForSelector();
        }

        this.showNotification('Documents refreshed');
    }

    /**
     * Utility functions - Now using FormattingUtils helper
     */
    formatFileSize(bytes) {
        return window.FormattingUtils.formatFileSize(bytes);
    }

    formatDate(dateString) {
        return window.FormattingUtils.formatDate(dateString);
    }

    formatStatus(status) {
        return window.FormattingUtils.formatStatus(status);
    }

    getStatusClass(status) {
        return window.FormattingUtils.getStatusClass(status);
    }

    showNotification(message, type = 'success') {
        return window.AppUtils.showNotification(message, type);
    }

    /**
     * Get appropriate file icon based on file extension
     */
    getFileIcon(extension) {
        return window.FormattingUtils.getFileIcon(extension);
    }

    /**
     * Get appropriate status icon based on processing status
     */
    getStatusIcon(status) {
        return window.FormattingUtils.getStatusIcon(status);
    }
}

// Create global instance
window.documentManager = new DocumentManager();
