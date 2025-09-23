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

// ---------------- Phase 1 Scaffold ----------------
// We keep the existing implementation as the legacy version and
// build a new pipeline-based parser that currently delegates to it.

/**
 * Legacy original parser (pre-refactor). Retained for fallback.
 * @param {string} text
 * @returns {string}
 */
function parseMarkdownLegacy(text) {
    // Sanitize input to prevent XSS by escaping core HTML characters.
    text = text.replace(/[<>&"']/g, function(match) {
        const htmlEntities = {
            '<': '&lt;',
            '>': '&gt;',
            '&': '&amp;',
            '"': '&quot;',
            "'": '&#x27;'
        };
        return htmlEntities[match];
    });

    let formatted = text;

    // Code blocks (```code```) - process first to avoid inner markdown parsing
    formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

    // Inline code (`code`)
    formatted = formatted.replace(/`([^`]+?)`/g, '<code>$1</code>');

    // Bold text (**text** or __text__)
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // Italic text (*text* or _text_)
    formatted = formatted.replace(/(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)/g, '<em>$1</em>');
    formatted = formatted.replace(/(?<!_)_(?!_)([^_]+?)_(?!_)/g, '<em>$1</em>');

    // Process lists
    formatted = processLists(formatted);

    return formatted;
}

// --- Pipeline Helpers (initial scaffolding: no-op / placeholders) ---

/** Escape HTML entities in a string */
function escapeHtml(str) {
    return str.replace(/[<>&"']/g, function(match) {
        const htmlEntities = { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#x27;' };
        return htmlEntities[match];
    });
}

/** Segment fenced code blocks (placeholder: simple regex extraction for Phase 1) */
function segmentFencedCode(input) {
    const codeBlocks = [];
    let placeholderIndex = 0;
    const output = input.replace(/```([\s\S]*?)```/g, (_, code) => {
        const token = `__CODE_BLOCK_${placeholderIndex}__`;
        codeBlocks.push({ token, code });
        placeholderIndex++;
        return token;
    });
    return { text: output, codeBlocks };
}

/** Reinsert previously extracted code blocks */
function reinsertCodeBlocks(text, codeBlocks) {
    for (const block of codeBlocks) {
        // mirror legacy output pattern
        text = text.replace(block.token, `<pre><code>${block.code}</code></pre>`);
    }
    return text;
}

/** Apply inline formatting & lists using legacy pathway for now */
function applyFormattingPhases(text) {
    // Delegate fully to legacy parser for Phase 1 (ensures identical output)
    return parseMarkdownLegacy(text);
}

/** Main new parser orchestrator (will evolve in later phases) */
function parseMarkdownPipeline(text, options) {
    // Length guard (Phase 1 minimal) - configurable later
    const max = (options && options.maxInputLength) || 100000;
    if (text.length > max) {
        // Truncate gracefully for now; later we may throw or handle differently
        text = text.slice(0, max);
    }
    const { text: segmented, codeBlocks } = segmentFencedCode(text);
    // Currently applyFormattingPhases re-does escaping & code formatting; in later phases
    // we'll avoid double handling. For now ensure identical legacy output via delegation.
    let html = applyFormattingPhases(segmented);
    html = reinsertCodeBlocks(html, codeBlocks);
    return html;
}

/**
 * New unified public parser with options.
 * @param {string} text
 * @param {Object} [options]
 * @param {boolean} [options.useLegacy=false] - Force legacy behavior
 * @returns {string}
 */
function parseMarkdown(text, options) {
    if (options && options.useLegacy) {
        return parseMarkdownLegacy(text);
    }
    return parseMarkdownPipeline(text, options || {});
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
        // Unordered list item
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
        // Ordered list item
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
        // Not a list item
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

    // Close any remaining lists at the end of the text
    if (inUl) processedLines.push('</ul>');
    if (inOl) processedLines.push('</ol>');

    return processedLines.join('\n');
}

// Export functions to global scope for backward compatibility
window.MarkdownUtils = {
    parseMarkdown,
    parseMarkdownLegacy,
    processLists,
    // Expose scaffolding for potential testing / future phases
    _internals: {
        escapeHtml,
        segmentFencedCode,
        reinsertCodeBlocks,
        applyFormattingPhases,
        parseMarkdownPipeline
    }
};