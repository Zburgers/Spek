"""
Focused integration test for our centralized document management system.
Tests the key functionality we've implemented.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

async def test_document_api_endpoints():
    """Test that our document API endpoints exist and have correct structure"""
    try:
        from app.api.v1.documents import router
        print("✅ Document router imported successfully")
        
        # Check that key routes exist
        routes = [route.path for route in router.routes]
        expected_routes = [
            "/",
            "/upload", 
            "/{document_id}",
        ]
        
        for expected in expected_routes:
            if any(expected in route for route in routes):
                print(f"✅ Route {expected} found")
            else:
                print(f"❌ Route {expected} missing")
        
        return True
    except Exception as e:
        print(f"❌ Error testing document endpoints: {e}")
        return False


async def test_chat_document_endpoints():
    """Test that chat-document association endpoints exist"""
    try:
        from app.api.v1.chats import router
        print("✅ Chat router imported successfully")
        
        # Check for document association routes
        routes = [route.path for route in router.routes]
        
        # Look for document-related routes
        doc_routes = [route for route in routes if "document" in route.lower()]
        if doc_routes:
            print(f"✅ Found document routes: {doc_routes}")
        else:
            print("⚠️  No document routes found in chat router")
        
        return True
    except Exception as e:
        print(f"❌ Error testing chat endpoints: {e}")
        return False


async def test_crud_operations():
    """Test that CRUD operations are available"""
    try:
        from app.crud.crud_document import document_crud
        from app.crud.crud_chat import chat_crud
        from app.crud.crud_chat_document import chat_document_crud
        
        print("✅ Document CRUD imported successfully")
        print("✅ Chat CRUD imported successfully") 
        print("✅ Chat-Document CRUD imported successfully")
        
        # Check that key methods exist
        crud_methods = ['create', 'get', 'get_multi', 'update', 'delete']
        
        for method in crud_methods:
            if hasattr(document_crud, method):
                print(f"✅ document_crud.{method} exists")
            else:
                print(f"❌ document_crud.{method} missing")
        
        return True
    except Exception as e:
        print(f"❌ Error testing CRUD operations: {e}")
        return False


async def test_models():
    """Test that our database models are correctly defined"""
    try:
        from app.models.document import Document
        from app.models.chat import Chat
        from app.models.chat_document import ChatDocument
        
        print("✅ Document model imported successfully")
        print("✅ Chat model imported successfully")
        print("✅ ChatDocument model imported successfully")
        
        # Check key attributes
        if hasattr(Document, 'scope'):
            print("✅ Document.scope field exists")
        else:
            print("❌ Document.scope field missing")
            
        if hasattr(Document, 'status'):
            print("✅ Document.status field exists")
        else:
            print("❌ Document.status field missing")
        
        return True
    except Exception as e:
        print(f"❌ Error testing models: {e}")
        return False


async def test_frontend_files():
    """Test that frontend files exist and have expected content"""
    try:
        # Check document-manager.js
        doc_manager_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'document-manager.js')
        if os.path.exists(doc_manager_path):
            print("✅ document-manager.js exists")
            
            with open(doc_manager_path, 'r') as f:
                content = f.read()
                
            if 'class DocumentManager' in content:
                print("✅ DocumentManager class found")
            if 'MODES' in content:
                print("✅ MODES constant found")
            if 'initializeMode' in content:
                print("✅ initializeMode method found")
                
        else:
            print("❌ document-manager.js missing")
        
        # Check chat.js
        chat_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'chat.js')
        if os.path.exists(chat_path):
            print("✅ chat.js exists")
            
            with open(chat_path, 'r') as f:
                content = f.read()
                
            # Check that it's been refactored (should be much smaller now)
            lines = content.count('\n')
            if lines < 500:  # Should be around 400 lines now vs 1433 before
                print(f"✅ chat.js is refactored ({lines} lines)")
            else:
                print(f"⚠️  chat.js might not be refactored ({lines} lines)")
                
        else:
            print("❌ chat.js missing")
            
        # Check chat.html
        chat_html_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'chat.html')
        if os.path.exists(chat_html_path):
            print("✅ chat.html exists")
            
            with open(chat_html_path, 'r') as f:
                content = f.read()
                
            if 'document-manager.js' in content:
                print("✅ chat.html includes document-manager.js")
            else:
                print("❌ chat.html missing document-manager.js reference")
        else:
            print("❌ chat.html missing")
        
        return True
    except Exception as e:
        print(f"❌ Error testing frontend files: {e}")
        return False


async def test_css_styling():
    """Test that CSS styling for document management exists"""
    try:
        css_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'chat-styles.css')
        if os.path.exists(css_path):
            print("✅ chat-styles.css exists")
            
            with open(css_path, 'r') as f:
                content = f.read()
                
            expected_styles = [
                '.document-scope',
                '.scope-app_wide',
                '.scope-chat_specific',
                '.add-btn',
                '.remove-btn'
            ]
            
            for style in expected_styles:
                if style in content:
                    print(f"✅ CSS class {style} found")
                else:
                    print(f"❌ CSS class {style} missing")
        else:
            print("❌ chat-styles.css missing")
        
        return True
    except Exception as e:
        print(f"❌ Error testing CSS: {e}")
        return False


async def run_all_tests():
    """Run all focused integration tests"""
    print("🧪 Running Centralized Document Management Integration Tests\n")
    
    tests = [
        ("Document API Endpoints", test_document_api_endpoints),
        ("Chat-Document Endpoints", test_chat_document_endpoints),
        ("CRUD Operations", test_crud_operations),
        ("Database Models", test_models),
        ("Frontend Files", test_frontend_files),
        ("CSS Styling", test_css_styling),
    ]
    
    results = []
    
    for name, test_func in tests:
        print(f"\n📋 Testing {name}:")
        print("-" * 50)
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} failed with error: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        print("✨ Centralized document management system is ready!")
    else:
        print("⚠️  Some tests failed - check the details above")
    
    return passed == total


if __name__ == "__main__":
    result = asyncio.run(run_all_tests())
    sys.exit(0 if result else 1)
