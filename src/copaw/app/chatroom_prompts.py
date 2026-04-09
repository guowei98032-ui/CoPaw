# -*- coding: utf-8 -*-
"""Prompts for chatroom poll service.

All prompts for Leader and Workers are centralized here for easy maintenance.

Note: Chatroom context (room name, agent role, team members, task status) is
injected via build_chatroom_context_prompt in the agent's system prompt.
These prompt builders only contain action-specific instructions.
"""
from typing import Dict, List, Any, Optional


def build_chatroom_context_prompt(
    room_id: str,
    agent_id: str,
) -> str:
    """Build chatroom context for agent system prompt.

    This is injected into the agent's system prompt when in a chatroom,
    providing context about the room, the agent's role, team members,
    and current task status.

    Args:
        room_id: The chatroom ID
        agent_id: The agent's ID

    Returns:
        Formatted context string to prepend to system prompt
    """
    from .db.chatroom_db import ChatRoomDatabase

    db = ChatRoomDatabase()
    room = db.get_room(room_id)
    if not room:
        return ""

    parts = [
        "# 你现在在聊天室内",
        "",
        f"**聊天室**: {room.name}",
        f"**你在聊天室的身份**: {agent_id}" + (" (Leader)" if room.lead_agent_id == agent_id else ""),
    ]

    # Add role description
    team_roles = room.agent_roles or {}
    agent_role = team_roles.get(agent_id, "")
    if agent_role:
        parts.extend([
            "",
            "## 你的角色",
            agent_role,
        ])

    # Leader role clarification
    if room.lead_agent_id == agent_id:
        parts.extend([
            "",
            "**Leader 角色**: 你负责协调团队、创建任务、监督进度。",
            "**重要**: Leader 不执行具体任务，只创建任务让团队成员认领执行。",
        ])

    # Add team members
    other_roles = {
        aid: role for aid, role in team_roles.items()
        if aid != agent_id and role
    }
    if other_roles:
        parts.extend([
            "",
            "## 团队成员",
        ])
        for aid, role in other_roles.items():
            lead_marker = " (Leader)" if aid == room.lead_agent_id else ""
            parts.append(f"- {aid}{lead_marker}: {role[:80]}{'...' if len(role) > 80 else ''}")

    # Add current tasks status
    tasks = db.get_tasks(room_id)
    if tasks:
        parts.extend([
            "",
            "## 当前任务状态",
        ])
        for t in tasks[:10]:  # Limit to 10 tasks
            status_icon = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "🚫"
            }.get(t.status, "❓")
            owner = f" → {t.owner}" if t.owner else " (待认领)"
            parts.append(f"- {status_icon} #{t.id} {t.subject}{owner}")

    return "\n".join(parts)


def build_leader_prompt(
    all_tasks: List[Any],
    completed_tasks: List[Dict],
) -> str:
    """Build prompt for Leader to check completed tasks and decide on follow-up.

    Note: Chatroom context is already in system prompt. This only contains
    action-specific instructions for task creation and retry.

    Args:
        all_tasks: All tasks in the room
        completed_tasks: Recently completed tasks that triggered this check

    Returns:
        Formatted prompt string with action instructions
    """
    parts = []

    # Show recently completed tasks that triggered this check
    if completed_tasks:
        parts.extend([
            "## 最近完成的任务",
            "",
            "以下任务刚完成，请判断是否需要创建后续任务：",
        ])
        for t in completed_tasks:
            parts.append(f"- ✅ #{t['id']} {t['subject']}")
            if t.get('description'):
                desc_preview = t['description'][:300] + "..." if len(t['description']) > 300 else t['description']
                parts.append(f"  完成情况: {desc_preview}")

    # Show failed tasks for retry consideration
    failed_tasks = [t for t in all_tasks if t.status == "failed"]
    if failed_tasks:
        parts.extend([
            "",
            "## 失败的任务",
            "",
            "以下任务已失败，请判断是否需要重试：",
        ])
        for t in failed_tasks:
            parts.append(f"- ❌ #{t.id} {t['subject']} (重试次数: {t.retry_count}/{t.max_retries})")

    # Build example with real task ID from current tasks
    example_task_id = "task_xxx"
    if all_tasks:
        for t in all_tasks:
            if t.status in ("pending", "in_progress"):
                example_task_id = t.id
                break

    parts.extend([
        "",
        "---",
        "",
        "请根据任务完成情况，判断是否需要创建后续任务或重试失败任务。",
        "",
        "**输出 JSON 格式示例**:",
        "",
        "示例1 - 创建无依赖的任务：",
        "```json",
        "{",
        '  "tasks_to_create": [',
        "    {",
        '      "subject": "编写集成测试",',
        '      "description": "为已完成的模块编写集成测试",',
        '      "priority": "medium"',
        "    }",
        "  ],",
        '  "tasks_to_retry": []',
        "}",
        "```",
        "",
        f"示例2 - 创建依赖现有任务 #{example_task_id} 的任务：",
        "```json",
        "{",
        '  "tasks_to_create": [',
        "    {",
        '      "subject": "编写API文档",',
        '      "priority": "medium",',
        f'      "blocked_by": ["{example_task_id}"]',
        "    }",
        "  ],",
        '  "tasks_to_retry": []',
        "}",
        "```",
        "",
        "示例3 - 重试永久失败的任务：",
        "```json",
        "{",
        '  "tasks_to_create": [],',
        '  "tasks_to_retry": ["failed_task_id_1", "failed_task_id_2"]',
        "}",
        "```",
        "",
        "示例4 - 不需要任何操作：",
        "```json",
        "{",
        '  "tasks_to_create": [],',
        '  "tasks_to_retry": []',
        "}",
        "```",
        "",
        "**字段说明**:",
        "- `tasks_to_create`: 要创建的新任务列表",
        "  - `subject`: 任务标题（必填）",
        "  - `description`: 任务详细描述（可选）",
        "  - `priority`: `high`/`medium`/`low`（可选，默认medium）",
        "  - `blocked_by`: 依赖的**现有**任务ID列表",
        "  - `blocked_by_subject`: 依赖的**同批次新任务**标题列表",
        "- `tasks_to_retry`: 要重试的失败任务ID列表",
    ])

    return "\n".join(parts)


def build_idle_worker_prompt(
    ready_tasks: List[Dict],
    blocked_tasks: List[Dict],
) -> str:
    """Build prompt for idle worker who can claim tasks.

    Note: Chatroom context is already in system prompt. This only contains
    action-specific instructions for task claiming.

    Args:
        ready_tasks: Tasks ready to claim (dependencies satisfied)
        blocked_tasks: Tasks blocked by dependencies

    Returns:
        Formatted prompt string with action instructions
    """
    parts = []

    # Show available tasks
    if ready_tasks:
        parts.extend([
            "## 可认领任务",
            "",
            "### ✅ 可立即认领",
        ])
        for task in ready_tasks:
            auto_flag = " 🚀" if task.get("auto_mode") else ""
            parts.append(f"- **#{task['id']}** [{task['priority']}] {task['subject']}{auto_flag}")
            if task.get("description"):
                parts.append(f"  描述: {task['description']}")

    if blocked_tasks:
        parts.extend([
            "",
            "### ⏳ 等待依赖完成",
        ])
        for task in blocked_tasks:
            blocked_by = task.get("blocked_by", [])
            parts.append(f"- **#{task['id']}** [{task['priority']}] {task['subject']} (等待: #{', #'.join(blocked_by)})")

    if not ready_tasks and not blocked_tasks:
        parts.extend([
            "## 可认领任务",
            "",
            "当前没有可认领的任务。",
        ])

    # JSON format examples
    example_task_id = ready_tasks[0]["id"] if ready_tasks else "task_xxx"

    parts.extend([
        "",
        "---",
        "",
        "请根据你的角色和能力，决定是否认领一个任务。",
        "",
        "**输出 JSON 格式示例**:",
        "",
        f"示例1 - 认领任务 #{example_task_id}：",
        "```json",
        "{",
        f'  "task_to_claim": "{example_task_id}"',
        "}",
        "```",
        "",
        "示例2 - 暂不认领：",
        "```json",
        "{",
        '  "task_to_claim": null',
        "}",
        "```",
        "",
        "**认领规则**:",
        "- 只能认领「✅ 可立即认领」部分的任务",
        "- ⏳ 标记的任务依赖未完成，认领会失败",
        "- 选择匹配你角色描述的任务",
    ])

    return "\n".join(parts)


def build_busy_worker_prompt(
    task: Dict,
) -> str:
    """Build prompt for worker who is busy executing a task.

    Note: Chatroom context is already in system prompt. This only contains
    action-specific instructions for task execution and status reporting.

    Args:
        task: Current task being executed

    Returns:
        Formatted prompt string with action instructions
    """
    parts = [
        "## 你的当前任务",
        f"**任务ID**: {task['id']}",
        f"**标题**: {task['subject']}",
        f"**优先级**: {task['priority']}",
    ]

    if task.get("description"):
        parts.append(f"**描述**: {task['description']}")

    auto_mode = task.get("auto_mode", False)
    if auto_mode:
        parts.extend([
            "",
            "**模式**: 🚀 自动模式 - 自主执行，无需中间确认",
        ])

    # Show blocked tasks that depend on this task
    blocks = task.get("blocks", [])
    if blocks:
        parts.extend([
            "",
            "**后续依赖任务**: " + ", ".join(f"#{t}" for t in blocks),
            "完成此任务后，这些任务才能被认领。",
        ])

    parts.extend([
        "",
        "---",
        "",
        "请执行上述任务。完成后，输出以下格式的 JSON：",
        "",
        "示例1 - 任务完成：",
        "```json",
        "{",
        '  "status": "completed",',
        '  "reason": "已完成用户登录功能开发，包括：1. 用户名密码登录 2. OAuth登录"',
        "}",
        "```",
        "",
        "示例2 - 任务失败：",
        "```json",
        "{",
        '  "status": "failed",',
        '  "reason": "数据库连接失败，已重试3次，错误: Connection timeout"',
        "}",
        "```",
        "",
        "示例3 - 任务取消：",
        "```json",
        "{",
        '  "status": "cancelled",',
        '  "reason": "需求已变更，此任务不再需要"',
        "}",
        "```",
        "",
        "**状态说明**:",
        "- `completed`: 任务已完成，在 reason 中详细说明完成内容",
        "- `failed`: 遇到无法解决的问题，说明具体错误",
        "- `cancelled`: 任务不再需要执行，说明原因",
        "",
        "**重要**: 你必须实际执行任务，然后报告结果。",
    ])

    if auto_mode:
        parts.extend([
            "",
            "**自动模式要求**:",
            "- 自主读取文件、搜索代码、执行测试",
            "- 可以修改代码、创建文件",
            "- 只在真正卡住时才报告 failed",
        ])

    return "\n".join(parts)


def build_fix_json_prompt(
    original_text: str,
    expected_schema: str,
) -> str:
    """Build prompt for fixing malformed JSON.

    Args:
        original_text: The original text containing malformed JSON
        expected_schema: Schema type to fix to

    Returns:
        Prompt string for the fix request
    """
    examples = {
        "leader": '{"tasks_to_create": [{"subject": "任务标题", "description": "任务描述", "priority": "medium", "blocked_by": []}], "tasks_to_retry": []}',
        "idle_worker": '{"task_to_claim": "task_abc123"}',
        "busy_worker": '{"status": "completed", "reason": "完成说明"}',
    }

    descriptions = {
        "leader": "创建任务列表，tasks_to_create 是数组，tasks_to_retry 是要重试的失败任务ID数组",
        "idle_worker": "认领任务，task_to_claim 是任务ID字符串或null",
        "busy_worker": "报告任务状态，status 是 completed/failed/cancelled 之一，reason 字段说明完成内容或失败原因",
    }

    return f"""以下文本包含JSON但格式有误，请修正并输出正确的JSON。

原始文本：
{original_text[:1000]}

期望格式说明：
{descriptions[expected_schema]}

正确示例：
{examples[expected_schema]}

请只输出修正后的JSON，不要其他解释。"""