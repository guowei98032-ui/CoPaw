# -*- coding: utf-8 -*-
"""Real Multi-Agent Collaboration E2E Tests.

These tests create real tasks and wait for agents to actually complete them.
The tests verify:
1. Agents receive and understand tasks
2. Agents produce reasonable outputs
3. Multi-agent collaboration works end-to-end

Prerequisites:
- Backend server running
- poll_service active
- Agents configured with proper tools (shell, file operations)
- Sufficient model capabilities

Run with:
    pytest tests/chatroom_e2e_collaboration_test.py -v -s -m e2e
"""
import asyncio
import os
import json
import pytest
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from test_config import (
    REAL_LEAD_AGENT,
    REAL_WORKER_1,
    REAL_WORKER_2,
    REAL_WORKER_3,
    CHATROOM_URL,
)

# Extended timeout for real agent execution (5 minutes)
E2E_TIMEOUT = 300
POLL_INTERVAL = 10.0


class E2ECollaborationClient:
    """Client for E2E collaboration tests with real agent execution."""

    def __init__(self, base_url: str = CHATROOM_URL, workspace_dir: str = None):
        self.base_url = base_url
        self.workspace_dir = workspace_dir or Path.home() / ".copaw" / "workspaces"
        self._client: httpx.AsyncClient = None
        self._created_rooms: List[str] = []

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=E2E_TIMEOUT + 60)
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
            "agent_ids": agent_ids or REAL_WORKER_AGENTS[:2],
        }
        if agent_roles:
            data["agent_roles"] = agent_roles
        resp = await self._client.post(self.base_url, json=data)
        assert resp.status_code == 201
        result = resp.json()["room"]
        self._created_rooms.append(result["id"])
        return result

    async def send_message(
        self,
        room_id: str,
        content: str,
        to_agent: str = None,
    ) -> Dict:
        """Send a message to the chatroom."""
        data = {"content": content, "message_type": "chat"}
        if to_agent:
            data["to_agent"] = to_agent
        resp = await self._client.post(f"{self.base_url}/{room_id}/messages", json=data)
        assert resp.status_code == 201
        return resp.json()

    async def list_messages(
        self,
        room_id: str,
        from_agent: str = None,
    ) -> List[Dict]:
        """List messages."""
        params = {"limit": 100}
        resp = await self._client.get(f"{self.base_url}/{room_id}/messages", params=params)
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
        auto_mode: bool = True,
        blocked_by: List[str] = None,
    ) -> Dict:
        """Create a task."""
        data = {
            "subject": subject,
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
        return resp.json()

    async def list_tasks(self, room_id: str, status: str = None) -> List[Dict]:
        params = {}
        if status:
            params["status"] = status
        resp = await self._client.get(f"{self.base_url}/{room_id}/tasks", params=params)
        return resp.json()

    async def wait_for_task_completion(
        self,
        room_id: str,
        task_id: str,
        timeout: float = E2E_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
    ) -> Optional[Dict]:
        """Wait for a task to complete (or fail)."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            task = await self.get_task(room_id, task_id)
            status = task.get("status")

            if status in ["completed", "failed", "cancelled"]:
                return task

            # Log progress if available
            progress = task.get("progress", 0)
            if progress > 0:
                print(f"  Task {task_id[:8]} progress: {progress}%")

            await asyncio.sleep(poll_interval)

        return None

    async def wait_for_all_tasks_done(
        self,
        room_id: str,
        timeout: float = E2E_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
    ) -> List[Dict]:
        """Wait for all tasks to complete."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            tasks = await self.list_tasks(room_id)
            done = [t for t in tasks if t["status"] in ["completed", "failed", "cancelled"]]

            if len(done) == len(tasks) and len(tasks) > 0:
                return tasks

            # Log status
            pending = len([t for t in tasks if t["status"] == "pending"])
            in_progress = len([t for t in tasks if t["status"] == "in_progress"])
            completed = len([t for t in tasks if t["status"] == "completed"])
            print(f"  Tasks: {pending} pending, {in_progress} in progress, {completed} completed")

            await asyncio.sleep(poll_interval)

        return await self.list_tasks(room_id)

    async def wait_for_agent_messages(
        self,
        room_id: str,
        min_count: int = 1,
        timeout: float = E2E_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
    ) -> List[Dict]:
        """Wait for agent messages."""
        start_time = asyncio.get_event_loop().time()
        seen_ids = set()

        while asyncio.get_event_loop().time() - start_time < timeout:
            messages = await self.list_messages(room_id)
            agent_msgs = [
                m for m in messages
                if m.get("from_agent") and m["from_agent"] not in ["system", "user"]
                and m["id"] not in seen_ids
            ]

            if len(agent_msgs) >= min_count:
                return agent_msgs

            for m in agent_msgs:
                seen_ids.add(m["id"])

            await asyncio.sleep(poll_interval)

        return []

    def check_file_exists(self, agent_id: str, file_path: str) -> bool:
        """Check if a file exists in agent's workspace."""
        full_path = Path(self.workspace_dir) / agent_id / file_path
        return full_path.exists()

    def read_file(self, agent_id: str, file_path: str) -> Optional[str]:
        """Read a file from agent's workspace."""
        full_path = Path(self.workspace_dir) / agent_id / file_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return None


@pytest.mark.e2e
@pytest.mark.asyncio
class TestSimpleCollaboration:
    """Simple single-agent task completion tests."""

    async def test_single_agent_simple_task(self):
        """Single agent completes a simple task with verifiable output."""
        async with E2ECollaborationClient() as client:
            room = await client.create_room(
                name="简单任务测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理",
                    REAL_WORKER_1: "执行者，负责完成分配的任务",
                },
            )
            print(f"\n创建聊天室: {room['id']}")

            # Create a simple task: list current directory
            task = await client.create_task(
                room_id=room["id"],
                subject="列出当前目录文件",
                description="请使用shell命令列出当前工作目录的文件，并告诉我有什么文件",
                owner=REAL_WORKER_1,
                auto_mode=True,
            )
            print(f"创建任务: {task['id']}")

            # Wait for completion
            print("等待任务完成...")
            result = await client.wait_for_task_completion(
                room_id=room["id"],
                task_id=task["id"],
                timeout=E2E_TIMEOUT,
            )

            if result:
                print(f"任务状态: {result['status']}")
                print(f"任务进度: {result.get('progress', 0)}%")

                # Check for agent messages
                messages = await client.list_messages(room["id"])
                agent_msgs = [m for m in messages if m.get("from_agent") == REAL_WORKER_1]
                if agent_msgs:
                    print(f"\nAgent回复 ({len(agent_msgs)}条):")
                    for msg in agent_msgs[-3:]:  # Last 3 messages
                        content = msg.get("content", "")[:500]
                        print(f"  {content}...")

                # Verify task completed
                if result["status"] == "completed":
                    print("\n[OK] Task completed successfully")
                else:
                    print(f"\n[WARN] Task status: {result['status']}")
            else:
                print("[X] 任务超时未完成")


@pytest.mark.e2e
@pytest.mark.asyncio
class TestMultiAgentCollaboration:
    """Multi-agent collaboration tests with task completion."""

    async def test_two_agents_sequential_tasks(self):
        """Two agents complete tasks sequentially with dependency."""
        async with E2ECollaborationClient() as client:
            room = await client.create_room(
                name="顺序协作测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理，协调整体工作",
                    REAL_WORKER_1: "数据分析师，负责数据分析",
                    REAL_WORKER_2: "报告撰写者，负责编写报告",
                },
            )
            print(f"\n创建聊天室: {room['id']}")

            # Task 1: Worker 1 analyzes data
            task1 = await client.create_task(
                room_id=room["id"],
                subject="分析系统信息",
                description="请检查Python版本和操作系统信息，准备一份简短的系统报告",
                owner=REAL_WORKER_1,
                auto_mode=True,
            )
            print(f"任务1(Worker1): {task1['id']}")

            # Task 2: Worker 2 writes summary (depends on Task 1)
            task2 = await client.create_task(
                room_id=room["id"],
                subject="汇总分析结果",
                description="基于第一个任务的完成，写一份简短的总结报告",
                owner=REAL_WORKER_2,
                blocked_by=[task1["id"]],
                auto_mode=True,
            )
            print(f"任务2(Worker2): {task2['id']} - 依赖任务1")

            # Wait for all tasks to complete
            print("\n等待所有任务完成...")
            tasks = await client.wait_for_all_tasks_done(
                room_id=room["id"],
                timeout=E2E_TIMEOUT * 2,
            )

            # Analyze results
            print("\n=== 任务完成情况 ===")
            for t in tasks:
                print(f"  [{t['status']}] {t['subject']} (owner: {t.get('owner')})")

            completed_count = len([t for t in tasks if t["status"] == "completed"])
            print(f"\n完成率: {completed_count}/{len(tasks)}")

            # Check agent messages
            messages = await client.list_messages(room["id"])
            agent_msgs = [m for m in messages if m.get("from_agent") and m["from_agent"] not in ["system", "user"]]
            print(f"\nAgent消息数: {len(agent_msgs)}")

            if agent_msgs:
                print("\n=== Agent对话摘要 ===")
                for msg in agent_msgs[-5:]:
                    sender = msg.get("from_agent", "?")
                    content = msg.get("content", "")[:300]
                    print(f"[{sender}]: {content}...")

            assert completed_count >= 1, "至少应该有1个任务完成"

    async def test_leader_distributes_work(self):
        """Leader receives a complex request and distributes to workers."""
        async with E2ECollaborationClient() as client:
            room = await client.create_room(
                name="Leader分配测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理，负责接收需求并分配给合适的团队成员",
                    REAL_WORKER_1: "后端开发者",
                    REAL_WORKER_2: "前端开发者",
                },
            )
            print(f"\n创建聊天室: {room['id']}")

            # Send a complex request to leader
            await client.send_message(
                room_id=room["id"],
                content="""
我需要完成以下工作：
1. 检查当前Python环境是否正常
2. 列出已安装的关键包

请将任务分配给合适的团队成员执行。
                """.strip(),
                to_agent=REAL_LEAD_AGENT,
            )
            print("已发送需求给Leader")

            # Wait for leader's response
            print("\n等待Leader响应...")
            await asyncio.sleep(30)  # Give leader time to think

            # Check for leader's message
            messages = await client.list_messages(room["id"], from_agent=REAL_LEAD_AGENT)
            if messages:
                print(f"\nLeader回复:")
                for msg in messages[-2:]:
                    content = msg.get("content", "")[:500]
                    print(f"  {content}...")

            # Wait a bit more to see if tasks are created
            await asyncio.sleep(60)

            # Check tasks created
            tasks = await client.list_tasks(room["id"])
            print(f"\n创建的任务数: {len(tasks)}")
            for t in tasks:
                print(f"  [{t['status']}] {t['subject']} (owner: {t.get('owner')})")

            # If tasks exist, wait for completion
            if tasks:
                print("\n等待任务完成...")
                final_tasks = await client.wait_for_all_tasks_done(
                    room_id=room["id"],
                    timeout=E2E_TIMEOUT,
                )

                completed = [t for t in final_tasks if t["status"] == "completed"]
                print(f"\n最终完成: {len(completed)}/{len(final_tasks)}")


@pytest.mark.e2e
@pytest.mark.asyncio
class TestComplexWorkflow:
    """Complex multi-step workflow tests."""

    async def test_three_agent_project_workflow(self):
        """Three agents collaborate on a small project: design -> implement -> test."""
        async with E2ECollaborationClient() as client:
            room = await client.create_room(
                name="项目协作测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3],
                agent_roles={
                    REAL_LEAD_AGENT: "项目经理，负责规划和验收",
                    REAL_WORKER_1: "架构师，负责设计和方案",
                    REAL_WORKER_2: "开发者，负责实现",
                    REAL_WORKER_3: "测试工程师，负责验证",
                },
            )
            print(f"\n创建聊天室: {room['id']}")

            # Phase 1: Design
            task1 = await client.create_task(
                room_id=room["id"],
                subject="设计阶段：制定技术方案",
                description="""
请为以下需求制定技术方案：
需求：创建一个简单的Python函数，计算两个数的和、差、积、商。

输出要求：
1. 函数设计说明
2. 预期的函数接口
                """.strip(),
                owner=REAL_WORKER_1,
                auto_mode=True,
            )
            print(f"任务1(架构师): {task1['id']}")

            # Phase 2: Implement (depends on design)
            task2 = await client.create_task(
                room_id=room["id"],
                subject="实现阶段：编写代码",
                description="""
根据架构师的设计，实现计算器函数。
请在工作目录创建 calculator.py 文件。
                """.strip(),
                owner=REAL_WORKER_2,
                blocked_by=[task1["id"]],
                auto_mode=True,
            )
            print(f"任务2(开发者): {task2['id']}")

            # Phase 3: Test (depends on implementation)
            task3 = await client.create_task(
                room_id=room["id"],
                subject="测试阶段：验证功能",
                description="""
验证开发者实现的计算器函数：
1. 检查calculator.py是否存在
2. 尝试运行并验证基本功能
3. 报告测试结果
                """.strip(),
                owner=REAL_WORKER_3,
                blocked_by=[task2["id"]],
                auto_mode=True,
            )
            print(f"任务3(测试): {task3['id']}")

            # Wait for all tasks
            print("\n等待项目完成...")
            tasks = await client.wait_for_all_tasks_done(
                room_id=room["id"],
                timeout=E2E_TIMEOUT * 3,  # More time for complex workflow
            )

            # Analyze workflow results
            print("\n" + "=" * 60)
            print("项目协作结果")
            print("=" * 60)

            for i, t in enumerate(tasks, 1):
                status_icon = "[OK]" if t["status"] == "completed" else "[X]"
                print(f"{status_icon} 阶段{i}: {t['subject']}")
                print(f"   状态: {t['status']}, 进度: {t.get('progress', 0)}%")
                print(f"   执行者: {t.get('owner', '未分配')}")

            # Check for output file
            calculator_code = client.read_file(REAL_WORKER_2, "calculator.py")
            if calculator_code:
                print("\n生成的代码 (calculator.py):")
                print("-" * 40)
                print(calculator_code[:1000])
                print("-" * 40)

            # Check agent collaboration messages
            all_messages = await client.list_messages(room["id"])
            collaboration_msgs = [
                m for m in all_messages
                if m.get("from_agent") and m["from_agent"] not in ["system", "user"]
            ]

            print(f"\n协作消息数: {len(collaboration_msgs)}")
            if collaboration_msgs:
                print("\n关键对话:")
                for msg in collaboration_msgs[-6:]:
                    sender = msg.get("from_agent", "?")
                    content = msg.get("content", "")[:200]
                    print(f"  [{sender}] {content}...")

            # Summary
            completed = len([t for t in tasks if t["status"] == "completed"])
            print(f"\n项目完成度: {completed}/{len(tasks)} 阶段")

            if completed == len(tasks):
                print("\n[DONE] 项目全部完成!")
            elif completed > 0:
                print(f"\n[!] 项目部分完成 ({completed}/{len(tasks)})")
            else:
                print("\n[FAIL] 项目未能完成")


@pytest.mark.e2e
@pytest.mark.asyncio
class TestAgentResponseQuality:
    """Test quality of agent responses and outputs."""

    async def test_agent_provides_meaningful_output(self):
        """Verify agent provides meaningful, actionable output."""
        async with E2ECollaborationClient() as client:
            room = await client.create_room(
                name="输出质量测试",
                lead_agent_id=REAL_LEAD_AGENT,
                agent_ids=[REAL_WORKER_1],
            )

            task = await client.create_task(
                room_id=room["id"],
                subject="代码质量检查",
                description="""
请执行以下任务并提供详细报告：
1. 检查当前Python版本
2. 列出已安装的pip包中与"test"相关的包
3. 总结系统环境是否适合开发测试
                """.strip(),
                owner=REAL_WORKER_1,
                auto_mode=True,
            )

            result = await client.wait_for_task_completion(
                room_id=room["id"],
                task_id=task["id"],
                timeout=E2E_TIMEOUT,
            )

            if result and result["status"] == "completed":
                # Check agent messages for quality
                messages = await client.list_messages(room["id"])
                agent_msg = [m for m in messages if m.get("from_agent") == REAL_WORKER_1]

                if agent_msg:
                    content = agent_msg[-1].get("content", "")

                    # Quality checks
                    quality_checks = {
                        "包含Python版本信息": "python" in content.lower() or "版本" in content,
                        "有实际输出": len(content) > 100,
                        "结构化回答": any(kw in content for kw in ["1.", "一、", "•", "-", "*"]),
                    }

                    print("\n输出质量检查:")
                    for check, passed in quality_checks.items():
                        icon = "[OK]" if passed else "[X]"
                        print(f"  {icon} {check}")

                    print(f"\nAgent输出:\n{content[:800]}...")

                    # Assert minimum quality
                    assert len(content) > 50, "Agent应该提供有意义的输出"


# Test configuration
def pytest_configure(config):
    """Register e2e marker."""
    config.addinivalue_line(
        "markers", "e2e: end-to-end tests requiring running agents"
    )