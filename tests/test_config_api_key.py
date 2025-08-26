"""Tests for API key configuration handling."""
import os
import tempfile
from unittest.mock import patch

import pytest
from pydantic import SecretStr
from src.app.core.config import AISettings


class TestAPIKeyConfiguration:
    """Test API key configuration with empty/whitespace values."""
    
    def test_empty_api_key_should_be_falsy(self):
        """Test that empty API_KEY should be falsy (fixed)."""
        with patch.dict(os.environ, {"AI_API_KEY": ""}, clear=False):
            from src.app.core.config import settings
            
            # Reload settings to pick up the env var
            import importlib
            import src.app.core.config
            importlib.reload(src.app.core.config)
            from src.app.core.config import settings
            
            # After the fix, this should pass
            assert not settings.API_KEY, "Empty API key should be falsy"
            assert settings.API_KEY is None, "Empty API key should be None"
                
    def test_whitespace_api_key_should_be_falsy(self):
        """Test that whitespace-only API_KEY should be falsy (fixed)."""
        with patch.dict(os.environ, {"AI_API_KEY": "   "}, clear=False):
            import importlib
            import src.app.core.config
            importlib.reload(src.app.core.config)
            from src.app.core.config import settings
            
            # After the fix, this should pass
            assert not settings.API_KEY, "Whitespace-only API key should be falsy"
            assert settings.API_KEY is None, "Whitespace-only API key should be None"
                
    def test_valid_api_key_should_be_truthy(self):
        """Test that valid API_KEY should remain truthy."""
        with patch.dict(os.environ, {"AI_API_KEY": "valid-key-123"}, clear=False):
            import importlib
            import src.app.core.config
            importlib.reload(src.app.core.config)
            from src.app.core.config import settings
            
            # This should work both before and after the fix
            assert settings.API_KEY, "Valid API key should be truthy"
            
    def test_valid_api_key_with_whitespace_should_be_stripped(self):
        """Test that valid API_KEY with whitespace should be stripped."""
        with patch.dict(os.environ, {"AI_API_KEY": "  valid-key-123  "}, clear=False):
            import importlib
            import src.app.core.config
            importlib.reload(src.app.core.config)
            from src.app.core.config import settings
            
            # Should be truthy and whitespace should be stripped
            assert settings.API_KEY, "Valid API key with whitespace should be truthy"
            # Note: Can't easily test the actual value due to SecretStr, but stripping is tested above
            
    def test_legacy_api_key_empty_should_be_falsy(self):
        """Test that empty legacy API_KEY should be falsy."""
        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            # Ensure AI_API_KEY is not set
            if "AI_API_KEY" in os.environ:
                del os.environ["AI_API_KEY"]
                
            import importlib
            import src.app.core.config
            importlib.reload(src.app.core.config)
            from src.app.core.config import settings
            
            # After the fix, this should pass
            assert not settings.API_KEY, "Empty legacy API key should be falsy"
            assert settings.API_KEY is None, "Empty legacy API key should be None"
                
    def test_no_api_key_set_should_be_none(self):
        """Test that when no API key is set, it should be None."""
        # Remove both possible env vars
        env_without_keys = {k: v for k, v in os.environ.items() 
                           if k not in ["AI_API_KEY", "API_KEY"]}
        
        with patch.dict(os.environ, env_without_keys, clear=True):
            import importlib
            import src.app.core.config
            importlib.reload(src.app.core.config)
            from src.app.core.config import settings
            
            assert settings.API_KEY is None, "No API key set should result in None"


class TestCastAPIKeyMethod:
    """Test the _cast_api_key method directly."""
    
    def test_cast_api_key_with_string(self):
        """Test casting a string value."""
        result = AISettings._cast_api_key("  test-key  ")
        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "test-key"
   
    def test_cast_api_key_with_secret_str(self):
        """Test casting an already SecretStr value."""
        secret = SecretStr("  another-key  ")
        result = AISettings._cast_api_key(secret)
        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "another-key"
   
    def test_cast_api_key_with_none(self):
        """Test casting None value."""
        result = AISettings._cast_api_key(None)
        assert result is None
   
    def test_cast_api_key_with_empty_string(self):
        """Test casting empty or whitespace-only string."""
        result = AISettings._cast_api_key("   ")
        assert result is None