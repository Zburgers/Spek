"""
Security Penetration Testing Suite for Posts Router

This module contains automated security tests that attempt various attack patterns
to verify the robustness of the authorization fixes in the posts router.

Attack Categories Tested:
1. ID Enumeration Attacks
2. Path Traversal Attacks  
3. SQL Injection Attempts
4. Authorization Bypass Techniques
5. Race Condition Exploitation
6. Token Manipulation
7. Parameter Pollution
8. IDOR (Insecure Direct Object Reference) vulnerabilities
"""

import asyncio
import json
import time
from typing import List, Dict, Any
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.security import create_access_token
from src.app.crud.crud_posts import crud_posts
from src.app.crud.crud_users import crud_users
from tests.helpers.generators import generate_random_string


class SecurityPenetrationTests:
    """Advanced security penetration testing for the posts API."""

    @pytest.fixture
    async def attack_users(self, db_session: AsyncSession) -> Dict[str, Any]:
        """Create multiple users for penetration testing."""
        users = {}
        
        # Create attacker user
        attacker_data = {
            "name": "Attacker User",
            "username": "attacker",
            "email": "attacker@evil.com", 
            "password": "AttackerPass123!"
        }
        attacker = await crud_users.create(db=db_session, object=attacker_data)
        users["attacker"] = {
            "user": attacker,
            "token": create_access_token(sub=attacker.id),
            "username": attacker.username,
            "id": attacker.id
        }
        
        # Create victim user
        victim_data = {
            "name": "Victim User",
            "username": "victim", 
            "email": "victim@innocent.com",
            "password": "VictimPass123!"
        }
        victim = await crud_users.create(db=db_session, object=victim_data)
        users["victim"] = {
            "user": victim,
            "token": create_access_token(sub=victim.id),
            "username": victim.username,
            "id": victim.id
        }
        
        # Create admin user for testing admin bypass
        admin_data = {
            "name": "Admin User",
            "username": "admin",
            "email": "admin@company.com",
            "password": "AdminPass123!",
            "is_superuser": True
        }
        admin = await crud_users.create(db=db_session, object=admin_data)
        users["admin"] = {
            "user": admin,
            "token": create_access_token(sub=admin.id),
            "username": admin.username,
            "id": admin.id
        }
        
        return users

    @pytest.fixture
    async def victim_posts(self, db_session: AsyncSession, attack_users: Dict) -> List[Dict]:
        """Create posts owned by the victim for testing unauthorized access."""
        posts = []
        victim_id = attack_users["victim"]["id"]
        
        for i in range(5):
            post_data = {
                "title": f"Victim's Secret Post {i}",
                "content": f"This is confidential content {i} that should not be accessible to attackers.",
                "created_by_user_id": victim_id
            }
            post = await crud_posts.create(db=db_session, object=post_data)
            posts.append({"post": post, "id": post.id})
            
        return posts

    # =================================================================
    # ID ENUMERATION ATTACK TESTS
    # =================================================================

    async def test_sequential_id_enumeration_attack(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test protection against sequential ID enumeration attacks."""
        attacker_token = attack_users["attacker"]["token"]
        victim_username = attack_users["victim"]["username"]
        
        # Try to enumerate posts by testing sequential IDs
        successful_access = 0
        total_attempts = 50
        
        for post_id in range(1, total_attempts + 1):
            # Attempt to access post
            response = await async_client.get(
                f"/{victim_username}/post/{post_id}",
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            if response.status_code == 200:
                successful_access += 1
                # If we can access any post, it's a security violation
                pytest.fail(f"SECURITY BREACH: Attacker accessed post ID {post_id} belonging to victim")
            
            # Attempt to modify post  
            response = await async_client.patch(
                f"/{victim_username}/post/{post_id}",
                json={"title": "HACKED BY ENUMERATION"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            if response.status_code == 200:
                pytest.fail(f"SECURITY BREACH: Attacker modified post ID {post_id} belonging to victim")
        
        # Should have no successful unauthorized access
        assert successful_access == 0, f"Enumeration attack succeeded {successful_access} times out of {total_attempts}"

    async def test_random_id_guessing_attack(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test protection against random ID guessing attacks."""
        import random
        
        attacker_token = attack_users["attacker"]["token"]
        victim_username = attack_users["victim"]["username"]
        
        # Generate random IDs to test
        random_ids = [random.randint(1, 10000) for _ in range(100)]
        
        for post_id in random_ids:
            response = await async_client.patch(
                f"/{victim_username}/post/{post_id}",
                json={"title": "RANDOM ATTACK"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            # Should never succeed with 200 OK
            assert response.status_code != 200, f"Random ID attack succeeded on ID {post_id}"
            assert response.status_code in [403, 404], f"Unexpected response code: {response.status_code}"

    # =================================================================
    # PATH TRAVERSAL ATTACK TESTS
    # =================================================================

    async def test_directory_traversal_username_attacks(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test protection against directory traversal attacks in username parameter."""
        attacker_token = attack_users["attacker"]["token"]
        victim_post_id = victim_posts[0]["id"]
        
        traversal_payloads = [
            "../victim",
            "../../victim", 
            "../../../victim",
            "..%2Fvictim",
            "..%2F..%2Fvictim",
            "%2e%2e/victim",
            "%2e%2e%2Fvictim",
            "....//victim",
            "..\\victim",
            "..\\..\\victim",
            ".%252e/.%252e/victim",
            "victim/../victim",
            "./victim",
            "/victim",
            "victim%00",
            "victim%2e%2e%2f",
            ".victim",
            "~victim"
        ]
        
        for payload in traversal_payloads:
            response = await async_client.patch(
                f"/{payload}/post/{victim_post_id}",
                json={"title": "TRAVERSAL ATTACK"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            # Should never succeed
            assert response.status_code != 200, f"Directory traversal succeeded with payload: {payload}"
            # Should be validation error, not found, or forbidden
            assert response.status_code in [400, 404, 422], f"Unexpected response for payload {payload}: {response.status_code}"

    # =================================================================
    # SQL INJECTION ATTACK TESTS
    # =================================================================

    async def test_sql_injection_in_id_parameter(
        self,
        async_client: AsyncClient,
        attack_users: Dict
    ):
        """Test protection against SQL injection attacks in ID parameter."""
        attacker_token = attack_users["attacker"]["token"]
        victim_username = attack_users["victim"]["username"]
        
        sql_payloads = [
            "1 OR 1=1",
            "1' OR '1'='1",
            "1; DROP TABLE posts;--",
            "1 UNION SELECT * FROM users",
            "1' UNION SELECT password FROM users--",
            "1; UPDATE posts SET title='HACKED'--",
            "1; DELETE FROM posts;--",
            "1' AND SLEEP(5)--",
            "1' OR BENCHMARK(1000000,MD5(1))--",
            "' OR 1=1#",
            "1'; WAITFOR DELAY '00:00:05'--",
            "1' OR 'x'='x",
            "1) OR 1=1--",
            "1)) OR 1=1--",
            "1 AND (SELECT COUNT(*) FROM users) > 0",
            "1' AND (SELECT SUBSTRING(password,1,1) FROM users LIMIT 1)='a'--"
        ]
        
        for payload in sql_payloads:
            # Test PATCH endpoint
            response = await async_client.patch(
                f"/{victim_username}/post/{payload}",
                json={"title": "SQL INJECTION TEST"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            # Should never succeed with 200 OK
            assert response.status_code != 200, f"SQL injection might have succeeded with payload: {payload}"
            # Should be validation error or not found
            assert response.status_code in [400, 404, 422], f"Unexpected response for SQL payload {payload}"
            
            # Test DELETE endpoint
            response = await async_client.delete(
                f"/{victim_username}/post/{payload}",
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            assert response.status_code != 200, f"SQL injection DELETE might have succeeded with payload: {payload}"

    async def test_sql_injection_in_username_parameter(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test protection against SQL injection attacks in username parameter."""
        attacker_token = attack_users["attacker"]["token"]
        victim_post_id = victim_posts[0]["id"]
        
        sql_usernames = [
            "victim' OR '1'='1",
            "victim'; DROP TABLE users;--",
            "victim' UNION SELECT * FROM posts--",
            "admin'--",
            "victim' AND 1=1--",
            "victim' OR EXISTS(SELECT 1 FROM users)--"
        ]
        
        for username in sql_usernames:
            response = await async_client.patch(
                f"/{username}/post/{victim_post_id}",
                json={"title": "SQL USERNAME INJECTION"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            # Should not succeed and should not cause database errors
            assert response.status_code in [400, 404, 422], f"SQL injection in username might have worked: {username}"

    # =================================================================
    # AUTHORIZATION BYPASS TESTS
    # =================================================================

    async def test_token_manipulation_attacks(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test protection against JWT token manipulation attacks."""
        victim_username = attack_users["victim"]["username"]
        victim_post_id = victim_posts[0]["id"]
        attacker_token = attack_users["attacker"]["token"]
        
        # Test various token manipulation techniques
        manipulated_tokens = [
            "",  # Empty token
            "Bearer ",  # Empty bearer
            "invalid_token",  # Invalid format
            attacker_token[:-5] + "XXXXX",  # Modified signature
            attacker_token.replace(".", "X"),  # Corrupted token
            "Bearer " + attacker_token + "extra",  # Extended token
            "Basic " + attacker_token,  # Wrong auth type
            attacker_token.upper(),  # Case changed
            attacker_token[10:],  # Truncated token
        ]
        
        for token in manipulated_tokens:
            headers = {"Authorization": f"Bearer {token}"} if not token.startswith("Bearer") and token else {"Authorization": token}
            
            response = await async_client.patch(
                f"/{victim_username}/post/{victim_post_id}",
                json={"title": "TOKEN MANIPULATION"},
                headers=headers
            )
            
            # Should always fail with 401 or 403
            assert response.status_code in [401, 403], f"Token manipulation might have worked: {token[:20]}..."

    async def test_privilege_escalation_attempts(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test protection against privilege escalation attacks."""
        # Try to use admin token to access user posts without proper authorization
        admin_token = attack_users["admin"]["token"]
        victim_username = attack_users["victim"]["username"]
        victim_post_id = victim_posts[0]["id"]
        
        # Admin should still not be able to access user posts via user endpoints
        # (Admin has separate db_post endpoints for legitimate admin access)
        response = await async_client.patch(
            f"/{victim_username}/post/{victim_post_id}",
            json={"title": "ADMIN PRIVILEGE ESCALATION"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Even admin should not be able to modify user posts via user endpoints
        assert response.status_code == 403, "Admin was able to bypass user post authorization"

    # =================================================================
    # RACE CONDITION TESTS
    # =================================================================

    async def test_concurrent_access_race_conditions(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test for race conditions in concurrent authorization checks."""
        attacker_token = attack_users["attacker"]["token"]
        victim_username = attack_users["victim"]["username"]
        victim_post_id = victim_posts[0]["id"]
        
        async def attack_attempt():
            """Single attack attempt."""
            return await async_client.patch(
                f"/{victim_username}/post/{victim_post_id}",
                json={"title": f"RACE CONDITION {generate_random_string(5)}"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
        
        # Launch 50 concurrent attacks
        tasks = [attack_attempt() for _ in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should fail - no race condition should allow success
        successful_attacks = 0
        for result in results:
            if hasattr(result, 'status_code') and result.status_code == 200:
                successful_attacks += 1
        
        assert successful_attacks == 0, f"Race condition allowed {successful_attacks} successful attacks"

    async def test_time_based_attacks(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test for timing-based information disclosure."""
        attacker_token = attack_users["attacker"]["token"]
        victim_username = attack_users["victim"]["username"]
        
        # Measure response times for existing vs non-existing posts
        existing_post_times = []
        nonexisting_post_times = []
        
        # Test existing posts
        for post in victim_posts[:3]:
            start_time = time.time()
            response = await async_client.patch(
                f"/{victim_username}/post/{post['id']}",
                json={"title": "TIMING ATTACK"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            end_time = time.time()
            existing_post_times.append(end_time - start_time)
            assert response.status_code == 403  # Should be forbidden
        
        # Test non-existing posts
        for fake_id in [99999, 88888, 77777]:
            start_time = time.time()
            response = await async_client.patch(
                f"/{victim_username}/post/{fake_id}",
                json={"title": "TIMING ATTACK"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            end_time = time.time()
            nonexisting_post_times.append(end_time - start_time)
            assert response.status_code == 404  # Should be not found
        
        # Check that timing differences don't reveal information
        avg_existing = sum(existing_post_times) / len(existing_post_times)
        avg_nonexisting = sum(nonexisting_post_times) / len(nonexisting_post_times)
        timing_diff = abs(avg_existing - avg_nonexisting)
        
        # Timing difference should not be suspiciously large (more than 100ms)
        assert timing_diff < 0.1, f"Timing attack possible: {timing_diff:.3f}s difference between existing/non-existing posts"

    # =================================================================
    # PARAMETER POLLUTION TESTS
    # =================================================================

    async def test_http_parameter_pollution(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test protection against HTTP Parameter Pollution attacks."""
        attacker_token = attack_users["attacker"]["token"]
        victim_username = attack_users["victim"]["username"]
        victim_post_id = victim_posts[0]["id"]
        
        # Test multiple ID parameters
        polluted_urls = [
            f"/{victim_username}/post/{victim_post_id}?id=1",
            f"/{victim_username}/post/{victim_post_id}?id=2&id=3",
            f"/{victim_username}/post/{victim_post_id}?post_id=999",
        ]
        
        for url in polluted_urls:
            response = await async_client.patch(
                url,
                json={"title": "PARAMETER POLLUTION"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            # Should not bypass authorization
            assert response.status_code == 403, f"Parameter pollution might have worked: {url}"

    # =================================================================
    # IDOR (INSECURE DIRECT OBJECT REFERENCE) TESTS
    # =================================================================

    async def test_idor_cross_user_access(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test protection against Insecure Direct Object Reference vulnerabilities."""
        attacker_token = attack_users["attacker"]["token"]
        attacker_username = attack_users["attacker"]["username"]
        victim_username = attack_users["victim"]["username"]
        
        # Attacker tries to access victim's posts using correct post IDs
        # but their own username in the URL
        for post in victim_posts:
            # This should fail because the post doesn't belong to the attacker
            response = await async_client.patch(
                f"/{attacker_username}/post/{post['id']}",
                json={"title": "IDOR ATTACK - WRONG USER"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            assert response.status_code == 404, f"IDOR vulnerability: Attacker accessed victim's post {post['id']} via their own username"
            
            # Also test with victim's username - should be forbidden
            response = await async_client.patch(
                f"/{victim_username}/post/{post['id']}",
                json={"title": "IDOR ATTACK - VICTIM USER"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            assert response.status_code == 403, f"IDOR vulnerability: Attacker accessed victim's post {post['id']} via victim's username"

    # =================================================================
    # SECURITY REGRESSION TESTS
    # =================================================================

    async def test_original_vulnerability_regression(
        self,
        async_client: AsyncClient,
        attack_users: Dict,
        victim_posts: List[Dict]
    ):
        """Test that the original TOCTOU vulnerability has been completely fixed."""
        attacker_token = attack_users["attacker"]["token"]
        victim_username = attack_users["victim"]["username"]
        
        # This test specifically validates the fix for the original vulnerability
        # where posts could be accessed without proper ownership verification
        
        for post in victim_posts:
            # 1. Verify attacker cannot read victim's post
            response = await async_client.get(
                f"/{victim_username}/post/{post['id']}",
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            # Note: GET endpoint might allow public access, focus on modifications
            
            # 2. Verify attacker cannot modify victim's post (CRITICAL TEST)
            response = await async_client.patch(
                f"/{victim_username}/post/{post['id']}",
                json={"title": "REGRESSION TEST - SHOULD FAIL"},
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            assert response.status_code == 403, f"REGRESSION: Original TOCTOU vulnerability reintroduced for post {post['id']}"
            
            # 3. Verify attacker cannot delete victim's post (CRITICAL TEST)
            response = await async_client.delete(
                f"/{victim_username}/post/{post['id']}",
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            assert response.status_code == 403, f"REGRESSION: Original TOCTOU vulnerability reintroduced for delete of post {post['id']}"

    # =================================================================
    # MASS ASSIGNMENT TESTS
    # =================================================================

    async def test_mass_assignment_attacks(
        self,
        async_client: AsyncClient,
        attack_users: Dict
    ):
        """Test protection against mass assignment attacks."""
        attacker_token = attack_users["attacker"]["token"]
        attacker_username = attack_users["attacker"]["username"]
        
        # Create a post as attacker
        response = await async_client.post(
            f"/{attacker_username}/post",
            json={"title": "Attacker Post", "content": "Content"},
            headers={"Authorization": f"Bearer {attacker_token}"}
        )
        assert response.status_code == 201
        post_id = response.json()["id"]
        
        # Try to modify protected fields via mass assignment
        malicious_updates = [
            {"title": "Updated", "id": 999},  # Try to change ID
            {"title": "Updated", "created_by_user_id": 999},  # Try to change owner
            {"title": "Updated", "is_deleted": False},  # Try to undelete
            {"title": "Updated", "created_at": "2020-01-01T00:00:00"},  # Try to change timestamps
            {"title": "Updated", "updated_at": "2020-01-01T00:00:00"},
        ]
        
        for malicious_data in malicious_updates:
            response = await async_client.patch(
                f"/{attacker_username}/post/{post_id}",
                json=malicious_data,
                headers={"Authorization": f"Bearer {attacker_token}"}
            )
            
            # Should succeed (ignoring extra fields) or fail safely
            assert response.status_code in [200, 422], "Mass assignment should be prevented or ignored safely"
