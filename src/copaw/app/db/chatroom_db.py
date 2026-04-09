# -*- coding: utf-8 -*-
"""ChatRoom database manager.

SQLite database operations for chatrooms and tasks.

Concurrency notes:
- Uses WAL mode for better concurrency (one writer, multiple readers)
- Sets busy_timeout to wait for locks instead of failing immediately
- All write operations are wrapped in transactions
"""
import sqlite3
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from contextlib import contextmanager

from ..models.chatroom import ChatRoom, SessionInfo, Task
from ...constant import WORKING_DIR

logger = logging.getLogger(__name__)

# Busy timeout in milliseconds - how long to wait for a lock before giving up
BUSY_TIMEOUT_MS = 5000  # 5 seconds


@dataclass
class ClaimTaskResult:
    """Result of attempting to claim a task."""
    success: bool
    reason: Optional[str] = None  # 'task_not_found', 'already_claimed', 'already_resolved', 'blocked', 'agent_busy'
    task: Optional[Task] = None
    blocked_by_tasks: Optional[List[str]] = None
    busy_with_tasks: Optional[List[str]] = None


class ChatRoomDatabase:
    """聊天室数据库管理器"""

    def __init__(self, db_path: Optional[str] = None):
        # Use working directory as default path for persistence
        if db_path is None:
            db_path = str(WORKING_DIR / "chatrooms.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # DEBUG: Log database path being used
        logger.info("[DEBUG] ChatRoomDatabase initialized with db_path=%s", self.db_path)
        self._init_db()

    @contextmanager
    def get_connection(self):
        """获取数据库连接（启用WAL模式和busy_timeout）"""
        conn = sqlite3.connect(str(self.db_path), timeout=BUSY_TIMEOUT_MS / 1000)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        # Set busy timeout for lock waiting
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        # Enable foreign key constraints (required for ON DELETE CASCADE)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_db(self):
        """初始化数据库 schema"""
        schema_sql = """
        -- ChatRooms table
        CREATE TABLE IF NOT EXISTS chatrooms (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'default',
            lead_agent_id TEXT,
            agent_ids TEXT NOT NULL DEFAULT '[]',
            agent_roles TEXT NOT NULL DEFAULT '{}',
            sessions TEXT NOT NULL DEFAULT '{}',
            layout TEXT NOT NULL DEFAULT 'tiles',
            matrix_room_id TEXT,
            matrix_alias TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Tasks table
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT,
            owner TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            blocked_by TEXT NOT NULL DEFAULT '[]',
            blocks TEXT NOT NULL DEFAULT '[]',
            priority TEXT NOT NULL DEFAULT 'medium',
            deadline DATETIME,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            auto_mode INTEGER DEFAULT 0,
            progress INTEGER DEFAULT 0,
            timeout_minutes INTEGER,
            started_at DATETIME,
            execution_log TEXT DEFAULT '[]',
            source_session_id TEXT,
            source_message_id TEXT,
            created_by TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (room_id) REFERENCES chatrooms(id) ON DELETE CASCADE
        );

        -- Basic indexes (safe to create on all columns that exist in initial schema)
        CREATE INDEX IF NOT EXISTS idx_chatrooms_user ON chatrooms(user_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_room ON tasks(room_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner, room_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, room_id);
        """

        with self.get_connection() as conn:
            conn.executescript(schema_sql)

            # Migrations: Add columns if they don't exist
            cursor = conn.execute("PRAGMA table_info(chatrooms)")
            columns = [row[1] for row in cursor.fetchall()]

            if "matrix_room_id" not in columns:
                conn.execute("ALTER TABLE chatrooms ADD COLUMN matrix_room_id TEXT")

            if "matrix_alias" not in columns:
                conn.execute("ALTER TABLE chatrooms ADD COLUMN matrix_alias TEXT")

            if "agent_roles" not in columns:
                conn.execute("ALTER TABLE chatrooms ADD COLUMN agent_roles TEXT DEFAULT '{}'")

            # Task table migrations
            cursor = conn.execute("PRAGMA table_info(tasks)")
            task_columns = [row[1] for row in cursor.fetchall()]

            if "retry_count" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN retry_count INTEGER DEFAULT 0")

            if "max_retries" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN max_retries INTEGER DEFAULT 3")

            if "auto_mode" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN auto_mode INTEGER DEFAULT 0")

            if "progress" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0")

            if "timeout_minutes" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN timeout_minutes INTEGER")

            if "started_at" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN started_at DATETIME")

            if "execution_log" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN execution_log TEXT DEFAULT '[]'")

            if "source_session_id" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN source_session_id TEXT")

            if "source_message_id" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN source_message_id TEXT")

            # Create index on started_at after migration (column guaranteed to exist)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_started ON tasks(started_at)")

    # ========== ChatRoom CRUD ==========

    def create_room(self, room: ChatRoom) -> ChatRoom:
        """创建聊天室"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO chatrooms
                (id, name, user_id, lead_agent_id, agent_ids, agent_roles, sessions, layout, matrix_room_id, matrix_alias, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    room.id,
                    room.name,
                    room.user_id,
                    room.lead_agent_id,
                    json.dumps(room.agent_ids),
                    json.dumps(room.agent_roles),
                    json.dumps(room.sessions),
                    room.layout,
                    room.matrix_room_id,
                    room.matrix_alias,
                    room.created_at.isoformat(),
                    room.updated_at.isoformat(),
                )
            )
        return room

    def get_room(self, room_id: str) -> Optional[ChatRoom]:
        """获取聊天室"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM chatrooms WHERE id = ?",
                (room_id,)
            ).fetchone()

            if not row:
                return None

            # Use dict-like access with fallback for new columns
            row_dict = dict(row)

            return ChatRoom(
                id=row_dict["id"],
                name=row_dict["name"],
                user_id=row_dict["user_id"],
                lead_agent_id=row_dict.get("lead_agent_id"),
                agent_ids=json.loads(row_dict["agent_ids"] or "[]"),
                agent_roles=json.loads(row_dict.get("agent_roles") or "{}"),
                sessions=json.loads(row_dict["sessions"] or "{}"),
                layout=row_dict.get("layout", "tiles"),
                matrix_room_id=row_dict.get("matrix_room_id"),
                matrix_alias=row_dict.get("matrix_alias"),
                created_at=datetime.fromisoformat(row_dict["created_at"]),
                updated_at=datetime.fromisoformat(row_dict["updated_at"]),
            )

    def list_rooms(self, user_id: str = "default") -> List[ChatRoom]:
        """列出用户的所有聊天室"""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chatrooms WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            ).fetchall()

            return [
                ChatRoom(
                    id=dict(row)["id"],
                    name=dict(row)["name"],
                    user_id=dict(row)["user_id"],
                    lead_agent_id=dict(row).get("lead_agent_id"),
                    agent_ids=json.loads(dict(row)["agent_ids"] or "[]"),
                    agent_roles=json.loads(dict(row).get("agent_roles") or "{}"),
                    sessions=json.loads(dict(row)["sessions"] or "{}"),
                    layout=dict(row).get("layout", "tiles"),
                    matrix_room_id=dict(row).get("matrix_room_id"),
                    matrix_alias=dict(row).get("matrix_alias"),
                    created_at=datetime.fromisoformat(dict(row)["created_at"]),
                    updated_at=datetime.fromisoformat(dict(row)["updated_at"]),
                )
                for row in rows
            ]

    def update_room(self, room: ChatRoom) -> ChatRoom:
        """更新聊天室"""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE chatrooms
                SET name=?, lead_agent_id=?, agent_ids=?, agent_roles=?, sessions=?, layout=?, matrix_room_id=?, matrix_alias=?, updated_at=?
                WHERE id=?
                """,
                (
                    room.name,
                    room.lead_agent_id,
                    json.dumps(room.agent_ids),
                    json.dumps(room.agent_roles),
                    json.dumps(room.sessions),
                    room.layout,
                    room.matrix_room_id,
                    room.matrix_alias,
                    room.updated_at.isoformat(),
                    room.id,
                )
            )
        return room

    def delete_room(self, room_id: str) -> bool:
        """删除聊天室（级联删除任务和消息）"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM chatrooms WHERE id = ?", (room_id,))
            # 级联删除由 FOREIGN KEY ON DELETE CASCADE 处理
        return True

    # ========== Session CRUD ==========

    def save_session(self, room_id: str, agent_id: str, session: SessionInfo) -> SessionInfo:
        """保存 Session 到聊天室"""
        room = self.get_room(room_id)
        if room:
            room.sessions[agent_id] = session
            room.updated_at = datetime.now()
            self.update_room(room)
        return session

    def get_sessions(self, room_id: str) -> Dict[str, SessionInfo]:
        """获取聊天室的所有 Session"""
        room = self.get_room(room_id)
        if room:
            return room.sessions
        return {}

    # ========== Task CRUD ==========

    def create_task(self, task: Task) -> Task:
        """创建任务"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks
                (id, room_id, subject, description, owner, status, blocked_by, blocks,
                 priority, deadline, retry_count, max_retries, auto_mode, progress,
                 timeout_minutes, started_at, execution_log, source_session_id, source_message_id,
                 created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.room_id,
                    task.subject,
                    task.description,
                    task.owner,
                    task.status,
                    json.dumps(task.blocked_by),
                    json.dumps(task.blocks),
                    task.priority,
                    task.deadline.isoformat() if task.deadline else None,
                    task.retry_count,
                    task.max_retries,
                    1 if task.auto_mode else 0,
                    task.progress,
                    task.timeout_minutes,
                    task.started_at.isoformat() if task.started_at else None,
                    json.dumps(task.execution_log),
                    task.source_session_id,
                    task.source_message_id,
                    task.created_by,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                )
            )
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,)
            ).fetchone()

            if not row:
                return None

            return self._row_to_task(row)

    def get_tasks(self, room_id: str, status: Optional[str] = None,
                  owner: Optional[str] = None) -> List[Task]:
        """获取聊天室的任务列表"""
        with self.get_connection() as conn:
            if status and owner:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE room_id = ? AND status = ? AND owner = ?",
                    (room_id, status, owner)
                ).fetchall()
            elif status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE room_id = ? AND status = ?",
                    (room_id, status)
                ).fetchall()
            elif owner:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE room_id = ? AND owner = ?",
                    (room_id, owner)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE room_id = ?",
                    (room_id,)
                ).fetchall()

            return [self._row_to_task(row) for row in rows]

    def update_task(self, task: Task) -> Task:
        """更新任务"""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET subject=?, description=?, owner=?, status=?,
                    blocked_by=?, blocks=?, priority=?, deadline=?,
                    retry_count=?, max_retries=?, auto_mode=?, progress=?,
                    timeout_minutes=?, started_at=?, execution_log=?,
                    source_session_id=?, source_message_id=?,
                    updated_at=?, completed_at=?
                WHERE id=?
                """,
                (
                    task.subject,
                    task.description,
                    task.owner,
                    task.status,
                    json.dumps(task.blocked_by),
                    json.dumps(task.blocks),
                    task.priority,
                    task.deadline.isoformat() if task.deadline else None,
                    task.retry_count,
                    task.max_retries,
                    1 if task.auto_mode else 0,
                    task.progress,
                    task.timeout_minutes,
                    task.started_at.isoformat() if task.started_at else None,
                    json.dumps(task.execution_log),
                    task.source_session_id,
                    task.source_message_id,
                    task.updated_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.id,
                )
            )
        return task

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return True

    def claim_task(
        self,
        task_id: str,
        agent_id: str,
        check_agent_busy: bool = False,
        room_id: Optional[str] = None,
    ) -> ClaimTaskResult:
        """原子认领任务（防止竞态条件）

        使用数据库事务确保原子性，支持以下检查：
        1. 任务是否存在
        2. 任务是否已被认领
        3. 任务是否已完成
        4. 任务依赖是否满足
        5. (可选) Agent是否忙碌

        Args:
            task_id: 任务ID
            agent_id: 认领的 Agent ID
            check_agent_busy: 是否检查Agent是否已有未完成任务
            room_id: 可选，用于限制Agent忙碌检查的范围

        Returns:
            ClaimTaskResult: 包含认领结果和详细原因
        """
        with self.get_connection() as conn:
            # 1. 获取任务信息
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,)
            ).fetchone()

            if not row:
                return ClaimTaskResult(success=False, reason='task_not_found')

            task = self._row_to_task(row)

            # 2. 检查是否已被其他Agent认领
            if task.owner and task.owner != agent_id:
                logger.info(
                    "Task %s already claimed by %s (requested by %s)",
                    task_id, task.owner, agent_id
                )
                return ClaimTaskResult(
                    success=False,
                    reason='already_claimed',
                    task=task
                )

            # 3. 检查是否已完成
            if task.status == 'completed':
                return ClaimTaskResult(
                    success=False,
                    reason='already_resolved',
                    task=task
                )

            # 4. 检查依赖阻塞
            if task.blocked_by:
                # 查找未完成的依赖任务
                placeholders = ','.join('?' * len(task.blocked_by))
                unresolved_rows = conn.execute(
                    f"""
                    SELECT id FROM tasks
                    WHERE id IN ({placeholders}) AND status != 'completed'
                    """,
                    task.blocked_by
                ).fetchall()
                blocked_by_tasks = [r['id'] for r in unresolved_rows]
                if blocked_by_tasks:
                    logger.info(
                        "Task %s is blocked by: %s",
                        task_id, blocked_by_tasks
                    )
                    return ClaimTaskResult(
                        success=False,
                        reason='blocked',
                        task=task,
                        blocked_by_tasks=blocked_by_tasks
                    )

            # 5. (可选) 检查Agent是否忙碌
            if check_agent_busy:
                if room_id:
                    # 只检查同一聊天室的任务
                    busy_rows = conn.execute(
                        """
                        SELECT id FROM tasks
                        WHERE owner = ? AND status != 'completed' AND id != ? AND room_id = ?
                        """,
                        (agent_id, task_id, room_id)
                    ).fetchall()
                else:
                    # 检查所有任务
                    busy_rows = conn.execute(
                        """
                        SELECT id FROM tasks
                        WHERE owner = ? AND status != 'completed' AND id != ?
                        """,
                        (agent_id, task_id)
                    ).fetchall()

                busy_with_tasks = [r['id'] for r in busy_rows]
                if busy_with_tasks:
                    logger.info(
                        "Agent %s is busy with tasks: %s",
                        agent_id, busy_with_tasks
                    )
                    return ClaimTaskResult(
                        success=False,
                        reason='agent_busy',
                        task=task,
                        busy_with_tasks=busy_with_tasks
                    )

            # 6. 原子认领：只有当 owner 为空或自己是owner时才能认领
            cursor = conn.execute(
                """
                UPDATE tasks
                SET owner = ?, status = 'in_progress', updated_at = ?
                WHERE id = ? AND (owner IS NULL OR owner = '' OR owner = ?)
                """,
                (agent_id, datetime.now().isoformat(), task_id, agent_id)
            )

            if cursor.rowcount > 0:
                logger.info(
                    "Task %s claimed by %s",
                    task_id, agent_id
                )
                task.owner = agent_id
                task.status = 'in_progress'
                return ClaimTaskResult(success=True, task=task)
            else:
                # 被其他Agent抢先认领
                logger.info(
                    "Task %s claim race lost (already claimed by another agent)",
                    task_id
                )
                # 重新获取最新状态
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?",
                    (task_id,)
                ).fetchone()
                if row:
                    task = self._row_to_task(row)
                return ClaimTaskResult(
                    success=False,
                    reason='already_claimed',
                    task=task
                )

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert a database row to a Task object."""
        return Task(
            id=row['id'],
            room_id=row['room_id'],
            subject=row['subject'],
            description=row['description'],
            owner=row['owner'],
            status=row['status'],
            blocked_by=json.loads(row['blocked_by'] or '[]'),
            blocks=json.loads(row['blocks'] or '[]'),
            priority=row['priority'],
            deadline=datetime.fromisoformat(row['deadline']) if row['deadline'] else None,
            retry_count=row['retry_count'] or 0,
            max_retries=row['max_retries'] or 3,
            auto_mode=bool(row['auto_mode'] or 0),
            progress=row['progress'] or 0,
            timeout_minutes=row['timeout_minutes'],
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            execution_log=json.loads(row['execution_log'] or '[]'),
            source_session_id=row['source_session_id'],
            source_message_id=row['source_message_id'],
            created_by=row['created_by'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
        )

    # ========== Task Timeout Helpers ==========

    def get_timed_out_tasks(self, timeout_threshold_minutes: int = 30) -> List[Task]:
        """获取超时的任务（started_at 已过但未完成）

        Args:
            timeout_threshold_minutes: 超时阈值（分钟），默认30分钟

        Returns:
            List[Task]: 超时的任务列表
        """
        with self.get_connection() as conn:
            # Find in_progress tasks that have started_at and have exceeded their timeout
            # or tasks without timeout_minutes that have exceeded the threshold
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = 'in_progress'
                AND started_at IS NOT NULL
                AND (
                    (timeout_minutes IS NOT NULL AND
                     (julianday('now') - julianday(started_at)) * 24 * 60 > timeout_minutes)
                    OR
                    (timeout_minutes IS NULL AND
                     (julianday('now') - julianday(started_at)) * 24 * 60 > ?)
                )
                """,
                (timeout_threshold_minutes,)
            ).fetchall()

            return [self._row_to_task(row) for row in rows]

    def get_stale_tasks(self, stale_threshold_minutes: int = 60) -> List[Task]:
        """获取长时间未更新的任务

        Args:
            stale_threshold_minutes: 长时间未更新阈值（分钟），默认60分钟

        Returns:
            List[Task]: 长时间未更新的任务列表
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = 'in_progress'
                AND (julianday('now') - julianday(updated_at)) * 24 * 60 > ?
                """,
                (stale_threshold_minutes,)
            ).fetchall()

            return [self._row_to_task(row) for row in rows]

    def add_task_log_entry(self, task_id: str, event: str, details: Optional[str] = None) -> bool:
        """添加任务执行日志条目

        Args:
            task_id: 任务ID
            event: 事件类型 (started, progress, completed, failed, cancelled, retry, timeout_warning, note)
            details: 事件详情

        Returns:
            bool: 是否成功
        """
        with self.get_connection() as conn:
            # Get current log
            row = conn.execute(
                "SELECT execution_log FROM tasks WHERE id = ?",
                (task_id,)
            ).fetchone()

            if not row:
                return False

            log = json.loads(row['execution_log'] or '[]')

            # Add new entry
            entry = {
                "timestamp": datetime.now().isoformat(),
                "event": event,
                "details": details,
            }
            log.append(entry)

            # Update log
            conn.execute(
                "UPDATE tasks SET execution_log = ?, updated_at = ? WHERE id = ?",
                (json.dumps(log), datetime.now().isoformat(), task_id)
            )

        return True
