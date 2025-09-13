"""
Frontend integration tests for the centralized document management system.
Tests the JavaScript functionality and DOM interactions.
"""

import pytest
import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import json
from pathlib import Path


class TestFrontendDocumentManagement:
    """Test suite for frontend document management functionality"""

    @pytest.fixture(scope="session")
    async def browser():
        """Browser fixture for Playwright tests"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, slow_mo=100)
            yield browser
            await browser.close()

    @pytest.fixture
    async def page(self, browser: Browser):
        """Page fixture with authentication setup"""
        context = await browser.new_context()
        page = await context.new_page()
        
        # Mock localStorage with auth token
        await page.add_init_script("""
            localStorage.setItem('token', 'test-jwt-token');
            localStorage.setItem('user', JSON.stringify({
                uuid: 'test-user-uuid',
                email: 'test@example.com',
                full_name: 'Test User'
            }));
        """)
        
        yield page
        await context.close()

    async def setup_mock_api_responses(self, page: Page):
        """Setup mock API responses for testing"""
        # Mock documents endpoint
        await page.route("**/api/v1/documents/**", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "data": [
                    {
                        "uuid": "doc-1-uuid",
                        "filename": "test_app_doc.pdf",
                        "file_size": 1024000,
                        "scope": "app_wide",
                        "status": "completed",
                        "content_type": "application/pdf",
                        "created_at": "2025-08-31T10:00:00Z"
                    },
                    {
                        "uuid": "doc-2-uuid", 
                        "filename": "test_chat_doc.txt",
                        "file_size": 512000,
                        "scope": "chat_specific",
                        "status": "completed",
                        "content_type": "text/plain",
                        "created_at": "2025-08-31T11:00:00Z"
                    }
                ],
                "count": 2,
                "page": 1,
                "per_page": 10,
                "has_more": False
            })
        ))
        
        # Mock chats endpoint
        await page.route("**/api/v1/chats/**", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "data": [
                    {
                        "uuid": "chat-1-uuid",
                        "title": "Test Chat Session",
                        "created_at": "2025-08-31T09:00:00Z"
                    }
                ],
                "count": 1,
                "page": 1,
                "per_page": 10,
                "has_more": False
            })
        ))

    async def test_document_manager_initialization(self, page: Page):
        """Test that the DocumentManager initializes correctly"""
        await self.setup_mock_api_responses(page)
        
        # Navigate to chat page
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        
        # Wait for scripts to load
        await page.wait_for_load_state("networkidle")
        
        # Check that DocumentManager is available globally
        document_manager_exists = await page.evaluate("typeof window.documentManager !== 'undefined'")
        assert document_manager_exists, "DocumentManager should be available globally"
        
        # Check that it's properly initialized
        is_initialized = await page.evaluate("window.documentManager && window.documentManager.initialized")
        assert is_initialized, "DocumentManager should be initialized"

    async def test_modal_mode_initialization(self, page: Page):
        """Test DocumentManager in modal mode"""
        await self.setup_mock_api_responses(page)
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Initialize in modal mode
        await page.evaluate("""
            window.documentManager.initializeMode('modal', {
                container: document.createElement('div'),
                onDocumentSelect: (doc) => console.log('Selected:', doc),
                onDocumentRemove: (doc) => console.log('Removed:', doc)
            });
        """)
        
        # Check mode is set correctly
        current_mode = await page.evaluate("window.documentManager.mode")
        assert current_mode == "modal", "Should be in modal mode"

    async def test_selector_mode_initialization(self, page: Page):
        """Test DocumentManager in selector mode"""
        await self.setup_mock_api_responses(page)
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Initialize in selector mode
        await page.evaluate("""
            window.documentManager.initializeMode('selector', {
                container: document.createElement('div'),
                chatId: 'test-chat-id',
                onDocumentAdd: (doc) => console.log('Added:', doc),
                onDocumentRemove: (doc) => console.log('Removed:', doc)
            });
        """)
        
        # Check mode is set correctly
        current_mode = await page.evaluate("window.documentManager.mode")
        assert current_mode == "selector", "Should be in selector mode"

    async def test_document_loading(self, page: Page):
        """Test that documents are loaded correctly"""
        await self.setup_mock_api_responses(page)
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Load documents
        documents = await page.evaluate("""
            (async () => {
                await window.documentManager.loadDocuments();
                return window.documentManager.documents;
            })()
        """)
        
        assert len(documents["app_wide"]) == 1, "Should have 1 app-wide document"
        assert len(documents["chat_specific"]) == 1, "Should have 1 chat-specific document"
        
        # Check document properties
        app_doc = documents["app_wide"][0]
        assert app_doc["filename"] == "test_app_doc.pdf"
        assert app_doc["scope"] == "app_wide"
        
        chat_doc = documents["chat_specific"][0]
        assert chat_doc["filename"] == "test_chat_doc.txt"
        assert chat_doc["scope"] == "chat_specific"

    async def test_document_filtering(self, page: Page):
        """Test document filtering functionality"""
        await self.setup_mock_api_responses(page)
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Load documents and test filtering
        filtered_results = await page.evaluate("""
            (async () => {
                await window.documentManager.loadDocuments();
                
                // Test status filter
                const completedDocs = window.documentManager.filterDocuments({status: 'completed'});
                
                // Test scope filter
                const appWideDocs = window.documentManager.filterDocuments({scope: 'app_wide'});
                
                // Test search filter
                const searchResults = window.documentManager.filterDocuments({search: 'pdf'});
                
                return {
                    completed: completedDocs.length,
                    appWide: appWideDocs.length,
                    searchPdf: searchResults.length
                };
            })()
        """)
        
        assert filtered_results["completed"] == 2, "Should find 2 completed documents"
        assert filtered_results["appWide"] == 1, "Should find 1 app-wide document"
        assert filtered_results["searchPdf"] == 1, "Should find 1 PDF document"

    async def test_document_rendering(self, page: Page):
        """Test document rendering in UI"""
        await self.setup_mock_api_responses(page)
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Create a container and render documents
        await page.evaluate("""
            (async () => {
                const container = document.createElement('div');
                container.id = 'test-container';
                document.body.appendChild(container);
                
                window.documentManager.initializeMode('modal', {
                    container: container,
                    onDocumentSelect: (doc) => console.log('Selected:', doc)
                });
                
                await window.documentManager.loadDocuments();
                window.documentManager.renderDocuments(container);
            })()
        """)
        
        # Check that documents are rendered
        document_items = await page.query_selector_all("#test-container .document-item")
        assert len(document_items) == 2, "Should render 2 document items"
        
        # Check document details are present
        first_doc_name = await document_items[0].query_selector(".document-name")
        assert first_doc_name is not None, "Document name should be present"
        
        doc_name_text = await first_doc_name.inner_text()
        assert doc_name_text in ["test_app_doc.pdf", "test_chat_doc.txt"], "Should show correct filename"

    async def test_scope_indicators(self, page: Page):
        """Test that document scope indicators are displayed correctly"""
        await self.setup_mock_api_responses(page)
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Render documents and check scope indicators
        scope_info = await page.evaluate("""
            (async () => {
                const container = document.createElement('div');
                document.body.appendChild(container);
                
                window.documentManager.initializeMode('modal', {
                    container: container,
                    onDocumentSelect: (doc) => console.log('Selected:', doc)
                });
                
                await window.documentManager.loadDocuments();
                window.documentManager.renderDocuments(container);
                
                const scopes = Array.from(container.querySelectorAll('.document-scope')).map(el => ({
                    text: el.textContent.trim(),
                    className: el.className
                }));
                
                return scopes;
            })()
        """)
        
        assert len(scope_info) == 2, "Should have 2 scope indicators"
        
        scope_texts = [scope["text"] for scope in scope_info]
        assert "App-wide" in scope_texts, "Should show App-wide scope"
        assert "Chat-specific" in scope_texts, "Should show Chat-specific scope"
        
        scope_classes = [scope["className"] for scope in scope_info]
        assert any("scope-app_wide" in cls for cls in scope_classes), "Should have app_wide CSS class"
        assert any("scope-chat_specific" in cls for cls in scope_classes), "Should have chat_specific CSS class"

    async def test_document_actions(self, page: Page):
        """Test document action buttons (Add/Remove)"""
        await self.setup_mock_api_responses(page)
        
        # Mock the association endpoints
        await page.route("**/api/v1/chats/*/documents", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"message": "Success", "associations_created": 1})
        ))
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Setup selector mode with chat ID
        button_interactions = await page.evaluate("""
            (async () => {
                const container = document.createElement('div');
                document.body.appendChild(container);
                
                window.documentManager.initializeMode('selector', {
                    container: container,
                    chatId: 'test-chat-id',
                    onDocumentAdd: (doc) => window.testResults = {action: 'add', doc: doc},
                    onDocumentRemove: (doc) => window.testResults = {action: 'remove', doc: doc}
                });
                
                await window.documentManager.loadDocuments();
                window.documentManager.renderDocuments(container);
                
                // Check if action buttons are present
                const addButtons = container.querySelectorAll('.add-btn');
                const removeButtons = container.querySelectorAll('.remove-btn');
                
                return {
                    addButtonCount: addButtons.length,
                    removeButtonCount: removeButtons.length,
                    hasButtons: addButtons.length > 0 || removeButtons.length > 0
                };
            })()
        """)
        
        assert button_interactions["hasButtons"], "Should have action buttons"
        # In initial state, all documents should have "Add" buttons since none are associated

    async def test_error_handling(self, page: Page):
        """Test error handling in frontend"""
        # Setup error responses
        await page.route("**/api/v1/documents/**", lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps({"detail": "Internal server error"})
        ))
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Test error handling
        error_result = await page.evaluate("""
            (async () => {
                try {
                    await window.documentManager.loadDocuments();
                    return {error: false};
                } catch (e) {
                    return {error: true, message: e.message};
                }
            })()
        """)
        
        assert error_result["error"], "Should handle API errors gracefully"

    async def test_memory_cleanup(self, page: Page):
        """Test that the DocumentManager cleans up properly"""
        await self.setup_mock_api_responses(page)
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Initialize and then cleanup
        cleanup_result = await page.evaluate("""
            (async () => {
                const container = document.createElement('div');
                document.body.appendChild(container);
                
                window.documentManager.initializeMode('modal', {
                    container: container,
                    onDocumentSelect: (doc) => console.log('Selected:', doc)
                });
                
                await window.documentManager.loadDocuments();
                
                // Check state before cleanup
                const beforeCleanup = {
                    hasDocuments: Object.keys(window.documentManager.documents).length > 0,
                    hasMode: window.documentManager.mode !== null
                };
                
                // Cleanup
                window.documentManager.cleanup();
                
                // Check state after cleanup
                const afterCleanup = {
                    hasDocuments: Object.keys(window.documentManager.documents).length > 0,
                    hasMode: window.documentManager.mode !== null
                };
                
                return {beforeCleanup, afterCleanup};
            })()
        """)
        
        assert cleanup_result["beforeCleanup"]["hasDocuments"], "Should have documents before cleanup"
        assert not cleanup_result["afterCleanup"]["hasDocuments"], "Should clear documents after cleanup"

    async def test_chat_integration(self, page: Page):
        """Test integration with chat functionality"""
        await self.setup_mock_api_responses(page)
        
        # Mock chat-specific endpoints
        await page.route("**/api/v1/chats/test-chat-id/documents", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps([
                {
                    "uuid": "doc-1-uuid",
                    "filename": "associated_doc.pdf",
                    "scope": "app_wide",
                    "status": "completed"
                }
            ])
        ))
        
        static_path = Path(__file__).parent.parent / "static"
        await page.goto(f"file://{static_path}/chat.html")
        await page.wait_for_load_state("networkidle")
        
        # Test chat document loading
        chat_docs = await page.evaluate("""
            (async () => {
                window.documentManager.initializeMode('selector', {
                    container: document.createElement('div'),
                    chatId: 'test-chat-id'
                });
                
                await window.documentManager.loadChatDocuments('test-chat-id');
                return window.documentManager.selectedDocuments;
            })()
        """)
        
        assert len(chat_docs) == 1, "Should load 1 associated document"
        assert chat_docs[0]["filename"] == "associated_doc.pdf", "Should have correct filename"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
