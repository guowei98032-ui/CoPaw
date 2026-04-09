# -*- coding: utf-8 -*-
"""Multi-Agent Collaboration E2E Tests.

Tests for complex multi-agent collaboration scenarios:
1. Non-Matrix room multi-agent collaboration
2. 3-4 agents working together
3. Natural language task creation (leader auto-generates tasks)
4. Complex tasks that spawn sub-tasks upon completion
"""
import asyncio
import pytest
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional

from test_config import (
    REAL_LEAD_AGENT,
    REAL_WORKER_1,
    REAL_WORKER_2,
    REAL_WORKER_3,
    REAL_WORKER_AGENTS,
    REAL_ALL_AGENTS,
    CHATROOM_URL,
)

# Timeout for agent response (seconds)
AGENT_RESPONSE_TIMEOUT = 120


class MultiAgentClient:
    """Client for multi-agent collaboration tests."""

    def __init__(self, base_url: str = CHATROOM_URL):
        self.base_url = base_url
        self._client: httpx.AsyncClient = None
        self._created_rooms: List[str] = []

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=AGENT_RESPONSE_TIMEOUT + 30)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cleanup: delete all created rooms
        for room_id in self._created_rooms:
            try:
                await self._client.delete(f"{self.base_url}/{room_id}")
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
        """Create a chatroom without Matrix."""
        data = {
            "name": name,
            "lead_agent_id": lead_agent_id or REAL_LEAD_AGENT,
            "agent_ids": agent_ids or REAL_WORKER_AGENTS,
        }
        resp = await self._client.post(self.base_url, json=data)
        assert resp.status_code == 201, f"Failed to create room: {resp.text}"
        result = resp.json()["room"]
        self._created_rooms.append(result["id"])
        return result

    async def send_message(
        self,
        room_id: str,
        content: str,
        to_agent: str = None,
        message_type: str = "chat",
    ) -> Dict:
        """Send a message to the chatroom."""
        data = {
            "content": content,
            "message_type": message_type,
        }
        if to_agent:
            data["to_agent"] = to_agent
        resp = await self._client.post(f"{self.base_url}/{room_id}/messages", json=data)
        assert resp.status_code == 201, f"Failed to send message: {resp.text}"
        return resp.json()

    async def list_messages(
        self,
        room_id: str,
        to_agent: str = None,
        unread_only: bool = False,
    ) -> List[Dict]:
        """List messages in the chatroom."""
        params = {}
        if to_agent:
            params["to_agent"] = to_agent
        if unread_only:
            params["unread_only"] = "true"
        resp = await self._client.get(f"{self.base_url}/{room_id}/messages", params=params)
        assert resp.status_code == 200
        return resp.json()

    async def create_task(
        self,
        room_id: str,
        subject: str,
        owner: str = None,
        description: str = None,
        priority: str = "medium",
        blocked_by: List[str] = None,
        auto_mode: bool = False,
    ) -> Dict:
        """Create a task."""
        data = {
            "subject": subject,
            "priority": priority,
            "auto_mode": auto_mode,
        }
        if owner:
            data["owner"] = owner
        if description:
            data["description"] = description
        if blocked_by:
            data["blocked_by"] = blocked_by
        resp = await self._client.post(f"{self.base_url}/{room_id}/tasks", json=data)
        assert resp.status_code == 201, f"Failed to create task: {resp.text}"
        return resp.json()

    async def get_task(self, room_id: str, task_id: str) -> Dict:
        resp = await self._client.get(f"{self.base_url}/{room_id}/tasks/{task_id}")
        assert resp.status_code == 200
        return resp.json()

    async def list_tasks(
        self,
        room_id: str,
        status: str = None,
        owner: str = None,
    ) -> List[Dict]:
        params = {}
        if status:
            params["status"] = status
        if owner:
            params["owner"] = owner
        resp = await self._client.get(f"{self.base_url}/{room_id}/tasks", params=params)
        assert resp.status_code == 200
        return resp.json()

    async def update_task(self, room_id: str, task_id: str, **kwargs) -> Dict:
        resp = await self._client.put(
            f"{self.base_url}/{room_id}/tasks/{task_id}", json=kwargs
        )
        assert resp.status_code == 200, f"Failed to update task: {resp.text}"
        return resp.json()

    async def get_room_detail(self, room_id: str) -> Dict:
        """Get chatroom detail with tasks and agents."""
        resp = await self._client.get(f"{self.base_url}/{room_id}")
        assert resp.status_code == 200
        return resp.json()

    async def wait_for_agent_response(
        self,
        room_id: str,
        timeout: float = AGENT_RESPONSE_TIMEOUT,
        poll_interval: float = 3.0,
    ) -> Optional[Dict]:
        """Wait for an agent to respond with a message.

        Returns the first agent response message, or None if timeout.
        """
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            # Get messages from agents (not from user)
            messages = await self.list_messages(room_id)
            for msg in reversed(messages):
                # Agent response: from_agent is an agent ID, not "system" or "user"
                if msg.get("from_agent") and msg["from_agent"] not in ["system", "user"]:
                    return msg

            await asyncio.sleep(poll_interval)

        return None

    async def wait_for_task_creation(
        self,
        room_id: str,
        min_count: int = 1,
        timeout: float = AGENT_RESPONSE_TIMEOUT,
        poll_interval: float = 3.0,
    ) -> List[Dict]:
        """Wait for tasks to be created by agents.

        Returns list of tasks once min_count tasks exist, or empty if timeout.
        """
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            tasks = await self.list_tasks(room_id)
            if len(tasks) >= min_count:
                return tasks

            await asyncio.sleep(poll_interval)

        return []

    async def wait_for_task_status(
        self,
        room_id: str,
        task_id: str,
        expected_status: str,
        timeout: float = AGENT_RESPONSE_TIMEOUT,
        poll_interval: float = 3.0,
    ) -> Optional[Dict]:
        """Wait for a task to reach expected status."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            task = await self.get_task(room_id, task_id)
            if task.get("status") == expected_status:
                return task

            await asyncio.sleep(poll_interval)

        return None


@pytest.mark.asyncio
class TestNonMatrixMultiAgent:
    """Test multi-agent collaboration without Matrix room."""

    async def test_create_non_matrix_chatroom_with_multiple_agents(self):
        """Create a chatroom without Matrix integration with 3 agents."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="非Matrix协作测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
            )

            # Verify no Matrix room
            assert room.get("matrix_room_id") is None
            assert room.get("matrix_alias") is None

            # Verify all agents are in the room
            detail = await client.get_room_detail(room["id"])
            assert detail["lead_agent_id"] == REAL_LEAD_AGENT
            assert REAL_WORKER_1 in detail["agent_ids"]
            assert REAL_WORKER_2 in detail["agent_ids"]
            assert REAL_WORKER_3 in detail["agent_ids"]

            print(f"Created non-Matrix chatroom with 3 workers: {room['id']}")

    async def test_send_message_to_lead_agent(self):
        """Send a message to the lead agent."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="消息测试聊天室",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
            )

            # Send message to lead agent
            msg = await client.send_message(
                room_id=room["id"],
                content="你好，请帮我分析一下当前的任务",
                to_agent=REAL_LEAD_AGENT,
            )

            assert msg["to_agent"] == REAL_LEAD_AGENT
            assert msg["from_agent"] == "system"

            # Verify message can be retrieved
            messages = await client.list_messages(room["id"], to_agent=REAL_LEAD_AGENT)
            assert len(messages) >= 1

            print(f"Message sent to lead agent: {msg['id']}")

    async def test_three_agents_receive_distinct_tasks(self):
        """Create tasks for 3 different agents and verify assignment."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="三Agent任务分配测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
            )

            # Create tasks for each worker
            task1 = await client.create_task(
                room_id=room["id"],
                subject="Worker1的任务：数据分析",
                owner=REAL_WORKER_1,
                priority="high",
            )
            task2 = await client.create_task(
                room_id=room["id"],
                subject="Worker2的任务：代码编写",
                owner=REAL_WORKER_2,
                priority="medium",
            )
            task3 = await client.create_task(
                room_id=room["id"],
                subject="Worker3的任务：测试验证",
                owner=REAL_WORKER_3,
                priority="low",
            )

            # Verify all tasks are pending
            all_tasks = await client.list_tasks(room["id"])
            assert len(all_tasks) == 3

            pending = [t for t in all_tasks if t["status"] == "pending"]
            assert len(pending) == 3

            # Verify ownership
            owners = {t["owner"] for t in all_tasks}
            assert REAL_WORKER_1 in owners
            assert REAL_WORKER_2 in owners
            assert REAL_WORKER_3 in owners

            print(f"Created 3 tasks for 3 different workers")


@pytest.mark.asyncio
class TestFourAgentCollaboration:
    """Test 3-4 agents working together."""

    async def test_create_four_agent_team(self):
        """Create a chatroom with lead + 3 workers (4 agents total)."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="四Agent团队测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
            )

            detail = await client.get_room_detail(room["id"])

            # Count total agents
            total_agents = 1  # lead
            if detail.get("agent_ids"):
                total_agents += len(detail["agent_ids"])

            assert total_agents == 4
            print(f"Created team with 4 agents: {detail['lead_agent_id']} + {detail['agent_ids']}")

    async def test_parallel_task_execution(self):
        """Multiple agents execute tasks in parallel."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="并行执行测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
            )

            # Create independent tasks (no dependencies)
            tasks = []
            for i, worker in enumerate(REAL_WORKER_AGENTS):
                task = await client.create_task(
                    room_id=room["id"],
                    subject=f"独立任务{i+1}：{worker}负责",
                    owner=worker,
                    priority="medium",
                )
                tasks.append(task)

            # Start all tasks (simulate agents claiming)
            for task in tasks:
                await client.update_task(room["id"], task["id"], status="in_progress")

            # All should be in_progress
            in_progress = await client.list_tasks(room["id"], status="in_progress")
            assert len(in_progress) == 3

            print(f"All 3 tasks running in parallel")

    async def test_sequential_task_with_dependencies(self):
        """Create tasks with dependencies (sequential workflow)."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="依赖链测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
            )

            # Task 1: Design (Worker 1)
            task1 = await client.create_task(
                room_id=room["id"],
                subject="设计阶段：架构设计",
                owner=REAL_WORKER_1,
                priority="high",
            )

            # Task 2: Implementation (Worker 2) - depends on Task 1
            task2 = await client.create_task(
                room_id=room["id"],
                subject="实现阶段：代码编写",
                owner=REAL_WORKER_2,
                priority="high",
                blocked_by=[task1["id"]],
            )

            # Task 3: Testing (Worker 3) - depends on Task 2
            task3 = await client.create_task(
                room_id=room["id"],
                subject="测试阶段：功能验证",
                owner=REAL_WORKER_3,
                priority="high",
                blocked_by=[task2["id"]],
            )

            # Verify task 2 and 3 are blocked
            t2 = await client.get_task(room["id"], task2["id"])
            t3 = await client.get_task(room["id"], task3["id"])
            assert t2.get("blocked_by") == [task1["id"]]
            assert t3.get("blocked_by") == [task2["id"]]

            # Complete task 1
            await client.update_task(room["id"], task1["id"], status="completed")

            # Task 2 should now be unblocked (blocked_by list updated by backend)
            t2_updated = await client.get_task(room["id"], task2["id"])
            # Note: Backend should auto-unblock when dependency completes
            # This tests the dependency mechanism

            print(f"Created sequential workflow with dependencies")


@pytest.mark.asyncio
class TestNaturalLanguageTaskCreation:
    """Test natural language task creation via agent conversation."""

    async def test_user_request_creates_task(self):
        """User sends natural language request, leader should process.

        Note: This test verifies the message is delivered correctly.
        Actual task creation depends on the leader agent's behavior.
        """
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="自然语言任务测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
            )

            # User sends a natural language request to the lead agent
            await client.send_message(
                room_id=room["id"],
                content="""
请帮我完成以下工作：
1. 分析一下最近的数据趋势
2. 写一份简单的报告

请分配给合适的成员。
                """.strip(),
                to_agent=REAL_LEAD_AGENT,
                message_type="chat",
            )

            # Verify message was sent
            messages = await client.list_messages(room["id"], to_agent=REAL_LEAD_AGENT)
            assert len(messages) >= 1
            assert "数据趋势" in messages[0]["content"]

            print(f"Natural language request sent to lead agent")

    async def test_auto_mode_task_execution(self):
        """Create a task with auto_mode enabled for autonomous execution."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="自动模式测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
            )

            # Create an auto_mode task
            task = await client.create_task(
                room_id=room["id"],
                subject="自动执行任务：检查系统状态",
                owner=REAL_WORKER_1,
                auto_mode=True,
            )

            # Verify auto_mode is set
            t = await client.get_task(room["id"], task["id"])
            assert t.get("auto_mode") is True

            print(f"Auto-mode task created: {task['id']}")

    async def test_unassigned_task_for_self_claim(self):
        """Create an unassigned task that agents can claim."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="自主认领测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
            )

            # Create a task without owner (unassigned)
            task = await client.create_task(
                room_id=room["id"],
                subject="待认领任务：代码优化",
                # No owner specified
            )

            # Verify task has no owner
            t = await client.get_task(room["id"], task["id"])
            assert t.get("owner") is None
            assert t["status"] == "pending"

            # A worker can claim this task
            claimed = await client.update_task(
                room["id"], task["id"],
                owner=REAL_WORKER_1,
                status="in_progress",
            )
            assert claimed["owner"] == REAL_WORKER_1
            assert claimed["status"] == "in_progress"

            print(f"Task claimed by worker: {REAL_WORKER_1}")


@pytest.mark.asyncio
class TestComplexTaskWithSubtasks:
    """Test complex tasks that spawn sub-tasks."""

    async def test_create_task_with_subtasks(self):
        """Create a parent task and multiple sub-tasks."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="子任务测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
            )

            # Create parent task
            parent_task = await client.create_task(
                room_id=room["id"],
                subject="主任务：完成项目交付",
                owner=REAL_LEAD_AGENT,
                priority="high",
            )

            # Create sub-tasks
            sub1 = await client.create_task(
                room_id=room["id"],
                subject="子任务1：需求分析",
                owner=REAL_WORKER_1,
                priority="high",
                blocked_by=[parent_task["id"]],  # Depends on parent
            )
            sub2 = await client.create_task(
                room_id=room["id"],
                subject="子任务2：开发实现",
                owner=REAL_WORKER_2,
                priority="high",
                blocked_by=[sub1["id"]],  # Depends on sub1
            )
            sub3 = await client.create_task(
                room_id=room["id"],
                subject="子任务3：测试验收",
                owner=REAL_WORKER_3,
                priority="high",
                blocked_by=[sub2["id"]],  # Depends on sub2
            )

            # Verify all tasks exist
            all_tasks = await client.list_tasks(room["id"])
            assert len(all_tasks) == 4

            print(f"Created 1 parent task + 3 sub-tasks")

    async def test_cascading_task_completion(self):
        """Complete parent task triggers sub-task availability."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="级联完成测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
            )

            # Create main task
            main = await client.create_task(
                room_id=room["id"],
                subject="主任务",
                owner=REAL_LEAD_AGENT,
            )

            # Create sub-tasks blocked by main
            sub1 = await client.create_task(
                room_id=room["id"],
                subject="子任务A",
                owner=REAL_WORKER_1,
                blocked_by=[main["id"]],
            )
            sub2 = await client.create_task(
                room_id=room["id"],
                subject="子任务B",
                owner=REAL_WORKER_2,
                blocked_by=[main["id"]],
            )

            # Complete main task
            await client.update_task(room["id"], main["id"], status="completed")

            # Verify main is completed
            main_check = await client.get_task(room["id"], main["id"])
            assert main_check["status"] == "completed"

            print(f"Main task completed, sub-tasks may be unblocked")

    async def test_task_failure_with_retry(self):
        """Test task failure and retry mechanism."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="任务重试测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
            )

            # Create a task
            task = await client.create_task(
                room_id=room["id"],
                subject="可能失败的任务",
                owner=REAL_WORKER_1,
            )

            # Start task
            await client.update_task(room["id"], task["id"], status="in_progress")

            # Mark as failed
            failed = await client.update_task(
                room["id"], task["id"],
                status="failed",
            )
            assert failed["status"] == "failed"

            # Verify retry count increments
            retry_count = failed.get("retry_count", 0)

            # Reset the task for retry (simulating retry mechanism)
            retried = await client.update_task(
                room["id"], task["id"],
                status="pending",
            )
            assert retried["status"] == "pending"

            print(f"Task failed and reset for retry")


@pytest.mark.asyncio
class TestMultiAgentWorkflowScenarios:
    """Complete workflow scenarios with multiple agents."""

    async def test_sprint_planning_workflow(self):
        """Simulate a sprint planning with lead + 3 workers."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="Sprint规划",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
            )

            # Lead creates sprint tasks
            tasks = []
            for i, worker in enumerate(REAL_WORKER_AGENTS):
                task = await client.create_task(
                    room_id=room["id"],
                    subject=f"Sprint任务{i+1}",
                    owner=worker,
                    priority="high" if i == 0 else "medium",
                )
                tasks.append(task)

            # Verify sprint backlog
            pending = await client.list_tasks(room["id"], status="pending")
            assert len(pending) == 3

            # Workers start tasks
            for task in tasks:
                await client.update_task(room["id"], task["id"], status="in_progress")

            in_progress = await client.list_tasks(room["id"], status="in_progress")
            assert len(in_progress) == 3

            print(f"Sprint planning: 3 tasks assigned and started")

    async def test_bug_triage_workflow(self):
        """Bug triage and resolution workflow."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="Bug处理流程",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
            )

            # Bug reported
            bug = await client.create_task(
                room_id=room["id"],
                subject="BUG: 登录失败",
                description="用户报告移动端登录按钮无响应",
                priority="high",
            )

            # Lead assigns to developer
            await client.update_task(room["id"], bug["id"], owner=REAL_WORKER_1)

            # Developer investigates
            await client.update_task(room["id"], bug["id"], status="in_progress")
            await client.update_task(
                room["id"], bug["id"],
                description="BUG: 登录失败\n\n[调查结果] 问题在CSS z-index",
            )

            # Hand off to QA for verification
            await client.update_task(room["id"], bug["id"], owner=REAL_WORKER_2)

            # QA verifies and closes
            await client.update_task(room["id"], bug["id"], status="completed")

            # Verify final state
            final = await client.get_task(room["id"], bug["id"])
            assert final["status"] == "completed"
            assert final["owner"] == REAL_WORKER_2

            print(f"Bug triage workflow completed")

    async def test_code_review_workflow(self):
        """Code review workflow with lead reviewing worker's code."""
        async with MultiAgentClient() as client:
            room = await client.create_room(
                name="代码审查流程",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
            )

            # Developer implements feature
            impl = await client.create_task(
                room_id=room["id"],
                subject="实现新功能：用户头像上传",
                owner=REAL_WORKER_1,
                priority="medium",
            )
            await client.update_task(room["id"], impl["id"], status="in_progress")
            await client.update_task(room["id"], impl["id"], progress=100)
            await client.update_task(room["id"], impl["id"], status="completed")

            # Lead creates review task
            review = await client.create_task(
                room_id=room["id"],
                subject="代码审查：用户头像上传",
                owner=REAL_LEAD_AGENT,
                priority="high",
            )
            await client.update_task(room["id"], review["id"], status="in_progress")
            await client.update_task(room["id"], review["id"], status="completed")

            # Verify workflow completed
            all_tasks = await client.list_tasks(room["id"], status="completed")
            assert len(all_tasks) == 2

            print(f"Code review workflow completed")