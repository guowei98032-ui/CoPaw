# -*- coding: utf-8 -*-
"""Tools for managing chatroom tasks.

Provides tools for agents to create, update, and cancel tasks
in the chatroom task management system.

Note: task_list, task_claim, task_delete, task_retry, task_set_auto_mode, chatroom_context
are kept as backend APIs for frontend use, not exposed as LLM tools.
"""
import logging
from datetime import datetime
from typing import Optional, List

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...app.db.chatroom_db import ChatRoomDatabase
from ...app.models.chatroom import Task
from ...config.utils import load_agent_config

logger = logging.getLogger(__name__)


def _get_current_agent_id() -> str:
    """Get current agent ID from context."""
    from ...app.agent_context import get_current_request_context
    context = get_current_request_context()
    if context:
        return context.get("agent_id", "")
    return ""


def _get_current_room_id() -> Optional[str]:
    """Get current room ID from context."""
    from ...app.agent_context import get_current_request_context
    context = get_current_request_context()
    if context:
        return context.get("room_id")
    return None


def _resolve_agent_id(room_id: str, owner_or_name: str) -> Optional[str]:
    """Resolve agent name or id to a valid agent_id.

    Args:
        room_id: The chatroom ID
        owner_or_name: Either an agent_id or agent_name

    Returns:
        Resolved agent_id or None if not found
    """
    db = ChatRoomDatabase()
    room = db.get_room(room_id)
    if not room:
        return None

    # Collect all agent IDs in this room
    all_agents = []
    if room.lead_agent_id:
        all_agents.append(room.lead_agent_id)
    if room.agent_ids:
        all_agents.extend(room.agent_ids)

    # Direct match by agent_id
    if owner_or_name in all_agents:
        return owner_or_name

    # Try to match by agent name
    for agent_id in all_agents:
        try:
            config = load_agent_config(agent_id)
            if config and config.name == owner_or_name:
                return agent_id
        except Exception:
            pass

    return None


async def _try_cancel_active_execution(room_id: str, agent_id: str) -> bool:
    """Try to cancel an active execution for an agent.

    This is a best-effort function that attempts to stop a running agent
    when their task is being cancelled.

    Args:
        room_id: The chatroom ID
        agent_id: The agent ID

    Returns:
        True if execution was cancelled, False otherwise
    """
    try:
        # Import here to avoid circular imports
        from ...app.chatroom_poll_service import get_poll_service

        poll_service = get_poll_service()
        if poll_service:
            return await poll_service.cancel_active_execution(room_id, agent_id)
    except Exception as e:
        logger.warning("Failed to cancel active execution: %s", e)
    return False


async def task_cancel(
    task_id: str,
    reason: Optional[str] = None,
) -> ToolResponse:
    """Cancel a task (LLM Tool).

    Use this tool when:
    - A task is no longer needed or relevant
    - A task cannot be completed due to blockers
    - You need to stop work on a task

    The system will automatically:
    - Stop running agent if task is in progress
    - Notify the task owner and lead agent
    - Unblock dependent tasks

    Args:
        task_id: The task ID to cancel.
        reason: Optional reason for cancellation (helpful for team coordination).

    Returns:
        ToolResponse: Cancellation confirmation.
    """
    db = ChatRoomDatabase()

    # Get cancelled_by from context
    cancelled_by = _get_current_agent_id() or "system"

    try:
        task = db.get_task(task_id)
        if not task:
            return ToolResponse(
                content=[TextBlock(type="text", text=f"Error: Task '{task_id}' not found.")],
            )

        if task.status == "completed":
            return ToolResponse(
                content=[TextBlock(type="text", text=f"Error: Task '{task_id}' is already completed and cannot be cancelled.")],
            )

        if task.status == "cancelled":
            return ToolResponse(
                content=[TextBlock(type="text", text=f"Task '{task_id}' is already cancelled.")],
            )

        # Store info before update
        room_id = task.room_id
        task_owner = task.owner
        task_subject = task.subject
        blocks_tasks = task.blocks  # Tasks that depend on this task

        # Stop active execution if task is in_progress
        execution_stopped = False
        if task.status == "in_progress" and task.owner:
            execution_stopped = await _try_cancel_active_execution(room_id, task.owner)
            if execution_stopped:
                logger.info("Stopped active execution for task %s owned by %s", task_id, task.owner)

        # Update status to cancelled
        task.status = "cancelled"  # type: ignore
        task.updated_at = datetime.now()
        task.owner = None

        # Add cancellation info to description
        cancellation_info = f"\n[Cancelled by {cancelled_by} at {datetime.now().isoformat()}]"
        if reason:
            cancellation_info += f" Reason: {reason}"
        if task.description:
            task.description = task.description + cancellation_info
        else:
            task.description = cancellation_info.strip()

        # Clear dependency lists
        task.blocked_by = []
        task.blocks = []

        updated_task = db.update_task(task)

        # Add log entry
        db.add_task_log_entry(task_id, "cancelled", f"Cancelled by {cancelled_by}; Reason: {reason or 'N/A'}")

        # Dependency cleanup: Remove this task from other tasks' blocked_by lists
        unblocked_tasks = []
        for blocked_task_id in blocks_tasks:
            blocked_task = db.get_task(blocked_task_id)
            if blocked_task and task_id in blocked_task.blocked_by:
                blocked_task.blocked_by.remove(task_id)
                blocked_task.updated_at = datetime.now()
                db.update_task(blocked_task)
                if not blocked_task.blocked_by and blocked_task.status == "pending":
                    unblocked_tasks.append(blocked_task_id)

        # Build response
        response_parts = [
            f"Task cancelled!",
            f"ID: {updated_task.id}",
            f"Subject: {task_subject}",
            f"Status: cancelled",
        ]
        if reason:
            response_parts.append(f"Reason: {reason}")
        if execution_stopped:
            response_parts.append("🛑 Active execution stopped")
        if unblocked_tasks:
            response_parts.append(f"✅ Unblocked tasks: {', '.join(f'#{t}' for t in unblocked_tasks)}")

        return ToolResponse(
            content=[TextBlock(type="text", text="\n".join(response_parts))],
        )
    except Exception as e:
        logger.error(f"Error cancelling task: {e}", exc_info=True)
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Error cancelling task: {str(e)}")],
        )


async def chatroom_context(
    room_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> ToolResponse:
    """Get the chatroom context including team member roles and current status (Backend API).

    This function is for frontend/backend use to get team context.
    Room ID and agent ID are auto-detected from context if not provided.

    Args:
        room_id: The chatroom ID. Auto-detected from context if not provided.
        agent_id: The agent ID to highlight your own role. Auto-detected if not provided.

    Returns:
        ToolResponse: Chatroom context with team information.
    """
    # Auto-detect room_id from context
    if room_id is None:
        room_id = _get_current_room_id()
        if not room_id:
            return ToolResponse(
                content=[TextBlock(type="text", text="Error: room_id not found in context.")],
            )

    # Auto-detect agent_id from context
    if agent_id is None:
        agent_id = _get_current_agent_id()

    db = ChatRoomDatabase()

    try:
        room = db.get_room(room_id)
        if not room:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: ChatRoom '{room_id}' not found.",
                    ),
                ],
            )

        parts = [f"# ChatRoom: {room.name}", ""]
        parts.append(f"Room ID: {room_id}")
        parts.append("")

        # Team members and their roles
        parts.append("## Team Members")
        parts.append("")

        if room.lead_agent_id:
            lead_role = room.agent_roles.get(room.lead_agent_id, "Team Lead")
            lead_marker = " (YOU)" if agent_id == room.lead_agent_id else ""
            parts.append(f"**Lead Agent**: {room.lead_agent_id}{lead_marker}")
            parts.append(f"  Role: {lead_role}")
            parts.append("")

        if room.agent_ids:
            parts.append("**Worker Agents**:")
            for aid in room.agent_ids:
                role = room.agent_roles.get(aid, "Worker")
                marker = " (YOU)" if agent_id == aid else ""
                parts.append(f"  - {aid}{marker}")
                parts.append(f"    Role: {role}")
            parts.append("")

        # Current tasks summary
        tasks = db.get_tasks(room_id)
        pending = [t for t in tasks if t.status == 'pending']
        in_progress = [t for t in tasks if t.status == 'in_progress']
        completed = [t for t in tasks if t.status == 'completed']

        parts.append("## Task Summary")
        parts.append(f"- Pending: {len(pending)}")
        parts.append(f"- In Progress: {len(in_progress)}")
        parts.append(f"- Completed: {len(completed)}")
        parts.append("")

        # Tasks by owner
        if in_progress:
            parts.append("## Active Assignments")
            for t in in_progress:
                owner_role = room.agent_roles.get(t.owner, "") if t.owner else ""
                owner_info = f"{t.owner}" + (f" ({owner_role})" if owner_role else "")
                parts.append(f"- #{t.id} '{t.subject}' - {owner_info}")
            parts.append("")

        # Your role summary
        if agent_id and agent_id in room.agent_roles:
            parts.append("## Your Role")
            parts.append(room.agent_roles[agent_id])
            parts.append("")

            # Your current tasks
            your_tasks = [t for t in tasks if t.owner == agent_id and t.status != 'completed']
            if your_tasks:
                parts.append("## Your Active Tasks")
                for t in your_tasks:
                    parts.append(f"- #{t.id} [{t.status}] {t.subject}")

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="\n".join(parts),
                ),
            ],
        )

    except Exception as e:
        logger.error("Error getting chatroom context: %s", e, exc_info=True)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error getting chatroom context: {str(e)}",
                ),
            ],
        )


async def task_list(
    room_id: Optional[str] = None,
    status: Optional[str] = None,
    owner: Optional[str] = None,
) -> ToolResponse:
    """List tasks in a chatroom (Backend API).

    Args:
        room_id: The chatroom ID. Auto-detected from context if not provided.
        status: Optional filter by status (pending, in_progress, completed, failed).
        owner: Optional filter by owner agent ID or name.

    Returns:
        ToolResponse: List of tasks.
    """
    # Auto-detect room_id from context
    if room_id is None:
        room_id = _get_current_room_id()
        if not room_id:
            return ToolResponse(
                content=[TextBlock(type="text", text="Error: room_id not found in context.")],
            )

    db = ChatRoomDatabase()

    try:
        # Get room for role context
        room = db.get_room(room_id)
        agent_roles = room.agent_roles if room else {}

        tasks = db.get_tasks(room_id, status=status, owner=owner)

        if not tasks:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="No tasks found in this chatroom.",
                    ),
                ],
            )

        task_list = []
        for task in tasks:
            # Show owner with role if available
            if task.owner:
                owner_role = agent_roles.get(task.owner, "")
                owner_display = f"{task.owner}"
                if owner_role:
                    owner_display += f" ({owner_role[:30]}...)" if len(owner_role) > 30 else f" ({owner_role})"
            else:
                owner_display = "Unassigned"

            task_info = (
                f"- #{task.id} [{task.status}] {task.subject}\n"
                f"  Owner: {owner_display}\n"
                f"  Priority: {task.priority}\n"
            )
            if task.blocked_by:
                task_info += f"  Blocked by: {', '.join(f'#{t}' for t in task.blocked_by)}\n"
            if task.description:
                task_info += f"  Description: {task.description[:200]}...\n" if len(task.description) > 200 else f"  Description: {task.description}\n"
            task_list.append(task_info)

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="Tasks in chatroom:\n\n" + "\n".join(task_list),
                ),
            ],
        )
    except Exception as e:
        logger.error(f"Error listing tasks: {e}", exc_info=True)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error listing tasks: {str(e)}",
                ),
            ],
        )


async def task_create(
    subject: str,
    description: Optional[str] = None,
    owner: Optional[str] = None,
    priority: str = "medium",
    blocked_by: Optional[List[str]] = None,
    room_id: Optional[str] = None,
    created_by: Optional[str] = None,
) -> ToolResponse:
    """Create a new task in a chatroom (Backend API version with owner parameter).

    This function is for frontend/backend use. For LLM tool, use create_task instead.

    Args:
        subject: Task subject/title (short, e.g., "开发计算器 web 程序").
        description: Optional task description with details, deliverables, requirements.
        owner: Optional owner agent ID or name (who will handle this task).
            Supports both agent_id and agent_name, will auto-convert.
            If not specified, the task will be unassigned and can be claimed.
        priority: Task priority (low, medium, high). Default: medium.
        blocked_by: Optional list of task IDs this task depends on.
        room_id: The chatroom ID. If not provided, auto-detected from context.
        created_by: Optional agent ID who created the task. Auto-detected if not provided.

    Returns:
        ToolResponse: Created task information.
    """
    # Auto-detect room_id from context
    if room_id is None:
        room_id = _get_current_room_id()
        if not room_id:
            return ToolResponse(
                content=[TextBlock(type="text", text="Error: room_id not found in context.")],
            )

    # Auto-detect created_by from context
    if created_by is None:
        created_by = _get_current_agent_id() or "system"

    db = ChatRoomDatabase()

    try:
        # Verify chatroom exists
        room = db.get_room(room_id)
        if not room:
            return ToolResponse(
                content=[TextBlock(type="text", text=f"Error: ChatRoom '{room_id}' not found.")],
            )

        # Resolve owner (support both agent_id and agent_name)
        resolved_owner = None
        if owner:
            resolved_owner = _resolve_agent_id(room_id, owner)
            if resolved_owner is None:
                # List available agents for helpful error message
                available = []
                if room.lead_agent_id:
                    available.append(room.lead_agent_id)
                available.extend(room.agent_ids or [])
                return ToolResponse(
                    content=[TextBlock(
                        type="text",
                        text=f"Error: Agent '{owner}' not found in this chatroom.\nAvailable agents: {', '.join(available)}"
                    )],
                )

        task = Task(
            room_id=room_id,
            subject=subject,
            description=description,
            owner=resolved_owner,
            priority=priority,
            blocked_by=blocked_by or [],
            created_by=created_by,
        )

        created_task = db.create_task(task)

        owner_str = f"assigned to {resolved_owner}" if resolved_owner else "unassigned"
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=(
                        f"Task created successfully!\n\n"
                        f"ID: {created_task.id}\n"
                        f"Subject: {created_task.subject}\n"
                        f"Status: {created_task.status}\n"
                        f"Priority: {created_task.priority}\n"
                        f"Owner: {owner_str}"
                    ),
                ),
            ],
        )
    except Exception as e:
        logger.error(f"Error creating task: {e}", exc_info=True)
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Error creating task: {str(e)}")],
        )


async def create_task(
    subject: str,
    description: Optional[str] = None,
    priority: str = "medium",
) -> ToolResponse:
    """Create a new task in the current chatroom (LLM Tool).

    Use this tool when:
    - A user requests to execute a task (e.g., "开发一个计算器", "写一个测试")
    - You want to record work that needs to be done
    - Breaking down a large task into smaller subtasks

    The task will be created as "unassigned" and can be claimed by any team member.
    As a Leader, you can coordinate task assignment through team discussion.

    Args:
        subject: Task subject/title (short, e.g., "开发计算器 web 程序").
            Should be concise and clear.
        description: Optional task description with details, deliverables, requirements.
            Include any important context, acceptance criteria, or technical requirements.
        priority: Task priority: "low", "medium", or "high". Default: "medium".

    Returns:
        ToolResponse: Created task information including task ID.
    """
    # Delegate to task_create without owner parameter
    return await task_create(
        subject=subject,
        description=description,
        owner=None,  # Always unassigned for LLM tool
        priority=priority,
        blocked_by=None,
    )


async def task_update(
    task_id: str,
    status: Optional[str] = None,
    description: Optional[str] = None,
    progress: Optional[int] = None,
) -> ToolResponse:
    """Update task status and progress (LLM Tool).

    Use this tool to:
    - Report task progress during execution (progress: 0-100)
    - Mark task as completed when done (status: "completed")
    - Mark task as failed if cannot complete (status: "failed")
    - Update task description with current status or findings

    Args:
        task_id: The task ID to update.
        status: Optional new status:
            - "in_progress": You are actively working on this task
            - "completed": Task is fully done and verified
            - "failed": Task cannot be completed (explain in description)
        description: Optional updated description with current status or findings.
        progress: Optional progress value (0-100). Use to report execution progress.
            - 0: Just started
            - 50: Halfway done
            - 100: Fully complete (also auto-set when status="completed")

    Returns:
        ToolResponse: Updated task information.
    """
    db = ChatRoomDatabase()

    try:
        task = db.get_task(task_id)
        if not task:
            return ToolResponse(
                content=[TextBlock(type="text", text=f"Error: Task '{task_id}' not found.")],
            )

        # Track changes for log
        log_events = []

        # Update fields
        if status is not None:
            old_status = task.status
            task.status = status  # type: ignore
            if status == "completed" and not task.completed_at:
                task.completed_at = datetime.now()
            # Auto-set progress to 100 when completed
            if status == "completed":
                task.progress = 100
            log_events.append(f"Status: {old_status} -> {status}")

        if description is not None:
            task.description = description

        if progress is not None:
            old_progress = task.progress
            task.progress = max(0, min(100, progress))  # Clamp to 0-100
            log_events.append(f"Progress: {old_progress}% -> {task.progress}%")

        task.updated_at = datetime.now()

        updated_task = db.update_task(task)

        # Add log entry if there were changes
        if log_events:
            db.add_task_log_entry(task_id, "update", "; ".join(log_events))

        # Build response
        response_parts = [
            f"Task updated!",
            f"ID: {updated_task.id}",
            f"Subject: {updated_task.subject}",
            f"Status: {updated_task.status}",
            f"Progress: {updated_task.progress}%",
        ]

        if updated_task.description:
            desc_preview = updated_task.description[:200] + "..." if len(updated_task.description) > 200 else updated_task.description
            response_parts.append(f"Description: {desc_preview}")

        return ToolResponse(
            content=[TextBlock(type="text", text="\n".join(response_parts))],
        )
    except Exception as e:
        logger.error(f"Error updating task: {e}", exc_info=True)
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Error updating task: {str(e)}")],
        )


async def task_claim(
    task_id: str,
    agent_id: Optional[str] = None,
    check_agent_busy: bool = False,
) -> ToolResponse:
    """Claim a task (Backend API - set owner to the agent).

    This is a backend API for frontend use. Agent ID is auto-detected from context
    if not provided.

    Args:
        task_id: The task ID to claim.
        agent_id: The agent ID claiming the task. Auto-detected from context if not provided.
        check_agent_busy: If True, check if agent already has unfinished tasks.

    Returns:
        ToolResponse: Confirmation of task claim or detailed error message.
    """
    # Auto-detect agent_id from context
    if agent_id is None:
        agent_id = _get_current_agent_id()
        if not agent_id:
            return ToolResponse(
                content=[TextBlock(type="text", text="Error: agent_id not found in context.")],
            )

    db = ChatRoomDatabase()

    try:
        # Use atomic claim with comprehensive checks
        result = db.claim_task(
            task_id=task_id,
            agent_id=agent_id,
            check_agent_busy=check_agent_busy,
        )

        if not result.success:
            # Build detailed error message based on failure reason
            error_parts = [f"Error: Cannot claim task '{task_id}'."]

            if result.reason == 'task_not_found':
                error_parts.append("Task does not exist.")

            elif result.reason == 'already_claimed':
                current_owner = result.task.owner if result.task else "unknown"
                error_parts.append(f"Already claimed by '{current_owner}'.")
                error_parts.append("You cannot claim a task that is already assigned.")

            elif result.reason == 'already_resolved':
                error_parts.append("Task is already completed.")

            elif result.reason == 'blocked':
                if result.blocked_by_tasks:
                    blocked_list = ', '.join(f"#{t}" for t in result.blocked_by_tasks)
                    error_parts.append(f"Task is blocked by unresolved dependencies: {blocked_list}.")
                    error_parts.append("Complete the blocking tasks first, or ask another agent to handle them.")

            elif result.reason == 'agent_busy':
                if result.busy_with_tasks:
                    busy_list = ', '.join(f"#{t}" for t in result.busy_with_tasks)
                    error_parts.append(f"You already have unfinished tasks: {busy_list}.")
                    error_parts.append("Complete your current tasks before claiming new ones.")

            else:
                error_parts.append(f"Reason: {result.reason or 'unknown'}")

            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="\n".join(error_parts),
                    ),
                ],
            )

        # Success - update started_at and add log entry
        task = result.task
        if task:
            task.started_at = datetime.now()
            task.updated_at = datetime.now()
            db.update_task(task)
            db.add_task_log_entry(task_id, "started", f"Task claimed by {agent_id}")

        success_msg = [
            "Task claimed successfully!",
            "",
            f"Task ID: {task_id}",
            f"Subject: {task.subject if task else 'N/A'}",
            f"Claimed by: {agent_id}",
            f"Status: in_progress",
        ]

        if task and task.description:
            success_msg.append(f"Description: {task.description[:200]}...")

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="\n".join(success_msg),
                ),
            ],
        )

    except Exception as e:
        logger.error("Error claiming task: %s", e, exc_info=True)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error claiming task: {str(e)}",
                ),
            ],
        )


async def task_delete(task_id: str) -> ToolResponse:
    """Delete a task.

    Args:
        task_id: The task ID to delete.

    Returns:
        ToolResponse: Deletion confirmation.
    """
    db = ChatRoomDatabase()

    try:
        task = db.get_task(task_id)
        if not task:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: Task '{task_id}' not found.",
                    ),
                ],
            )

        db.delete_task(task_id)

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Task '{task_id}' deleted successfully.",
                ),
            ],
        )
    except Exception as e:
        logger.error(f"Error deleting task: {e}", exc_info=True)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error deleting task: {str(e)}",
                ),
            ],
        )


async def task_retry(
    task_id: str,
    reset_owner: bool = True,
) -> ToolResponse:
    """Retry a failed or cancelled task.

    Resets the task status to pending so it can be claimed again.
    Increments retry_count. Cannot retry tasks that have exceeded max_retries.

    Args:
        task_id: The task ID to retry.
        reset_owner: If True, clears the owner so task can be claimed by anyone.
                    If False, keeps the original owner (same agent retries).

    Returns:
        ToolResponse: Retry confirmation or error message.
    """
    db = ChatRoomDatabase()

    try:
        task = db.get_task(task_id)
        if not task:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: Task '{task_id}' not found.",
                    ),
                ],
            )

        # Can only retry failed or cancelled tasks
        if task.status not in ["failed", "cancelled"]:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: Cannot retry task '{task_id}' with status '{task.status}'. Only failed or cancelled tasks can be retried.",
                    ),
                ],
            )

        # Check retry limit
        if task.retry_count >= task.max_retries:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=(
                            f"Error: Task '{task_id}' has exceeded maximum retries "
                            f"({task.retry_count}/{task.max_retries}). "
                            f"Consider creating a new task or increasing max_retries."
                        ),
                    ),
                ],
            )

        # Reset task for retry
        task.status = "pending"  # type: ignore
        task.retry_count = task.retry_count + 1
        task.updated_at = datetime.now()
        task.completed_at = None
        task.progress = 0  # Reset progress
        task.started_at = None  # Reset started_at

        if reset_owner:
            task.owner = None

        updated_task = db.update_task(task)

        # Add log entry
        db.add_task_log_entry(task_id, "retry", f"Retry #{task.retry_count}/{task.max_retries}")

        # Check if task is blocked by other tasks
        blocked_by_msg = ""
        if task.blocked_by:
            # Check blocking tasks status
            blocking_tasks = []
            for bt_id in task.blocked_by:
                bt = db.get_task(bt_id)
                if bt and bt.status != "completed":
                    blocking_tasks.append(f"#{bt_id} ({bt.status})")
            if blocking_tasks:
                blocked_by_msg = f"\n⚠️ Warning: Task is still blocked by: {', '.join(blocking_tasks)}"

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=(
                        f"Task reset for retry!\n\n"
                        f"ID: {updated_task.id}\n"
                        f"Subject: {updated_task.subject}\n"
                        f"Status: pending (awaiting claim)\n"
                        f"Retry count: {updated_task.retry_count}/{updated_task.max_retries}\n"
                        f"Owner: {updated_task.owner or 'Unassigned (can be claimed)'}{blocked_by_msg}"
                    ),
                ),
            ],
        )
    except Exception as e:
        logger.error(f"Error retrying task: {e}", exc_info=True)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error retrying task: {str(e)}",
                ),
            ],
        )


async def task_set_auto_mode(
    task_id: str,
    auto_mode: bool,
) -> ToolResponse:
    """Set auto_mode flag for a task.

    When auto_mode is True, the agent working on this task should:
    - Act autonomously without asking intermediate questions
    - Make decisions on their best judgment
    - Only escalate when genuinely stuck after investigation
    - NOT use AskUserQuestion as a first response to friction

    Args:
        task_id: The task ID to update.
        auto_mode: True to enable auto mode, False to disable.

    Returns:
        ToolResponse: Confirmation message.
    """
    db = ChatRoomDatabase()

    try:
        task = db.get_task(task_id)
        if not task:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error: Task '{task_id}' not found.",
                    ),
                ],
            )

        task.auto_mode = auto_mode
        task.updated_at = datetime.now()

        updated_task = db.update_task(task)

        mode_desc = (
            "enabled - agent will act autonomously without asking intermediate questions"
            if auto_mode
            else "disabled - agent may ask for confirmation on uncertain decisions"
        )

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=(
                        f"Task auto_mode updated!\n\n"
                        f"ID: {updated_task.id}\n"
                        f"Subject: {updated_task.subject}\n"
                        f"Auto mode: {mode_desc}"
                    ),
                ),
            ],
        )
    except Exception as e:
        logger.error(f"Error setting auto_mode: {e}", exc_info=True)
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Error setting auto_mode: {str(e)}",
                ),
            ],
        )
