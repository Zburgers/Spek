/**
 * UI Helper Functions
 * 
 * Collection of utility functions for creating and managing UI elements,
 * specifically for document management interfaces including chips and message components.
 * 
 * @module UIHelpers
 */

/**
 * Creates a DOM element for a document chip used in chat interface
 * 
 * @param {Object} doc - Document object from API
 * @param {string} doc.id - Document unique identifier
 * @param {string} doc.uuid - Document UUID (alternative identifier)
 * @param {string} doc.filename - Document filename
 * @param {string} doc.status - Processing status of the document
 * @returns {HTMLElement} Complete document chip element with icon, details, and remove button
 * 
 * @example
 * const doc = { id: '123', filename: 'report.pdf', status: 'processed' };
 * const chip = createDocumentChip(doc);
 * container.appendChild(chip);
 */
function createDocumentChip(doc) {
    const chip = document.createElement('div');
    chip.className = 'document-chip';
    
    // Handle different field names for document ID
    const docId = doc.id || doc.uuid || doc.document_id;
    chip.dataset.docId = docId;
    chip.title = doc.filename || doc.file_name;

    console.log('DEBUG: createDocumentChip - doc object:', doc);
    console.log('DEBUG: createDocumentChip - extracted docId:', docId);
    console.log('DEBUG: createDocumentChip - chip.dataset.docId:', chip.dataset.docId);

    const fileName = doc.filename || doc.file_name || 'Unknown file';
    const fileExtension = fileName.split('.').pop().toLowerCase();
    const icon = window.documentManager.getFileIcon(fileExtension);
    const status = doc.status || 'processing'; // Default to processing

    chip.innerHTML = `
        <div class="document-chip-icon ${fileExtension}">${icon}</div>
        <div class="document-chip-details">
            <div class="document-chip-name">${fileName}</div>
            <div class="document-chip-status status-${status}">${window.documentManager.formatStatus(status)}</div>
        </div>
        <button class="document-chip-remove" data-doc-id="${docId}">&times;</button>
    `;

    return chip;
}

/**
 * Updates the processing status display of an existing document chip
 * 
 * @param {string} docId - Document ID to update
 * @param {string} status - New processing status ('processing', 'completed', 'error', etc.)
 * 
 * @example
 * updateDocumentChipStatus('doc123', 'completed');
 * updateDocumentChipStatus('doc456', 'error');
 */
function updateDocumentChipStatus(docId, status) {
    const chip = document.querySelector(`.document-chip[data-doc-id="${docId}"]`);
    if (chip) {
        const statusElement = chip.querySelector('.document-chip-status');
        if (statusElement) {
            statusElement.textContent = window.documentManager.formatStatus(status);
            statusElement.className = `document-chip-status status-${status} ${window.documentManager.getStatusClass(status)}`;
        }
    }
}

/**
 * Creates a container displaying document icons within chat messages
 * 
 * @param {Array<Object>} documents - Array of document objects attached to message
 * @param {string} documents[].filename - Document filename for display
 * @param {string} documents[].id - Document ID for reference
 * @returns {HTMLElement|null} Container element with document icons, or null if no documents
 * 
 * @example
 * const docs = [
 *   { filename: 'report.pdf', id: '123' },
 *   { filename: 'data.xlsx', id: '456' }
 * ];
 * const container = createDocumentIconsForMessage(docs);
 * messageElement.appendChild(container);
 */
function createDocumentIconsForMessage(documents) {
    if (!documents || documents.length === 0) {
        return null;
    }

    const container = document.createElement('div');
    container.className = 'message-documents';

    documents.forEach(doc => {
            let fileExtension = 'unknown';
            if (doc.filename && typeof doc.filename === 'string') {
                fileExtension = doc.filename.split('.').pop().toLowerCase();
            } else {
                console.warn('UIHelpers: Document missing filename property:', doc);
            }
            const icon = window.documentManager.getFileIcon(fileExtension);
        
            const docCard = document.createElement('div');
            docCard.className = 'message-document-card';
        docCard.title = doc.filename;
        docCard.dataset.docId = doc.uuid || doc.id;
        
        docCard.innerHTML = `
            <div class="message-document-icon ${fileExtension}">${icon}</div>
            <div class="message-document-details">
                <div class="message-document-name">${doc.filename}</div>
                <div class="message-document-type">${fileExtension.toUpperCase()}</div>
            </div>
        `;
        
        container.appendChild(docCard);
    });

    return container;
}

// Export functions to global scope for backward compatibility
window.UIHelpers = {
    createDocumentChip,
    updateDocumentChipStatus,
    createDocumentIconsForMessage
};