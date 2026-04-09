# -*- coding: utf-8 -*-
"""ChatRoom management API.

RESTful API for managing chatrooms and tasks.
"""
import logging
import re
import shortuuid
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from ..models.chatroom import (
    ChatRoom,
    CreateChatRoomRequest,
    CreateChatRoomResponse,
    ChatRoomDetail,
    UpdateChatRoomRequest,
    CreateTaskRequest,
    UpdateTaskRequest,
    Task,
    BatchTaskOperationRequest,
    BatchOperationResult,
)
from ..db.chatroom_db import ChatRoomDatabase
from ..chatroom_poll_service import get_poll_service

router = APIRouter(prefix="/chatroom", tags=["chatroom"])
logger = logging.getLogger(__name__)


def _get_db() -> ChatRoomDatabase:
    """Get ChatRoomDatabase instance."""
    return ChatRoomDatabase()


async def _verify_agent_exists(request: Request, agent_id: str) -> bool:
    """Verify that an agent exists in the system.

    Args:
        request: FastAPI request
        agent_id: Agent ID to verify

    Returns:
        True if agent exists, False otherwise
    """
    if not hasattr(request.app.state, "multi_agent_manager"):
        # If no manager, skip validation (for testing)
        return True

    manager = request.app.state.multi_agent_manager
    try:
        workspace = await manager.get_agent(agent_id)
        return workspace is not None
    except Exception:
        return False


async def _verify_agents_exist(request: Request, agent_ids: List[str]) -> List[str]:
    """Verify that multiple agents exist.

    Args:
        request: FastAPI request
        agent_ids: List of agent IDs to verify

    Returns:
        List of agent IDs that do NOT exist
    """
    missing = []
    for agent_id in agent_ids:
        if not await _verify_agent_exists(request, agent_id):
            missing.append(agent_id)
    return missing


async def _get_matrix_channel_for_agent(request: Request, agent_id: str):
    """Get Matrix channel for a specific agent.

    Args:
        request: FastAPI request
        agent_id: Agent ID to get Matrix channel for

    Returns:
        MatrixChannel instance or None if not configured
    """
    from ..multi_agent_manager import MultiAgentManager

    if not hasattr(request.app.state, "multi_agent_manager"):
        return None

    manager: MultiAgentManager = request.app.state.multi_agent_manager
    try:
        workspace = await manager.get_agent(agent_id)
        if not workspace:
            return None

        channel_manager = workspace.channel_manager
        if not channel_manager:
            return None

        # Find Matrix channel
        for ch in channel_manager.channels:
            if ch.channel == "matrix" and getattr(ch, "enabled", False):
                return ch
    except Exception as e:
        logger.warning(f"Failed to get Matrix channel for agent {agent_id}: {e}")

    return None


async def _get_matrix_user_ids_for_agents(
    request: Request,
    agent_ids: List[str],
) -> List[str]:
    """Get Matrix user IDs for a list of agents.

    Args:
        request: FastAPI request
        agent_ids: List of agent IDs

    Returns:
        List of Matrix user IDs (excluding None values)
    """
    from ..multi_agent_manager import MultiAgentManager

    if not hasattr(request.app.state, "multi_agent_manager"):
        return []

    manager: MultiAgentManager = request.app.state.multi_agent_manager
    matrix_user_ids = []

    for agent_id in agent_ids:
        try:
            workspace = await manager.get_agent(agent_id)
            if not workspace:
                continue

            channel_manager = workspace.channel_manager
            if not channel_manager:
                continue

            # Find Matrix channel and get user_id
            for ch in channel_manager.channels:
                if ch.channel == "matrix" and getattr(ch, "enabled", False):
                    user_id = getattr(ch, "user_id", None)
                    if user_id:
                        matrix_user_ids.append(user_id)
                    break
        except Exception as e:
            logger.warning(f"Failed to get Matrix user_id for agent {agent_id}: {e}")

    return matrix_user_ids


async def _create_matrix_room(
    matrix_channel,
    name: str,
    alias: Optional[str] = None,
    invite_users: Optional[List[str]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Create a new Matrix room.

    Args:
        matrix_channel: MatrixChannel instance
        name: Room name
        alias: Room alias (without # and server)
        invite_users: List of Matrix user IDs to invite

    Returns:
        Tuple of (room_id, room_alias) or (None, None) on failure
    """
    import shortuuid
    from nio import RoomPreset

    client = matrix_channel.client
    if not client:
        logger.error("Matrix client not initialized")
        return None, None

    try:
        # Generate alias if not provided
        if not alias:
            alias = f"chatroom-{shortuuid.uuid()[:8]}"
        else:
            # Sanitize user-provided alias: only allow [a-zA-Z0-9._=-]
            sanitized = re.sub(r'[^a-zA-Z0-9._=-]', '', alias).lower()
            # If sanitized result is empty or too short, generate a random one
            if len(sanitized) < 3:
                alias = f"chatroom-{shortuuid.uuid()[:8]}"
            else:
                alias = sanitized

        # Remove leading underscores (not allowed in some servers)
        alias = alias.lstrip('_')
        # Remove consecutive dashes and trailing dashes
        alias = re.sub(r'-+', '-', alias).strip('-')
        # Ensure alias is not empty after cleanup
        if not alias:
            alias = f"chatroom-{shortuuid.uuid()[:8]}"

        # Create room with invite list
        response = await client.room_create(
            name=name,
            alias=alias,
            preset=RoomPreset.private_chat,
            invite=invite_users or [],
        )

        room_id = getattr(response, "room_id", None)
        if room_id:
            # Build full alias
            homeserver = matrix_channel.homeserver
            # Extract server name from homeserver URL
            from urllib.parse import urlparse
            parsed = urlparse(homeserver)
            server_name = parsed.netloc
            # Remove port from server_name (server_name typically doesn't include port)
            if ":" in server_name:
                server_name = server_name.split(":")[0]
            full_alias = f"#{alias}:{server_name}"
            logger.info(f"Created Matrix room: {room_id}, alias: {full_alias}, invited: {invite_users}")
            return room_id, full_alias
    except Exception as e:
        logger.error(f"Failed to create Matrix room: {e}")

    return None, None


async def _resolve_matrix_room_alias(matrix_channel, alias: str) -> Optional[str]:
    """Resolve a Matrix room alias to room_id.

    Args:
        matrix_channel: MatrixChannel instance
        alias: Full room alias (e.g., "#room:server")

    Returns:
        Room ID or None if not found
    """
    client = matrix_channel.client
    if not client:
        logger.error("Matrix client not initialized")
        return None

    try:
        response = await client.room_resolve_alias(alias)
        room_id = getattr(response, "room_id", None)
        if room_id:
            logger.info(f"Resolved Matrix alias {alias} -> {room_id}")
            return room_id
    except Exception as e:
        logger.error(f"Failed to resolve Matrix alias {alias}: {e}")

    return None


# ========== ChatRoom CRUD ==========

@router.post(
    "",
    response_model=CreateChatRoomResponse,
    status_code=201,
    summary="Create a chatroom",
    description="Create a new chatroom with lead agent and worker agents",
)
async def create_chatroom(
    http_request: Request,
    request: CreateChatRoomRequest,
) -> CreateChatRoomResponse:
    """Create a new chatroom.

    Supports Matrix room integration:
    - matrix_mode="none": No Matrix room (default)
    - matrix_mode="create_new": Create a new Matrix room
    - matrix_mode="link_existing": Link to existing Matrix room by alias
    """
    db = _get_db()

    # Verify agents exist
    all_agent_ids = []
    if request.lead_agent_id:
        all_agent_ids.append(request.lead_agent_id)
    if request.agent_ids:
        all_agent_ids.extend(request.agent_ids)

    missing_agents = await _verify_agents_exist(http_request, all_agent_ids)
    if missing_agents:
        raise HTTPException(
            status_code=400,
            detail=f"Agent(s) not found: {', '.join(missing_agents)}"
        )

    room = ChatRoom(
        name=request.name,
        user_id="default",  # Set default user_id
        lead_agent_id=request.lead_agent_id,
        agent_ids=request.agent_ids or [],
        layout=request.layout or "tiles",  # type: ignore
    )

    # Handle Matrix room integration
    matrix_room_id = None
    matrix_alias = None
    matrix_error = None
    matrix_warning = None

    if request.matrix_mode != "none" and request.lead_agent_id:
        matrix_channel = await _get_matrix_channel_for_agent(
            http_request, request.lead_agent_id
        )

        if not matrix_channel:
            raise HTTPException(
                status_code=400,
                detail=f"Matrix channel not configured for lead agent '{request.lead_agent_id}'. "
                       f"Please enable Matrix channel for this agent first.",
            )

        # Get all agent Matrix user IDs to invite
        all_agent_ids = [request.lead_agent_id] + (request.agent_ids or [])
        # Remove duplicates
        all_agent_ids = list(dict.fromkeys(all_agent_ids))
        matrix_user_ids = await _get_matrix_user_ids_for_agents(
            http_request, all_agent_ids
        )

        # Check if all agents have Matrix configured
        agents_without_matrix = []
        for agent_id in all_agent_ids:
            matrix_channel_for_agent = await _get_matrix_channel_for_agent(
                http_request, agent_id
            )
            if not matrix_channel_for_agent:
                agents_without_matrix.append(agent_id)

        if agents_without_matrix:
            matrix_warning = (
                f"Some agents do not have Matrix channel configured: {', '.join(agents_without_matrix)}. "
                f"They will not be invited to the Matrix room."
            )

        # Remove the creator's own user_id (they're already in the room)
        creator_user_id = getattr(matrix_channel, "user_id", None)
        if creator_user_id and creator_user_id in matrix_user_ids:
            matrix_user_ids.remove(creator_user_id)

        if request.matrix_mode == "create_new":
            # Create new Matrix room with all agents invited
            matrix_room_id, matrix_alias = await _create_matrix_room(
                matrix_channel,
                name=request.name,
                alias=request.matrix_alias,
                invite_users=matrix_user_ids,
            )
            if not matrix_room_id:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create Matrix room. Please check Matrix server connection and try again.",
                )

        elif request.matrix_mode == "link_existing" and request.matrix_alias:
            # Link to existing Matrix room by alias
            matrix_room_id = await _resolve_matrix_room_alias(
                matrix_channel, request.matrix_alias
            )
            if not matrix_room_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to resolve Matrix room alias '{request.matrix_alias}'. "
                           f"Please check the alias is correct and the room exists.",
                )

            matrix_alias = request.matrix_alias
            # Ensure the creator joins the room
            try:
                await matrix_channel.client.join(matrix_room_id)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to join Matrix room '{matrix_alias}': {str(e)}",
                )

            # Invite all other agents to the room
            failed_invites = []
            for user_id in matrix_user_ids:
                try:
                    await matrix_channel.client.room_invite(
                        room_id=matrix_room_id,
                        user_id=user_id,
                    )
                    logger.info(f"Invited {user_id} to Matrix room {matrix_room_id}")
                except Exception as e:
                    logger.warning(f"Failed to invite {user_id} to Matrix room: {e}")
                    failed_invites.append(user_id)

            if failed_invites:
                matrix_warning = (
                    f"Failed to invite some users to Matrix room: {', '.join(failed_invites)}. "
                    f"They may need to join manually."
                )

        # Update room with Matrix info
        if matrix_room_id:
            room.matrix_room_id = matrix_room_id
            room.matrix_alias = matrix_alias

    created_room = db.create_room(room)

    return CreateChatRoomResponse(
        room=created_room,
        message="ChatRoom created successfully",
        matrix_error=matrix_error,
        matrix_warning=matrix_warning,
    )


@router.get(
    "",
    response_model=List[ChatRoom],
    summary="List chatrooms",
    description="List all chatrooms for a user",
)
async def list_chatrooms(
    user_id: str = Query(default="default", description="User ID"),
) -> List[ChatRoom]:
    """List all chatrooms."""
    db = _get_db()
    return db.list_rooms(user_id=user_id)


@router.get(
    "/{room_id}",
    response_model=ChatRoomDetail,
    summary="Get chatroom detail",
    description="Get detailed information about a chatroom",
)
async def get_chatroom(
    room_id: str,
    request: Request,
) -> ChatRoomDetail:
    """Get a chatroom by ID."""
    db = _get_db()

    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    # Get tasks for the room
    tasks = db.get_tasks(room_id)

    return ChatRoomDetail(
        **room.model_dump(),
        tasks=tasks,
    )


@router.put(
    "/{room_id}",
    response_model=ChatRoom,
    summary="Update a chatroom",
    description="Update chatroom configuration",
)
async def update_chatroom(
    room_id: str,
    request: UpdateChatRoomRequest,
) -> ChatRoom:
    """Update a chatroom."""
    db = _get_db()

    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    # Update fields that are provided
    if request.name is not None:
        room.name = request.name
    if request.lead_agent_id is not None:
        room.lead_agent_id = request.lead_agent_id
    if request.agent_ids is not None:
        room.agent_ids = request.agent_ids
    if request.agent_roles is not None:
        room.agent_roles = request.agent_roles
    if request.sessions is not None:
        room.sessions = request.sessions
    if request.layout is not None:
        room.layout = request.layout  # type: ignore
    if request.matrix_room_id is not None:
        room.matrix_room_id = request.matrix_room_id
    if request.matrix_alias is not None:
        room.matrix_alias = request.matrix_alias

    room.updated_at = datetime.now()

    return db.update_room(room)


@router.delete(
    "/{room_id}",
    summary="Delete a chatroom",
    description="Delete a chatroom (cascade deletes tasks and messages)",
)
async def delete_chatroom(
    room_id: str,
    http_request: Request,
) -> dict:
    """Delete a chatroom."""
    db = _get_db()

    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    # Get all agents in this room before deletion
    agent_ids = []
    if room.lead_agent_id:
        agent_ids.append(room.lead_agent_id)
    if room.agent_ids:
        agent_ids.extend(room.agent_ids)

    # Delete from database
    db.delete_room(room_id)

    # Unregister agents from poll service
    poll_service = get_poll_service()
    if poll_service:
        for agent_id in agent_ids:
            await poll_service.unregister_agent(agent_id, room_id)
        logger.info(
            "[DEBUG] Deleted chatroom %s, unregistered %d agents from poll service",
            room_id,
            len(agent_ids),
        )

    return {"success": True, "message": "ChatRoom deleted"}


# ========== Task Management ==========

@router.get(
    "/{room_id}/tasks",
    response_model=List[Task],
    summary="List tasks",
    description="List tasks in a chatroom, optionally filtered by status or owner",
)
async def list_tasks(
    room_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    owner: Optional[str] = Query(None, description="Filter by owner agent"),
) -> List[Task]:
    """List tasks in a chatroom."""
    db = _get_db()

    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    return db.get_tasks(room_id, status=status, owner=owner)


@router.post(
    "/{room_id}/tasks",
    response_model=Task,
    status_code=201,
    summary="Create a task",
    description="Create a new task in a chatroom",
)
async def create_task(
    http_request: Request,
    room_id: str,
    request: CreateTaskRequest,
) -> Task:
    """Create a new task."""
    db = _get_db()

    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    # Verify owner exists if specified
    if request.owner:
        if not await _verify_agent_exists(http_request, request.owner):
            raise HTTPException(
                status_code=400,
                detail=f"Agent not found: {request.owner}"
            )

    task = Task(
        room_id=room_id,
        subject=request.subject,
        description=request.description,
        owner=request.owner,
        priority=request.priority,
        blocked_by=request.blocked_by,
        auto_mode=request.auto_mode,
        max_retries=request.max_retries,
        timeout_minutes=request.timeout_minutes,
        source_session_id=request.source_session_id,
        source_message_id=request.source_message_id,
        created_by="system",  # TODO: get from auth context
    )

    return db.create_task(task)


# ========== Static Task Routes (must be before /{task_id}) ==========

# Import for export functionality
from fastapi.responses import StreamingResponse
import io
import csv

class BatchOperationResult(BaseModel):
    """Result of batch task operation"""
    success_count: int
    failed_count: int
    failed_tasks: List[Dict[str, str]] = []  # [{task_id, reason}]

@router.post(
    "/{room_id}/tasks/batch",
    response_model=BatchOperationResult,
    summary="Batch task operations",
    description="Perform batch operations on multiple tasks",
)
async def batch_task_operation(
    room_id: str,
    request: BatchTaskOperationRequest,
) -> BatchOperationResult:
    """Perform batch operations on multiple tasks.

    Supported operations:
    - cancel: Cancel tasks with optional reason
    - delete: Delete tasks
    - assign: Assign tasks to an owner
    - set_status: Update task status
    - set_priority: Update task priority
    """
    db = _get_db()

    # Verify room exists
    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    success_count = 0
    failed_tasks = []

    for task_id in request.task_ids:
        try:
            task = db.get_task(task_id)
            if not task:
                failed_tasks.append({"task_id": task_id, "reason": "Task not found"})
                continue

            if task.room_id != room_id:
                failed_tasks.append({"task_id": task_id, "reason": "Task not in this chatroom"})
                continue

            if request.operation == "cancel":
                if task.status == "completed":
                    failed_tasks.append({"task_id": task_id, "reason": "Cannot cancel completed task"})
                    continue
                if task.status == "cancelled":
                    failed_tasks.append({"task_id": task_id, "reason": "Task already cancelled"})
                    continue
                task.status = "cancelled"  # type: ignore
                task.updated_at = datetime.now()
                if request.reason:
                    task.description = (task.description or "") + f"\n[Cancelled: {request.reason}]"
                db.update_task(task)

            elif request.operation == "delete":
                db.delete_task(task_id)

            elif request.operation == "assign":
                if not request.owner:
                    failed_tasks.append({"task_id": task_id, "reason": "Owner required for assign operation"})
                    continue
                task.owner = request.owner
                task.updated_at = datetime.now()
                db.update_task(task)

            elif request.operation == "set_status":
                if not request.status:
                    failed_tasks.append({"task_id": task_id, "reason": "Status required for set_status operation"})
                    continue
                if request.status not in ["pending", "in_progress", "completed", "failed", "cancelled"]:
                    failed_tasks.append({"task_id": task_id, "reason": f"Invalid status: {request.status}"})
                    continue
                task.status = request.status  # type: ignore
                task.updated_at = datetime.now()
                if request.status == "completed" and not task.completed_at:
                    task.completed_at = datetime.now()
                db.update_task(task)

            elif request.operation == "set_priority":
                if not request.priority:
                    failed_tasks.append({"task_id": task_id, "reason": "Priority required for set_priority operation"})
                    continue
                if request.priority not in ["low", "medium", "high"]:
                    failed_tasks.append({"task_id": task_id, "reason": f"Invalid priority: {request.priority}"})
                    continue
                task.priority = request.priority  # type: ignore
                task.updated_at = datetime.now()
                db.update_task(task)

            else:
                failed_tasks.append({"task_id": task_id, "reason": f"Unknown operation: {request.operation}"})
                continue

            success_count += 1

        except Exception as e:
            failed_tasks.append({"task_id": task_id, "reason": str(e)})

    return BatchOperationResult(
        success_count=success_count,
        failed_count=len(failed_tasks),
        failed_tasks=failed_tasks,
    )

@router.get(
    "/{room_id}/tasks/export",
    summary="Export tasks",
    description="Export tasks in CSV or JSON format",
)
async def export_tasks(
    room_id: str,
    format: str = Query("csv", description="Export format: csv or json"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> StreamingResponse:
    """Export tasks in CSV or JSON format."""
    db = _get_db()

    # Verify room exists
    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    tasks = db.get_tasks(room_id, status=status)

    if format == "json":
        import json
        content = json.dumps(
            [task.model_dump() for task in tasks],
            indent=2,
            default=str,
        )
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=tasks_{room_id}.json"
            },
        )

    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "ID", "Subject", "Status", "Owner", "Priority",
            "Progress", "Dependencies", "Created", "Updated", "Completed"
        ])

        # Rows
        for task in tasks:
            writer.writerow([
                task.id,
                task.subject,
                task.status,
                task.owner or "",
                task.priority,
                task.progress,
                f"blocked_by: {task.blocked_by}, blocks: {task.blocks}",
                task.created_at.isoformat() if task.created_at else "",
                task.updated_at.isoformat() if task.updated_at else "",
                task.completed_at.isoformat() if task.completed_at else "",
            ])

        output.seek(0)
        return StreamingResponse(
            io.StringIO(output.getvalue()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=tasks_{room_id}.csv"
            },
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

@router.get(
    "/{room_id}/tasks/timeout",
    response_model=List[Task],
    summary="Get timed out tasks",
    description="Get tasks that have exceeded their timeout threshold",
)
async def get_timeout_tasks(
    room_id: str,
) -> List[Task]:
    """Get tasks that have exceeded their timeout threshold."""
    db = _get_db()

    # Verify room exists
    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    # Get timed out tasks
    all_timed_out = db.get_timed_out_tasks()

    # Filter by room_id
    return [t for t in all_timed_out if t.room_id == room_id]


# ========== Dynamic Task Routes (/{task_id}) ==========

@router.get(
    "/{room_id}/tasks/{task_id}",
    response_model=Task,
    summary="Get a task",
    description="Get details of a specific task",
)
async def get_task(
    room_id: str,
    task_id: str,
) -> Task:
    """Get a task by ID."""
    db = _get_db()

    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.room_id != room_id:
        raise HTTPException(status_code=400, detail="Task does not belong to this chatroom")

    return task


@router.put(
    "/{room_id}/tasks/{task_id}",
    response_model=Task,
    summary="Update a task",
    description="Update task information",
)
async def update_task(
    room_id: str,
    task_id: str,
    request: UpdateTaskRequest,
) -> Task:
    """Update a task."""
    db = _get_db()

    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.room_id != room_id:
        raise HTTPException(status_code=400, detail="Task does not belong to this chatroom")

    # Update fields that are provided
    if request.status is not None:
        task.status = request.status  # type: ignore
        if request.status == "completed" and not task.completed_at:
            task.completed_at = datetime.now()
            task.progress = 100  # Auto-set progress to 100% on completion
        if request.status == "in_progress" and not task.started_at:
            task.started_at = datetime.now()
    if request.owner is not None:
        task.owner = request.owner
    if request.description is not None:
        task.description = request.description
    if request.auto_mode is not None:
        task.auto_mode = request.auto_mode
    if request.max_retries is not None:
        task.max_retries = request.max_retries
    if request.progress is not None:
        task.progress = max(0, min(100, request.progress))  # Clamp to 0-100

    task.updated_at = datetime.now()

    return db.update_task(task)


class CancelTaskRequest(BaseModel):
    """Request model for cancelling a task"""
    reason: Optional[str] = None
    cancelled_by: Optional[str] = None


@router.post(
    "/{room_id}/tasks/{task_id}/cancel",
    response_model=Task,
    summary="Cancel a task",
    description="Cancel a task that is pending, in progress, or failed",
)
async def cancel_task(
    room_id: str,
    task_id: str,
    request: CancelTaskRequest,
) -> Task:
    """Cancel a task.

    Can cancel tasks in pending, in_progress, or failed status.
    Cannot cancel already completed or cancelled tasks.
    """
    db = _get_db()

    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.room_id != room_id:
        raise HTTPException(status_code=400, detail="Task does not belong to this chatroom")

    if task.status == "completed":
        raise HTTPException(status_code=400, detail="Cannot cancel a completed task")

    if task.status == "cancelled":
        raise HTTPException(status_code=400, detail="Task is already cancelled")

    # If task is in_progress, try to stop any active execution
    if task.status == "in_progress" and task.owner:
        poll_service = get_poll_service()
        if poll_service:
            await poll_service.cancel_active_execution(
                room_id=room_id,
                agent_id=task.owner,  # Use task owner as agent_id
            )

    # Update status to cancelled
    task.status = "cancelled"  # type: ignore
    task.owner = None  # Clear owner on cancellation
    task.updated_at = datetime.now()

    # Add cancellation info to description
    cancellation_info = f"\n[Cancelled by {request.cancelled_by or 'system'} at {datetime.now().isoformat()}]"
    if request.reason:
        cancellation_info += f" Reason: {request.reason}"
    if task.description:
        task.description = task.description + cancellation_info
    else:
        task.description = cancellation_info.strip()

    return db.update_task(task)


class RetryTaskRequest(BaseModel):
    """Request model for retrying a task"""
    reset_owner: bool = True  # If True, clears owner so anyone can claim


@router.post(
    "/{room_id}/tasks/{task_id}/retry",
    response_model=Task,
    summary="Retry a failed or cancelled task",
    description="Reset a failed or cancelled task to pending for retry",
)
async def retry_task(
    room_id: str,
    task_id: str,
    request: RetryTaskRequest,
) -> Task:
    """Retry a failed or cancelled task.

    Resets task status to pending and increments retry_count.
    Cannot retry if max_retries has been reached.
    """
    db = _get_db()

    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.room_id != room_id:
        raise HTTPException(status_code=400, detail="Task does not belong to this chatroom")

    if task.status not in ["failed", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry task with status '{task.status}'. Only failed or cancelled tasks can be retried."
        )

    if task.retry_count >= task.max_retries:
        raise HTTPException(
            status_code=400,
            detail=f"Task has exceeded maximum retries ({task.retry_count}/{task.max_retries})"
        )

    # Reset task for retry
    task.status = "pending"  # type: ignore
    task.retry_count = task.retry_count + 1
    task.updated_at = datetime.now()
    task.completed_at = None

    if request.reset_owner:
        task.owner = None

    return db.update_task(task)


class SetAutoModeRequest(BaseModel):
    """Request model for setting auto_mode"""
    auto_mode: bool


@router.post(
    "/{room_id}/tasks/{task_id}/auto-mode",
    response_model=Task,
    summary="Set task auto_mode",
    description="Enable or disable auto_mode for a task",
)
async def set_task_auto_mode(
    room_id: str,
    task_id: str,
    request: SetAutoModeRequest,
) -> Task:
    """Set auto_mode flag for a task.

    When auto_mode is True, the agent working on this task should:
    - Act autonomously without asking intermediate questions
    - Make decisions on their best judgment
    - Only escalate when genuinely stuck after investigation
    """
    db = _get_db()

    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.room_id != room_id:
        raise HTTPException(status_code=400, detail="Task does not belong to this chatroom")

    task.auto_mode = request.auto_mode
    task.updated_at = datetime.now()

    return db.update_task(task)


@router.delete(
    "/{room_id}/tasks/{task_id}",
    summary="Delete a task",
    description="Delete a task",
)
async def delete_task(
    room_id: str,
    task_id: str,
) -> dict:
    """Delete a task."""
    db = _get_db()

    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.room_id != room_id:
        raise HTTPException(status_code=400, detail="Task does not belong to this chatroom")

    db.delete_task(task_id)

    return {"success": True, "message": "Task deleted"}


# ========== Task Log Management ==========

from ..models.chatroom import TaskLogEntry


@router.post(
    "/{room_id}/tasks/{task_id}/log",
    response_model=Task,
    summary="Add task log entry",
    description="Add an execution log entry to a task",
)
async def add_task_log(
    room_id: str,
    task_id: str,
    request: TaskLogEntry,
) -> Task:
    """Add an execution log entry to a task.

    Used to track task execution progress and events.
    """
    db = _get_db()

    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.room_id != room_id:
        raise HTTPException(status_code=400, detail="Task does not belong to this chatroom")

    # Add log entry
    db.add_task_log_entry(task_id, request.event, request.details)

    # Return updated task
    updated_task = db.get_task(task_id)
    if not updated_task:
        raise HTTPException(status_code=500, detail="Failed to get updated task")

    return updated_task


# ========== Real-time Updates via SSE ==========

from fastapi.responses import StreamingResponse as SSEStreamingResponse
import asyncio

# Store active SSE connections
_sse_connections: Dict[str, List[asyncio.Queue]] = {}


async def _broadcast_task_update(room_id: str, task: Task) -> None:
    """Broadcast task update to all connected SSE clients for a room."""
    if room_id not in _sse_connections:
        return

    import json
    message = json.dumps({
        "type": "task_update",
        "room_id": room_id,
        "task": task.model_dump(),
    }, default=str)

    for queue in _sse_connections.get(room_id, []):
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            pass


@router.get(
    "/{room_id}/events",
    summary="Subscribe to task events",
    description="Server-Sent Events endpoint for real-time task updates",
)
async def subscribe_task_events(
    room_id: str,
) -> SSEStreamingResponse:
    """Subscribe to real-time task updates via Server-Sent Events."""
    db = _get_db()

    # Verify room exists
    room = db.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="ChatRoom not found")

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        if room_id not in _sse_connections:
            _sse_connections[room_id] = []
        _sse_connections[room_id].append(queue)

        try:
            # Send initial connection message
            yield f"event: connected\ndata: {{\"room_id\": \"{room_id}\"}}\n\n"

            while True:
                try:
                    # Wait for messages with timeout
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: task_update\ndata: {message}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"event: keepalive\ndata: {{\"time\": \"{datetime.now().isoformat()}\"}}\n\n"

        except asyncio.CancelledError:
            # Clean up on disconnect
            if room_id in _sse_connections:
                try:
                    _sse_connections[room_id].remove(queue)
                    if not _sse_connections[room_id]:
                        del _sse_connections[room_id]
                except ValueError:
                    pass
            raise

    return SSEStreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ========== Matrix Room Integration ==========


class MatrixConfigResponse(BaseModel):
    """Matrix configuration for an agent"""
    enabled: bool = False
    homeserver: str = ""
    user_id: str = ""
    access_token: str = ""


@router.get(
    "/agents/{agent_id}/matrix-config",
    response_model=MatrixConfigResponse,
    summary="Get agent Matrix config",
    description="Get Matrix channel configuration for a specific agent",
)
async def get_agent_matrix_config(
    http_request: Request,
    agent_id: str,
) -> MatrixConfigResponse:
    """Get Matrix channel configuration for an agent.

    Returns Matrix server URL, user ID, and access token for iframe integration.
    """
    matrix_channel = await _get_matrix_channel_for_agent(http_request, agent_id)

    if not matrix_channel:
        return MatrixConfigResponse(enabled=False)

    # Check if channel has valid configuration
    homeserver = getattr(matrix_channel, "homeserver", "")
    user_id = getattr(matrix_channel, "user_id", "")
    access_token = getattr(matrix_channel, "access_token", "")

    # Only return enabled=True if all required fields are present
    if not homeserver or not user_id or not access_token:
        return MatrixConfigResponse(enabled=False)

    return MatrixConfigResponse(
        enabled=getattr(matrix_channel, "enabled", False),
        homeserver=homeserver,
        user_id=user_id,
        access_token=access_token,
    )


# ========== Poll Service Management ==========


class PollServiceStatus(BaseModel):
    """Poll service status response."""
    running: bool
    registered_agents: List[str]
    agent_rooms: Dict[str, List[str]]
    poll_intervals: Dict[str, int]
    active_tasks: List[str]


@router.get(
    "/poll-service/status",
    response_model=PollServiceStatus,
    summary="Get poll service status",
    description="Get the current status of the ChatRoom poll service",
)
async def get_poll_service_status(
    http_request: Request,
) -> PollServiceStatus:
    """Get the status of the ChatRoom poll service.

    Returns information about which agents are being polled and their rooms.
    """
    poll_service = getattr(http_request.app.state, "chatroom_poll_service", None)

    if not poll_service:
        logger.info("[DEBUG] /poll-service/status: poll_service not found in app.state")
        return PollServiceStatus(
            running=False,
            registered_agents=[],
            agent_rooms={},
            poll_intervals={},
            active_tasks=[],
        )

    status = poll_service.get_status()
    # DEBUG: Log poll service status
    db_path = getattr(poll_service._db, "db_path", "unknown")
    logger.info(
        "[DEBUG] /poll-service/status: db_path=%s, running=%s, agent_rooms=%s",
        db_path,
        status["running"],
        status["agent_rooms"],
    )
    return PollServiceStatus(**status)


@router.post(
    "/poll-service/cleanup",
    summary="Clean up stale room references",
    description="Remove non-existent chatrooms from poll service tracking",
)
async def cleanup_poll_service(
    http_request: Request,
) -> dict:
    """Clean up stale room references from poll service.

    This removes references to deleted chatrooms from the poll service's
    internal tracking, preventing errors when agents try to poll non-existent rooms.
    """
    poll_service = getattr(http_request.app.state, "chatroom_poll_service", None)

    if not poll_service:
        raise HTTPException(
            status_code=503,
            detail="Poll service not available",
        )

    # DEBUG: Log before cleanup
    db_path = getattr(poll_service._db, "db_path", "unknown")
    before_status = poll_service.get_status()
    logger.info(
        "[DEBUG] /poll-service/cleanup BEFORE: db_path=%s, agent_rooms=%s",
        db_path,
        before_status["agent_rooms"],
    )

    removed_count = poll_service.cleanup_stale_rooms()

    # DEBUG: Log after cleanup
    after_status = poll_service.get_status()
    logger.info(
        "[DEBUG] /poll-service/cleanup AFTER: removed_count=%s, agent_rooms=%s",
        removed_count,
        after_status["agent_rooms"],
    )

    return {
        "success": True,
        "removed_count": removed_count,
        "message": f"Cleaned up {removed_count} stale room references",
    }


class RegisterPollRequest(BaseModel):
    """Request to register an agent for polling."""
    agent_id: str
    room_id: str
    poll_interval: Optional[int] = None


@router.post(
    "/poll-service/register",
    summary="Register agent for polling",
    description="Register an agent to be polled for tasks and messages in a chatroom",
)
async def register_agent_poll(
    http_request: Request,
    request: RegisterPollRequest,
) -> dict:
    """Register an agent for polling in a chatroom.

    The agent will be polled for tasks and messages at the specified interval.
    """
    poll_service = getattr(http_request.app.state, "chatroom_poll_service", None)

    if not poll_service:
        raise HTTPException(
            status_code=503,
            detail="Poll service not available",
        )

    await poll_service.register_agent(
        agent_id=request.agent_id,
        room_id=request.room_id,
        poll_interval=request.poll_interval,
    )

    return {
        "success": True,
        "message": f"Agent {request.agent_id} registered for polling in room {request.room_id}",
    }


@router.delete(
    "/poll-service/register/{agent_id}/{room_id}",
    summary="Unregister agent from polling",
    description="Remove an agent from polling in a specific chatroom",
)
async def unregister_agent_poll(
    http_request: Request,
    agent_id: str,
    room_id: str,
) -> dict:
    """Unregister an agent from polling in a chatroom."""
    poll_service = getattr(http_request.app.state, "chatroom_poll_service", None)

    if not poll_service:
        raise HTTPException(
            status_code=503,
            detail="Poll service not available",
        )

    await poll_service.unregister_agent(
        agent_id=agent_id,
        room_id=room_id,
    )

    return {
        "success": True,
        "message": f"Agent {agent_id} unregistered from polling in room {room_id}",
    }
