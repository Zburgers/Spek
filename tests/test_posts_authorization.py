"""
Comprehensive Security Test Suite for Posts Router Authorization

This test suite validates the authorization fixes implemented in the posts router
and prevents regression of the TOCTOU vulnerability that was discovered and fixed.

Test Categories:
1. Ownership verification tests
2. Authentication requirement tests  
3. Authorization bypass prevention tests
4. Edge cases and error handling tests
5. Security penetration tests
"""

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.security import create_access_token
from src.app.crud.crud_posts import crud_posts
from src.app.crud.crud_users import crud_users
from src.app.schemas.post import PostCreate, PostUpdate
from src.app.schemas.user import UserCreate
from tests.helpers.generators import generate_random_string


class TestPostsAuthorization:
    """Test suite for posts authorization security."""

    @pytest.fixture
    async def test_user_1(self, db_session: AsyncSession) -> dict:
        """Create first test user."""
        user_data = UserCreate(
            name="Test User 1",
            username="testuser1",
            email="test1@example.com",
            password="TestPassword123!"
        )
        user = await crud_users.create(db=db_session, object=user_data)
        token = create_access_token(sub=user.id)
        return {
            "user": user,
            "token": token,
            "username": user.username,
            "id": user.id
        }

    @pytest.fixture  
    async def test_user_2(self, db_session: AsyncSession) -> dict:
        """Create second test user."""
        user_data = UserCreate(
            name="Test User 2", 
            username="testuser2",
            email="test2@example.com",
            password="TestPassword123!"
        )
        user = await crud_users.create(db=db_session, object=user_data)
        token = create_access_token(sub=user.id)
        return {
            "user": user,
            "token": token, 
            "username": user.username,
            "id": user.id
        }

    @pytest.fixture
    async def test_post_user_1(self, db_session: AsyncSession, test_user_1: dict) -> dict:
        """Create a test post owned by user 1."""
        post_data = {
            "title": "Test Post by User 1",
            "content": "This is a test post content.",
            "created_by_user_id": test_user_1["id"]
        }
        post = await crud_posts.create(db=db_session, object=post_data)
        return {"post": post, "id": post.id}

    @pytest.fixture
    async def test_post_user_2(self, db_session: AsyncSession, test_user_2: dict) -> dict:
        """Create a test post owned by user 2."""
        post_data = {
            "title": "Test Post by User 2", 
            "content": "This is another test post content.",
            "created_by_user_id": test_user_2["id"]
        }
        post = await crud_posts.create(db=db_session, object=post_data)
        return {"post": post, "id": post.id}

    # =================================================================
    # PATCH ENDPOINT SECURITY TESTS
    # =================================================================

    async def test_patch_own_post_success(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that users can successfully patch their own posts."""
        update_data = PostUpdate(
            title="Updated Title",
            content="Updated content"
        )
        
        response = await async_client.patch(
            f"/{test_user_1['username']}/post/{test_post_user_1['id']}",
            json=update_data.model_dump(),
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Post updated"

    async def test_patch_other_user_post_forbidden(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_user_2: dict,
        test_post_user_2: dict
    ):
        """Test that users cannot patch posts owned by other users."""
        update_data = PostUpdate(
            title="Malicious Update",
            content="Trying to update someone else's post"
        )
        
        # User 1 tries to update User 2's post
        response = await async_client.patch(
            f"/{test_user_2['username']}/post/{test_post_user_2['id']}",
            json=update_data.model_dump(),
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_patch_nonexistent_post_not_found(
        self,
        async_client: AsyncClient,
        test_user_1: dict
    ):
        """Test that patching a non-existent post returns 404."""
        update_data = PostUpdate(title="Update", content="Content")
        
        response = await async_client.patch(
            f"/{test_user_1['username']}/post/99999",
            json=update_data.model_dump(),
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Post not found" in response.json()["detail"]

    async def test_patch_without_authentication_unauthorized(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that patching without authentication returns 401."""
        update_data = PostUpdate(title="Update", content="Content")
        
        response = await async_client.patch(
            f"/{test_user_1['username']}/post/{test_post_user_1['id']}",
            json=update_data.model_dump()
            # No Authorization header
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_patch_with_invalid_username_not_found(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that patching with invalid username returns 404."""
        update_data = PostUpdate(title="Update", content="Content")
        
        response = await async_client.patch(
            f"/nonexistent_user/post/{test_post_user_1['id']}",
            json=update_data.model_dump(),
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in response.json()["detail"]

    # =================================================================
    # DELETE ENDPOINT SECURITY TESTS  
    # =================================================================

    async def test_delete_own_post_success(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that users can successfully delete their own posts."""
        response = await async_client.delete(
            f"/{test_user_1['username']}/post/{test_post_user_1['id']}",
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Post deleted"

    async def test_delete_other_user_post_forbidden(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_user_2: dict,
        test_post_user_2: dict
    ):
        """Test that users cannot delete posts owned by other users."""
        # User 1 tries to delete User 2's post
        response = await async_client.delete(
            f"/{test_user_2['username']}/post/{test_post_user_2['id']}",
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_delete_nonexistent_post_not_found(
        self,
        async_client: AsyncClient,
        test_user_1: dict
    ):
        """Test that deleting a non-existent post returns 404."""
        response = await async_client.delete(
            f"/{test_user_1['username']}/post/99999",
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Post not found" in response.json()["detail"]

    async def test_delete_without_authentication_unauthorized(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that deleting without authentication returns 401."""
        response = await async_client.delete(
            f"/{test_user_1['username']}/post/{test_post_user_1['id']}"
            # No Authorization header
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_delete_with_invalid_username_not_found(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that deleting with invalid username returns 404."""
        response = await async_client.delete(
            f"/nonexistent_user/post/{test_post_user_1['id']}",
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in response.json()["detail"]

    # =================================================================
    # EDGE CASES AND SECURITY TESTS
    # =================================================================

    async def test_patch_deleted_post_not_found(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that patching a soft-deleted post returns 404."""
        # First soft delete the post
        await crud_posts.delete(db=db_session, id=test_post_user_1["id"])
        
        update_data = PostUpdate(title="Update", content="Content")
        response = await async_client.patch(
            f"/{test_user_1['username']}/post/{test_post_user_1['id']}",
            json=update_data.model_dump(),
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_already_deleted_post_not_found(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that deleting an already soft-deleted post returns 404."""
        # First soft delete the post
        await crud_posts.delete(db=db_session, id=test_post_user_1["id"])
        
        response = await async_client.delete(
            f"/{test_user_1['username']}/post/{test_post_user_1['id']}",
            headers={"Authorization": f"Bearer {test_user_1['token']}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_malicious_id_injection_attempts(
        self,
        async_client: AsyncClient,
        test_user_1: dict
    ):
        """Test that SQL injection attempts in ID parameter are handled safely."""
        malicious_ids = [
            "1 OR 1=1",
            "1; DROP TABLE posts;",
            "1' OR '1'='1",
            "../../../etc/passwd",
            "NULL",
            "-1"
        ]
        
        for malicious_id in malicious_ids:
            # Test PATCH
            response = await async_client.patch(
                f"/{test_user_1['username']}/post/{malicious_id}",
                json={"title": "test"},
                headers={"Authorization": f"Bearer {test_user_1['token']}"}
            )
            # Should either be 404, 422 (validation error), or 400 (bad request)
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_400_BAD_REQUEST
            ]
            
            # Test DELETE
            response = await async_client.delete(
                f"/{test_user_1['username']}/post/{malicious_id}",
                headers={"Authorization": f"Bearer {test_user_1['token']}"}
            )
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_400_BAD_REQUEST
            ]

    # =================================================================
    # AUTHORIZATION BYPASS PREVENTION TESTS
    # =================================================================

    async def test_id_enumeration_attack_prevention(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_user_2: dict,
        test_post_user_2: dict
    ):
        """Test that users cannot enumerate posts by trying different IDs."""
        # User 1 tries to access User 2's post by ID enumeration
        for post_id in range(test_post_user_2["id"] - 5, test_post_user_2["id"] + 5):
            response = await async_client.patch(
                f"/{test_user_1['username']}/post/{post_id}",
                json={"title": "enumeration attack"},
                headers={"Authorization": f"Bearer {test_user_1['token']}"}
            )
            # Should be 404 (not found) or 403 (forbidden), never 200 (success)
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_403_FORBIDDEN
            ]

    async def test_path_traversal_attack_prevention(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that path traversal attacks in username are prevented."""
        malicious_usernames = [
            "../admin",
            "../../root", 
            "../testuser1",
            "..%2F..%2Fadmin",
            "%2e%2e%2fadmin"
        ]
        
        for malicious_username in malicious_usernames:
            response = await async_client.patch(
                f"/{malicious_username}/post/{test_post_user_1['id']}",
                json={"title": "path traversal"},
                headers={"Authorization": f"Bearer {test_user_1['token']}"}
            )
            
            # Should be 404 (user not found) or validation error
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_400_BAD_REQUEST
            ]

    async def test_concurrent_modification_race_condition(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that concurrent modifications don't create race conditions."""
        import asyncio
        
        async def patch_post():
            return await async_client.patch(
                f"/{test_user_1['username']}/post/{test_post_user_1['id']}",
                json={"title": f"Concurrent update {generate_random_string(5)}"},
                headers={"Authorization": f"Bearer {test_user_1['token']}"}
            )
        
        async def delete_post():
            return await async_client.delete(
                f"/{test_user_1['username']}/post/{test_post_user_1['id']}",
                headers={"Authorization": f"Bearer {test_user_1['token']}"}
            )
        
        # Run concurrent operations
        results = await asyncio.gather(
            patch_post(),
            delete_post(),
            patch_post(),
            return_exceptions=True
        )
        
        # At least one operation should succeed, others should fail gracefully
        success_count = sum(1 for r in results if hasattr(r, 'status_code') and r.status_code == 200)
        error_count = sum(1 for r in results if hasattr(r, 'status_code') and r.status_code in [404, 403])
        
        assert success_count >= 1  # At least one should succeed
        assert success_count + error_count == len(results)  # All should return valid status codes

    # =================================================================
    # PERFORMANCE AND REGRESSION TESTS
    # =================================================================

    @pytest.mark.performance
    async def test_authorization_check_performance(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_post_user_1: dict
    ):
        """Test that authorization checks don't significantly impact performance."""
        import time
        
        start_time = time.time()
        
        # Perform multiple operations to measure average time
        for _ in range(10):
            response = await async_client.patch(
                f"/{test_user_1['username']}/post/{test_post_user_1['id']}",
                json={"title": "Performance test"},
                headers={"Authorization": f"Bearer {test_user_1['token']}"}
            )
            assert response.status_code == status.HTTP_200_OK
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 10
        
        # Authorization check should not add more than 100ms per request
        assert avg_time < 0.1, f"Authorization check too slow: {avg_time:.3f}s per request"

    async def test_ownership_verification_consistency(
        self,
        async_client: AsyncClient,
        test_user_1: dict,
        test_user_2: dict
    ):
        """Test that ownership verification is consistently applied."""
        # Create multiple posts for user 1
        post_ids = []
        for i in range(5):
            response = await async_client.post(
                f"/{test_user_1['username']}/post",
                json={
                    "title": f"Test Post {i}",
                    "content": f"Content {i}"
                },
                headers={"Authorization": f"Bearer {test_user_1['token']}"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            post_ids.append(response.json()["id"])
        
        # User 2 should not be able to access any of user 1's posts
        for post_id in post_ids:
            # Test PATCH
            response = await async_client.patch(
                f"/{test_user_1['username']}/post/{post_id}",
                json={"title": "Unauthorized access"},
                headers={"Authorization": f"Bearer {test_user_2['token']}"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN
            
            # Test DELETE
            response = await async_client.delete(
                f"/{test_user_1['username']}/post/{post_id}",
                headers={"Authorization": f"Bearer {test_user_2['token']}"}
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN
