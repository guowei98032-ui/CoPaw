# Multi-Agent ChatRoom 使用指南

## 概述

CoPaw 聊天室功能支持多 Agent 协作，采用 Lead-Worker 模式。每个聊天室可以配置一个 Lead Agent 和多个 Worker Agents，通过任务管理和邮箱机制实现协作。

## 核心概念

### 聊天室 (ChatRoom)
- **Lead Agent**: 负责协调和分配任务的智能体
- **Worker Agents**: 参与协作的工作智能体
- **Layout**: 界面布局模式（tiles/tabs/list）

### 任务 (Task)
- **status**: pending | in_progress | completed | failed
- **owner**: 负责该任务的 Agent ID
- **priority**: low | medium | high
- **blocked_by**: 依赖的其他任务 ID 列表
- **blocks**: 被哪些任务依赖

### 邮箱 (Mailbox)
- **message_type**: task_assign | task_update | chat | system
- **to_agent**: 收件人 Agent ID（"broadcast"表示广播）
- **read**: 是否已读

## Agent 可用工具

### 任务管理工具

#### `task_list(room_id, status, owner)`
列出聊天室中的任务。

**参数：**
- `room_id`: 聊天室 ID
- `status`: (可选) 按状态筛选：pending, in_progress, completed, failed
- `owner`: (可选) 按负责人筛选

**示例：**
```
task_list(room_id="room-abc", status="pending")
```

#### `task_create(room_id, subject, description, owner, priority, blocked_by)`
创建新任务。

**参数：**
- `room_id`: 聊天室 ID
- `subject`: 任务主题（必填）
- `description`: 任务描述（可选）
- `owner`: 负贋人 Agent ID（可选）
- `priority`: 优先级 low|medium|high（默认：medium）
- `blocked_by`: 依赖的任务 ID 列表（可选）

**示例：**
```
task_create(
    room_id="room-abc",
    subject="完成数据分析报告",
    description="需要分析 Q1 销售数据并生成报告",
    owner="agent-xyz",
    priority="high"
)
```

#### `task_update(task_id, status, owner, description)`
更新任务信息。

**参数：**
- `task_id`: 任务 ID（必填）
- `status`: 新状态（可选）
- `owner`: 新负责人（可选）
- `description`: 新描述（可选）

**示例：**
```
task_update(task_id="task-123", status="completed")
```

#### `task_claim(task_id, agent_id)`
认领任务。

**参数：**
- `task_id`: 任务 ID
- `agent_id`: 认领任务的 Agent ID

**示例：**
```
task_claim(task_id="task-123", agent_id="agent-xyz")
```

### 邮箱通讯工具

#### `mailbox_read(room_id, to_agent, unread_only, limit)`
读取消息。

**参数：**
- `room_id`: 聊天室 ID
- `to_agent`: (可选) 按收件人筛选
- `unread_only`: (可选) 是否只显示未读消息（默认：false）
- `limit`: (可选) 最大返回数量（默认：50）

**示例：**
```
mailbox_read(room_id="room-abc", to_agent="agent-xyz", unread_only=true)
```

#### `mailbox_send(room_id, to_agent, content, message_type)`
发送消息给特定 Agent。

**参数：**
- `room_id`: 聊天室 ID
- `to_agent`: 收件人 Agent ID
- `content`: 消息内容
- `message_type`: chat | task_assign | task_update | system

**示例：**
```
mailbox_send(
    room_id="room-abc",
    to_agent="agent-xyz",
    content="请查看新分配的任务",
    message_type="task_assign"
)
```

#### `mailbox_broadcast(room_id, content, from_agent, message_type)`
广播消息给所有 Agent。

**参数：**
- `room_id`: 聊天室 ID
- `content`: 消息内容
- `from_agent`: (可选) 发送者 Agent ID
- `message_type`: (可选) 消息类型（默认：system）

**示例：**
```
mailbox_broadcast(
    room_id="room-abc",
    content="各位请注意，系统将在 10 分钟后进行维护",
    message_type="system"
)
```

## 协作流程示例

### Lead Agent 分配任务

1. Lead Agent 查看待办任务：
   ```
   task_list(room_id="room-abc", status="pending")
   ```

2. 创建新任务并分配：
   ```
   task_create(
       room_id="room-abc",
       subject="分析用户反馈数据",
       owner="agent-analyst",
       priority="high"
   )
   ```

3. 通知 Worker Agent：
   ```
   mailbox_send(
       room_id="room-abc",
       to_agent="agent-analyst",
       content="已分配新任务，请优先处理"
   )
   ```

### Worker Agent 认领任务

1. 查看分配给自己的任务：
   ```
   task_list(room_id="room-abc", owner="agent-analyst")
   ```

2. 认领任务并开始工作：
   ```
   task_claim(task_id="task-123", agent_id="agent-analyst")
   task_update(task_id="task-123", status="in_progress")
   ```

3. 完成任务：
   ```
   task_update(task_id="task-123", status="completed")
   mailbox_broadcast(
       room_id="room-abc",
       content="任务已完成，请查看结果"
   )
   ```

## API Endpoints

### ChatRoom CRUD
- `POST /api/chatroom` - 创建聊天室
- `GET /api/chatroom` - 列出聊天室
- `GET /api/chatroom/{room_id}` - 获取详情
- `PUT /api/chatroom/{room_id}` - 更新配置
- `DELETE /api/chatroom/{room_id}` - 删除聊天室

### Task Management
- `GET /api/chatroom/{room_id}/tasks` - 列出任务
- `POST /api/chatroom/{room_id}/tasks` - 创建任务
- `PUT /api/chatroom/{room_id}/tasks/{task_id}` - 更新任务
- `DELETE /api/chatroom/{room_id}/tasks/{task_id}` - 删除任务

### Message Management
- `GET /api/chatroom/{room_id}/messages` - 列出消息
- `POST /api/chatroom/{room_id}/messages` - 发送消息
- `PUT /api/chatroom/{room_id}/messages/{id}/read` - 标记已读

## 前端页面

- **管理页**: `/chatrooms` - 聊天室列表管理
- **详情页**: `/chatrooms/{room_id}` - 任务/消息/信息管理

## 注意事项

1. **房间 ID**: 所有工具调用都需要提供有效的 `room_id`
2. **Agent ID**: 确保使用的 Agent ID 存在于聊天室配置中
3. **任务依赖**: 创建任务时可通过 `blocked_by` 指定前置任务
4. **消息类型**: 选择合适 `message_type` 帮助接收者分类处理
