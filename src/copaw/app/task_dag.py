# -*- coding: utf-8 -*-
"""Task DAG (Directed Acyclic Graph) management.

Provides utilities for managing task dependencies in chatrooms.
"""
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

from .db.chatroom_db import ChatRoomDatabase
from .models.chatroom import Task


@dataclass
class TaskDependencyInfo:
    """Task with its dependency status."""
    task: Task
    is_ready: bool  # All dependencies satisfied
    blocked_by: List[str]  # Uncompleted dependency task IDs


class TaskDAG:
    """Task dependency graph manager.

    Manages task dependencies and provides methods to query
    task readiness status and dependency chains.
    """

    def __init__(self, db: Optional[ChatRoomDatabase] = None):
        """Initialize TaskDAG.

        Args:
            db: Optional ChatRoomDatabase instance. Creates new one if not provided.
        """
        self._db = db or ChatRoomDatabase()

    def get_ready_tasks(self, room_id: str, status: str = "pending") -> List[Task]:
        """Get all tasks whose dependencies are satisfied and can be claimed.

        Args:
            room_id: The chatroom ID
            status: Task status filter (default: "pending")

        Returns:
            List of tasks ready to be claimed
        """
        all_pending = self._db.get_tasks(room_id, status=status)
        ready = []

        for task in all_pending:
            if not task.blocked_by:
                # No dependencies, always ready
                ready.append(task)
            else:
                # Check if all dependencies are completed
                if self._check_dependencies_complete(task.blocked_by):
                    ready.append(task)

        return ready

    def get_blocked_tasks(
        self,
        room_id: str,
        status: str = "pending"
    ) -> List[Tuple[Task, List[str]]]:
        """Get tasks that are blocked by uncompleted dependencies.

        Args:
            room_id: The chatroom ID
            status: Task status filter (default: "pending")

        Returns:
            List of (task, uncompleted_dependency_ids) tuples
        """
        all_pending = self._db.get_tasks(room_id, status=status)
        blocked = []

        for task in all_pending:
            if task.blocked_by:
                uncompleted = self._get_uncompleted_dependencies(task.blocked_by)
                if uncompleted:
                    blocked.append((task, uncompleted))

        return blocked

    def check_dependencies(self, task_id: str) -> Tuple[bool, List[str]]:
        """Check if a task's dependencies are all satisfied.

        Args:
            task_id: The task ID to check

        Returns:
            Tuple of (is_ready, uncompleted_dependency_ids)
        """
        task = self._db.get_task(task_id)
        if not task:
            return False, []

        if not task.blocked_by:
            return True, []

        uncompleted = self._get_uncompleted_dependencies(task.blocked_by)
        return len(uncompleted) == 0, uncompleted

    def get_dependency_chain(self, task_id: str) -> List[str]:
        """Get the full dependency chain for a task (BFS traversal).

        Args:
            task_id: The task ID to analyze

        Returns:
            List of task IDs that this task depends on (direct and indirect)
        """
        task = self._db.get_task(task_id)
        if not task or not task.blocked_by:
            return []

        visited: Set[str] = set()
        chain: List[str] = []
        queue = list(task.blocked_by)

        while queue:
            dep_id = queue.pop(0)
            if dep_id in visited:
                continue
            visited.add(dep_id)

            chain.append(dep_id)

            dep_task = self._db.get_task(dep_id)
            if dep_task and dep_task.blocked_by:
                for sub_dep in dep_task.blocked_by:
                    if sub_dep not in visited:
                        queue.append(sub_dep)

        return chain

    def get_task_dependency_info(self, task: Task) -> TaskDependencyInfo:
        """Get dependency info for a single task.

        Args:
            task: The task to analyze

        Returns:
            TaskDependencyInfo with readiness status
        """
        if not task.blocked_by:
            return TaskDependencyInfo(
                task=task,
                is_ready=True,
                blocked_by=[]
            )

        uncompleted = self._get_uncompleted_dependencies(task.blocked_by)
        return TaskDependencyInfo(
            task=task,
            is_ready=len(uncompleted) == 0,
            blocked_by=uncompleted
        )

    def get_task_dependency_info_by_dict(self, task_dict: Dict) -> TaskDependencyInfo:
        """Get dependency info for a task represented as dict.

        Args:
            task_dict: Task as dict with 'id', 'blocked_by' fields

        Returns:
            TaskDependencyInfo with readiness status (task field will be None)
        """
        blocked_by = task_dict.get("blocked_by", [])
        if not blocked_by:
            return TaskDependencyInfo(
                task=None,
                is_ready=True,
                blocked_by=[]
            )

        uncompleted = self._get_uncompleted_dependencies(blocked_by)
        return TaskDependencyInfo(
            task=None,
            is_ready=len(uncompleted) == 0,
            blocked_by=uncompleted
        )

    def get_all_tasks_with_deps(
        self,
        room_id: str,
        status: Optional[str] = None
    ) -> List[TaskDependencyInfo]:
        """Get all tasks with their dependency status.

        Args:
            room_id: The chatroom ID
            status: Optional status filter

        Returns:
            List of TaskDependencyInfo for all tasks
        """
        tasks = self._db.get_tasks(room_id, status=status)
        return [self.get_task_dependency_info(t) for t in tasks]

    def has_recently_completed_tasks(
        self,
        room_id: str,
        within_minutes: int = 5
    ) -> bool:
        """Check if there are any recently completed tasks.

        Args:
            room_id: The chatroom ID
            within_minutes: Time window in minutes

        Returns:
            True if there are recently completed tasks
        """
        tasks = self._db.get_tasks(room_id, status="completed")
        cutoff = datetime.now() - timedelta(minutes=within_minutes)

        for task in tasks:
            if task.completed_at and task.completed_at >= cutoff:
                return True

        return False

    def _check_dependencies_complete(self, dep_ids: List[str]) -> bool:
        """Check if all dependencies are completed.

        Args:
            dep_ids: List of dependency task IDs

        Returns:
            True if all dependencies are completed
        """
        for dep_id in dep_ids:
            dep_task = self._db.get_task(dep_id)
            if not dep_task or dep_task.status != "completed":
                return False
        return True

    def _get_uncompleted_dependencies(self, dep_ids: List[str]) -> List[str]:
        """Get list of uncompleted dependency IDs.

        Args:
            dep_ids: List of dependency task IDs

        Returns:
            List of dependency IDs that are not completed
        """
        uncompleted = []
        for dep_id in dep_ids:
            dep_task = self._db.get_task(dep_id)
            if not dep_task or dep_task.status != "completed":
                uncompleted.append(dep_id)
        return uncompleted