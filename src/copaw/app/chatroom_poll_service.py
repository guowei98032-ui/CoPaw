# -*- coding: utf-8 -*-
"""ChatRoom Poll Service - Background service for auto-polling tasks.

This service runs in the background and polls for:
- Pending tasks assigned to agents in chatrooms
- Unassigned tasks that can be claimed

When work is found, it triggers the agent to process it.
"""
import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from .db.chatroom_db import ChatRoomDatabase
from .multi_agent_manager import MultiAgentManager

logger = logging.getLogger(__name__)

# Global reference to the poll service (set during app startup)
_poll_service_instance: Optional["ChatRoomPollService"] = None


def get_poll_service() -> Optional["ChatRoomPollService"]:
    """Get the global poll service instance.

    Returns:
        The ChatRoomPollService instance or None if not initialized.
    """
    return _poll_service_instance


def set_poll_service(service: Optional["ChatRoomPollService"]) -> None:
    """Set the global poll service instance.

    Called during app startup/shutdown.

    Args:
        service: The ChatRoomPollService instance or None to clear.
    """
    global _poll_service_instance
    _poll_service_instance = service


@dataclass
class PollResult:
    """Result of a single poll operation."""

    agent_id: str
    room_id: str
    room_name: str = ""
    agent_role: str = ""  # This agent's role description in the chatroom
    team_roles: Dict[str, str] = field(default_factory=dict)  # All team members' roles
    matrix_room_id: Optional[str] = None  # Matrix room ID for forwarding messages
    is_lead: bool = False  # Whether this agent is the lead agent
    has_work: bool = False
    tasks: List[Dict[str, Any]] = field(default_factory=list)


class ChatRoomPollService:
    """Background service for polling ChatRoom tasks.

    Each agent configured in chatrooms gets its own polling task that:
    1. Polls for tasks assigned to the agent
    2. Polls for unassigned tasks
    3. Triggers agent execution when there's work to do

    The service is designed to be non-blocking and runs independently
    from the main request handling flow.
    """

    def __init__(
        self,
        multi_agent_manager: MultiAgentManager,
        default_poll_interval: int = 30,
    ):
        """Initialize the poll service.

        Args:
            multi_agent_manager: Manager for accessing agent workspaces
            default_poll_interval: Default polling interval in seconds
        """
        self._manager = multi_agent_manager
        self._default_interval = default_poll_interval
        self._db = ChatRoomDatabase()
        self._running = False
        self._poll_tasks: Dict[str, asyncio.Task] = {}
        self._agent_intervals: Dict[str, int] = {}
        self._agent_rooms: Dict[str, Set[str]] = {}  # agent_id -> set of room_ids
        self._last_trigger: Dict[str, datetime] = {}  # agent_id -> last trigger time
        self._lock = asyncio.Lock()
        # Track active executions: task_id -> {agent_id, room_id, chat_id, asyncio.Task}
        self._active_executions: Dict[str, Dict[str, Any]] = {}
        # DEBUG: Log database path and initial state
        logger.info(
            "ChatRoomPollService initialized with interval=%ds, db_path=%s",
            default_poll_interval,
            self._db.db_path,
        )

    async def start(self) -> None:
        """Start the polling service."""
        if self._running:
            logger.warning("ChatRoomPollService already running")
            return

        self._running = True
        logger.info("[DEBUG] ChatRoomPollService starting, db_path=%s", self._db.db_path)

        # Initial discovery of agents in chatrooms
        await self._discover_agents()

        # Start the discovery task (periodically check for new agents)
        self._discovery_task = asyncio.create_task(self._discovery_loop())

        logger.info(
            "[DEBUG] ChatRoomPollService started, initial agent_rooms: %s",
            {aid: list(rooms) for aid, rooms in self._agent_rooms.items()},
        )

    async def stop(self) -> None:
        """Stop the polling service."""
        self._running = False

        # Cancel discovery task
        if hasattr(self, "_discovery_task"):
            self._discovery_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._discovery_task

        # Cancel all poll tasks
        for task in self._poll_tasks.values():
            task.cancel()

        # Wait for all tasks to complete
        if self._poll_tasks:
            await asyncio.gather(*self._poll_tasks.values(), return_exceptions=True)

        self._poll_tasks.clear()
        self._agent_rooms.clear()
        logger.info("ChatRoomPollService stopped")

    async def register_agent(
        self,
        agent_id: str,
        room_id: str,
        poll_interval: Optional[int] = None,
    ) -> None:
        """Register an agent for polling in a specific chatroom.

        Args:
            agent_id: The agent ID to register
            room_id: The chatroom ID the agent is in
            poll_interval: Optional custom poll interval for this agent
        """
        async with self._lock:
            # Track rooms for this agent
            if agent_id not in self._agent_rooms:
                self._agent_rooms[agent_id] = set()
            self._agent_rooms[agent_id].add(room_id)

            # Set custom interval if provided
            if poll_interval:
                self._agent_intervals[agent_id] = poll_interval

            # Start poll task if not already running for this agent
            key = f"poll:{agent_id}"
            if key not in self._poll_tasks and self._running:
                self._poll_tasks[key] = asyncio.create_task(
                    self._poll_loop(agent_id)
                )
                logger.info(
                    "Registered poll task for agent %s in room %s",
                    agent_id,
                    room_id,
                )

    async def unregister_agent(self, agent_id: str, room_id: str) -> None:
        """Unregister an agent from a specific chatroom.

        Args:
            agent_id: The agent ID to unregister
            room_id: The chatroom ID to remove
        """
        async with self._lock:
            if agent_id in self._agent_rooms:
                self._agent_rooms[agent_id].discard(room_id)

                # If agent has no more rooms, cancel its poll task
                if not self._agent_rooms[agent_id]:
                    del self._agent_rooms[agent_id]
                    key = f"poll:{agent_id}"
                    if key in self._poll_tasks:
                        self._poll_tasks[key].cancel()
                        del self._poll_tasks[key]
                        logger.info(
                            "Removed poll task for agent %s (no more rooms)",
                            agent_id,
                        )

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the poll service.

        Returns:
            Dict with service status information
        """
        return {
            "running": self._running,
            "registered_agents": list(self._agent_rooms.keys()),
            "agent_rooms": {
                agent_id: list(rooms)
                for agent_id, rooms in self._agent_rooms.items()
            },
            "poll_intervals": dict(self._agent_intervals),
            "active_tasks": list(self._poll_tasks.keys()),
        }

    def cleanup_stale_rooms(self) -> int:
        """Remove non-existent rooms from tracking.

        This should be called periodically or after chatroom deletions.

        Returns:
            Number of stale rooms removed
        """
        logger.info(
            "[DEBUG] cleanup_stale_rooms: starting with db_path=%s, current agent_rooms=%s",
            self._db.db_path,
            {aid: list(rooms) for aid, rooms in self._agent_rooms.items()},
        )
        removed_count = 0
        for agent_id in list(self._agent_rooms.keys()):
            rooms = self._agent_rooms.get(agent_id, set())
            for room_id in list(rooms):
                room = self._db.get_room(room_id)
                logger.info(
                    "[DEBUG] cleanup_stale_rooms: checking room_id=%s, exists=%s",
                    room_id,
                    room is not None,
                )
                if not room:
                    self._agent_rooms[agent_id].discard(room_id)
                    removed_count += 1
                    logger.info(
                        "[DEBUG] Removed stale room %s from agent %s tracking",
                        room_id,
                        agent_id,
                    )

        if removed_count > 0:
            logger.info(
                "[DEBUG] cleanup_stale_rooms: cleaned up %d stale room references, remaining agent_rooms=%s",
                removed_count,
                {aid: list(rooms) for aid, rooms in self._agent_rooms.items()},
            )
        else:
            logger.info("[DEBUG] cleanup_stale_rooms: no stale rooms found")

        return removed_count

    async def _discover_agents(self) -> None:
        """Discover agents that are part of chatrooms."""
        try:
            rooms = self._db.list_rooms()
            # DEBUG: Log discovered rooms from database
            logger.info(
                "[DEBUG] _discover_agents: db_path=%s, found %d rooms from database",
                self._db.db_path,
                len(rooms),
            )
            for room in rooms:
                logger.info(
                    "[DEBUG] Room from DB: id=%s, name=%s, lead=%s, agents=%s",
                    room.id,
                    room.name,
                    room.lead_agent_id,
                    room.agent_ids,
                )

            for room in rooms:
                # Register lead agent
                if room.lead_agent_id:
                    await self.register_agent(room.lead_agent_id, room.id)

                # Register worker agents
                for agent_id in room.agent_ids:
                    await self.register_agent(agent_id, room.id)

            logger.info(
                "[DEBUG] After discovery: agent_rooms state: %s",
                {aid: list(rooms) for aid, rooms in self._agent_rooms.items()},
            )
        except Exception as e:
            logger.error("Error discovering agents: %s", e, exc_info=True)

    async def _check_timeouts(self) -> None:
        """Check for timed-out tasks and send notifications."""
        try:
            # Get all timed-out tasks
            timed_out_tasks = self._db.get_timed_out_tasks()
            stale_tasks = self._db.get_stale_tasks()

            for task in timed_out_tasks:
                # Add log entry
                self._db.add_task_log_entry(
                    task.id,
                    "timeout_warning",
                    f"Task has exceeded timeout of {task.timeout_minutes} minutes",
                )

                # Notify task owner
                if task.owner:
                    await self._send_timeout_notification(task, "timeout")

                # Notify lead agent if different from owner
                room = self._db.get_room(task.room_id)
                if room and room.lead_agent_id and room.lead_agent_id != task.owner:
                    await self._send_timeout_notification(task, "timeout", room.lead_agent_id)

            for task in stale_tasks:
                # Skip if already in timed_out (avoid duplicate notifications)
                if any(t.id == task.id for t in timed_out_tasks):
                    continue

                # Add log entry
                self._db.add_task_log_entry(
                    task.id,
                    "stale_warning",
                    "Task has not been updated in over 60 minutes",
                )

                # Notify task owner
                if task.owner:
                    await self._send_timeout_notification(task, "stale")

            if timed_out_tasks or stale_tasks:
                logger.info(
                    "Timeout check: %d timed out, %d stale tasks",
                    len(timed_out_tasks),
                    len(stale_tasks),
                )

        except Exception as e:
            logger.error("Error checking timeouts: %s", e, exc_info=True)

    async def _send_timeout_notification(
        self,
        task: Any,
        notification_type: str,
        override_agent: Optional[str] = None,
    ) -> None:
        """Log timeout notification (no longer sends message).

        Agent will see task status on next poll.
        """
        target_agent = override_agent or task.owner
        logger.info(
            "Task %s timeout notification: type=%s, target_agent=%s",
            task.id[:6],
            notification_type,
            target_agent,
        )

    async def _discovery_loop(self) -> None:
        """Periodically discover new agents in chatrooms."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._discover_agents()
                # Check for timed-out tasks
                await self._check_timeouts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in discovery loop: %s", e, exc_info=True)

    async def _poll_loop(self, agent_id: str) -> None:
        """Main polling loop for a single agent.

        Args:
            agent_id: The agent ID to poll for
        """
        interval = self._agent_intervals.get(agent_id, self._default_interval)

        while self._running:
            try:
                # Poll all rooms this agent is in
                results = await self._poll_agent(agent_id)

                # If work was found, trigger the agent
                for result in results:
                    if result.has_work:
                        await self._trigger_agent(result)

                # Dynamic interval: shorter if work was found
                actual_interval = interval
                if any(r.has_work for r in results):
                    actual_interval = max(10, interval // 3)  # Faster when active

                await asyncio.sleep(actual_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Error in poll loop for agent %s: %s",
                    agent_id,
                    e,
                    exc_info=True,
                )
                await asyncio.sleep(interval)

    async def _poll_agent(self, agent_id: str) -> List[PollResult]:
        """Poll for tasks and messages for a specific agent.

        Args:
            agent_id: The agent ID to poll for

        Returns:
            List of PollResult for each room the agent is in
        """
        results = []

        rooms = self._agent_rooms.get(agent_id, set())
        rooms_to_remove = []  # Track rooms that no longer exist

        # DEBUG: Log agent's registered rooms
        logger.info(
            "[DEBUG] _poll_agent: agent_id=%s, registered_rooms=%s",
            agent_id,
            list(rooms) if rooms else "empty",
        )

        for room_id in rooms:
            try:
                result = PollResult(agent_id=agent_id, room_id=room_id)

                # Get room info including agent_roles
                room = self._db.get_room(room_id)
                if not room:
                    # Room no longer exists, mark for removal
                    rooms_to_remove.append(room_id)
                    logger.warning(
                        "[DEBUG] Room %s no longer exists (db_path=%s), will remove from agent %s tracking",
                        room_id,
                        self._db.db_path,
                        agent_id,
                    )
                    continue

                # Room exists - set room info
                result.room_name = room.name
                result.team_roles = room.agent_roles or {}
                result.agent_role = result.team_roles.get(agent_id, "")
                result.matrix_room_id = room.matrix_room_id  # For message forwarding
                result.is_lead = room.lead_agent_id == agent_id  # Check if this is lead agent

                # Query all pending and in_progress tasks
                # Workers need to see both: pending (to claim) and in_progress (to execute)
                all_pending = self._db.get_tasks(room_id, status="pending")
                all_in_progress = self._db.get_tasks(room_id, status="in_progress")

                # Tasks assigned to this agent (owner == agent_id)
                # Check both pending and in_progress status
                # Note: Leader should NOT have assigned tasks - they coordinate only
                if not result.is_lead:
                    assigned_tasks = [
                        t for t in all_pending + all_in_progress
                        if t.owner == agent_id
                    ]
                else:
                    assigned_tasks = []  # Leader never executes tasks directly

                # Unassigned tasks (owner is None or empty, pending status only)
                unassigned_tasks = [t for t in all_pending if not t.owner]

                logger.info(
                    "[DEBUG] _poll_agent: room_id=%s, agent_id=%s, assigned=%d, unassigned=%d",
                    room_id,
                    agent_id,
                    len(assigned_tasks),
                    len(unassigned_tasks),
                )

                # Build task list for this agent
                if assigned_tasks:
                    result.has_work = True
                    result.tasks.extend([
                        {
                            "id": t.id,
                            "subject": t.subject,
                            "priority": t.priority,
                            "auto_mode": t.auto_mode,
                            "description": t.description,
                            "retry_count": t.retry_count,
                            "max_retries": t.max_retries,
                            "blocked_by": t.blocked_by,
                            "blocks": t.blocks,
                        }
                        for t in assigned_tasks[:5]  # Limit assigned tasks
                    ])

                # Add unassigned tasks for Workers (not for Leader to poll)
                # Leader only triggers when tasks complete, not when tasks are pending
                if unassigned_tasks and not result.is_lead:
                    result.has_work = True
                    result.tasks.extend([
                        {
                            "id": t.id,
                            "subject": t.subject,
                            "priority": t.priority,
                            "unassigned": True,
                            "suggested_for_lead": False,
                            "auto_mode": t.auto_mode,
                            "description": t.description,
                            "blocked_by": t.blocked_by,
                            "blocks": t.blocks,
                        }
                        for t in unassigned_tasks
                    ])

                # Leader only triggers when tasks are recently completed
                # (to decide if follow-up tasks are needed)
                if result.is_lead and not result.has_work:
                    from .task_dag import TaskDAG
                    dag = TaskDAG(self._db)
                    if dag.has_recently_completed_tasks(room_id, within_minutes=5):
                        result.has_work = True
                        # Add context about completed tasks for Leader
                        result.tasks.extend([
                            {
                                "id": t.id,
                                "subject": t.subject,
                                "status": t.status,
                                "description": t.description,
                                "completed_at": t.completed_at,
                            }
                            for t in self._db.get_tasks(room_id, status="completed")[-3:]
                        ])
                        logger.info(
                            "[DEBUG] Leader %s triggered due to recently completed tasks",
                            agent_id,
                        )

                logger.info(
                    "[DEBUG] _poll_agent: room_id=%s, agent_id=%s, has_work=%s, total_tasks=%d",
                    room_id,
                    agent_id,
                    result.has_work,
                    len(result.tasks),
                )

                results.append(result)

            except Exception as e:
                logger.error(
                    "Error polling room %s for agent %s: %s",
                    room_id,
                    agent_id,
                    e,
                )

        # Clean up non-existent rooms
        if rooms_to_remove:
            for room_id in rooms_to_remove:
                if agent_id in self._agent_rooms:
                    self._agent_rooms[agent_id].discard(room_id)
            logger.info(
                "Removed %d non-existent rooms from agent %s tracking",
                len(rooms_to_remove),
                agent_id,
            )

        return results

    async def _trigger_agent(self, result: PollResult) -> None:
        """Trigger an agent to process pending work.

        Args:
            result: The poll result containing work to process
        """
        try:
            # Check if agent already has an active execution
            execution_key = f"{result.room_id}:{result.agent_id}"
            if execution_key in self._active_executions:
                logger.debug(
                    "Skipping trigger for agent %s - already executing in room %s",
                    result.agent_id,
                    result.room_id,
                )
                return

            # Check if we recently triggered this agent (debounce)
            now = datetime.now()
            last = self._last_trigger.get(result.agent_id)
            if last and (now - last).total_seconds() < 10:
                logger.debug(
                    "Skipping trigger for agent %s (debounced)",
                    result.agent_id,
                )
                return

            self._last_trigger[result.agent_id] = now

            # Build the query for the agent
            query = self._build_poll_query(result)
            if not query:
                return

            logger.info(
                "Triggering agent %s for room %s: %d tasks",
                result.agent_id,
                result.room_id,
                len(result.tasks),
            )

            # Get the workspace and trigger the agent
            try:
                workspace = await self._manager.get_agent(result.agent_id)
            except ValueError:
                logger.warning(
                    "Agent %s not found, removing from poll service",
                    result.agent_id,
                )
                # Clean up
                if result.agent_id in self._agent_rooms:
                    del self._agent_rooms[result.agent_id]
                return

            # Get the runner
            runner = workspace.runner
            if not runner:
                logger.warning("No runner for agent %s", result.agent_id)
                return

            # Build the request with room_id in meta for chatroom tool loading
            # session_id format matches frontend: chatroom-{roomId}-{agentId}
            session_id = f"chatroom-{result.room_id}-{result.agent_id}"
            request = {
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": query}],
                    }
                ],
                "session_id": session_id,
                "user_id": result.agent_id,
                "meta": {
                    "room_id": result.room_id,
                    "room_name": result.room_name,
                    "agent_role": result.agent_role,
                    "matrix_room_id": result.matrix_room_id,  # For message forwarding
                },
            }

            # Execute the agent (non-blocking, fire-and-forget)
            # Pass result for poll response processing
            asyncio.create_task(
                self._execute_agent(runner, request, workspace, result)
            )

        except Exception as e:
            logger.error(
                "Error triggering agent %s: %s",
                result.agent_id,
                e,
                exc_info=True,
            )

    async def _execute_agent(
        self,
        runner: Any,
        request: Dict[str, Any],
        workspace: Any,
        poll_result: Optional[PollResult] = None,
    ) -> None:
        """Execute the agent with the given request.

        runner.stream_query will:
        1. Record messages to chat history (via session/memory)
        2. Return event stream for processing

        This method also:
        1. Tracks active executions for task cancellation
        2. Handles exceptions and marks tasks as failed
        3. Checks for max_iters exhaustion and marks tasks as failed
        4. Notifies leader on task failures
        5. Processes poll response JSON for task status updates

        Args:
            runner: The agent runner
            request: The request to execute (contains session_id, meta)
            workspace: The workspace instance for accessing channels
            poll_result: The PollResult that triggered this execution (for JSON processing)
        """
        from agentscope_runtime.engine.schemas.agent_schemas import RunStatus, MessageType

        meta = request.get("meta", {})
        room_id = meta.get("room_id", "")
        session_id = request.get("session_id", "")
        agent_id = request.get("user_id", "")

        # Get tasks that are in_progress for this agent before execution
        tasks_before = self._db.get_tasks(room_id, status="in_progress", owner=agent_id)
        task_ids_before = {t.id for t in tasks_before}

        execution_key = f"{room_id}:{agent_id}"

        # Accumulate response text for poll response processing
        response_text_parts: List[str] = []

        # Register this execution
        async with self._lock:
            self._active_executions[execution_key] = {
                "agent_id": agent_id,
                "room_id": room_id,
                "session_id": session_id,
                "task_ids": task_ids_before,
                "started_at": datetime.now(),
            }

        try:
            async for event in runner.stream_query(request):
                obj = getattr(event, "object", None)
                status = getattr(event, "status", None)
                ev_type = getattr(event, "type", None)

                # Forward MESSAGE type events to Matrix and push store
                # Chat history is already recorded by runner.stream_query
                if (
                    obj == "message"
                    and status == RunStatus.Completed
                    and ev_type == MessageType.MESSAGE
                ):
                    # Accumulate response text for JSON processing
                    content = getattr(event, "content", [])
                    for c in content:
                        if hasattr(c, "text"):
                            response_text_parts.append(c.text)

                    # Build meta with session_id for push_store
                    meta_copy = dict(meta)
                    meta_copy["session_id"] = session_id
                    await self._forward_to_matrix(workspace, event, meta_copy)

        except asyncio.CancelledError:
            logger.info(
                "Agent execution cancelled for agent %s in room %s",
                agent_id,
                room_id,
            )
            # Task was cancelled - mark affected tasks and notify
            await self._handle_execution_cancelled(room_id, agent_id, task_ids_before)
            raise

        except Exception as e:
            logger.error(
                "Error executing agent %s in room %s: %s",
                agent_id,
                room_id,
                e,
                exc_info=True,
            )
            # Exception occurred - mark affected tasks as failed
            await self._handle_execution_error(room_id, agent_id, task_ids_before, str(e))

        finally:
            # Unregister this execution
            async with self._lock:
                self._active_executions.pop(execution_key, None)

            # Process poll response if execution completed normally
            # (poll_result is set and we have response text)
            if poll_result and response_text_parts:
                response_text = "\n".join(response_text_parts)
                try:
                    await asyncio.shield(
                        self._process_poll_response(poll_result, response_text)
                    )
                except asyncio.CancelledError:
                    logger.warning(
                        "Poll response processing was cancelled for agent %s in room %s",
                        agent_id,
                        room_id,
                    )
                except Exception as e:
                    logger.error(
                        "Error processing poll response for agent %s: %s",
                        agent_id,
                        e,
                    )

            # Post-execution check: verify tasks were properly updated
            # Use shield to protect from CancelledError during cleanup
            # Only verify tasks that were NOT processed by _process_poll_response
            try:
                # Re-fetch task status after _process_poll_response
                # to avoid overwriting completed status
                tasks_still_in_progress = []
                for task_id in task_ids_before:
                    task = self._db.get_task(task_id)
                    if task and task.status == "in_progress":
                        tasks_still_in_progress.append(task_id)

                if tasks_still_in_progress:
                    logger.warning(
                        "Tasks still in_progress after poll response processing: %s",
                        tasks_still_in_progress,
                    )
                    await asyncio.shield(
                        self._verify_task_completion(room_id, agent_id, set(tasks_still_in_progress))
                    )
            except asyncio.CancelledError:
                # If shield is cancelled from outside, log but don't propagate
                # The verification should have completed or be safely interrupted
                logger.warning(
                    "Verification of task completion was cancelled for agent %s in room %s",
                    agent_id,
                    room_id,
                )
                # Don't re-raise - cleanup should complete

    # Terminal states - tasks in these states should not be modified
    TERMINAL_STATES = ("completed", "cancelled", "failed")

    async def _handle_execution_cancelled(
        self,
        room_id: str,
        agent_id: str,
        task_ids: Set[str],
    ) -> None:
        """Handle execution cancellation - mark tasks as cancelled if still in_progress."""
        for task_id in task_ids:
            task = self._db.get_task(task_id)
            if not task:
                logger.warning("Task %s not found during cancellation handling", task_id)
                continue
            if task.status in self.TERMINAL_STATES:
                logger.debug(
                    "Task %s already in terminal state (%s), skipping",
                    task_id,
                    task.status,
                )
                continue
            if task.status == "in_progress":
                logger.info(
                    "Marking task %s as cancelled due to execution cancellation",
                    task_id,
                )
                task.status = "cancelled"  # type: ignore
                task.updated_at = datetime.now()
                task.description = (task.description or "") + "\n[Execution cancelled by user]"
                self._db.update_task(task)
                self._db.add_task_log_entry(task_id, "cancelled", "Execution cancelled by user")

                # Notify leader
                await self._notify_leader_task_failed(room_id, task, "Execution cancelled by user")

    async def _handle_execution_error(
        self,
        room_id: str,
        agent_id: str,
        task_ids: Set[str],
        error_message: str,
    ) -> None:
        """Handle execution error - mark tasks as failed."""
        for task_id in task_ids:
            task = self._db.get_task(task_id)
            if not task:
                logger.warning("Task %s not found during error handling", task_id)
                continue
            if task.status in self.TERMINAL_STATES:
                logger.debug(
                    "Task %s already in terminal state (%s), skipping",
                    task_id,
                    task.status,
                )
                continue
            if task.status == "in_progress":
                logger.info(
                    "Marking task %s as failed due to execution error: %s",
                    task_id,
                    error_message[:100],
                )
                task.status = "failed"  # type: ignore
                task.updated_at = datetime.now()
                task.description = (task.description or "") + f"\n[Execution failed: {error_message[:200]}]"
                self._db.update_task(task)
                self._db.add_task_log_entry(task_id, "failed", f"Execution error: {error_message[:200]}")

                # Notify leader
                await self._notify_leader_task_failed(room_id, task, f"Execution error: {error_message[:100]}")

    async def _verify_task_completion(
        self,
        room_id: str,
        agent_id: str,
        task_ids: Set[str],
    ) -> None:
        """Verify tasks were properly completed after execution.

        If tasks are still in_progress, they may have hit max_iters without
        properly updating status. Mark them as failed.
        """
        for task_id in task_ids:
            task = self._db.get_task(task_id)
            if not task:
                logger.warning("Task %s not found during verification", task_id)
                continue
            if task.status in self.TERMINAL_STATES:
                logger.debug(
                    "Task %s already in terminal state (%s), verification passed",
                    task_id,
                    task.status,
                )
                continue
            if task.status == "in_progress":
                logger.warning(
                    "Task %s still in_progress after execution - may have hit max_iters, marking as failed",
                    task_id,
                )
                task.status = "failed"  # type: ignore
                task.updated_at = datetime.now()
                task.description = (
                    (task.description or "") +
                    "\n[Task did not complete - possibly hit max iterations without proper completion]"
                )
                self._db.update_task(task)
                self._db.add_task_log_entry(
                    task_id,
                    "failed",
                    "Task did not complete - possibly hit max iterations"
                )

                # Notify leader
                await self._notify_leader_task_failed(
                    room_id,
                    task,
                    "Task did not complete (possibly hit max iterations)"
                )

    async def _notify_leader_task_failed(
        self,
        room_id: str,
        task: Any,
        reason: str,
    ) -> None:
        """Log task failure (no longer sends message).

        Agent will see task status on next poll.
        """
        try:
            room = self._db.get_room(room_id)
            if not room or not room.lead_agent_id:
                return

            # Don't log if the leader is the one who was working on it
            if room.lead_agent_id == task.owner:
                return

            logger.info(
                "Task %s failed: owner=%s, reason=%s, leader=%s",
                task.id[:6],
                task.owner,
                reason[:50],
                room.lead_agent_id,
            )
        except Exception as e:
            logger.warning("Failed to log task failure: %s", e)

    async def cancel_active_execution(
        self,
        room_id: str,
        agent_id: str,
    ) -> bool:
        """Cancel an active execution for an agent in a room.

        This is called when a task is cancelled to stop the running agent.

        Args:
            room_id: The chatroom ID
            agent_id: The agent ID

        Returns:
            True if an execution was cancelled, False otherwise
        """
        execution_key = f"{room_id}:{agent_id}"

        async with self._lock:
            execution = self._active_executions.get(execution_key)
            if not execution:
                return False

            session_id = execution.get("session_id", "")
            if not session_id:
                return False

        try:
            # Get workspace and task tracker
            workspace = await self._manager.get_agent(agent_id)
            if not workspace:
                return False

            task_tracker = workspace.task_tracker
            if not task_tracker:
                return False

            # Get chat_id for this session
            chat_manager = workspace.chat_manager
            if not chat_manager:
                return False

            channel_manager = workspace.channel_manager
            channel_id = "console"
            if channel_manager and channel_manager.channels:
                for ch in channel_manager.channels:
                    if ch.enabled:
                        channel_id = ch.channel
                        break

            chat_id = await chat_manager.get_chat_id_by_session(session_id, channel_id)
            if not chat_id:
                return False

            # Request stop via task tracker
            stopped = await task_tracker.request_stop(chat_id)

            # Clear queued messages
            if channel_manager:
                await channel_manager.clear_queue(channel_id, session_id, 20)

            logger.info(
                "Cancelled active execution for agent %s in room %s: stopped=%s",
                agent_id,
                room_id,
                stopped,
            )

            return stopped

        except Exception as e:
            logger.error(
                "Error cancelling execution for agent %s: %s",
                agent_id,
                e,
                exc_info=True,
            )
            return False

    def get_active_executions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active executions."""
        return dict(self._active_executions)

    async def _forward_to_matrix(
        self,
        workspace: Any,
        event: Any,
        meta: Dict[str, Any],
    ) -> None:
        """Forward agent response to Matrix room and push store.

        Args:
            workspace: Workspace instance for accessing channels
            event: The message event to forward
            meta: Metadata containing matrix_room_id, agent_name, session_id, etc.
        """
        from agentscope_runtime.engine.schemas.agent_schemas import (
            TextContent,
            ContentType,
        )
        from .console_push_store import append as push_store_append

        matrix_room_id = meta.get("matrix_room_id")

        try:
            channel_manager = getattr(workspace, "channel_manager", None)
            if not channel_manager:
                return

            # Get Matrix channel
            matrix_channel = None
            for ch in channel_manager.channels:
                if ch.channel == "matrix" and getattr(ch, "enabled", False):
                    matrix_channel = ch
                    break

            # Extract content parts from event
            content = getattr(event, "content", [])
            if not content:
                return

            # Convert to OutgoingContentParts and extract text
            parts = []
            text_parts = []
            for c in content:
                ct = getattr(c, "type", None)
                if ct == ContentType.TEXT:
                    text = getattr(c, "text", None)
                    if text:
                        parts.append(TextContent(type=ContentType.TEXT, text=text))
                        text_parts.append(text)

            if not parts:
                return

            # Get agent name for attribution
            agent_name = meta.get("agent_role", "") or getattr(
                workspace.config, "name", ""
            )

            # 1. Forward to Matrix (if configured)
            if matrix_channel and matrix_room_id:
                success = await matrix_channel.forward_to_room(
                    room_id=matrix_room_id,
                    parts=parts,
                    from_agent_name=agent_name,
                )
                if success:
                    logger.info(
                        "PollService: forwarded message to Matrix room %s",
                        matrix_room_id,
                    )

            # 2. Push to console store for Chat page polling
            # This allows Chat page to receive messages via /console/push-messages
            session_id = meta.get("session_id", "")
            if session_id and text_parts:
                full_text = "\n".join(text_parts)
                await push_store_append(session_id, full_text)
                logger.info(
                    "[DEBUG] PollService: pushed message to store for session %s, text length=%d",
                    session_id,
                    len(full_text),
                )
            else:
                logger.warning(
                    "[DEBUG] PollService: skipped push to store - session_id=%s, text_parts=%d",
                    session_id,
                    len(text_parts),
                )

        except Exception as e:
            logger.warning(
                "Failed to forward message: %s",
                e,
            )

    def _build_poll_query(self, result: PollResult) -> str:
        """Build a query string from polling result.

        This method generates different prompts based on the agent's situation:
        - Leader with unassigned tasks: Ask to decide which tasks to create
        - Worker (idle) with unassigned tasks: Ask which task to claim
        - Worker (busy) with assigned tasks: Execute and report status

        Note: Chatroom context is injected in system prompt via build_chatroom_context_prompt.
        This method only builds action-specific instructions.

        Args:
            result: The poll result

        Returns:
            Query string for the agent, or empty string if no action needed
        """
        # Separate tasks by type
        assigned_tasks = [t for t in result.tasks if not t.get("unassigned")]
        unassigned_tasks = [t for t in result.tasks if t.get("unassigned")]

        # Determine agent's current state
        is_busy = len(assigned_tasks) > 0

        # === SCENARIO 1: Worker busy with tasks ===
        # Note: Leader never has assigned_tasks, so this only applies to workers
        if is_busy:
            task = assigned_tasks[0]  # One task at a time
            return self._build_busy_worker_prompt(task)

        # === SCENARIO 2: Worker idle with unassigned tasks (claim) ===
        elif unassigned_tasks and not result.is_lead:
            return self._build_idle_worker_prompt(unassigned_tasks, result)

        # === SCENARIO 3: Leader checking completed tasks ===
        # Leader triggers when tasks are completed to decide on follow-up tasks
        elif result.is_lead and result.tasks:
            # result.tasks contains recently completed tasks
            completed_tasks = result.tasks
            return self._build_leader_prompt(completed_tasks, result)

        # No work to do
        return ""

    def _build_busy_worker_prompt(self, task: Dict) -> str:
        """Build prompt for worker who is busy executing a task."""
        from .chatroom_prompts import build_busy_worker_prompt
        return build_busy_worker_prompt(task=task)

    def _build_idle_worker_prompt(self, unassigned_tasks: List[Dict], result: PollResult) -> str:
        """Build prompt for idle worker who can claim tasks."""
        from .chatroom_prompts import build_idle_worker_prompt
        from .task_dag import TaskDAG

        # Separate tasks by dependency status using TaskDAG
        dag = TaskDAG(self._db)
        ready_tasks = []
        blocked_tasks = []

        for task in unassigned_tasks:
            dep_info = dag.get_task_dependency_info_by_dict(task)
            if dep_info.is_ready:
                ready_tasks.append(task)
            else:
                blocked_tasks.append(task)

        return build_idle_worker_prompt(
            ready_tasks=ready_tasks,
            blocked_tasks=blocked_tasks,
        )

    def _build_leader_prompt(self, completed_tasks: List[Dict], result: PollResult) -> str:
        """Build prompt for leader to check completed tasks and decide on follow-up."""
        from .chatroom_prompts import build_leader_prompt

        # Get all tasks for context
        all_tasks = self._db.get_tasks(result.room_id)

        return build_leader_prompt(
            all_tasks=all_tasks,
            completed_tasks=completed_tasks,
        )

    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """Extract JSON from agent response text.

        Args:
            text: The response text from the agent

        Returns:
            Parsed JSON dict or None if not found
        """
        import json
        import re

        # Try to find JSON in code blocks
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, text)

        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # Try to parse the entire text as JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try to find JSON object pattern
        json_obj_pattern = r'\{[\s\S]*\}'
        match = re.search(json_obj_pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _validate_schema(
        self,
        json_data: Dict,
        expected_schema: str,
    ) -> bool:
        """Validate JSON data against expected schema type.

        Args:
            json_data: Parsed JSON dict
            expected_schema: Schema type: "leader", "idle_worker", "busy_worker"

        Returns:
            True if JSON matches expected schema
        """
        if not isinstance(json_data, dict):
            return False

        if expected_schema == "leader":
            # Leader: {"tasks_to_create": [...], "tasks_to_retry": [...]}
            if "tasks_to_create" not in json_data:
                return False
            if not isinstance(json_data["tasks_to_create"], list):
                return False
            # Validate each task in list
            for task in json_data["tasks_to_create"]:
                if not isinstance(task, dict):
                    return False
                if "subject" not in task:
                    return False
            # Validate tasks_to_retry if present
            if "tasks_to_retry" in json_data:
                if not isinstance(json_data["tasks_to_retry"], list):
                    return False
                for task_id in json_data["tasks_to_retry"]:
                    if not isinstance(task_id, str):
                        return False
            return True

        elif expected_schema == "idle_worker":
            # Idle worker: {"task_to_claim": "id" or null}
            if "task_to_claim" not in json_data:
                return False
            task_id = json_data["task_to_claim"]
            if task_id is not None and not isinstance(task_id, str):
                return False
            return True

        elif expected_schema == "busy_worker":
            # Busy worker: {"status": "completed|failed|cancelled", "reason": "..."}
            if "status" not in json_data:
                return False
            status = json_data["status"]
            if status not in ("completed", "failed", "cancelled"):
                return False
            return True

        return False

    def _build_fix_json_prompt(
        self,
        original_text: str,
        expected_schema: str,
    ) -> str:
        """Build prompt for fixing malformed JSON."""
        from .chatroom_prompts import build_fix_json_prompt
        return build_fix_json_prompt(original_text, expected_schema)

    async def _fix_json_with_light_agent(
        self,
        original_text: str,
        expected_schema: str,
    ) -> Optional[Dict]:
        """Use a lightweight model call to fix malformed JSON.

        This creates a direct model call without loading tools, skills, or MCP.

        Args:
            original_text: The original text containing malformed JSON
            expected_schema: Schema type to fix to

        Returns:
            Fixed JSON dict or None if fix failed
        """
        try:
            from agentscope.message import Msg
            from ..agents.model_factory import create_model_and_formatter

            # Get model and formatter (no agent, no tools)
            model, formatter = create_model_and_formatter()

            # Build fix prompt
            fix_prompt = self._build_fix_json_prompt(original_text, expected_schema)

            # Create message and format
            msg = Msg(role="user", content=fix_prompt)
            formatted = await formatter._format([msg])

            # Call model directly
            response = model(formatted)

            # Extract response text
            if hasattr(response, 'content'):
                if isinstance(response.content, str):
                    response_text = response.content
                elif isinstance(response.content, list):
                    # Extract text from content blocks
                    texts = []
                    for block in response.content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            texts.append(block.get('text', ''))
                        elif hasattr(block, 'text'):
                            texts.append(block.text)
                    response_text = '\n'.join(texts)
                else:
                    response_text = str(response.content)
            else:
                response_text = str(response)

            logger.info(
                "JSON fix attempt for schema %s, response length: %d",
                expected_schema,
                len(response_text),
            )

            # Try to extract and validate fixed JSON
            fixed_json = self._extract_json_from_response(response_text)
            if fixed_json and self._validate_schema(fixed_json, expected_schema):
                logger.info("JSON fix successful for schema %s", expected_schema)
                return fixed_json

            logger.warning("JSON fix failed validation for schema %s", expected_schema)
            return None

        except Exception as e:
            logger.error("Error in JSON fix attempt: %s", e, exc_info=True)
            return None

    async def _parse_json_with_retry(
        self,
        response_text: str,
        expected_schema: str,
    ) -> Optional[Dict]:
        """Parse JSON with retry mechanism using light agent for fix.

        Args:
            response_text: The response text to parse
            expected_schema: Expected schema type

        Returns:
            Parsed and validated JSON dict or None if all attempts failed
        """
        # First attempt: direct extraction
        json_data = self._extract_json_from_response(response_text)
        if json_data and self._validate_schema(json_data, expected_schema):
            return json_data

        logger.warning(
            "JSON validation failed for schema %s, attempting fix",
            expected_schema,
        )

        # Second attempt: fix with light agent
        corrected = await self._fix_json_with_light_agent(
            response_text,
            expected_schema,
        )
        if corrected:
            return corrected

        logger.warning(
            "JSON parse failed after retry for schema %s, giving up",
            expected_schema,
        )
        return None

    async def _process_poll_response(
        self,
        result: PollResult,
        response_text: str,
    ) -> None:
        """Process the JSON response from poll-triggered agent execution.

        Args:
            result: The poll result that triggered this execution
            response_text: The agent's response text containing JSON
        """
        from ..agents.tools.task_management import (
            task_create,
            task_update,
            task_cancel,
            task_claim,
        )

        agent_id = result.agent_id
        room_id = result.room_id
        is_lead = result.is_lead

        # Check if agent is busy (has assigned tasks)
        assigned_tasks = [t for t in result.tasks if not t.get("unassigned")]
        is_busy = len(assigned_tasks) > 0

        # Determine expected schema based on agent state
        if is_busy:
            expected_schema = "busy_worker"
        elif is_lead:
            expected_schema = "leader"
        else:
            expected_schema = "idle_worker"

        # Parse JSON with retry mechanism
        json_data = await self._parse_json_with_retry(response_text, expected_schema)
        if not json_data:
            logger.warning(
                "Could not parse valid JSON from poll response for agent %s (schema: %s)",
                result.agent_id,
                expected_schema,
            )
            return

        try:
            if is_busy:
                # Worker reporting task status
                status = json_data.get("status")
                reason = json_data.get("reason", "")

                if status and assigned_tasks:
                    task = assigned_tasks[0]
                    if status == "completed":
                        await task_update(task["id"], status="completed")
                        logger.info(
                            "Task %s marked as completed by agent %s",
                            task["id"],
                            agent_id,
                        )
                    elif status == "failed":
                        # Check if task can be auto-retried
                        task_obj = self._db.get_task(task["id"])
                        if task_obj and task_obj.retry_count < task_obj.max_retries:
                            # Auto retry: increment count and reset status
                            # Keep blocked_by and blocks - dependencies are preserved
                            task_obj.retry_count += 1
                            task_obj.status = "pending"
                            task_obj.owner = None  # Clear owner for re-claim
                            task_obj.description = (task_obj.description or "") + f"\n[Auto retry #{task_obj.retry_count}/{task_obj.max_retries}: {reason}]"
                            self._db.update_task(task_obj)
                            self._db.add_task_log_entry(
                                task["id"],
                                "auto_retry",
                                f"Auto retry #{task_obj.retry_count}/{task_obj.max_retries}: {reason[:100]}"
                            )
                            logger.info(
                                "Task %s auto-retrying (%d/%d), dependencies preserved",
                                task["id"],
                                task_obj.retry_count,
                                task_obj.max_retries,
                            )
                        else:
                            # Max retries reached, permanently failed
                            task_obj.status = "failed"
                            task_obj.description = (task_obj.description or "") + f"\n[Permanently failed after {task_obj.retry_count} retries: {reason}]"
                            self._db.update_task(task_obj)
                            self._db.add_task_log_entry(
                                task["id"],
                                "permanent_failure",
                                f"Max retries ({task_obj.max_retries}) reached: {reason[:100]}"
                            )
                            logger.warning(
                                "Task %s permanently failed after %d/%d retries",
                                task["id"],
                                task_obj.retry_count,
                                task_obj.max_retries,
                            )

                            # Handle tasks that depend on this failed task
                            if task_obj.blocks:
                                for blocked_task_id in task_obj.blocks:
                                    blocked_task = self._db.get_task(blocked_task_id)
                                    if blocked_task and blocked_task.status == "pending":
                                        # Add a note about the dependency failure
                                        blocked_task.description = (
                                            blocked_task.description or ""
                                        ) + f"\n⚠️ 依赖任务 #{task['id']} 已永久失败，可能无法完成"
                                        self._db.update_task(blocked_task)
                                        logger.warning(
                                            "Task #%s has dependency on permanently failed task #%s",
                                            blocked_task_id,
                                            task["id"],
                                        )
                    elif status == "cancelled":
                        await task_cancel(task["id"], reason=reason)
                        logger.info(
                            "Task %s cancelled by agent %s: %s",
                            task["id"],
                            agent_id,
                            reason,
                        )

            elif not is_lead:
                # Worker claiming a task
                task_id = json_data.get("task_to_claim")
                if task_id:
                    # Claim task via database directly
                    claim_result = self._db.claim_task(
                        task_id=task_id,
                        agent_id=agent_id,
                    )
                    if claim_result.success:
                        logger.info(
                            "Task %s claimed by agent %s",
                            task_id,
                            agent_id,
                        )
                        # Immediately trigger execution for claimed task
                        # Build a PollResult with the claimed task
                        task = self._db.get_task(task_id)
                        if task:
                            immediate_result = PollResult(
                                agent_id=agent_id,
                                room_id=room_id,
                                room_name=result.room_name,
                                agent_role=result.agent_role,
                                team_roles=result.team_roles,
                                is_lead=False,
                                has_work=True,
                                tasks=[{
                                    "id": task.id,
                                    "subject": task.subject,
                                    "priority": task.priority,
                                    "auto_mode": task.auto_mode,
                                    "description": task.description,
                                    "retry_count": task.retry_count,
                                    "max_retries": task.max_retries,
                                    "blocked_by": task.blocked_by,
                                    "blocks": task.blocks,
                                }],
                            )
                            # Trigger immediate execution
                            asyncio.create_task(
                                self._trigger_agent(immediate_result)
                            )
                            logger.info(
                                "Immediate execution triggered for claimed task %s",
                                task_id,
                            )
                    else:
                        logger.warning(
                            "Task %s claim failed: %s",
                            task_id,
                            claim_result.reason,
                        )

            elif is_lead:
                # Leader creating tasks with dependency support
                tasks_to_create = json_data.get("tasks_to_create", [])
                if not tasks_to_create:
                    return

                # Step 1: Create all tasks and build subject -> task_id mapping
                subject_to_id: Dict[str, str] = {}
                created_tasks = []

                for task_info in tasks_to_create:
                    subject = task_info.get("subject", "")
                    if not subject:
                        continue

                    # Create task directly via database
                    from .models.chatroom import Task as TaskModel
                    task = TaskModel(
                        room_id=room_id,
                        subject=subject,
                        description=task_info.get("description"),
                        priority=task_info.get("priority", "medium"),
                        blocked_by=task_info.get("blocked_by", []),
                        created_by=agent_id,
                    )
                    created = self._db.create_task(task)
                    subject_to_id[subject] = created.id
                    created_tasks.append({
                        'id': created.id,
                        'subject': subject,
                        'blocked_by_subject': task_info.get("blocked_by_subject", []),
                    })
                    logger.info(
                        "Task #%s '%s' created by leader %s",
                        created.id,
                        subject,
                        agent_id,
                    )

                # Step 2: Resolve blocked_by_subject references
                for task_info in created_tasks:
                    blocked_by_subject = task_info.get('blocked_by_subject', [])
                    if not blocked_by_subject:
                        continue

                    # Convert subject to task ID
                    resolved_deps = [
                        subject_to_id[subj]
                        for subj in blocked_by_subject
                        if subj in subject_to_id
                    ]

                    if resolved_deps:
                        # Update task dependencies directly
                        task = self._db.get_task(task_info['id'])
                        if task:
                            task.blocked_by = resolved_deps
                            self._db.update_task(task)
                            logger.info(
                                "Task #%s dependencies resolved: %s -> %s",
                                task_info['id'],
                                blocked_by_subject,
                                resolved_deps,
                            )

                # Step 3: Handle tasks_to_retry - reset failed tasks
                tasks_to_retry = json_data.get("tasks_to_retry", [])
                for task_id in tasks_to_retry:
                    task = self._db.get_task(task_id)
                    if not task:
                        logger.warning(
                            "Task %s to retry not found",
                            task_id,
                        )
                        continue
                    if task.status != "failed":
                        logger.warning(
                            "Task %s is not failed (status: %s), cannot retry",
                            task_id,
                            task.status,
                        )
                        continue

                    # Reset for retry
                    task.status = "pending"
                    task.owner = None
                    task.retry_count = 0  # Reset retry count
                    task.updated_at = datetime.now()
                    self._db.update_task(task)
                    self._db.add_task_log_entry(
                        task_id,
                        "leader_retry",
                        f"Reset by leader {agent_id} for retry",
                    )
                    logger.info(
                        "Task #%s reset by leader %s for retry",
                        task_id,
                        agent_id,
                    )

        except Exception as e:
            logger.error(
                "Error processing poll response for agent %s: %s",
                agent_id,
                e,
                exc_info=True,
            )