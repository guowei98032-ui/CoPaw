# CoPaw Multi-Agent ChatRoom Design

**Date**: 2026-04-07
**Status**: Approved
**Approach**: Core Integration (Approach B)

---

## 1. Overview

### 1.1 Goals

为 CoPaw 实现多 Agent 协作的聊天室功能，支持：

- **多聊天室管理** - 用户可创建多个命名聊天室
- **Lead-Worker 协作模式** - Lead Agent 分配任务，Worker Agent 执行并汇报
- **任务管理** - 创建、认领、更新任务状态
- **Agent 间消息传递** - 通过邮箱机制异步通信
- **持久化存储** - SQLite 存储聊天室、任务、消息

### 1.2 Non-Goals

- 多进程/多终端执行（如 free-code 的 tmux 模式）
- 实时推送（WebSocket）- 第一版使用轮询
- 多用户协作

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend Layer                                 │
│  console/src/pages/ChatRoom/                                            │
│  ├── index.tsx              # Main ChatRoom page                        │
│  ├── components/                                                         │
│  │   ├── AgentSelector.tsx  # Select agents to join room               │
│  │   ├── ChatPanel.tsx      # Individual agent chat panel               │
│  │   ├── TaskPanel.tsx      # Task list & assignment UI                 │
│  │   └── BroadcastInput.tsx # Broadcast messages to all/selected       │
│  └── store/                                                              │
│      └── chatRoomStore.ts   # Zustand state management                  │
├─────────────────────────────────────────────────────────────────────────┤
│                           API Layer                                      │
│  src/copaw/app/routers/                                                 │
│  ├── chatroom.py            # ChatRoom CRUD + messaging                 │
│  └── tasks.py               # Task management API                       │
├─────────────────────────────────────────────────────────────────────────┤
│                         Persistence Layer                                │
│  src/copaw/app/db/                                                       │
│  ├── chatroom_db.py         # SQLite operations                         │
│  └── schema.sql             # Database schema                           │
├─────────────────────────────────────────────────────────────────────────┤
│                          Agent Tools Layer                               │
│  src/copaw/agents/tools/                                                │
│  ├── task_list.py           # List/filter tasks                         │
│  ├── task_create.py         # Create new task                           │
│  ├── task_update.py         # Update task status                        │
│  ├── task_claim.py          # Claim a task                              │
│  ├── mailbox_read.py        # Read messages from inbox                  │
│  └── mailbox_send.py        # Send message to agent's inbox             │
├─────────────────────────────────────────────────────────────────────────┤
│                       Agent Coordination Layer                           │
│  src/copaw/agents/                                                       │
│  ├── lead_agent.py          # Lead agent behavior (task assignment)     │
│  └── mailbox_manager.py     # Inter-agent message routing               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Models

### 3.1 ChatRoom

```python
class ChatRoom(BaseModel):
    id: str
    name: str                           # 聊天室名称
    user_id: str = "default"
    lead_agent_id: Optional[str]        # Lead Agent ID
    agent_ids: List[str]                # Worker Agent IDs
    sessions: Dict[str, SessionInfo]    # agent_id -> session
    layout: Literal["tiles", "tabs", "list"] = "tiles"
    created_at: datetime
    updated_at: datetime
```

### 3.2 SessionInfo

```python
class SessionInfo(BaseModel):
    session_id: str
    agent_id: str
    user_id: str = "default"
    channel: str = "console"
    created_at: datetime
```

### 3.3 Task

```python
class Task(BaseModel):
    id: str
    room_id: str                        # 所属聊天室
    subject: str                        # 任务标题
    description: Optional[str]          # 任务描述
    owner: Optional[str]                # 认领的 Agent ID
    status: Literal["pending", "in_progress", "completed", "failed"]
    blocked_by: List[str]               # 依赖的任务ID
    blocks: List[str]                   # 被依赖的任务ID
    priority: Literal["low", "medium", "high"]
    deadline: Optional[datetime]
    created_by: str                     # 创建者 Agent ID
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
```

### 3.4 MailboxMessage

```python
class MailboxMessage(BaseModel):
    id: str
    room_id: str
    from_agent: str
    to_agent: str
    message_type: Literal["task_assign", "task_update", "chat", "system"]
    content: str
    read: bool = False
    created_at: datetime
    read_at: Optional[datetime]
```

---

## 4. Database Schema

```sql
-- ChatRooms
CREATE TABLE IF NOT EXISTS chatrooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'default',
    lead_agent_id TEXT,
    agent_ids TEXT NOT NULL DEFAULT '[]',
    sessions TEXT NOT NULL DEFAULT '{}',
    layout TEXT NOT NULL DEFAULT 'tiles',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tasks
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
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (room_id) REFERENCES chatrooms(id) ON DELETE CASCADE
);

-- Mailbox Messages
CREATE TABLE IF NOT EXISTS mailbox_messages (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'chat',
    content TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME,
    FOREIGN KEY (room_id) REFERENCES chatrooms(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chatrooms_user ON chatrooms(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_room ON tasks(room_id);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner, room_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, room_id);
CREATE INDEX IF NOT EXISTS idx_mailbox_to ON mailbox_messages(to_agent, room_id, read);
```

---

## 5. Agent Tools

### 5.1 Task Management

| Tool | Description | Parameters |
|------|-------------|------------|
| `task_list` | 列出任务 | `room_id`, `status?`, `owner?` |
| `task_create` | 创建任务 | `room_id`, `subject`, `description?`, `owner?`, `priority?`, `blocked_by?` |
| `task_update` | 更新任务 | `task_id`, `status?`, `description?` |
| `task_claim` | 认领任务 | `task_id` |

### 5.2 Mailbox

| Tool | Description | Parameters |
|------|-------------|------------|
| `mailbox_read` | 读取收件箱 | `room_id`, `unread_only?` |
| `mailbox_send` | 发送消息 | `room_id`, `to_agent`, `content`, `message_type?` |

### 5.3 Usage Examples

**Lead Agent - 创建并分配任务：**

```python
# 创建任务并直接分配
task = await task_create(
    room_id="room-123",
    subject="编写 API 单元测试",
    description="为 user.py 编写测试",
    owner="ztNTTm",
)

# 或广播让 worker 认领
await mailbox_send(
    room_id="room-123",
    to_agent="ztNTTm",
    content="新任务：代码审查，请查看并认领",
    message_type="task_assign",
)
```

**Worker Agent - 认领并完成任务：**

```python
# 轮询收件箱
messages = await mailbox_read(room_id="room-123")

# 查看待认领任务
tasks = await task_list(room_id="room-123", status="pending")

# 认领任务
await task_claim(task_id="task-456")

# 完成任务
await task_update(task_id="task-456", status="completed")

# 通知 Lead
await mailbox_send(
    room_id="room-123",
    to_agent="default",
    content="任务已完成",
    message_type="task_update",
)
```

---

## 6. API Endpoints

### 6.1 ChatRoom Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chatroom` | 创建聊天室 |
| GET | `/api/chatroom` | 列出所有聊天室 |
| GET | `/api/chatroom/{room_id}` | 获取聊天室详情 |
| PUT | `/api/chatroom/{room_id}` | 更新聊天室配置 |
| DELETE | `/api/chatroom/{room_id}` | 删除聊天室 |

### 6.2 Agent Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chatroom/{room_id}/agents/{agent_id}` | 添加 Agent |
| DELETE | `/api/chatroom/{room_id}/agents/{agent_id}` | 移除 Agent |

### 6.3 Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chatroom/{room_id}/messages` | 发送消息 |
| GET | `/api/chatroom/{room_id}/messages` | 获取消息历史 |

### 6.4 Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chatroom/{room_id}/tasks` | 获取任务列表 |
| POST | `/api/chatroom/{room_id}/tasks` | 创建任务 |
| PUT | `/api/chatroom/{room_id}/tasks/{task_id}` | 更新任务 |

---

## 7. Frontend Components

### 7.1 Directory Structure

```
console/src/pages/ChatRoom/
├── index.tsx                    # 主页面
├── components/
│   ├── ChatRoomList.tsx         # 聊天室列表
│   ├── ChatRoomCard.tsx         # 聊天室卡片
│   ├── CreateRoomModal.tsx      # 创建弹窗
│   ├── ChatRoomView.tsx         # 聊天室详情
│   ├── AgentSelector.tsx        # Agent 选择器
│   ├── ChatPanel.tsx            # 聊天面板
│   ├── TaskPanel.tsx            # 任务面板
│   ├── TaskCard.tsx             # 任务卡片
│   ├── BroadcastInput.tsx       # 广播输入
│   └── LayoutToggle.tsx         # 布局切换
├── store/
│   └── chatRoomStore.ts         # Zustand store
├── hooks/
│   ├── useChatRoom.ts
│   ├── useTasks.ts
│   └── useMailbox.ts
└── types/
    └── index.ts
```

### 7.2 UI Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [返回列表]  项目开发讨论                    [布局: 平铺▼] [设置]      │
├─────────────────────────────────────────────────────────────────────────┤
│  已加入: [default✓ Lead] [ztNTTm✓] [Ls9Gr3✓]  [+ 添加 Agent▼]         │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┬──────────────┬──────────────┐                        │
│  │ ChatPanel    │ ChatPanel    │ ChatPanel    │                        │
│  │ default      │ ztNTTm       │ Ls9Gr3       │                        │
│  │ [对话]       │ [对话]       │ [对话]       │                        │
│  │ [输入框]     │ [输入框]     │ [输入框]     │                        │
│  └──────────────┴──────────────┴──────────────┘                        │
├─────────────────────────────────────────────────────────────────────────┤
│  任务面板 [待处理: 3] [进行中: 2] [已完成: 5]                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 📋 编写API测试  | ztNTTm   | 进行中 | [查看]                    │   │
│  │ 📋 代码审查     | 待认领   | 待处理 | [认领]                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│  [发送到: 全部▼] [________________输入消息________________] [发送]      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Implementation Phases

### Phase 1: Backend Foundation (3-4 days)

1. 创建数据模型 (`src/copaw/app/models/chatroom.py`)
2. 实现 SQLite 数据库管理器 (`src/copaw/app/db/chatroom_db.py`)
3. 实现 ChatRoom API 路由 (`src/copaw/app/routers/chatroom.py`)
4. 注册路由到 FastAPI 应用

### Phase 2: Agent Tools (2-3 days)

1. 实现 Task 管理工具 (`src/copaw/agents/tools/task_*.py`)
2. 实现 Mailbox 工具 (`src/copaw/agents/tools/mailbox_*.py`)
3. 注册工具到 Agent Toolkit
4. 编写工具使用文档

### Phase 3: Frontend (3-4 days)

1. 创建 ChatRoom 页面骨架
2. 实现 Zustand store
3. 实现各 UI 组件
4. 集成 AgentScopeRuntimeWebUI

### Phase 4: Integration & Testing (2-3 days)

1. 端到端测试
2. 性能优化
3. 错误处理
4. 文档编写

**Total Estimate: 10-14 days**

---

## 9. Open Questions

1. **消息轮询频率** - Worker Agent 多久轮询一次邮箱？（建议 5-10 秒）
2. **任务依赖检测** - 是否需要在创建任务时自动检测循环依赖？
3. **Agent 状态显示** - 是否显示 Agent 的在线/离线/忙碌状态？

---

## 10. References

- [copaw-chatroom-implementation-analysis.md](C:/workspace/reports/copaw-chatroom-implementation-analysis.md)
- [copaw-chatroom-persistence-design.md](C:/workspace/reports/copaw-chatroom-persistence-design.md)
- [copaw-agent-teams-implementation-analysis.md](C:/workspace/reports/copaw-agent-teams-implementation-analysis.md)
- [free-code-main](C:/workspace/free-code-main) - Reference implementation