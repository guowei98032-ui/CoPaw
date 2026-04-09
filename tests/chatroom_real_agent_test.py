# -*- coding: utf-8 -*-
"""Real Agent Integration Tests.

Tests using REAL agents that exist in the system.
Set REAL_AGENTS in environment or use these defaults:
- default
- Ls9Gr3
- ztNTTm
- CoPaw_QA_Agent_0.1beta1
"""
import asyncio
import json
import pytest
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional

BASE_URL = "http://127.0.0.1:8088/api"
CHATROOM_URL = f"{BASE_URL}/chatroom"

# REAL agents in the system - MUST match actual agent IDs
REAL_LEAD_AGENT = "Ls9Gr3"
REAL_WORKER_AGENTS = ["ztNTTm", "default"]
REAL_ALL_AGENTS = [REAL_LEAD_AGENT] + REAL_WORKER_AGENTS


class RealAgentClient:
    """Client that uses real agents for testing."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.chatroom_url = f"{base_url}/chatroom"
        self._client: httpx.AsyncClient = None
        self._created_rooms: List[str] = []

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=60.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for room_id in self._created_rooms:
            try:
                await self._client.delete(f"{self.chatroom_url}/{room_id}")
            except Exception:
                pass
        if self._client:
            await self._client.aclose()

    async def create_room(
        self,
        name: str,
        lead_agent_id: str = None,
        agent_ids: List[str] = None,
    ) -> Dict:
        """Create a chatroom with REAL agents."""
        data = {
            "name": name,
            "lead_agent_id": lead_agent_id or REAL_LEAD_AGENT,
            "agent_ids": agent_ids or REAL_WORKER_AGENTS,
        }
        resp = await self._client.post(self.chatroom_url, json=data)
        assert resp.status_code == 201, f"Failed to create room: {resp.text}"
        result = resp.json()["room"]
        self._created_rooms.append(result["id"])
        return result

    async def create_task(self, room_id: str, subject: str, owner: str = None, **kwargs) -> Dict:
        """Create a task."""
        data = {"subject": subject, **kwargs}
        if owner:
            data["owner"] = owner
        resp = await self._client.post(f"{self.chatroom_url}/{room_id}/tasks", json=data)
        assert resp.status_code == 201, f"Failed to create task: {resp.text}"
        return resp.json()

    async def get_task(self, room_id: str, task_id: str) -> Dict:
        resp = await self._client.get(f"{self.chatroom_url}/{room_id}/tasks/{task_id}")
        assert resp.status_code == 200, f"Failed to get task: {resp.text}"
        return resp.json()

    async def list_tasks(self, room_id: str, status: str = None) -> List[Dict]:
        params = {}
        if status:
            params["status"] = status
        resp = await self._client.get(f"{self.chatroom_url}/{room_id}/tasks", params=params)
        assert resp.status_code == 200
        return resp.json()

    async def update_task(self, room_id: str, task_id: str, **kwargs) -> Dict:
        resp = await self._client.put(
            f"{self.chatroom_url}/{room_id}/tasks/{task_id}", json=kwargs
        )
        assert resp.status_code == 200, f"Failed to update task: {resp.text}"
        return resp.json()

    async def send_message(self, room_id: str, content: str, to_agent: str = None) -> Dict:
        data = {"content": content, "message_type": "chat"}
        if to_agent:
            data["to_agent"] = to_agent
        resp = await self._client.post(f"{self.chatroom_url}/{room_id}/messages", json=data)
        assert resp.status_code == 201, f"Failed to send message: {resp.text}"
        return resp.json()

    async def list_messages(self, room_id: str, to_agent: str = None) -> List[Dict]:
        params = {}
        if to_agent:
            params["to_agent"] = to_agent
        resp = await self._client.get(f"{self.chatroom_url}/{room_id}/messages", params=params)
        assert resp.status_code == 200
        return resp.json()


@pytest.mark.asyncio
class TestRealAgentValidation:
    """Test that API validates agent existence."""

    async def test_create_room_with_nonexistent_agent_fails(self):
        """Creating a room with non-existent agent should fail."""
        async with RealAgentClient() as client:
            resp = await client._client.post(
                client.chatroom_url,
                json={
                    "name": "Invalid Room",
                    "lead_agent_id": "nonexistent-agent",
                    "agent_ids": [],
                }
            )
            assert resp.status_code == 400
            assert "not found" in resp.text.lower()

    async def test_create_task_with_nonexistent_owner_fails(self):
        """Creating a task with non-existent owner should fail."""
        async with RealAgentClient() as client:
            room = await client.create_room("Test Room")

            resp = await client._client.post(
                f"{client.chatroom_url}/{room['id']}/tasks",
                json={"subject": "Test", "owner": "nonexistent-worker"}
            )
            assert resp.status_code == 400
            assert "not found" in resp.text.lower()


@pytest.mark.asyncio
class TestRealAgentCollaboration:
    """Test multi-agent collaboration with REAL agents."""

    async def test_create_room_with_real_agents(self):
        """Create a chatroom with real agents that exist."""
        async with RealAgentClient() as client:
            room = await client.create_room(
                name="Real Agent Team",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=REAL_WORKER_AGENTS,
            )

            assert room["lead_agent_id"] == REAL_LEAD_AGENT
            assert all(a in room["agent_ids"] for a in REAL_WORKER_AGENTS)
            print(f"Created room with real agents: {room['id']}")

    async def test_assign_task_to_real_agent(self):
        """Assign task to a real agent."""
        async with RealAgentClient() as client:
            room = await client.create_room("Task Assignment Test")

            # Assign to real worker
            task = await client.create_task(
                room_id=room["id"],
                subject="Real task for real agent",
                owner=REAL_WORKER_AGENTS[0],
            )

            t = await client.get_task(room["id"], task["id"])
            assert t["owner"] == REAL_WORKER_AGENTS[0]
            assert t["status"] == "pending"
            print(f"Task assigned to {REAL_WORKER_AGENTS[0]}")

    async def test_multiple_real_agents_claim_tasks(self):
        """Multiple real agents can claim different tasks."""
        async with RealAgentClient() as client:
            room = await client.create_room(
                name="Multi-Agent Task Test",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=REAL_WORKER_AGENTS,
            )

            # Create tasks for each worker
            tasks = []
            for i, agent in enumerate(REAL_WORKER_AGENTS):
                task = await client.create_task(
                    room_id=room["id"],
                    subject=f"Task {i+1} for {agent}",
                    owner=agent,
                )
                tasks.append(task)

            # Verify assignments
            all_tasks = await client.list_tasks(room["id"])
            assert len(all_tasks) == len(REAL_WORKER_AGENTS)

            for task in all_tasks:
                assert task["owner"] in REAL_WORKER_AGENTS
                print(f"Task '{task['subject']}' assigned to {task['owner']}")

    async def test_message_to_real_agent(self):
        """Send message to a real agent."""
        async with RealAgentClient() as client:
            room = await client.create_room("Message Test")

            # Send message to real worker
            msg = await client.send_message(
                room_id=room["id"],
                content="Hello from lead!",
                to_agent=REAL_WORKER_AGENTS[0],
            )

            assert msg["to_agent"] == REAL_WORKER_AGENTS[0]

            # Verify message can be retrieved
            messages = await client.list_messages(room["id"], to_agent=REAL_WORKER_AGENTS[0])
            assert len(messages) >= 1
            print(f"Message sent to {REAL_WORKER_AGENTS[0]}")

    async def test_task_handoff_between_real_agents(self):
        """Hand off task between real agents."""
        async with RealAgentClient() as client:
            room = await client.create_room("Task Handoff Test")

            # Create task for first worker
            task = await client.create_task(
                room_id=room["id"],
                subject="Handoff task",
                owner=REAL_WORKER_AGENTS[0],
            )

            # Start task
            await client.update_task(room["id"], task["id"], status="in_progress")
            await client.update_task(room["id"], task["id"], progress=50)

            # Hand off to second worker
            t = await client.update_task(
                room["id"], task["id"],
                owner=REAL_WORKER_AGENTS[1],
            )

            assert t["owner"] == REAL_WORKER_AGENTS[1]
            assert t["progress"] == 50  # Progress preserved
            print(f"Task handed off from {REAL_WORKER_AGENTS[0]} to {REAL_WORKER_AGENTS[1]}")


@pytest.mark.asyncio
class TestRealAgentWorkflow:
    """Complete workflow tests with real agents."""

    async def test_sprint_planning_with_real_agents(self):
        """Simulate sprint planning with real agents."""
        async with RealAgentClient() as client:
            room = await client.create_room(
                name="Sprint Planning",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=REAL_WORKER_AGENTS,
            )

            # Lead creates tasks
            tasks = []
            for i, agent in enumerate(REAL_WORKER_AGENTS):
                task = await client.create_task(
                    room_id=room["id"],
                    subject=f"Sprint task {i+1}",
                    owner=agent,
                    priority="high" if i == 0 else "medium",
                )
                tasks.append(task)

            # Verify sprint backlog
            pending = await client.list_tasks(room["id"], status="pending")
            assert len(pending) == len(REAL_WORKER_AGENTS)

            # Workers claim tasks (simulate by updating status)
            for task in tasks[:len(REAL_WORKER_AGENTS)]:
                await client.update_task(room["id"], task["id"], status="in_progress")

            in_progress = await client.list_tasks(room["id"], status="in_progress")
            assert len(in_progress) == len(REAL_WORKER_AGENTS)
            print(f"Sprint planning complete: {len(in_progress)} tasks in progress")

    async def test_task_completion_by_real_agent(self):
        """Real agent completes a task."""
        async with RealAgentClient() as client:
            room = await client.create_room("Completion Test")

            task = await client.create_task(
                room_id=room["id"],
                subject="Task to complete",
                owner=REAL_WORKER_AGENTS[0],
            )

            # Simulate agent work
            await client.update_task(room["id"], task["id"], status="in_progress")
            await client.update_task(room["id"], task["id"], progress=50)
            await client.update_task(room["id"], task["id"], progress=100)
            await client.update_task(room["id"], task["id"], status="completed")

            t = await client.get_task(room["id"], task["id"])
            assert t["status"] == "completed"
            assert t["progress"] == 100
            assert t["completed_at"] is not None
            print(f"Task completed by {REAL_WORKER_AGENTS[0]}")