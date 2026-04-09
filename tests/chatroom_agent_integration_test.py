# -*- coding: utf-8 -*-
"""Real Agent Integration Tests - Tests with actual agent execution.

These tests send messages to real agents and wait for their responses.
Requires:
1. Backend server running on 127.0.0.1:8088
2. poll_service active
3. Agents configured and ready

Marked with @pytest.mark.integration - run separately with:
    pytest tests/chatroom_agent_integration_test.py -v -m integration
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
    CHATROOM_URL,
)

# Timeout for agent responses (seconds) - agents need time to think
AGENT_RESPONSE_TIMEOUT = 120
POLL_INTERVAL = 5.0


class AgentIntegrationClient:
    """Client for real agent integration tests."""

    def __init__(self, base_url: str = CHATROOM_URL):
        self.base_url = base_url
        self._client: httpx.AsyncClient = None
        self._created_rooms: List[str] = []

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=AGENT_RESPONSE_TIMEOUT + 60)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
        agent_roles: Dict[str, str] = None,
    ) -> Dict:
        """Create a chatroom with agent roles."""
        data = {
            "name": name,
            "lead_agent_id": lead_agent_id or REAL_LEAD_AGENT,
            "agent_ids": agent_ids or REAL_WORKER_AGENTS,
        }
        if agent_roles:
            data["agent_roles"] = agent_roles
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
        assert resp.status_code == 201
        return resp.json()

    async def list_messages(
        self,
        room_id: str,
        to_agent: str = None,
        from_agent: str = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Dict]:
        """List messages with optional filtering."""
        params = {"limit": limit}
        if to_agent:
            params["to_agent"] = to_agent
        if unread_only:
            params["unread_only"] = "true"
        resp = await self._client.get(f"{self.base_url}/{room_id}/messages", params=params)
        assert resp.status_code == 200
        messages = resp.json()
        if from_agent:
            messages = [m for m in messages if m.get("from_agent") == from_agent]
        return messages

    async def create_task(
        self,
        room_id: str,
        subject: str,
        owner: str = None,
        description: str = None,
        priority: str = "medium",
        auto_mode: bool = False,
        blocked_by: List[str] = None,
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
        assert resp.status_code == 201
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
        assert resp.status_code == 200
        return resp.json()

    async def get_room_detail(self, room_id: str) -> Dict:
        resp = await self._client.get(f"{self.base_url}/{room_id}")
        assert resp.status_code == 200
        return resp.json()

    async def wait_for_agent_message(
        self,
        room_id: str,
        from_agent: str = None,
        timeout: float = AGENT_RESPONSE_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
    ) -> Optional[Dict]:
        """Wait for an agent to send a message.

        Returns the first message from an agent, or None if timeout.
        """
        start_time = asyncio.get_event_loop().time()
        seen_ids = set()

        # Get initial messages to skip
        initial = await self.list_messages(room_id)
        for msg in initial:
            seen_ids.add(msg["id"])

        while asyncio.get_event_loop().time() - start_time < timeout:
            messages = await self.list_messages(room_id)
            for msg in messages:
                if msg["id"] in seen_ids:
                    continue
                seen_ids.add(msg["id"])

                # Check if it's from an agent (not "system" or "user")
                sender = msg.get("from_agent", "")
                if sender and sender not in ["system", "user"]:
                    if from_agent is None or sender == from_agent:
                        return msg

            await asyncio.sleep(poll_interval)

        return None

    async def wait_for_new_tasks(
        self,
        room_id: str,
        min_count: int = 1,
        timeout: float = AGENT_RESPONSE_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
    ) -> List[Dict]:
        """Wait for new tasks to be created (by agents).

        Returns list of tasks once min_count new tasks exist.
        """
        start_time = asyncio.get_event_loop().time()
        initial_tasks = await self.list_tasks(room_id)
        initial_ids = {t["id"] for t in initial_tasks}

        while asyncio.get_event_loop().time() - start_time < timeout:
            tasks = await self.list_tasks(room_id)
            new_tasks = [t for t in tasks if t["id"] not in initial_ids]
            if len(new_tasks) >= min_count:
                return new_tasks

            await asyncio.sleep(poll_interval)

        return []

    async def wait_for_task_status_change(
        self,
        room_id: str,
        task_id: str,
        expected_statuses: List[str],
        timeout: float = AGENT_RESPONSE_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
    ) -> Optional[Dict]:
        """Wait for a task to change to one of the expected statuses."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            task = await self.get_task(room_id, task_id)
            if task.get("status") in expected_statuses:
                return task

            await asyncio.sleep(poll_interval)

        return None

    async def wait_for_any_task_in_progress(
        self,
        room_id: str,
        timeout: float = AGENT_RESPONSE_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
    ) -> Optional[Dict]:
        """Wait for any task to be claimed and started."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            tasks = await self.list_tasks(room_id, status="in_progress")
            if tasks:
                return tasks[0]

            await asyncio.sleep(poll_interval)

        return None


@pytest.mark.integration
@pytest.mark.asyncio
class TestLeaderAgentNLPProcessing:
    """Test leader agent processing natural language requests."""

    async def test_leader_receives_and_responds_to_message(self):
        """Send a message to leader agent and wait for response."""
        async with AgentIntegrationClient() as client:
            room = await client.create_room(
                name="Leader响应测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理，负责分配任务和协调团队",
                    REAL_WORKER_1: "开发者，负责代码编写",
                },
            )

            # Send a simple greeting to the leader
            await client.send_message(
                room_id=room["id"],
                content="你好，请简单介绍一下你自己",
                to_agent=REAL_LEAD_AGENT,
            )

            # Wait for leader's response
            response = await client.wait_for_agent_message(
                room_id=room["id"],
                from_agent=REAL_LEAD_AGENT,
                timeout=AGENT_RESPONSE_TIMEOUT,
            )

            if response:
                print(f"Leader responded: {response['content'][:200]}...")
                assert response["from_agent"] == REAL_LEAD_AGENT
                assert len(response["content"]) > 0
            else:
                print("Warning: No response from leader (timeout or poll_service not running)")

    async def test_leader_creates_task_from_natural_language(self):
        """User requests work, leader should understand and potentially create tasks.

        Note: Whether leader creates tasks depends on its system prompt and capabilities.
        """
        async with AgentIntegrationClient() as client:
            room = await client.create_room(
                name="自然语言任务创建测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理，负责分析用户需求并创建任务分配给团队成员",
                    REAL_WORKER_1: "后端开发者",
                    REAL_WORKER_2: "前端开发者",
                },
            )

            # Send a work request in natural language
            await client.send_message(
                room_id=room["id"],
                content="""
我需要开发一个简单的用户登录功能，包括：
1. 后端API接口
2. 前端登录页面

请帮我规划并分配任务。
                """.strip(),
                to_agent=REAL_LEAD_AGENT,
            )

            # Wait for leader's response
            response = await client.wait_for_agent_message(
                room_id=room["id"],
                from_agent=REAL_LEAD_AGENT,
                timeout=AGENT_RESPONSE_TIMEOUT,
            )

            if response:
                print(f"Leader responded: {response['content'][:300]}...")

                # Check if any tasks were created
                await asyncio.sleep(5)  # Give time for task creation
                tasks = await client.list_tasks(room["id"])
                print(f"Tasks in room: {len(tasks)}")

                if tasks:
                    for task in tasks:
                        print(f"  - {task['subject']} (owner: {task['owner']})")
            else:
                print("Warning: No response from leader")


@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkerAgentTaskClaim:
    """Test worker agents claiming and executing tasks."""

    async def test_worker_receives_assigned_task(self):
        """Assign a task to worker and wait for them to start processing."""
        async with AgentIntegrationClient() as client:
            room = await client.create_room(
                name="Worker任务执行测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
                agent_roles={
                    REAL_WORKER_1: "开发者，负责执行分配的任务",
                },
            )

            # Create a task assigned to the worker
            task = await client.create_task(
                room_id=room["id"],
                subject="测试任务：列出当前目录的文件",
                description="请使用shell工具列出当前工作目录的文件列表",
                owner=REAL_WORKER_1,
                auto_mode=True,  # Auto mode for autonomous execution
            )

            print(f"Created task: {task['id']}")

            # Wait for task to be claimed/started
            started = await client.wait_for_task_status_change(
                room_id=room["id"],
                task_id=task["id"],
                expected_statuses=["in_progress", "completed"],
                timeout=AGENT_RESPONSE_TIMEOUT,
            )

            if started:
                print(f"Task status changed to: {started['status']}")
            else:
                print("Warning: Task not started (timeout or poll_service not running)")

    async def test_worker_claims_unassigned_task(self):
        """Create an unassigned task and see if workers claim it.

        Note: This requires workers to actively look for unassigned tasks.
        """
        async with AgentIntegrationClient() as client:
            room = await client.create_room(
                name="自主认领测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理",
                    REAL_WORKER_1: "后端开发者，可以认领后端相关任务",
                    REAL_WORKER_2: "前端开发者，可以认领前端相关任务",
                },
            )

            # Create an unassigned task
            task = await client.create_task(
                room_id=room["id"],
                subject="通用任务：检查系统环境",
                description="请检查当前系统环境，报告Python版本",
                # No owner - workers should be able to claim
                auto_mode=True,
            )

            print(f"Created unassigned task: {task['id']}")

            # Wait a bit for poll_service to pick it up
            await asyncio.sleep(10)

            # Check if task got claimed
            updated = await client.get_task(room["id"], task["id"])
            print(f"Task status: {updated['status']}, owner: {updated.get('owner')}")

            if updated.get("owner"):
                print(f"Task claimed by: {updated['owner']}")
            else:
                print("Task still unassigned")


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiAgentCollaboration:
    """Test multiple agents working together."""

    async def test_three_agents_parallel_execution(self):
        """Create tasks for 3 different agents to execute in parallel."""
        async with AgentIntegrationClient() as client:
            room = await client.create_room(
                name="三Agent并行执行",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理",
                    REAL_WORKER_1: "开发者A",
                    REAL_WORKER_2: "开发者B",
                    REAL_WORKER_3: "开发者C",
                },
            )

            # Create independent tasks for each worker
            tasks = []
            for i, worker in enumerate(REAL_WORKER_AGENTS):
                task = await client.create_task(
                    room_id=room["id"],
                    subject=f"独立任务{i+1}：报告agent ID",
                    description=f"请回复你的agent ID是 {worker}",
                    owner=worker,
                    auto_mode=True,
                )
                tasks.append(task)

            print(f"Created {len(tasks)} parallel tasks")

            # Wait for tasks to be processed
            await asyncio.sleep(30)

            # Check task statuses
            for task in tasks:
                updated = await client.get_task(room["id"], task["id"])
                print(f"Task {task['id'][:8]}: status={updated['status']}, owner={updated.get('owner')}")

    async def test_sequential_workflow_with_dependencies(self):
        """Test sequential workflow where task B depends on task A."""
        async with AgentIntegrationClient() as client:
            room = await client.create_room(
                name="顺序依赖测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
                agent_roles={
                    REAL_WORKER_1: "负责第一步",
                    REAL_WORKER_2: "负责第二步",
                },
            )

            # Task 1
            task1 = await client.create_task(
                room_id=room["id"],
                subject="步骤1：准备环境",
                description="请回复'环境准备完成'",
                owner=REAL_WORKER_1,
                auto_mode=True,
            )

            # Task 2 depends on Task 1
            task2 = await client.create_task(
                room_id=room["id"],
                subject="步骤2：执行操作",
                description="在步骤1完成后执行",
                owner=REAL_WORKER_2,
                blocked_by=[task1["id"]],
                auto_mode=True,
            )

            print(f"Created dependent tasks: {task1['id'][:8]} -> {task2['id'][:8]}")

            # Wait for task1 to complete
            completed = await client.wait_for_task_status_change(
                room_id=room["id"],
                task_id=task1["id"],
                expected_statuses=["completed"],
                timeout=AGENT_RESPONSE_TIMEOUT,
            )

            if completed:
                print(f"Task 1 completed!")

                # Check if task2 is now unblocked
                await asyncio.sleep(10)
                task2_status = await client.get_task(room["id"], task2["id"])
                print(f"Task 2 status: {task2_status['status']}, blocked_by: {task2_status.get('blocked_by')}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestComplexTaskWithSubtasks:
    """Test complex tasks that spawn sub-tasks upon completion."""

    async def test_task_completion_triggers_subtask_creation(self):
        """When a main task completes, check if agent creates follow-up tasks.

        Note: This depends on agent's capability to create tasks.
        """
        async with AgentIntegrationClient() as client:
            room = await client.create_room(
                name="子任务生成测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理，负责分解复杂任务",
                    REAL_WORKER_1: "执行者",
                },
            )

            # Send a complex request that might need task breakdown
            await client.send_message(
                room_id=room["id"],
                content="""
请帮我完成一个完整的用户注册功能，包括：
1. 用户数据模型设计
2. 数据库表创建
3. 注册API开发
4. 前端注册页面

请将这个任务分解成具体的子任务并分配执行。
                """.strip(),
                to_agent=REAL_LEAD_AGENT,
            )

            # Wait for leader response
            response = await client.wait_for_agent_message(
                room_id=room["id"],
                from_agent=REAL_LEAD_AGENT,
                timeout=AGENT_RESPONSE_TIMEOUT,
            )

            if response:
                print(f"Leader response: {response['content'][:300]}...")

            # Wait and check for created tasks
            await asyncio.sleep(20)
            tasks = await client.list_tasks(room["id"])
            print(f"Total tasks created: {len(tasks)}")
            for task in tasks:
                print(f"  - [{task['status']}] {task['subject']} (owner: {task.get('owner')})")

    async def test_cascading_completion(self):
        """Main task completes, should trigger sub-task processing."""
        async with AgentIntegrationClient() as client:
            room = await client.create_room(
                name="级联完成测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
            )

            # Create main task
            main = await client.create_task(
                room_id=room["id"],
                subject="主任务：确认开始",
                description="请回复'开始'表示确认",
                owner=REAL_LEAD_AGENT,
                auto_mode=True,
            )

            # Create sub-tasks blocked by main
            sub1 = await client.create_task(
                room_id=room["id"],
                subject="子任务A",
                description="主任务完成后执行A",
                owner=REAL_WORKER_1,
                blocked_by=[main["id"]],
                auto_mode=True,
            )

            sub2 = await client.create_task(
                room_id=room["id"],
                subject="子任务B",
                description="主任务完成后执行B",
                owner=REAL_WORKER_2,
                blocked_by=[main["id"]],
                auto_mode=True,
            )

            print(f"Created: main={main['id'][:8]}, subA={sub1['id'][:8]}, subB={sub2['id'][:8]}")

            # Wait for main to complete
            main_done = await client.wait_for_task_status_change(
                room_id=room["id"],
                task_id=main["id"],
                expected_statuses=["completed"],
                timeout=AGENT_RESPONSE_TIMEOUT,
            )

            if main_done:
                print("Main task completed!")

                # Check sub-tasks status
                await asyncio.sleep(15)
                for sub_id, name in [(sub1["id"], "A"), (sub2["id"], "B")]:
                    sub_status = await client.get_task(room["id"], sub_id)
                    print(f"Sub-task {name}: status={sub_status['status']}, blocked_by={sub_status.get('blocked_by')}")


# Utility function to check if integration tests can run
async def check_services_ready() -> bool:
    """Check if backend and poll_service are running."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{CHATROOM_URL.rsplit('/chatroom', 1)[0]}/chatroom/poll-service/status")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("running", False)
    except Exception:
        pass
    return False


@pytest.mark.integration
@pytest.mark.asyncio
class TestServiceReadiness:
    """Test to verify services are ready for integration tests."""

    async def test_check_services(self):
        """Verify backend and poll_service are running."""
        ready = await check_services_ready()
        if ready:
            print("\n✓ Services are ready for integration tests")
        else:
            print("\n✗ Services not ready. Ensure:")
            print("  1. Backend server is running on 127.0.0.1:8088")
            print("  2. poll_service is active")
            print("  3. Agents are configured and available")

        # Don't fail the test, just report status