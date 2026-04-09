# -*- coding: utf-8 -*-
"""ChatRoom data models.

Pydantic models for chatroom and tasks.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from uuid import uuid4


# ========== ChatRoom ==========

class AgentRole(BaseModel):
    """Agent 在聊天室中的角色信息"""
    agent_id: str
    role_description: str = ""  # 角色描述，默认为空（会使用 agent 的原始描述）


class ChatRoom(BaseModel):
    """聊天室配置"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "我的聊天室"
    user_id: str = "default"

    # Lead agent ID (the coordinator)
    lead_agent_id: Optional[str] = None

    # Worker agent IDs
    agent_ids: List[str] = []

    # Agent roles - each agent's role description in this chatroom
    agent_roles: Dict[str, str] = {}  # {agent_id: role_description}

    # Each agent's session info
    sessions: Dict[str, "SessionInfo"] = {}

    # Layout mode
    layout: Literal["tiles", "tabs", "list"] = "tiles"

    # Matrix room association
    matrix_room_id: Optional[str] = None  # Matrix room ID (e.g., "!abc123:matrix.server")
    matrix_alias: Optional[str] = None    # Matrix room alias (e.g., "#chatroom-xxx:matrix.server")

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SessionInfo(BaseModel):
    """Agent session 信息"""
    session_id: str
    agent_id: str
    user_id: str = "default"
    channel: str = "console"
    created_at: datetime = Field(default_factory=datetime.now)


# ========== Task ==========

class Task(BaseModel):
    """协作任务"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    room_id: str  # 所属聊天室

    # Task content
    subject: str
    description: Optional[str] = None

    # Assignment
    owner: Optional[str] = None  # agent_id who claimed the task
    status: Literal["pending", "in_progress", "completed", "failed", "cancelled"] = "pending"

    # Dependencies
    blocked_by: List[str] = []  # task_ids this task depends on
    blocks: List[str] = []      # task_ids that depend on this task

    # Priority and deadline
    priority: Literal["low", "medium", "high"] = "medium"
    deadline: Optional[datetime] = None

    # Retry tracking
    retry_count: int = 0
    max_retries: int = 3  # Default max retries for failed tasks

    # Auto mode - task should complete without asking intermediate questions
    auto_mode: bool = False  # If True, agent should act autonomously without confirmation

    # Task tracing - link back to user conversation that created this task
    source_session_id: Optional[str] = None  # Session ID where task was created
    source_message_id: Optional[str] = None  # Message ID that triggered task creation

    # Execution progress (0-100)
    progress: int = 0  # 0 = not started, 100 = completed

    # Timeout settings
    timeout_minutes: Optional[int] = None  # Expected completion time in minutes
    started_at: Optional[datetime] = None  # When task was started (claimed)

    # Execution log - records key events during task execution
    execution_log: List[Dict[str, Any]] = []  # [{"timestamp": "..., "event": "...", "details": "..."}]

    # Metadata
    created_by: str  # agent_id who created the task
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None




# ========== API Request/Response Models ==========

class CreateChatRoomRequest(BaseModel):
    """Request model for creating a chatroom"""
    name: str = "我的聊天室"
    lead_agent_id: Optional[str] = None
    agent_ids: List[str] = []
    layout: str = "tiles"

    # Matrix room options
    matrix_mode: Literal["none", "create_new", "link_existing"] = "none"
    matrix_alias: Optional[str] = None  # For create_new: alias name (without # and server)
                                      # For link_existing: full alias (e.g., "#room:server")


class CreateChatRoomResponse(BaseModel):
    """Response model for creating a chatroom"""
    room: ChatRoom
    message: str = "ChatRoom created successfully"
    matrix_error: Optional[str] = None  # Error message if Matrix room creation failed
    matrix_warning: Optional[str] = None  # Warning message (e.g., some invites failed)


class ChatRoomDetail(ChatRoom):
    """ChatRoom with tasks"""
    tasks: List[Task] = []


class UpdateChatRoomRequest(BaseModel):
    """Request model for updating a chatroom"""
    name: Optional[str] = None
    lead_agent_id: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    agent_roles: Optional[Dict[str, str]] = None  # {agent_id: role_description}
    sessions: Optional[Dict[str, SessionInfo]] = None
    layout: Optional[str] = None
    matrix_room_id: Optional[str] = None
    matrix_alias: Optional[str] = None




class CreateTaskRequest(BaseModel):
    """Request model for creating a task"""
    subject: str
    description: Optional[str] = None
    owner: Optional[str] = None
    priority: str = "medium"
    blocked_by: List[str] = []
    auto_mode: bool = False  # If True, agent acts autonomously without intermediate questions
    max_retries: int = 3  # Maximum retry count for failed tasks
    timeout_minutes: Optional[int] = None  # Expected completion time in minutes
    # Task tracing
    source_session_id: Optional[str] = None
    source_message_id: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    """Request model for updating a task"""
    status: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    auto_mode: Optional[bool] = None  # Update auto_mode flag
    max_retries: Optional[int] = None  # Update max_retries limit
    progress: Optional[int] = None  # Update execution progress (0-100)
    timeout_minutes: Optional[int] = None  # Update timeout


class BatchTaskOperationRequest(BaseModel):
    """Request model for batch task operations"""
    task_ids: List[str]
    operation: Literal["cancel", "delete", "assign", "set_status", "set_priority"]
    # Parameters for different operations
    reason: Optional[str] = None  # For cancel
    owner: Optional[str] = None  # For assign
    status: Optional[str] = None  # For set_status
    priority: Optional[str] = None  # For set_priority


class BatchOperationResult(BaseModel):
    """Result model for batch task operations"""
    success_count: int
    failed_count: int
    failed_tasks: List[Dict[str, str]] = []


class TaskLogEntry(BaseModel):
    """Request model for adding a log entry to task"""
    event: str  # Event type: "started", "progress", "completed", "failed", "cancelled", "retry", "timeout_warning", "note"
    details: Optional[str] = None  # Additional details
