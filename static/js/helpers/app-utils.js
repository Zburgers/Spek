/**
 * Application Utilities Helper
 * 
 * Collection of common utility functions used across the application including
 * SpekApp initialization waiting, URL manipulation, and validation functions.
 * 
 * @module AppUtils
 */

/**
 * Waits for window.spekApp to be initialized before executing callback
 * 
 * @param {Function} callback - Function to execute once spekApp is available
 * @param {number} interval - Polling interval in milliseconds (default: 20)
 * 
 * @example
 * waitForSpekApp(() => {
 *   console.log('SpekApp is ready!');
 *   // Initialize page-specific functionality
 * });
 */
function waitForSpekApp(callback, interval = 20) {
    if (window.spekApp) {
        callback();
    } else {
        setTimeout(() => waitForSpekApp(callback, interval), interval);
    }
}

/**
 * Updates URL search parameters without page reload
 * 
 * @param {string} key - Parameter key to update
 * @param {string} value - Parameter value to set
 * @param {boolean} replaceState - Whether to replace state (default: true)
 * 
 * @example
 * updateUrlParameter('session_id', 'abc123');
 * updateUrlParameter('mode', 'register', false); // Pushes new state instead
 */
function updateUrlParameter(key, value, replaceState = true) {
    const newUrl = new URL(window.location);
    newUrl.searchParams.set(key, value);
    
    if (replaceState) {
        window.history.replaceState(null, '', newUrl);
    } else {
        window.history.pushState(null, '', newUrl);
    }
}

/**
 * Gets URL search parameter value
 * 
 * @param {string} key - Parameter key to retrieve
 * @param {string} defaultValue - Default value if parameter not found
 * @returns {string} Parameter value or default
 * 
 * @example
 * getUrlParameter('session_id') // Returns session ID or null
 * getUrlParameter('mode', 'login') // Returns mode or 'login' as default
 */
function getUrlParameter(key, defaultValue = null) {
    const params = new URLSearchParams(window.location.search);
    return params.get(key) || defaultValue;
}

/**
 * Validates file for upload based on size and type constraints
 * 
 * @param {File} file - File object to validate
 * @param {number} maxSizeMB - Maximum file size in MB (default: 10)
 * @param {Array<string>} allowedTypes - Array of allowed MIME types
 * @returns {Object} Validation result with success boolean and error message
 * 
 * @example
 * const result = validateFile(file, 5, ['application/pdf', 'text/plain']);
 * if (!result.success) {
 *   console.error(result.error);
 * }
 */
function validateFile(file, maxSizeMB = 10, allowedTypes = [
    'application/pdf',
    'text/plain',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
]) {
    // Check file size
    const maxSizeBytes = maxSizeMB * 1024 * 1024;
    if (file.size > maxSizeBytes) {
        return {
            success: false,
            error: `File "${file.name}" is too large. Maximum size is ${maxSizeMB}MB.`
        };
    }

    // Check file type
    if (!allowedTypes.includes(file.type)) {
        return {
            success: false,
            error: `File type "${file.type}" is not supported.`
        };
    }

    return { success: true };
}

/**
 * Shows notification using available notification system
 * 
 * @param {string} message - Notification message
 * @param {string} type - Notification type ('success', 'error', 'info')
 * 
 * @example
 * showNotification('File uploaded successfully!', 'success');
 * showNotification('Upload failed', 'error');
 */
function showNotification(message, type = 'success') {
    console.log(`📁 ${type.toUpperCase()}: ${message}`);
    
    // Use the existing notification system if available
    if (window.spekApp && window.spekApp.notifications) {
        const mgr = window.spekApp.notifications;
        switch (type) {
            case 'error':
                return mgr.error(message);
            case 'info':
                return mgr.info ? mgr.info(message) : mgr.show(message, 'info');
            case 'success':
            default:
                return mgr.success ? mgr.success(message) : mgr.show(message, 'success');
        }
    }
    // Fallback to alert
    alert(`${type.toUpperCase()}: ${message}`);
}

/**
 * Debounces function execution to prevent rapid successive calls
 * 
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 * 
 * @example
 * const debouncedSearch = debounce((query) => {
 *   performSearch(query);
 * }, 300);
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Generates a unique ID string
 * 
 * @param {number} length - Length of the ID (default: 8)
 * @returns {string} Unique ID string
 * 
 * @example
 * generateUniqueId() // "a7b3c9d2"
 * generateUniqueId(12) // "a7b3c9d2e4f1"
 */
function generateUniqueId(length = 8) {
    return Math.random().toString(36).substring(2, 2 + length);
}

/**
 * Safely parses JSON string with error handling
 * 
 * @param {string} jsonString - JSON string to parse
 * @param {*} defaultValue - Default value if parsing fails
 * @returns {*} Parsed object or default value
 * 
 * @example
 * const data = safeJsonParse('{"key": "value"}', {});
 * const invalid = safeJsonParse('invalid json', null); // Returns null
 */
function safeJsonParse(jsonString, defaultValue = null) {
    try {
        return JSON.parse(jsonString);
    } catch (error) {
        console.warn('Failed to parse JSON:', error);
        return defaultValue;
    }
}

// Export functions to global scope for backward compatibility
window.AppUtils = {
    waitForSpekApp,
    updateUrlParameter,
    getUrlParameter,
    validateFile,
    showNotification,
    debounce,
    generateUniqueId,
    safeJsonParse
};
