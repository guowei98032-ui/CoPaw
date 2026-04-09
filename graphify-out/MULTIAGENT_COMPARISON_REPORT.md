# CoPaw vs free-code 多Agent机制对比分析报告

**分析日期**: 2026-04-08
**分析范围**: CoPaw 多Agent机制 vs free-code teammate机制
**关注重点**: 功能性差异与改进机会（排除安全相关内容）

---

## 一、架构对比概览

### 1.1 设计模式

| 维度 | CoPaw | free-code |
|------|-------|-----------|
| **关系模型** | Lead-Worker (层级) | Leader-Worker (层级) |
| **生命周期** | 持久化 (ChatRoom) | 持久化 (Session) |
| **通信机制** | 数据库存储 + Poll轮询 | 文件存储 + 实时通知 |
| **任务模型** | Task (显式状态) | 隐式 (通过消息) |

### 1.2 核心组件对比

```
CoPaw:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ ChatRoom    │────▶│ PollService │────▶│ AgentRunner │
│ (DB Model)  │     │ (定时轮询)   │     │ (执行查询)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│ Task        │     │ Mailbox     │
│ (状态管理)   │     │ (消息存储)   │
└─────────────┘     └─────────────┘

free-code:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Session     │────▶│ Mailbox     │────▶│ InProcess   │
│ (状态管理)   │     │ (文件+Lock)  │     │ Runner      │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Teammate    │     │ Structured  │     │ Idle        │
│ Manager     │     │ Messages    │     │ Notification│
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## 二、消息类型对比

### 2.1 free-code 消息类型（丰富）

```typescript
// teammateMailbox.ts - 结构化消息类型
enum MessageType {
  'idle_notification',      // 任务完成通知
  'shutdown_request',       // 关闭协商请求
  'shutdown_approved',      // 关闭批准
  'shutdown_rejected',      // 关闭拒绝
  'plan_approval_request',  // 计划审批请求
  'mode_set_request',       // 模式切换请求
  'chat',                   // 普通聊天
}
```

**设计意图**:
- 每种消息类型对应明确的功能流程
- `idle_notification` 实现主动完成通知
- `shutdown_*` 实现优雅退出协商
- 结构化消息可以被路由处理，而非直接显示

### 2.2 CoPaw 消息类型（简单）

```python
# chatroom.py - MailboxMessage模型
message_type: Literal["task_assign", "task_update", "chat", "system"]
```

**现状分析**:
- 类型过于通用，缺乏语义区分
- `chat` 涵盖太多场景，无法区分不同用途
- 没有"任务完成"的明确通知类型
- 没有"退出协商"机制

### 2.3 改进建议：扩展消息类型

```python
# 建议添加的消息类型
message_type: Literal[
  "chat",               # 普通聊天
  "task_assign",        # 任务分配
  "task_update",        # 任务状态更新
  "task_complete",      # 任务完成通知 (新增)
  "agent_idle",         # Agent空闲通知 (新增)
  "shutdown_request",   # 关闭协商请求 (新增)
  "shutdown_response",  # 关闭协商响应 (新增)
  "plan_proposal",      # 计划提议 (新增)
  "plan_feedback",      # 计划反馈 (新增)
  "system",             # 系统通知
]
```

---

## 三、任务完成通知机制

### 3.1 free-code: 主动通知模式

```typescript
// inProcessRunner.ts
async function notifyIdle() {
  await mailbox.sendMessage({
    type: 'idle_notification',
    summary: buildSummary(result),  // 结构化摘要
    timestamp: Date.now()
  })
}

// Worker完成后主动通知Leader
// Leader收到后可以立即分配新任务或关闭Worker
```

**优势**:
- 减少 Leader 的轮询压力
- 实时响应，任务完成后立即感知
- 摘要机制避免发送完整输出

### 3.2 CoPaw: 轮询驱动模式

```python
# chatroom_poll_service.py
async def poll_loop(self):
    while running:
        messages = db.get_messages(room_id, unread_only=True)
        if messages:
            await self._trigger_agent(...)
        
        await asyncio.sleep(interval)  # 固定间隔轮询
```

**现状分析**:
- Leader 无法实时感知 Worker 完成状态
- 定时轮询浪费资源（无消息时也要查询）
- `interval` 动态调整是优化，但仍是轮询模式
- 没有任务摘要，Worker 输出需要完整存储

### 3.3 改进建议：添加主动通知

```python
# mailbox.py - 新增发送空闲通知的工具
async def mailbox_notify_idle(
    room_id: str,
    agent_id: str,
    summary: str,
    task_ids_completed: List[str] = [],
) -> ToolResponse:
    """Worker Agent完成任务后发送空闲通知"""
    
    message = MailboxMessage(
        room_id=room_id,
        from_agent=agent_id,
        to_agent="lead",  # 或 "broadcast"
        content=summary,
        message_type="agent_idle",
    )
    
    db.save_message(message)
    
    # 可选：更新Task状态
    for task_id in task_ids_completed:
        db.update_task(task_id, status="completed")
    
    return ToolResponse(
        content=[TextBlock(type="text", text="Idle notification sent.")],
    )
```

**配合改进 PollService**:

```python
# chatroom_poll_service.py
async def poll_loop(self):
    while running:
        messages = db.get_messages(room_id, unread_only=True)
        
        # 路由消息
        for msg in messages:
            if msg.message_type == "agent_idle":
                # Worker空闲，检查是否有待分配任务
                await self._handle_idle_notification(msg)
            elif msg.message_type in ["task_assign", "chat"]:
                # 需要Agent处理的业务消息
                await self._trigger_agent(...)
        
        await asyncio.sleep(interval)
```

---

## 四、进度跟踪机制

### 4.1 free-code: 详细进度记录

```typescript
// inProcessRunner.ts - ToolActivity跟踪
interface ToolActivity {
  tool: string
  status: 'pending' | 'running' | 'complete' | 'error'
  timestamp: number
  duration?: number
  result_summary?: string
}

const progress: ToolActivity[] = []

// 每个tool调用记录activity
progress.push({
  tool: toolName,
  status: 'running',
  timestamp: Date.now()
})

// 完成后更新状态
activity.status = 'complete'
activity.duration = Date.now() - activity.timestamp
```

**用途**:
- Leader 可实时查看 Worker 执行进度
- 用户界面可显示进度条/状态
- 用于调试和性能分析

### 4.2 CoPaw: 无进度跟踪

```python
# Task模型只有最终状态
status: Literal["pending", "in_progress", "completed", "failed", "cancelled"]
```

**现状分析**:
- `in_progress` 状态太粗粒度
- 无法知道 Worker 正在执行什么工具
- 用户界面只能显示"进行中"，无细节
- 没有工具执行历史记录

### 4.3 改进建议：添加进度字段

```python
# chatroom.py - Task模型扩展
class Task(BaseModel):
    # 原有字段...
    
    # 新增：进度跟踪
    progress: List[ToolActivity] = []
    current_activity: Optional[str] = None
    
    # 新增：执行统计
    tools_used: List[str] = []
    files_modified: List[str] = []
    errors_encountered: List[str] = []

class ToolActivity(BaseModel):
    """工具执行活动记录"""
    tool_name: str
    status: Literal["pending", "running", "complete", "error"]
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    result_summary: Optional[str] = None  # 简短摘要，不超过200字
```

**Agent工具集成**:

```python
# 在Agent执行过程中，通过工具回调更新进度
async def update_task_progress(
    room_id: str,
    task_id: str,
    activity: ToolActivity,
) -> ToolResponse:
    """Agent在执行工具时更新任务进度"""
    db = ChatRoomDatabase()
    task = db.get_task(task_id)
    
    task.progress.append(activity)
    task.current_activity = f"{activity.tool_name}: {activity.status}"
    
    db.update_task(task_id, progress=task.progress)
    
    return ToolResponse(...)
```

---

## 五、消息摘要机制

### 5.1 free-code: 摘要提取与存储

```typescript
// teammateMailbox.ts
function getLastPeerDmSummary(messages: Message[]): string | null {
  // 从最后一条消息中提取摘要
  // 用于避免在历史中重复发送完整内容
  const lastUserMsg = messages.filter(m => m.role === 'user').pop()
  if (!lastUserMsg) return null
  
  // 提取 "Scope: ... Result: ... Key files: ..." 格式的摘要
  const summaryMatch = lastUserMsg.content.match(/^(Scope:.+)$/m)
  return summaryMatch ? summaryMatch[1] : null
}
```

**设计意图**:
- 长输出只保留摘要，减少历史膨胀
- 摘要格式标准化，便于提取和显示
- 新对话引用摘要而非完整输出

### 5.2 CoPaw: 完整存储

```python
# MailboxMessage模型
content: str  # 完整内容，无摘要
```

**现状分析**:
- 每条消息完整存储，历史表膨胀快
- 长输出（如代码分析结果）占用大量存储
- 读取历史时加载完整内容，效率低

### 5.3 改进建议：添加摘要字段

```python
# chatroom.py - MailboxMessage模型扩展
class MailboxMessage(BaseModel):
    # 原有字段...
    
    # 新增：摘要机制
    content_summary: Optional[str] = None  # 自动生成的摘要
    full_content_file: Optional[str] = None  # 完整内容存储路径（可选）
    has_full_content: bool = True  # content字段是否完整
    
    def generate_summary(self) -> str:
        """生成消息摘要"""
        if len(self.content) <= 200:
            return self.content
        
        # 提取关键部分（如Scope/Result格式）
        # 或截取前200字 + "..."
        return self.content[:200] + "..."

# mailbox_send时自动生成摘要
async def mailbox_send(...) -> ToolResponse:
    message = MailboxMessage(...)
    message.content_summary = message.generate_summary()
    
    # 长内容可选：存储到文件
    if len(content) > 5000:
        message.full_content_file = f"messages/{message.id}.txt"
        # 写入文件...
        message.content = message.content_summary  # DB只存摘要
        message.has_full_content = False
    
    db.save_message(message)
```

---

## 六、消息路由机制

### 6.1 free-code: 结构化消息路由

```typescript
// teammateMailbox.ts
function isStructuredProtocolMessage(msg: Message): boolean {
  // 判断消息是否需要特殊处理，而非直接显示给用户
  return msg.type in [
    'idle_notification',
    'shutdown_request',
    'plan_approval_request',
    // 这些消息会被路由处理，不会出现在对话历史中
  ]
}

// 路由处理
if (isStructuredProtocolMessage(msg)) {
  await handleProtocolMessage(msg)  // 内部处理
} else {
  await displayToUser(msg)  // 显示给用户
}
```

**设计意图**:
- 协议消息不污染对话历史
- 用户界面更清晰，只显示业务消息
- Leader 自动处理协议消息

### 6.2 CoPaw: 统一处理

```python
# chatroom_poll_service.py
messages = db.get_messages(room_id, unread_only=True)
for msg in messages:
    # 所有消息统一触发Agent处理
    await self._trigger_agent(...)
```

**现状分析**:
- 所有消息都被 Agent 处理
- 协议消息（如 task_update）也进入 Agent 上下文
- 浪费 Agent token 处理非业务消息

### 6.3 改进建议：添加消息路由

```python
# chatroom_poll_service.py
PROTOCOL_MESSAGE_TYPES = ["agent_idle", "shutdown_request", "shutdown_response"]

async def poll_loop(self):
    messages = db.get_messages(room_id, unread_only=True)
    
    business_messages = []
    for msg in messages:
        if msg.message_type in PROTOCOL_MESSAGE_TYPES:
            # 协议消息：直接处理，不触发Agent
            await self._handle_protocol_message(msg)
        else:
            # 业务消息：收集后触发Agent
            business_messages.append(msg)
    
    if business_messages:
        await self._trigger_agent(business_messages)

async def _handle_protocol_message(self, msg: MailboxMessage):
    """处理协议消息，不触发Agent"""
    if msg.message_type == "agent_idle":
        # Worker空闲通知
        await self._on_worker_idle(msg.from_agent)
    elif msg.message_type == "shutdown_request":
        # 关闭协商请求
        await self._on_shutdown_request(msg)
```

---

## 七、退出协商机制

### 7.1 free-code: 优雅退出

```typescript
// Worker请求退出
await mailbox.sendMessage({
  type: 'shutdown_request',
  reason: 'Task completed, no pending work',
})

// Leader响应
await mailbox.sendMessage({
  type: 'shutdown_approved',  // 或 'shutdown_rejected'
  reason: 'Approved - all tasks done',
})

// 被拒绝时Worker继续工作
if (response.type === 'shutdown_rejected') {
  // 继续等待新任务
}
```

**设计意图**:
- Worker 不能擅自退出，需要协商
- Leader 可能拒绝（有新任务待分配）
- 防止 Worker 在有工作时退出

### 7.2 CoPaw: 无退出协商

```python
# Agent退出依赖外部控制（用户手动关闭）
# 无Worker主动退出机制
```

**现状分析**:
- Worker 无法主动请求退出
- 空闲 Worker 持续消耗资源（poll循环）
- 无法实现"任务完成后自动关闭Worker"

### 7.3 改进建议：添加退出协商

```python
# mailbox.py - 新增退出协商工具
async def mailbox_request_shutdown(
    room_id: str,
    agent_id: str,
    reason: str,
) -> ToolResponse:
    """Worker请求退出"""
    message = MailboxMessage(
        room_id=room_id,
        from_agent=agent_id,
        to_agent="lead",
        content=reason,
        message_type="shutdown_request",
    )
    db.save_message(message)
    return ToolResponse(...)

# chatroom_poll_service.py - 处理退出请求
async def _on_shutdown_request(self, msg: MailboxMessage):
    # 检查是否有待分配任务
    pending_tasks = db.get_tasks(room_id, status="pending", owner=None)
    
    if pending_tasks:
        # 有待分配任务，拒绝退出
        await mailbox_send(
            room_id=msg.room_id,
            to_agent=msg.from_agent,
            content=f"Rejected: {len(pending_tasks)} pending tasks",
            message_type="shutdown_response",
        )
    else:
        # 无待分配任务，批准退出
        await mailbox_send(
            room_id=msg.room_id,
            to_agent=msg.from_agent,
            content="Approved: shutdown",
            message_type="shutdown_response",
        )
        # 关闭Agent session
        await self._shutdown_agent(msg.from_agent)
```

---

## 八、计划协作机制

### 8.1 free-code: 计划审批流程

```typescript
// Leader发送计划提议
await mailbox.sendMessage({
  type: 'plan_proposal',
  content: planDetails,
})

// Worker反馈
await mailbox.sendMessage({
  type: 'plan_feedback',
  content: feedback,
  approved: true/false,
})
```

**用途**:
- Leader 提出执行计划，Worker 反馈可行性
- 避免单向命令式分配
- 协商式任务协调

### 8.2 CoPaw: 无计划协作

```python
# task_assign 是单向分配
message_type: "task_assign"  # Lead分配给Worker，无协商
```

### 8.3 改进建议：添加计划消息类型

```python
# chatroom.py - 扩展消息类型
class PlanProposal(BaseModel):
    """计划提议"""
    plan_id: str
    tasks: List[str]  # 拟分配的任务
    rationale: str    # 分配理由
    constraints: Optional[str] = None  # 约束条件

class PlanFeedback(BaseModel):
    """计划反馈"""
    plan_id: str
    approved: bool
    concerns: Optional[str] = None  # 担忧点
    suggestions: Optional[str] = None  # 建议

# mailbox_send支持发送计划
async def mailbox_send_plan(
    room_id: str,
    to_agent: str,
    plan: PlanProposal,
) -> ToolResponse:
    message = MailboxMessage(
        room_id=room_id,
        to_agent=to_agent,
        content=json.dumps(plan.model_dump()),
        message_type="plan_proposal",
    )
```

---

## 九、改进优先级矩阵

| 优先级 | 改进项 | 实现难度 | 预期收益 |
|--------|--------|----------|----------|
| **P0 高** | `agent_idle` 消息类型 | 低 | 减少轮询，实时响应 |
| **P0 高** | 消息路由机制 | 中 | 节省Agent token |
| **P1 中** | 进度跟踪字段 | 低 | 用户可见执行过程 |
| **P1 中** | 退出协商机制 | 中 | 资源优化 |
| **P2 低** | 消息摘要机制 | 中 | 存储优化 |
| **P2 低** | 计划协作消息 | 低 | 协商式任务分配 |

---

## 十、总结

### CoPaw 多Agent机制的优势

1. **数据存储可靠** - 数据库事务保证，优于文件存储
2. **Task模型清晰** - 显式状态管理，便于追踪
3. **PollService集中管理** - 单点控制，便于监控

### 需要改进的方面

1. **消息类型过于简单** - 缺乏语义区分和协议消息
2. **轮询驱动效率低** - 缺少主动通知机制
3. **进度不可见** - 用户只能看到最终状态
4. **缺乏协作协商** - 单向命令式分配
5. **历史膨胀风险** - 完整存储无摘要

### 核心改进方向

```
从"命令驱动"转向"协议驱动"
├── 丰富的消息类型（协议语义）
├── 消息路由（协议vs业务）
├── 主动通知（减少轮询）
└── 协商机制（退出、计划）
```

---

*报告基于 CoPaw chatroom.py, chatroom_poll_service.py, mailbox.py 与 free-code teammateMailbox.ts, inProcessRunner.ts 对比分析生成*
*分析日期: 2026-04-08*