/**
 * Markdown Processing Helper
 * 
 * Utility functions for parsing and formatting markdown text into HTML.
 * Supports bold, italic, code blocks, inline code, and lists.
 * 
 * @module MarkdownUtils
 */

/**
 * Parses markdown text and converts it to HTML
 * 
 * @param {string} text - Raw markdown text
 * @returns {string} HTML formatted text
 * 
 * @example
 * parseMarkdown("**bold** and *italic*") // "<strong>bold</strong> and <em>italic</em>"
 * parseMarkdown("```code block```") // "<pre><code>code block</code></pre>"
 * parseMarkdown("- item 1\n- item 2") // "<ul><li>item 1</li><li>item 2</li></ul>"
 */
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

/**
 * Processes markdown lists (both unordered and ordered) and converts to HTML
 * 
 * @param {string} text - Text containing markdown lists
 * @returns {string} Text with lists converted to HTML
 * 
 * @example
 * processLists("- item 1\n- item 2") // "<ul><li>item 1</li><li>item 2</li></ul>"
 * processLists("1. first\n2. second") // "<ol><li>first</li><li>second</li></ol>"
 */
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

    // Close any remaining lists
    if (inUl) processedLines.push('</ul>');
    if (inOl) processedLines.push('</ol>');

    return processedLines.join('\n');
}

// Export functions to global scope for backward compatibility
window.MarkdownUtils = {
    parseMarkdown,
    processLists
};
