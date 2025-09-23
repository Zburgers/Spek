/**
 * Formatting Utilities Helper
 * 
 * Collection of utility functions for formatting various data types including
 * file sizes, dates, status indicators, and file icons.
 * 
 * @module FormattingUtils
 */

/**
 * Formats file size in bytes to human-readable format
 * 
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted file size (e.g., "1.5 MB", "512 KB")
 * 
 * @example
 * formatFileSize(1024) // "1 KB"
 * formatFileSize(1572864) // "1.5 MB"
 * formatFileSize(0) // "0 Bytes"
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Formats ISO date string to localized date and time
 * 
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date and time string
 * 
 * @example
 * formatDate("2024-03-15T10:30:00Z") // "3/15/2024 10:30 AM"
 * formatDate(null) // "Unknown"
 */
function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'Unknown';
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

/**
 * Formats processing status to title case
 * 
 * @param {string} status - Raw status string
 * @returns {string} Formatted status with first letter capitalized
 * 
 * @example
 * formatStatus("processing") // "Processing"
 * formatStatus("completed") // "Completed"
 * formatStatus(null) // "Unknown"
 */
function formatStatus(status) {
    if (!status) return 'Unknown';
    return status.charAt(0).toUpperCase() + status.slice(1);
}

/**
 * Gets CSS class name for status styling
 * 
 * @param {string} status - Processing status
 * @returns {string} CSS class name for status styling
 * 
 * @example
 * getStatusClass("processed") // "processed"
 * getStatusClass("error") // "error"
 * getStatusClass("unknown") // "unknown"
 */
function getStatusClass(status) {
    if (!status) return 'unknown';
    switch (status.toLowerCase()) {
        case 'uploaded': return 'uploaded';
        case 'processed': return 'processed';
        case 'processing': return 'processing';
        case 'error': return 'error';
        default: return 'unknown';
    }
}

/**
 * Gets appropriate FontAwesome icon class for file extensions
 * 
 * @param {string} extension - File extension (without dot)
 * @returns {string} FontAwesome icon class name
 * 
 * @example
 * getFileIcon("pdf") // "fa-file-pdf"
 * getFileIcon("jpg") // "fa-file-image"
 * getFileIcon("unknown") // "fa-file-alt"
 */
function getFileIcon(extension) {
    const iconMap = {
        // Documents
        'pdf': 'fa-file-pdf',
        'doc': 'fa-file-word',
        'docx': 'fa-file-word',
        'txt': 'fa-file-alt',
        'rtf': 'fa-file-alt',
        
        // Spreadsheets
        'xls': 'fa-file-excel',
        'xlsx': 'fa-file-excel',
        'csv': 'fa-file-csv',
        
        // Presentations
        'ppt': 'fa-file-powerpoint',
        'pptx': 'fa-file-powerpoint',
        
        // Images
        'jpg': 'fa-file-image',
        'jpeg': 'fa-file-image',
        'png': 'fa-file-image',
        'gif': 'fa-file-image',
        'svg': 'fa-file-image',
        'webp': 'fa-file-image',
        
        // Audio
        'mp3': 'fa-file-audio',
        'wav': 'fa-file-audio',
        'flac': 'fa-file-audio',
        'aac': 'fa-file-audio',
        
        // Video
        'mp4': 'fa-file-video',
        'avi': 'fa-file-video',
        'mov': 'fa-file-video',
        'wmv': 'fa-file-video',
        
        // Code
        'js': 'fa-file-code',
        'html': 'fa-file-code',
        'css': 'fa-file-code',
        'py': 'fa-file-code',
        'java': 'fa-file-code',
        'cpp': 'fa-file-code',
        'c': 'fa-file-code',
        
        // Archives
        'zip': 'fa-file-archive',
        'rar': 'fa-file-archive',
        '7z': 'fa-file-archive',
        'tar': 'fa-file-archive',
        'gz': 'fa-file-archive'
    };
    
    return iconMap[extension] || 'fa-file-alt';
}

/**
 * Gets appropriate FontAwesome icon class for processing status
 * 
 * @param {string} status - Processing status
 * @returns {string} FontAwesome icon class name
 * 
 * @example
 * getStatusIcon("processing") // "fa-cog fa-spin"
 * getStatusIcon("completed") // "fa-check"
 * getStatusIcon("error") // "fa-exclamation-triangle"
 **/

function getStatusIcon(status) {
    // Normalize (coerce null/undefined, trim whitespace, lowercase)
    const normalized = (status ?? '').toString().trim().toLowerCase();
    if (!normalized) return 'fa-question';

    const iconMap = {
        uploaded: 'fa-upload',
        processing: 'fa-cog fa-spin',
        processed: 'fa-check',
        error: 'fa-exclamation-triangle',
        failed: 'fa-times'
    };

    return iconMap[normalized] || 'fa-question';
}

// Export functions to global scope for backward compatibility
window.FormattingUtils = {
    formatFileSize,
    formatDate,
    formatStatus,
    getStatusClass,
    getFileIcon,
    getStatusIcon
};
