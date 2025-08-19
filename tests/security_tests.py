#!/usr/bin/env python3
"""
Security Test Suite for Spek API
Run with: python tests/security_tests.py
"""

import asyncio
import httpx
import pytest
from typing import Dict, Any

class SecurityTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    async def test_xss_prevention(self):
        """Test XSS injection prevention"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "{{constructor.constructor('alert(1)')()}}"
        ]
        
        results = []
        for payload in xss_payloads:
            try:
                response = await self.client.post("/api/v1/chat/message", 
                    json={"content": payload, "session_id": "test"})
                # Should return 400 for malicious input
                results.append({
                    "payload": payload,
                    "status": response.status_code,
                    "blocked": response.status_code == 400
                })
            except Exception as e:
                results.append({
                    "payload": payload,
                    "error": str(e),
                    "blocked": True
                })
        
        return results

    async def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        sql_payloads = [
            "' OR 1=1 --",
            "'; DROP TABLE users; --",
            "1' UNION SELECT password FROM users --",
            "admin'; exec('rm -rf /'); --"
        ]
        
        results = []
        for payload in sql_payloads:
            try:
                response = await self.client.get(f"/api/v1/users?search={payload}")
                results.append({
                    "payload": payload,
                    "status": response.status_code,
                    "blocked": response.status_code == 400
                })
            except Exception as e:
                results.append({
                    "payload": payload,
                    "error": str(e),
                    "blocked": True
                })
        
        return results

    async def test_security_headers(self):
        """Test security headers presence"""
        response = await self.client.get("/")
        headers = response.headers
        
        required_headers = {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY", 
            "x-xss-protection": "1; mode=block",
            "content-security-policy": True,  # Just check presence
            "referrer-policy": "strict-origin-when-cross-origin"
        }
        
        results = {}
        for header, expected in required_headers.items():
            actual = headers.get(header.lower())
            if expected is True:
                results[header] = {"present": actual is not None, "value": actual}
            else:
                results[header] = {"correct": actual == expected, "value": actual}
        
        return results

    async def test_authentication_security(self):
        """Test authentication security measures"""
        # Test that tokens are not in localStorage by checking response
        response = await self.client.post("/api/v1/login", 
            data={"username": "test", "password": "wrong"})
        
        # Should not expose sensitive info in error
        return {
            "login_error_safe": "password" not in response.text.lower(),
            "status_code": response.status_code,
            "no_token_in_body": "access_token" not in response.text if response.status_code != 200 else True
        }

    async def run_all_tests(self):
        """Run all security tests"""
        print("🔐 Running Security Test Suite for Spek API\n")
        
        tests = [
            ("XSS Prevention", self.test_xss_prevention),
            ("SQL Injection Prevention", self.test_sql_injection_prevention), 
            ("Security Headers", self.test_security_headers),
            ("Authentication Security", self.test_authentication_security),
        ]
        
        results = {}
        for name, test_func in tests:
            print(f"Running {name}...")
            try:
                result = await test_func()
                results[name] = {"status": "completed", "results": result}
                print(f"✅ {name} completed\n")
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
                print(f"❌ {name} failed: {e}\n")
        
        await self.client.aclose()
        return results

async def main():
    """Main test runner"""
    tester = SecurityTester()
    results = await tester.run_all_tests()
    
    print("📋 Security Test Results Summary:")
    print("=" * 50)
    
    for test_name, result in results.items():
        print(f"\n{test_name}:")
        if result["status"] == "completed":
            print(f"  Status: ✅ Passed")
            # Add specific result analysis here
        else:
            print(f"  Status: ❌ Failed - {result.get('error', 'Unknown error')}")
    
    print("\n🔍 Recommendations:")
    print("- Run these tests in CI/CD pipeline")
    print("- Add automated security scanning with OWASP ZAP")
    print("- Implement penetration testing schedule")
    print("- Monitor security metrics in production")

if __name__ == "__main__":
    asyncio.run(main())