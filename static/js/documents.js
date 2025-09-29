// Documents Page JavaScript

class DocumentManager {
    constructor() {
        this.selectedDocument = null;
        this.documents = [];
        this.pollInterval = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadDocuments();
    }

    setupEventListeners() {
        // File upload
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');

        uploadArea.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', this.handleFileUpload.bind(this));

        // Drag and drop
        uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
        uploadArea.addEventListener('dragleave', this.handleDragLeave.bind(this));
        uploadArea.addEventListener('drop', this.handleFileDrop.bind(this));

        // Query
        document.getElementById('query-btn').addEventListener('click', this.handleQuery.bind(this));
        document.getElementById('query-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                this.handleQuery();
            }
        });

        // Clear selection
        document.getElementById('clear-selection').addEventListener('click', this.clearSelection.bind(this));
    }

    handleDragOver(e) {
        e.preventDefault();
        document.getElementById('upload-area').classList.add('dragover');
    }

    handleDragLeave(e) {
        e.preventDefault();
        document.getElementById('upload-area').classList.remove('dragover');
    }

    handleFileDrop(e) {
        e.preventDefault();
        document.getElementById('upload-area').classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            this.uploadFile(files[0]);
        }
    }

    handleFileUpload(e) {
        const file = e.target.files[0];
        if (file) {
            this.uploadFile(file);
        }
    }

    async uploadFile(file) {
        // Validate file type
        const allowedTypes = ['text/plain', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|pdf|docx)$/i)) {
            window.spekApp.notifications.error('Unsupported file type. Please upload PDF, TXT, or DOCX files.');
            return;
        }

        // Validate file size (e.g., 10MB limit)
        const maxSize = 10 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
            window.spekApp.notifications.error('File too large. Please upload files smaller than 10MB.');
            return;
        }

        this.showUploadProgress(true);
        
        try {
            const formData = new FormData();
            formData.append('file', file);

            const result = await window.spekApp.apiClient.uploadDocument(formData);
            
            window.spekApp.notifications.success(`Document "${file.name}" uploaded successfully!`);
            this.showUploadProgress(false);
            this.loadDocuments(); // Refresh document list
            
            // Start polling for processing status if document is being processed
            this.startPolling();

        } catch (error) {
            console.error('Upload failed:', error);
            window.spekApp.notifications.error(`Upload failed: ${error.message}`);
            this.showUploadProgress(false);
        }
    }

    showUploadProgress(show) {
        const progressEl = document.getElementById('upload-progress');
        const uploadArea = document.getElementById('upload-area');
        
        if (show) {
            progressEl.style.display = 'block';
            uploadArea.style.opacity = '0.6';
            uploadArea.style.pointerEvents = 'none';
        } else {
            progressEl.style.display = 'none';
            uploadArea.style.opacity = '1';
            uploadArea.style.pointerEvents = 'auto';
        }
    }

    async loadDocuments() {
        const listEl = document.getElementById('documents-list');
        const loadingEl = document.getElementById('documents-loading');
        
        try {
            this.documents = await window.spekApp.apiClient.listDocuments();
            this.renderDocuments();
        } catch (error) {
            console.error('Failed to load documents:', error);
            listEl.innerHTML = '<div class="empty-state">Failed to load documents. Please try again.</div>';
        }
    }

    renderDocuments() {
        const listEl = document.getElementById('documents-list');
        
        if (this.documents.length === 0) {
            listEl.innerHTML = `
                <div class="empty-state">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <h3>No documents yet</h3>
                    <p>Upload your first document to get started</p>
                </div>
            `;
            return;
        }

        listEl.innerHTML = this.documents.map(doc => this.renderDocumentItem(doc)).join('');
        
        // Add click listeners
        document.querySelectorAll('.document-item').forEach(item => {
            item.addEventListener('click', () => {
                const docId = item.dataset.docId;
                const document = this.documents.find(d => d.document_id === docId);
                if (document && document.is_queryable) {
                    this.selectDocument(document);
                }
            });
        });
    }

    renderDocumentItem(doc) {
        const uploadedAt = new Date(doc.uploaded_at).toLocaleString();
        const fileSize = this.formatFileSize(doc.file_size);
        const isQueryable = doc.is_queryable;
        
        return `
            <div class="document-item ${this.selectedDocument?.document_id === doc.document_id ? 'selected' : ''}" 
                 data-doc-id="${doc.document_id}" 
                 ${isQueryable ? '' : 'style="opacity: 0.6; cursor: default;"'}>
                <div class="document-info">
                    <div class="document-name">${this.escapeHtml(doc.file_name)}</div>
                    <div class="document-meta">
                        <span>${doc.file_type}</span>
                        <span>${fileSize}</span>
                        <span>Uploaded: ${uploadedAt}</span>
                    </div>
                </div>
                <div class="document-actions">
                    <span class="document-status status-${doc.status}">
                        ${this.getStatusLabel(doc.status)}
                    </span>
                    ${isQueryable ? '<button class="btn-secondary btn-sm">Query</button>' : ''}
                </div>
            </div>
        `;
    }

    getStatusLabel(status) {
        const labels = {
            'uploaded': 'Uploaded',
            'processing': 'Processing',
            'processed': 'Ready',
            'error': 'Error',
            'unsupported_type': 'Unsupported'
        };
        return labels[status] || status;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    selectDocument(document) {
        this.selectedDocument = document;
        this.updateSelectedDocumentUI();
        this.showQuerySection();
    }

    clearSelection() {
        this.selectedDocument = null;
        this.updateSelectedDocumentUI();
        this.hideQuerySection();
        this.renderDocuments(); // Refresh to remove selection styling
    }

    updateSelectedDocumentUI() {
        const selectedDocEl = document.getElementById('selected-doc-name');
        if (this.selectedDocument) {
            selectedDocEl.textContent = this.selectedDocument.file_name;
        } else {
            selectedDocEl.textContent = 'No document selected';
        }
    }

    showQuerySection() {
        document.getElementById('query-section').style.display = 'block';
        document.getElementById('query-input').focus();
    }

    hideQuerySection() {
        document.getElementById('query-section').style.display = 'none';
        document.getElementById('query-result').style.display = 'none';
        document.getElementById('query-input').value = '';
    }

    async handleQuery() {
        if (!this.selectedDocument) {
            window.spekApp.notifications.error('Please select a document first.');
            return;
        }

        const queryInput = document.getElementById('query-input');
        const query = queryInput.value.trim();
        
        if (!query) {
            window.spekApp.notifications.error('Please enter a question.');
            return;
        }

        const queryBtn = document.getElementById('query-btn');
        queryBtn.disabled = true;
        queryBtn.textContent = 'Asking...';

        try {
            const result = await window.spekApp.apiClient.queryDocument(
                this.selectedDocument.document_id, 
                query
            );
            
            this.displayQueryResult(result);

        } catch (error) {
            console.error('Query failed:', error);
            window.spekApp.notifications.error(`Query failed: ${error.message}`);
        } finally {
            queryBtn.disabled = false;
            queryBtn.textContent = 'Ask Question';
        }
    }

    displayQueryResult(result) {
        const resultEl = document.getElementById('query-result');
        const answerEl = document.getElementById('answer-content');
        const confidenceEl = document.getElementById('confidence-value');
        const excerptsEl = document.getElementById('relevant-excerpts');
        const excerptsListEl = document.getElementById('excerpts-list');

        // Display answer
        answerEl.textContent = result.answer;
        
        // Display confidence
        const confidencePercent = Math.round(result.confidence * 100);
        confidenceEl.textContent = `${confidencePercent}%`;
        confidenceEl.style.color = confidencePercent > 70 ? 'var(--success-color)' : 
                                   confidencePercent > 40 ? 'var(--warning-color)' : 'var(--error-color)';

        // Display relevant excerpts if available
        if (result.relevant_excerpts && result.relevant_excerpts.length > 0) {
            excerptsListEl.innerHTML = result.relevant_excerpts.map(excerpt => 
                `<div class="excerpt-item">${this.escapeHtml(excerpt)}</div>`
            ).join('');
            excerptsEl.style.display = 'block';
        } else {
            excerptsEl.style.display = 'none';
        }

        resultEl.style.display = 'block';
    }

    startPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
        }

        this.pollInterval = setInterval(async () => {
            try {
                const hasProcessingDocs = this.documents.some(doc => doc.status === 'processing');
                if (hasProcessingDocs) {
                    await this.loadDocuments();
                } else {
                    // Stop polling if no documents are processing
                    clearInterval(this.pollInterval);
                    this.pollInterval = null;
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 3000); // Poll every 3 seconds
    }
}

// Initialize when page loads
window.spekApp.onReady(() => {
    new DocumentManager();
});