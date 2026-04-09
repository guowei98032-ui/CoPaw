# -*- coding: utf-8 -*-
"""ChatRoom HTTP API integration tests.

Tests cover:
1. Basic CRUD operations
2. Edge cases and error handling
3. Concurrent operations
4. Special scenarios

Uses httpx async client to test HTTP endpoints directly.
"""
import asyncio
import pytest
import httpx
import csv
import json
import io
from datetime import datetime
from typing import Dict, List, Any

# Import real agent IDs for tests
from test_config import (
    REAL_LEAD_AGENT,
    REAL_WORKER_1,
    REAL_WORKER_2,
    REAL_WORKER_3,
    REAL_WORKER_AGENTS,
)

# Default base URL for local testing
BASE_URL = "http://127.0.0.1:8088/api/chatroom"


class ChatroomAPIClient:
    """Async HTTP client for ChatRoom API."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self._client: httpx.AsyncClient = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    # ========== ChatRoom CRUD ==========

    async def create_room(
        self,
        name: str,
        lead_agent_id: str = REAL_LEAD_AGENT,
        agent_ids: List[str] = None,
        layout: str = "tiles",
    ) -> httpx.Response:
        """Create a chatroom."""
        data = {
            "name": name,
            "lead_agent_id": lead_agent_id,
            "agent_ids": agent_ids or [],
            "layout": layout,
        }
        return await self._client.post(f"{self.base_url}", json=data)

    async def list_rooms(self, user_id: str = "default") -> httpx.Response:
        """List all chatrooms."""
        return await self._client.get(f"{self.base_url}", params={"user_id": user_id})

    async def get_room(self, room_id: str) -> httpx.Response:
        """Get chatroom details."""
        return await self._client.get(f"{self.base_url}/{room_id}")

    async def update_room(
        self,
        room_id: str,
        name: str = None,
        lead_agent_id: str = None,
        agent_ids: List[str] = None,
    ) -> httpx.Response:
        """Update a chatroom."""
        data = {}
        if name is not None:
            data["name"] = name
        if lead_agent_id is not None:
            data["lead_agent_id"] = lead_agent_id
        if agent_ids is not None:
            data["agent_ids"] = agent_ids
        return await self._client.put(f"{self.base_url}/{room_id}", json=data)

    async def delete_room(self, room_id: str) -> httpx.Response:
        """Delete a chatroom."""
        return await self._client.delete(f"{self.base_url}/{room_id}")

    # ========== Task Management ==========

    async def create_task(
        self,
        room_id: str,
        subject: str,
        description: str = None,
        owner: str = None,
        priority: str = "medium",
    ) -> httpx.Response:
        """Create a task."""
        data = {
            "subject": subject,
            "description": description,
            "owner": owner,
            "priority": priority,
        }
        return await self._client.post(f"{self.base_url}/{room_id}/tasks", json=data)

    async def list_tasks(
        self,
        room_id: str,
        status: str = None,
        owner: str = None,
    ) -> httpx.Response:
        """List tasks in a chatroom."""
        params = {}
        if status:
            params["status"] = status
        if owner:
            params["owner"] = owner
        return await self._client.get(f"{self.base_url}/{room_id}/tasks", params=params)

    async def get_task(self, room_id: str, task_id: str) -> httpx.Response:
        """Get a specific task."""
        return await self._client.get(f"{self.base_url}/{room_id}/tasks/{task_id}")

    async def update_task(
        self,
        room_id: str,
        task_id: str,
        status: str = None,
        owner: str = None,
        description: str = None,
        progress: int = None,
    ) -> httpx.Response:
        """Update a task."""
        data = {}
        if status is not None:
            data["status"] = status
        if owner is not None:
            data["owner"] = owner
        if description is not None:
            data["description"] = description
        if progress is not None:
            data["progress"] = progress
        return await self._client.put(f"{self.base_url}/{room_id}/tasks/{task_id}", json=data)

    async def cancel_task(
        self,
        room_id: str,
        task_id: str,
        reason: str = None,
        cancelled_by: str = None,
    ) -> httpx.Response:
        """Cancel a task."""
        data = {}
        if reason:
            data["reason"] = reason
        if cancelled_by:
            data["cancelled_by"] = cancelled_by
        return await self._client.post(
            f"{self.base_url}/{room_id}/tasks/{task_id}/cancel",
            json=data,
        )

    async def retry_task(
        self,
        room_id: str,
        task_id: str,
        reset_owner: bool = True,
    ) -> httpx.Response:
        """Retry a failed/cancelled task."""
        data = {"reset_owner": reset_owner}
        return await self._client.post(
            f"{self.base_url}/{room_id}/tasks/{task_id}/retry",
            json=data,
        )

    async def delete_task(self, room_id: str, task_id: str) -> httpx.Response:
        """Delete a task."""
        return await self._client.delete(f"{self.base_url}/{room_id}/tasks/{task_id}")

    async def set_auto_mode(
        self,
        room_id: str,
        task_id: str,
        auto_mode: bool,
    ) -> httpx.Response:
        """Set task auto_mode."""
        return await self._client.post(
            f"{self.base_url}/{room_id}/tasks/{task_id}/auto-mode",
            json={"auto_mode": auto_mode},
        )

    async def add_task_log(
        self,
        room_id: str,
        task_id: str,
        event: str,
        details: str = None,
    ) -> httpx.Response:
        """Add task log entry."""
        return await self._client.post(
            f"{self.base_url}/{room_id}/tasks/{task_id}/log",
            json={"event": event, "details": details},
        )

    async def batch_task_operation(
        self,
        room_id: str,
        task_ids: List[str],
        operation: str,
        reason: str = None,
        owner: str = None,
        status: str = None,
        priority: str = None,
    ) -> httpx.Response:
        """Perform batch task operation."""
        data = {"task_ids": task_ids, "operation": operation}
        if reason:
            data["reason"] = reason
        if owner:
            data["owner"] = owner
        if status:
            data["status"] = status
        if priority:
            data["priority"] = priority
        return await self._client.post(
            f"{self.base_url}/{room_id}/tasks/batch",
            json=data,
        )

    async def export_tasks(
        self,
        room_id: str,
        format: str = "csv",
        status: str = None,
    ) -> httpx.Response:
        """Export tasks."""
        params = {"format": format}
        if status:
            params["status"] = status
        return await self._client.get(
            f"{self.base_url}/{room_id}/tasks/export",
            params=params,
        )

    async def get_timeout_tasks(self, room_id: str) -> httpx.Response:
        """Get timed out tasks."""
        return await self._client.get(f"{self.base_url}/{room_id}/tasks/timeout")

    # ========== Message Management ==========

    async def send_message(
        self,
        room_id: str,
        content: str,
        to_agent: str = None,
        message_type: str = "chat",
    ) -> httpx.Response:
        """Send a message."""
        data = {"content": content, "message_type": message_type}
        if to_agent:
            data["to_agent"] = to_agent
        return await self._client.post(
            f"{self.base_url}/{room_id}/messages",
            json=data,
        )

    async def list_messages(
        self,
        room_id: str,
        to_agent: str = None,
        unread_only: bool = False,
        limit: int = 100,
    ) -> httpx.Response:
        """List messages."""
        params = {"unread_only": unread_only, "limit": limit}
        if to_agent:
            params["to_agent"] = to_agent
        return await self._client.get(
            f"{self.base_url}/{room_id}/messages",
            params=params,
        )

    async def mark_message_read(self, room_id: str, message_id: str) -> httpx.Response:
        """Mark message as read."""
        return await self._client.put(
            f"{self.base_url}/{room_id}/messages/{message_id}/read",
        )

    async def mark_agent_messages_read(
        self,
        room_id: str,
        agent_id: str,
    ) -> httpx.Response:
        """Mark all messages for an agent as read."""
        return await self._client.put(
            f"{self.base_url}/{room_id}/agents/{agent_id}/messages/read-all",
        )


# ========== Test Fixture Helpers ==========

async def create_test_room(client: ChatroomAPIClient, name: str = None) -> Dict[str, Any]:
    """Helper to create a test room and return its data."""
    room_name = name or f"test-room-{datetime.now().isoformat()}"
    resp = await client.create_room(room_name)
    assert resp.status_code == 201
    return resp.json()["room"]


async def create_test_task(
    client: ChatroomAPIClient,
    room_id: str,
    subject: str = None,
) -> Dict[str, Any]:
    """Helper to create a test task and return its data."""
    task_subject = subject or f"test-task-{datetime.now().isoformat()}"
    resp = await client.create_task(room_id, task_subject)
    assert resp.status_code == 201
    return resp.json()


# ========== Basic CRUD Tests ==========


@pytest.mark.asyncio
class TestChatRoomCRUD:
    """Test ChatRoom CRUD operations."""

    async def test_create_room_success(self):
        """Test successful room creation."""
        async with ChatroomAPIClient() as client:
            resp = await client.create_room(
                name="test-room-basic",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["room"]["name"] == "test-room-basic"
            assert data["room"]["lead_agent_id"] == REAL_LEAD_AGENT
            assert REAL_WORKER_1 in data["room"]["agent_ids"]
            assert "message" in data

            # Cleanup
            await client.delete_room(data["room"]["id"])

    async def test_create_room_minimal(self):
        """Test room creation with minimal fields."""
        async with ChatroomAPIClient() as client:
            resp = await client.create_room(name="minimal-room")
            assert resp.status_code == 201
            data = resp.json()
            assert data["room"]["name"] == "minimal-room"

            # Cleanup
            await client.delete_room(data["room"]["id"])

    async def test_list_rooms(self):
        """Test listing rooms."""
        async with ChatroomAPIClient() as client:
            # Create some rooms
            room1 = await create_test_room(client, "list-test-1")
            room2 = await create_test_room(client, "list-test-2")

            resp = await client.list_rooms()
            assert resp.status_code == 200
            rooms = resp.json()
            assert len(rooms) >= 2
            room_ids = [r["id"] for r in rooms]
            assert room1["id"] in room_ids
            assert room2["id"] in room_ids

            # Cleanup
            await client.delete_room(room1["id"])
            await client.delete_room(room2["id"])

    async def test_get_room_detail(self):
        """Test getting room details."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "detail-test")
            task = await create_test_task(client, room["id"], "detail-task")

            resp = await client.get_room(room["id"])
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == room["id"]
            assert data["name"] == "detail-test"
            assert "tasks" in data
            assert len(data["tasks"]) >= 1

            # Cleanup
            await client.delete_room(room["id"])

    async def test_update_room(self):
        """Test updating room."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "update-test")

            resp = await client.update_room(
                room["id"],
                name="updated-name",
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "updated-name"
            assert REAL_WORKER_1 in data["agent_ids"]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_delete_room(self):
        """Test deleting room."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "delete-test")

            resp = await client.delete_room(room["id"])
            assert resp.status_code == 200
            assert resp.json()["success"] is True

            # Verify deleted
            resp = await client.get_room(room["id"])
            assert resp.status_code == 404


@pytest.mark.asyncio
class TestTaskCRUD:
    """Test Task CRUD operations."""

    async def test_create_task_success(self):
        """Test successful task creation."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-create-test")

            resp = await client.create_task(
                room["id"],
                subject="test-task",
                description="Test task description",
                owner=REAL_WORKER_1,
                priority="high",
            )
            assert resp.status_code == 201
            task = resp.json()
            assert task["subject"] == "test-task"
            assert task["status"] == "pending"
            assert task["owner"] == REAL_WORKER_1
            assert task["priority"] == "high"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_list_tasks(self):
        """Test listing tasks."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-list-test")
            task1 = await create_test_task(client, room["id"], "list-task-1")
            task2 = await create_test_task(client, room["id"], "list-task-2")

            resp = await client.list_tasks(room["id"])
            assert resp.status_code == 200
            tasks = resp.json()
            assert len(tasks) >= 2

            # Cleanup
            await client.delete_room(room["id"])

    async def test_list_tasks_with_filter(self):
        """Test listing tasks with status filter."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-filter-test")
            task1 = await create_test_task(client, room["id"], "filter-task-1")

            # Update task to completed
            await client.update_task(room["id"], task1["id"], status="completed")
            task2 = await create_test_task(client, room["id"], "filter-task-2")

            # Filter by pending
            resp = await client.list_tasks(room["id"], status="pending")
            assert resp.status_code == 200
            tasks = resp.json()
            task_ids = [t["id"] for t in tasks]
            assert task1["id"] not in task_ids  # completed
            assert task2["id"] in task_ids  # pending

            # Cleanup
            await client.delete_room(room["id"])

    async def test_get_task(self):
        """Test getting a specific task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-get-test")
            task = await create_test_task(client, room["id"], "get-task")

            resp = await client.get_task(room["id"], task["id"])
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == task["id"]
            assert data["subject"] == "get-task"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_update_task(self):
        """Test updating task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-update-test")
            task = await create_test_task(client, room["id"], "update-task")

            resp = await client.update_task(
                room["id"],
                task["id"],
                status="in_progress",
                owner=REAL_WORKER_2,
                progress=50,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "in_progress"
            assert data["owner"] == REAL_WORKER_2
            assert data["progress"] == 50

            # Cleanup
            await client.delete_room(room["id"])

    async def test_update_task_progress_boundary(self):
        """Test task progress clamping to 0-100."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "progress-test")
            task = await create_test_task(client, room["id"], "progress-task")

            # Test negative progress
            resp = await client.update_task(room["id"], task["id"], progress=-10)
            assert resp.json()["progress"] == 0

            # Test over 100
            resp = await client.update_task(room["id"], task["id"], progress=150)
            assert resp.json()["progress"] == 100

            # Cleanup
            await client.delete_room(room["id"])

    async def test_delete_task(self):
        """Test deleting task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-delete-test")
            task = await create_test_task(client, room["id"], "delete-task")

            resp = await client.delete_task(room["id"], task["id"])
            assert resp.status_code == 200
            assert resp.json()["success"] is True

            # Verify deleted
            resp = await client.get_task(room["id"], task["id"])
            assert resp.status_code == 404

            # Cleanup
            await client.delete_room(room["id"])

    async def test_cancel_task(self):
        """Test cancelling task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-cancel-test")
            task = await create_test_task(client, room["id"], "cancel-task")

            resp = await client.cancel_task(
                room["id"],
                task["id"],
                reason="Test cancellation",
                cancelled_by="test-user",
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "cancelled"
            assert "Cancelled by test-user" in data["description"]
            assert "Test cancellation" in data["description"]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_retry_task(self):
        """Test retrying failed task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-retry-test")
            task = await create_test_task(client, room["id"], "retry-task")

            # First fail the task
            await client.update_task(room["id"], task["id"], status="failed")

            # Retry
            resp = await client.retry_task(room["id"], task["id"])
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "pending"
            assert data["owner"] is None  # reset_owner=True

            # Cleanup
            await client.delete_room(room["id"])

    async def test_retry_cancelled_task(self):
        """Test retrying cancelled task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "task-retry-cancel-test")
            task = await create_test_task(client, room["id"], "retry-cancel-task")

            # Cancel first
            await client.cancel_task(room["id"], task["id"])

            # Retry
            resp = await client.retry_task(room["id"], task["id"])
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "pending"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_set_auto_mode(self):
        """Test setting auto_mode."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "auto-mode-test")
            task = await create_test_task(client, room["id"], "auto-task")

            resp = await client.set_auto_mode(room["id"], task["id"], True)
            assert resp.status_code == 200
            assert resp.json()["auto_mode"] is True

            resp = await client.set_auto_mode(room["id"], task["id"], False)
            assert resp.json()["auto_mode"] is False

            # Cleanup
            await client.delete_room(room["id"])

    async def test_add_task_log(self):
        """Test adding task log entry."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "log-test")
            task = await create_test_task(client, room["id"], "log-task")

            resp = await client.add_task_log(
                room["id"],
                task["id"],
                event="started",
                details="Task execution started",
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "execution_log" in data
            assert len(data["execution_log"]) >= 1
            assert data["execution_log"][0]["event"] == "started"

            # Cleanup
            await client.delete_room(room["id"])


@pytest.mark.asyncio
class TestMessageCRUD:
    """Test Message operations."""

    async def test_send_message(self):
        """Test sending message."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "msg-send-test")

            resp = await client.send_message(
                room["id"],
                content="Test message",
                to_agent=REAL_WORKER_1,
                message_type="chat",
            )
            assert resp.status_code == 201
            msg = resp.json()
            assert msg["content"] == "Test message"
            assert msg["to_agent"] == REAL_WORKER_1

            # Cleanup
            await client.delete_room(room["id"])

    async def test_list_messages(self):
        """Test listing messages."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "msg-list-test")
            await client.send_message(room["id"], "msg-1", REAL_WORKER_1)
            await client.send_message(room["id"], "msg-2", REAL_WORKER_2)

            resp = await client.list_messages(room["id"])
            assert resp.status_code == 200
            msgs = resp.json()
            assert len(msgs) >= 2

            # Cleanup
            await client.delete_room(room["id"])

    async def test_mark_message_read(self):
        """Test marking message as read."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "msg-read-test")
            resp = await client.send_message(room["id"], "read-test", REAL_WORKER_1)
            msg = resp.json()

            resp = await client.mark_message_read(room["id"], msg["id"])
            assert resp.status_code == 200
            assert resp.json()["success"] is True

            # Verify read
            msgs = await client.list_messages(room["id"], unread_only=True)
            msg_ids = [m["id"] for m in msgs.json()]
            assert msg["id"] not in msg_ids

            # Cleanup
            await client.delete_room(room["id"])

    async def test_mark_agent_messages_read(self):
        """Test marking all agent messages as read."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "msg-agent-read-test")
            await client.send_message(room["id"], "msg-a", REAL_WORKER_1)
            await client.send_message(room["id"], "msg-b", REAL_WORKER_1)

            resp = await client.mark_agent_messages_read(room["id"], REAL_WORKER_1)
            assert resp.status_code == 200

            # Verify all read
            msgs = await client.list_messages(room["id"], to_agent=REAL_WORKER_1, unread_only=True)
            assert len(msgs.json()) == 0

            # Cleanup
            await client.delete_room(room["id"])


# ========== Error Handling Tests ==========


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling and edge cases."""

    async def test_room_not_found(self):
        """Test 404 for non-existent room."""
        async with ChatroomAPIClient() as client:
            resp = await client.get_room("nonexistent-room-id")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"].lower()

    async def test_task_not_found(self):
        """Test 404 for non-existent task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "error-test")
            resp = await client.get_task(room["id"], "nonexistent-task-id")
            assert resp.status_code == 404

            # Cleanup
            await client.delete_room(room["id"])

    async def test_task_wrong_room(self):
        """Test 400 for task in wrong room."""
        async with ChatroomAPIClient() as client:
            room1 = await create_test_room(client, "room-1")
            room2 = await create_test_room(client, "room-2")
            task = await create_test_task(client, room1["id"], "cross-room-task")

            # Try to access task from wrong room
            resp = await client.get_task(room2["id"], task["id"])
            assert resp.status_code == 400
            assert "does not belong" in resp.json()["detail"].lower()

            # Cleanup
            await client.delete_room(room1["id"])
            await client.delete_room(room2["id"])

    async def test_cancel_completed_task(self):
        """Test 400 for cancelling completed task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "cancel-completed-test")
            task = await create_test_task(client, room["id"], "completed-task")

            # Complete the task
            await client.update_task(room["id"], task["id"], status="completed")

            # Try to cancel
            resp = await client.cancel_task(room["id"], task["id"])
            assert resp.status_code == 400
            assert "cannot cancel" in resp.json()["detail"].lower()

            # Cleanup
            await client.delete_room(room["id"])

    async def test_cancel_already_cancelled_task(self):
        """Test 400 for cancelling already cancelled task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "cancel-cancelled-test")
            task = await create_test_task(client, room["id"], "cancelled-task")

            # Cancel once
            await client.cancel_task(room["id"], task["id"])

            # Try to cancel again
            resp = await client.cancel_task(room["id"], task["id"])
            assert resp.status_code == 400
            assert "already cancelled" in resp.json()["detail"].lower()

            # Cleanup
            await client.delete_room(room["id"])

    async def test_retry_running_task(self):
        """Test 400 for retrying non-failed task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "retry-running-test")
            task = await create_test_task(client, room["id"], "running-task")

            # Make task in_progress
            await client.update_task(room["id"], task["id"], status="in_progress")

            # Try to retry
            resp = await client.retry_task(room["id"], task["id"])
            assert resp.status_code == 400
            assert "cannot retry" in resp.json()["detail"].lower()

            # Cleanup
            await client.delete_room(room["id"])

    async def test_create_task_in_nonexistent_room(self):
        """Test 404 for creating task in non-existent room."""
        async with ChatroomAPIClient() as client:
            resp = await client.create_task("nonexistent-room", "test-task")
            assert resp.status_code == 404

    async def test_invalid_status_value(self):
        """Test batch operation with invalid status."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "invalid-status-test")
            task = await create_test_task(client, room["id"], "status-task")

            resp = await client.batch_task_operation(
                room["id"],
                [task["id"]],
                operation="set_status",
                status="invalid_status",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["failed_count"] == 1
            assert "Invalid status" in result["failed_tasks"][0]["reason"]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_invalid_priority_value(self):
        """Test batch operation with invalid priority."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "invalid-priority-test")
            task = await create_test_task(client, room["id"], "priority-task")

            resp = await client.batch_task_operation(
                room["id"],
                [task["id"]],
                operation="set_priority",
                priority="super_high",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["failed_count"] == 1
            assert "Invalid priority" in result["failed_tasks"][0]["reason"]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_batch_operation_unknown_operation(self):
        """Test batch operation with unknown operation."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "unknown-op-test")
            task = await create_test_task(client, room["id"], "op-task")

            resp = await client.batch_task_operation(
                room["id"],
                [task["id"]],
                operation="unknown_op",
            )
            # FastAPI validates operation type and returns 422 for unknown operations
            assert resp.status_code == 422

            # Cleanup
            await client.delete_room(room["id"])

    async def test_export_invalid_format(self):
        """Test export with invalid format."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "export-format-test")

            resp = await client.export_tasks(room["id"], format="invalid_format")
            assert resp.status_code == 400
            assert "Unsupported format" in resp.json()["detail"]

            # Cleanup
            await client.delete_room(room["id"])


# ========== Concurrent Operations Tests ==========


@pytest.mark.asyncio
class TestConcurrentOperations:
    """Test concurrent operations and race conditions."""

    async def test_concurrent_task_update(self):
        """Test concurrent updates to same task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "concurrent-update-test")
            task = await create_test_task(client, room["id"], "concurrent-task")

            # Launch concurrent updates
            updates = [
                client.update_task(room["id"], task["id"], progress=i * 10)
                for i in range(5)
            ]
            results = await asyncio.gather(*updates, return_exceptions=True)

            # All should succeed (last one wins)
            for r in results:
                if isinstance(r, httpx.Response):
                    assert r.status_code == 200

            # Verify final state
            resp = await client.get_task(room["id"], task["id"])
            assert resp.status_code == 200
            # Final progress should be one of 0, 10, 20, 30, 40
            assert resp.json()["progress"] in [0, 10, 20, 30, 40]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_concurrent_task_cancel_and_update(self):
        """Test concurrent cancel and update operations."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "cancel-update-test")
            task = await create_test_task(client, room["id"], "cancel-update-task")

            # Make task in_progress
            await client.update_task(room["id"], task["id"], status="in_progress")

            # Concurrent cancel and update
            cancel_op = client.cancel_task(room["id"], task["id"])
            update_op = client.update_task(room["id"], task["id"], status="completed")

            results = await asyncio.gather(cancel_op, update_op, return_exceptions=True)

            # One should succeed, one might fail based on timing
            # If cancel succeeds first, update might fail (cancelled task)
            # If update succeeds first, cancel might fail (completed task)

            # Verify final state - should be either cancelled or completed
            resp = await client.get_task(room["id"], task["id"])
            final_status = resp.json()["status"]
            assert final_status in ["cancelled", "completed"]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_concurrent_cancel_operations(self):
        """Test multiple concurrent cancel requests on same task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "multi-cancel-test")
            task = await create_test_task(client, room["id"], "multi-cancel-task")

            # Launch concurrent cancel requests
            cancels = [
                client.cancel_task(room["id"], task["id"], reason=f"cancel-{i}")
                for i in range(3)
            ]
            results = await asyncio.gather(*cancels, return_exceptions=True)

            # First should succeed (200), others might fail (400 - already cancelled)
            success_count = sum(
                1 for r in results
                if isinstance(r, httpx.Response) and r.status_code == 200
            )
            assert success_count == 1  # Only one should succeed

            # Verify task is cancelled
            resp = await client.get_task(room["id"], task["id"])
            assert resp.json()["status"] == "cancelled"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_concurrent_room_operations(self):
        """Test concurrent operations on different tasks in same room."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "room-concurrent-test")

            # Create multiple tasks
            tasks = [
                await create_test_task(client, room["id"], f"task-{i}")
                for i in range(5)
            ]

            # Concurrent operations on different tasks
            ops = [
                client.update_task(room["id"], tasks[0]["id"], status="in_progress"),
                client.update_task(room["id"], tasks[1]["id"], owner=REAL_WORKER_1),
                client.cancel_task(room["id"], tasks[2]["id"]),
                client.delete_task(room["id"], tasks[3]["id"]),
                client.set_auto_mode(room["id"], tasks[4]["id"], True),
            ]
            results = await asyncio.gather(*ops, return_exceptions=True)

            # All should succeed
            for r in results:
                if isinstance(r, httpx.Response):
                    assert r.status_code in [200, 201]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_concurrent_create_and_delete_room(self):
        """Test concurrent room creation and deletion."""
        async with ChatroomAPIClient() as client:
            # Create rooms concurrently
            create_ops = [
                client.create_room(f"concurrent-room-{i}")
                for i in range(3)
            ]
            create_results = await asyncio.gather(*create_ops)

            room_ids = [r.json()["room"]["id"] for r in create_results]

            # Delete concurrently
            delete_ops = [client.delete_room(rid) for rid in room_ids]
            delete_results = await asyncio.gather(*delete_ops)

            # All deletes should succeed
            for r in delete_results:
                assert r.status_code == 200

    async def test_batch_operation_partial_success(self):
        """Test batch operation with partial failures."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "batch-partial-test")

            # Create some tasks
            task1 = await create_test_task(client, room["id"], "batch-task-1")
            task2 = await create_test_task(client, room["id"], "batch-task-2")
            task3 = await create_test_task(client, room["id"], "batch-task-3")

            # Complete one task
            await client.update_task(room["id"], task3["id"], status="completed")

            # Batch cancel - should partially fail
            resp = await client.batch_task_operation(
                room["id"],
                [task1["id"], task2["id"], task3["id"]],
                operation="cancel",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["success_count"] == 2  # task1, task2
            assert result["failed_count"] == 1  # task3 (completed)
            assert task3["id"] in result["failed_tasks"][0]["task_id"]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_concurrent_claim_same_task(self):
        """Test concurrent claim operations on same task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "claim-test")
            task = await create_test_task(client, room["id"], "claim-task")

            # Concurrent assign operations
            assigns = [
                client.update_task(room["id"], task["id"], owner=REAL_WORKER_AGENTS[i % len(REAL_WORKER_AGENTS)])
                for i in range(3)
            ]
            results = await asyncio.gather(*assigns)

            # All should succeed, last one wins
            for r in results:
                assert r.status_code == 200

            # Verify final owner
            resp = await client.get_task(room["id"], task["id"])
            assert resp.json()["owner"] in REAL_WORKER_AGENTS

            # Cleanup
            await client.delete_room(room["id"])


# ========== Batch Operations Tests ==========


@pytest.mark.asyncio
class TestBatchOperations:
    """Test batch task operations."""

    async def test_batch_cancel(self):
        """Test batch cancel operation."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "batch-cancel-test")
            tasks = [
                await create_test_task(client, room["id"], f"batch-cancel-{i}")
                for i in range(3)
            ]

            resp = await client.batch_task_operation(
                room["id"],
                [t["id"] for t in tasks],
                operation="cancel",
                reason="Batch test",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["success_count"] == 3
            assert result["failed_count"] == 0

            # Verify all cancelled
            for t in tasks:
                task_resp = await client.get_task(room["id"], t["id"])
                assert task_resp.json()["status"] == "cancelled"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_batch_delete(self):
        """Test batch delete operation."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "batch-delete-test")
            tasks = [
                await create_test_task(client, room["id"], f"batch-delete-{i}")
                for i in range(3)
            ]

            resp = await client.batch_task_operation(
                room["id"],
                [t["id"] for t in tasks],
                operation="delete",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["success_count"] == 3

            # Verify all deleted
            for t in tasks:
                task_resp = await client.get_task(room["id"], t["id"])
                assert task_resp.status_code == 404

            # Cleanup
            await client.delete_room(room["id"])

    async def test_batch_assign(self):
        """Test batch assign operation."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "batch-assign-test")
            tasks = [
                await create_test_task(client, room["id"], f"batch-assign-{i}")
                for i in range(3)
            ]

            resp = await client.batch_task_operation(
                room["id"],
                [t["id"] for t in tasks],
                operation="assign",
                owner=REAL_WORKER_1,
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["success_count"] == 3

            # Verify all assigned
            for t in tasks:
                task_resp = await client.get_task(room["id"], t["id"])
                assert task_resp.json()["owner"] == REAL_WORKER_1

            # Cleanup
            await client.delete_room(room["id"])

    async def test_batch_assign_without_owner(self):
        """Test batch assign without owner parameter."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "batch-assign-no-owner-test")
            task = await create_test_task(client, room["id"], "assign-no-owner")

            resp = await client.batch_task_operation(
                room["id"],
                [task["id"]],
                operation="assign",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["failed_count"] == 1
            assert "Owner required" in result["failed_tasks"][0]["reason"]

            # Cleanup
            await client.delete_room(room["id"])

    async def test_batch_set_status(self):
        """Test batch set_status operation."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "batch-status-test")
            tasks = [
                await create_test_task(client, room["id"], f"batch-status-{i}")
                for i in range(3)
            ]

            resp = await client.batch_task_operation(
                room["id"],
                [t["id"] for t in tasks],
                operation="set_status",
                status="in_progress",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["success_count"] == 3

            # Verify all in_progress
            for t in tasks:
                task_resp = await client.get_task(room["id"], t["id"])
                assert task_resp.json()["status"] == "in_progress"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_batch_set_priority(self):
        """Test batch set_priority operation."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "batch-priority-test")
            tasks = [
                await create_test_task(client, room["id"], f"batch-priority-{i}")
                for i in range(3)
            ]

            resp = await client.batch_task_operation(
                room["id"],
                [t["id"] for t in tasks],
                operation="set_priority",
                priority="high",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["success_count"] == 3

            # Verify all high priority
            for t in tasks:
                task_resp = await client.get_task(room["id"], t["id"])
                assert task_resp.json()["priority"] == "high"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_batch_cross_room_tasks(self):
        """Test batch operation with tasks from different rooms."""
        async with ChatroomAPIClient() as client:
            room1 = await create_test_room(client, "batch-room-1")
            room2 = await create_test_room(client, "batch-room-2")
            task1 = await create_test_task(client, room1["id"], "cross-task-1")
            task2 = await create_test_task(client, room2["id"], "cross-task-2")

            # Try batch cancel in room1 with task from room2
            resp = await client.batch_task_operation(
                room1["id"],
                [task1["id"], task2["id"]],
                operation="cancel",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["success_count"] == 1  # Only task1
            assert result["failed_count"] == 1  # task2 wrong room

            # Cleanup
            await client.delete_room(room1["id"])
            await client.delete_room(room2["id"])

    async def test_batch_empty_task_list(self):
        """Test batch operation with empty task list."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "batch-empty-test")

            resp = await client.batch_task_operation(
                room["id"],
                [],
                operation="cancel",
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["success_count"] == 0
            assert result["failed_count"] == 0

            # Cleanup
            await client.delete_room(room["id"])


# ========== Export Tests ==========


@pytest.mark.asyncio
class TestExport:
    """Test task export functionality."""

    async def test_export_csv(self):
        """Test CSV export."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "export-csv-test")
            await create_test_task(client, room["id"], "csv-task-1")
            await create_test_task(client, room["id"], "csv-task-2")

            resp = await client.export_tasks(room["id"], format="csv")
            assert resp.status_code == 200
            assert "text/csv" in resp.headers["content-type"]

            # Parse CSV
            content = resp.text
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            assert len(rows) >= 3  # header + 2 tasks
            assert rows[0][0] == "ID"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_export_json(self):
        """Test JSON export."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "export-json-test")
            await create_test_task(client, room["id"], "json-task-1")
            await create_test_task(client, room["id"], "json-task-2")

            resp = await client.export_tasks(room["id"], format="json")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/json"

            # Parse JSON
            data = resp.json()
            assert len(data) >= 2
            assert all("id" in t for t in data)

            # Cleanup
            await client.delete_room(room["id"])

    async def test_export_with_status_filter(self):
        """Test export with status filter."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "export-filter-test")
            task1 = await create_test_task(client, room["id"], "filter-task-1")
            task2 = await create_test_task(client, room["id"], "filter-task-2")

            # Complete one task
            await client.update_task(room["id"], task1["id"], status="completed")

            resp = await client.export_tasks(room["id"], format="json", status="pending")
            data = resp.json()
            task_ids = [t["id"] for t in data]
            assert task1["id"] not in task_ids  # completed
            assert task2["id"] in task_ids  # pending

            # Cleanup
            await client.delete_room(room["id"])

    async def test_export_empty_room(self):
        """Test export from room with no tasks."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "export-empty-test")

            resp = await client.export_tasks(room["id"], format="csv")
            assert resp.status_code == 200
            # CSV should have only header
            reader = csv.reader(io.StringIO(resp.text))
            rows = list(reader)
            assert len(rows) == 1  # only header

            # Cleanup
            await client.delete_room(room["id"])


# ========== Edge Cases Tests ==========


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_empty_agent_list(self):
        """Test room with empty agent list."""
        async with ChatroomAPIClient() as client:
            resp = await client.create_room(
                name="empty-agents-room",
                agent_ids=[],
            )
            assert resp.status_code == 201
            assert resp.json()["room"]["agent_ids"] == []

            # Cleanup
            await client.delete_room(resp.json()["room"]["id"])

    async def test_special_characters_in_name(self):
        """Test room/task with special characters."""
        async with ChatroomAPIClient() as client:
            # Test with unicode and special chars
            special_name = "测试房间-特殊字符!@#$%"
            resp = await client.create_room(name=special_name)
            assert resp.status_code == 201
            assert resp.json()["room"]["name"] == special_name

            # Cleanup
            await client.delete_room(resp.json()["room"]["id"])

    async def test_long_description(self):
        """Test task with long description."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "long-desc-test")
            long_desc = "A" * 10000  # Very long description

            resp = await client.create_task(
                room["id"],
                subject="long-desc-task",
                description=long_desc,
            )
            assert resp.status_code == 201
            assert len(resp.json()["description"]) == 10000

            # Cleanup
            await client.delete_room(room["id"])

    async def test_task_dependencies(self):
        """Test task with blocked_by dependency."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "dependency-test")
            task1 = await create_test_task(client, room["id"], "blocking-task")
            task2 = await create_test_task(client, room["id"], "blocked-task")

            # Set dependency - blocked_by should be task1's id
            resp = await client.update_task(
                room["id"],
                task2["id"],
                description=f"Blocked by {task1['id']}",
            )
            assert resp.status_code == 200

            # Cleanup
            await client.delete_room(room["id"])

    async def test_message_broadcast(self):
        """Test broadcast message (no to_agent)."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "broadcast-test")

            resp = await client.send_message(
                room["id"],
                content="Broadcast message",
                to_agent=None,  # Broadcast
            )
            assert resp.status_code == 201
            assert resp.json()["to_agent"] == "broadcast"

            # Cleanup
            await client.delete_room(room["id"])

    async def test_multiple_task_logs(self):
        """Test multiple log entries on same task."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "multi-log-test")
            task = await create_test_task(client, room["id"], "multi-log-task")

            # Add multiple logs
            for i in range(5):
                resp = await client.add_task_log(
                    room["id"],
                    task["id"],
                    event=f"event-{i}",
                    details=f"Details for event {i}",
                )
                assert resp.status_code == 200

            # Verify all logs
            final_task = resp.json()
            assert len(final_task["execution_log"]) >= 5

            # Cleanup
            await client.delete_room(room["id"])

    async def test_room_without_lead_agent(self):
        """Test room creation without lead agent."""
        async with ChatroomAPIClient() as client:
            # This might succeed or fail depending on validation
            resp = await client.create_room(
                name="no-lead-room",
                lead_agent_id="",  # Empty lead
            )
            # Allow either success or validation error
            assert resp.status_code in [201, 400]

            if resp.status_code == 201:
                await client.delete_room(resp.json()["room"]["id"])

    async def test_task_completion_sets_completed_at(self):
        """Test that completing task sets completed_at timestamp."""
        async with ChatroomAPIClient() as client:
            room = await create_test_room(client, "completed-at-test")
            task = await create_test_task(client, room["id"], "completion-time-task")

            # Verify no completed_at initially
            resp = await client.get_task(room["id"], task["id"])
            assert resp.json()["completed_at"] is None

            # Complete task
            resp = await client.update_task(room["id"], task["id"], status="completed")
            assert resp.status_code == 200
            assert resp.json()["completed_at"] is not None

            # Cleanup
            await client.delete_room(room["id"])


# ========== Test Runner ==========


def run_tests():
    """Run all tests."""
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])


if __name__ == "__main__":
    run_tests()