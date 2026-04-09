# CoPaw 多Agent错误异常处理机制对比分析

**分析日期**: 2026-04-08
**对比对象**: CoPaw chatroom_poll_service.py vs free-code inProcessRunner.ts

---

## 一、错误处理流程对比

### 1.1 free-code 错误处理流程（完整）

```typescript
// inProcessRunner.ts:1465-1533
} catch (error) {
  const errorMessage = error instanceof Error ? error.message : 'Unknown error'
  
  logForDebugging(`[inProcessRunner] Agent ${identity.agentId} failed: ${errorMessage}`)

  // 1. 检查是否已经是终态，避免重复处理
  let alreadyTerminal = false
  let toolUseId: string | undefined
  
  updateTaskState(taskId, task => {
    if (task.status !== 'running') {
      alreadyTerminal = true  // 防止覆盖已处理的终态
      return task
    }
    toolUseId = task.toolUseId
    task.onIdleCallbacks?.forEach(cb => cb())
    task.unregisterCleanup?.()
    return {
      ...task,
      status: 'failed' as const,
      notified: true,           // 标记已通知
      error: errorMessage,      // 记录错误信息
      isIdle: true,
      endTime: Date.now(),
      onIdleCallbacks: [],
      messages: task.messages?.length ? [task.messages.at(-1)!] : undefined,
      pendingUserMessages: [],
      inProgressToolUseIDs: undefined,
      abortController: undefined,
      unregisterCleanup: undefined,
      currentWorkAbortController: undefined,
    }
  }, setAppState)

  // 2. 清理输出文件
  void evictTaskOutput(taskId)
  
  // 3. 从 AppState 中移除已终止的任务
  evictTerminalTask(taskId, setAppState)
  
  // 4. 发送 SDK 终止事件
  if (!alreadyTerminal) {
    emitTaskTerminatedSdk(taskId, 'failed', {
      toolUseId,
      summary: identity.agentId,
    })
  }

  // 5. 通过 mailbox 发送失败通知给 Leader
  await sendIdleNotification(identity.agentName, identity.color, identity.teamName, {
    idleReason: 'failed',
    completedStatus: 'failed',
    failureReason: errorMessage,   // 包含详细错误原因
  })

  // 6. 清理遥测资源
  unregisterPerfettoAgent(identity.agentId)
  
  return { success: false, error: errorMessage, messages: allMessages }
}
```

### 1.2 CoPaw 错误处理流程（当前实现）

```python
# chatroom_poll_service.py:649-666
except Exception as e:
    logger.error(
        "Error executing agent %s in room %s: %s",
        agent_id,
        room_id,
        e,
        exc_info=True,
    )
    # 异常发生 - 标记受影响的任务为失败
    await self._handle_execution_error(room_id, agent_id, task_ids_before, str(e))

finally:
    # 注销此执行
    async with self._lock:
        self._active_executions.pop(execution_key, None)

    # 执行后检查：验证任务是否正确更新
    await self._verify_task_completion(room_id, agent_id, task_ids_before)
```

```python
# chatroom_poll_service.py:691-714
async def _handle_execution_error(
    self,
    room_id: str,
    agent_id: str,
    task_ids: Set[str],
    error_message: str,
) -> None:
    """处理执行错误 - 标记任务为失败"""
    for task_id in task_ids:
        task = self._db.get_task(task_id)
        if task and task.status == "in_progress":
            logger.info(
                "Marking task %s as failed due to execution error: %s",
                task_id,
                error_message[:100],
            )
            task.status = "failed"
            task.updated_at = datetime.now()
            task.description = (task.description or "") + f"\n[Execution failed: {error_message[:200]}]"
            self._db.update_task(task)
            self._db.add_task_log_entry(task_id, "failed", f"Execution error: {error_message[:200]}")

            # 通知 Leader
            await self._notify_leader_task_failed(room_id, task, f"Execution error: {error_message[:100]}")
```

---

## 二、关键差异分析

### 2.1 终态检查（防重复处理）

| 项目 | free-code | CoPaw |
|------|-----------|-------|
| **实现** | ✅ `alreadyTerminal` 检查 | ❌ 无检查 |
| **作用** | 防止覆盖已处理的终态状态 | 可能重复处理 |

**free-code 实现**:
```typescript
if (task.status !== 'running') {
  alreadyTerminal = true  // 已被其他流程处理
  return task  // 不修改
}
```

**CoPaw 问题**:
```python
# 如果任务已被取消或其他流程处理，这里仍会执行
if task and task.status == "in_progress":
    # 只检查了 in_progress，但没有考虑并发场景
```

**改进建议**:
```python
async def _handle_execution_error(...):
    for task_id in task_ids:
        task = self._db.get_task(task_id)
        # 添加终态检查
        if not task or task.status in ("completed", "cancelled", "failed"):
            logger.debug("Task %s already in terminal state, skipping", task_id)
            continue
        # ... 处理逻辑
```

### 2.2 错误信息完整性

| 项目 | free-code | CoPaw |
|------|-----------|-------|
| **Task.error字段** | ✅ 有专门的 `error` 字段 | ❌ 写入 `description` |
| **错误时间戳** | ✅ `endTime` | ❌ 无 |
| **错误类型** | ✅ `idleReason: 'failed'` | ❌ 只有状态 |

**free-code 任务状态**:
```typescript
{
  status: 'failed',
  error: errorMessage,        // 专门的错误字段
  endTime: Date.now(),        // 失败时间
  notified: true,             // 已通知标记
}
```

**CoPaw 任务状态**:
```python
# 错误信息写入 description，不是专门字段
task.description = (task.description or "") + f"\n[Execution failed: {error_message[:200]}]"
```

**改进建议**: 在 Task 模型中添加专门的错误字段：

```python
# chatroom.py - Task 模型扩展
class Task(BaseModel):
    # 原有字段...
    
    # 新增：错误追踪
    error: Optional[str] = None          # 错误信息
    error_time: Optional[datetime] = None  # 错误发生时间
    error_type: Optional[str] = None     # 错误类型：exception, timeout, cancelled, max_iters
```

### 2.3 取消处理对比

**free-code 取消处理**:
```typescript
// inProcessRunner.ts:1291-1309
if (workWasAborted) {
  logForDebugging(`[inProcessRunner] ${identity.agentId} work interrupted, returning to idle`)
  
  // 添加中断消息到队友的消息列表
  const interruptMessage = createAssistantAPIErrorMessage({
    content: ERROR_MESSAGE_USER_ABORT,
  })
  updateTaskState(taskId, task => ({
    ...task,
    messages: appendCappedMessage(task.messages, interruptMessage),
  }), setAppState)
  
  // 继续等待下一个提示，不是直接退出
}
```

**CoPaw 取消处理**:
```python
# chatroom_poll_service.py:639-647
except asyncio.CancelledError:
    logger.info(
        "Agent execution cancelled for agent %s in room %s",
        agent_id,
        room_id,
    )
    await self._handle_execution_cancelled(room_id, agent_id, task_ids_before)
    raise  # 重新抛出
```

**差异**: 
- free-code: 工作中断后回到 idle 状态，继续等待新任务
- CoPaw: 取消后标记任务失败，抛出异常

**改进建议**: 区分"工作中断"和"生命周期终止"：

```python
async def _execute_agent(...):
    try:
        async for event in runner.stream_query(request):
            # ...
    except asyncio.CancelledError:
        # 区分取消类型
        if self._is_work_abort:  # 只是当前工作被中断
            await self._handle_work_interrupted(room_id, agent_id, task_ids_before)
            # 不重新抛出，继续轮询
        else:  # 整个 Agent 生命周期终止
            await self._handle_execution_cancelled(room_id, agent_id, task_ids_before)
            raise
```

### 2.4 资源清理对比

**free-code 清理流程**:
```typescript
// 1. 清理输出文件
void evictTaskOutput(taskId)

// 2. 从 AppState 移除
evictTerminalTask(taskId, setAppState)

// 3. 清理遥测
unregisterPerfettoAgent(identity.agentId)

// 4. 清理回调
task.onIdleCallbacks?.forEach(cb => cb())
task.unregisterCleanup?.()

// 5. 清理状态引用
abortController: undefined,
unregisterCleanup: undefined,
currentWorkAbortController: undefined,
```

**CoPaw 清理流程**:
```python
finally:
    # 只清理了 active_executions
    async with self._lock:
        self._active_executions.pop(execution_key, None)
    
    # 后续检查
    await self._verify_task_completion(room_id, agent_id, task_ids_before)
```

**改进建议**: 添加更完整的资源清理：

```python
async def _cleanup_execution_resources(self, room_id: str, agent_id: str, execution_key: str):
    """清理执行相关的所有资源"""
    async with self._lock:
        self._active_executions.pop(execution_key, None)
    
    # 清理 session 相关资源
    # 清理内存中的临时状态
    # 清理其他跟踪状态
```

### 2.5 通知机制对比

**free-code 通知**:
```typescript
// 通过 mailbox 发送结构化通知
await sendIdleNotification(identity.agentName, identity.color, identity.teamName, {
  idleReason: 'failed',
  completedStatus: 'failed',
  failureReason: errorMessage,  // 详细错误原因
  completedTaskId: task.id,     // 关联任务
  summary: getLastPeerDmSummary(allMessages),  // 摘要
})
```

**CoPaw 通知**:
```python
# 通过 mailbox 发送文本消息
notification_msg = (
    f"⚠️ 任务执行失败通知\n\n"
    f"任务 #{task.id[:6]} '{task.subject}' 执行失败。\n"
    f"执行者: {task.owner}\n"
    f"原因: {reason}\n\n"
    f"请检查任务状态并决定是否需要重新分配或重试。"
)
```

**差异**: 
- free-code: 结构化通知，机器可解析
- CoPaw: 纯文本通知，人类可读但难以程序处理

**改进建议**: 定义结构化通知类型：

```python
# models/chatroom.py
class TaskFailureNotification(BaseModel):
    """任务失败通知（结构化）"""
    type: Literal["task_failure"] = "task_failure"
    task_id: str
    agent_id: str
    error_type: str  # exception, timeout, cancelled, max_iters
    error_message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    retry_available: bool = True
```

### 2.6 超时检测机制

**free-code**: 依赖外部超时控制（AbortController）

**CoPaw**: 已实现超时检测：

```python
# chatroom_poll_service.py:211-259
async def _check_timeouts(self) -> None:
    """检查超时任务并发送通知"""
    try:
        timed_out_tasks = self._db.get_timed_out_tasks()
        stale_tasks = self._db.get_stale_tasks()
        
        for task in timed_out_tasks:
            # 添加日志
            self._db.add_task_log_entry(task.id, "timeout_warning", ...)
            # 通知任务所有者
            if task.owner:
                await self._send_timeout_notification(task, "timeout")
```

**评价**: CoPaw 的超时检测机制比 free-code 更完善。

### 2.7 任务日志追踪

**CoPaw 已实现**:
```python
# chatroom_poll_service.py
self._db.add_task_log_entry(task_id, "failed", f"Execution error: {error_message[:200]}")
self._db.add_task_log_entry(task_id, "timeout_warning", ...)
self._db.add_task_log_entry(task_id, "stale_warning", ...)
```

**free-code**: 依赖 AppState 中的 messages 数组

**评价**: CoPaw 的任务日志机制更结构化，便于追踪。

---

## 三、工具层错误处理对比

### 3.1 CoPaw 工具错误处理

```python
# task_management.py - 所有工具的模式
except Exception as e:
    logger.error(f"Error creating task: {e}", exc_info=True)
    return ToolResponse(
        content=[
            TextBlock(type="text", text=f"Error creating task: {str(e)}"),
        ],
    )
```

**问题**:
1. 异常信息直接暴露给 Agent，可能不够友好
2. 没有区分异常类型
3. 没有恢复建议

### 3.2 改进建议

```python
class TaskError(Exception):
    """任务相关错误基类"""
    def __init__(self, message: str, recoverable: bool = True, suggestion: str = None):
        super().__init__(message)
        self.recoverable = recoverable
        self.suggestion = suggestion

class TaskNotFoundError(TaskError):
    def __init__(self, task_id: str):
        super().__init__(
            f"Task '{task_id}' not found",
            recoverable=False,
            suggestion="Check if the task ID is correct or create a new task."
        )

class TaskAlreadyClaimedError(TaskError):
    def __init__(self, task_id: str, current_owner: str):
        super().__init__(
            f"Task '{task_id}' is already claimed by '{current_owner}'",
            recoverable=True,
            suggestion="Wait for the current owner to complete or release the task."
        )

# 使用示例
async def task_claim(...):
    try:
        result = db.claim_task(...)
        if not result.success:
            if result.reason == 'task_not_found':
                raise TaskNotFoundError(task_id)
            elif result.reason == 'already_claimed':
                raise TaskAlreadyClaimedError(task_id, result.task.owner)
            # ...
    except TaskError as e:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(e))],
        )
```

---

## 四、改进优先级

| 优先级 | 改进项 | 影响 | 工作量 |
|--------|--------|------|--------|
| **P0** | 终态检查（防重复处理） | 防止状态混乱 | 小 |
| **P0** | Task.error 专门字段 | 错误追踪更清晰 | 小 |
| **P1** | 结构化失败通知 | 便于程序处理 | 小 |
| **P1** | 区分工作中断 vs 生命周期终止 | 恢复机制更合理 | 中 |
| **P2** | 工具层错误分类 | 错误信息更友好 | 中 |
| **P2** | 资源清理完整性 | 防止内存泄漏 | 中 |

---

## 五、具体改进代码

### 5.1 Task 模型扩展

```python
# chatroom.py
class Task(BaseModel):
    # 原有字段...
    
    # 错误追踪（新增）
    error: Optional[str] = None
    error_type: Optional[Literal["exception", "timeout", "cancelled", "max_iters"]] = None
    error_time: Optional[datetime] = None
    
    # 通知状态（新增）
    failure_notified: bool = False  # 避免重复通知
```

### 5.2 终态检查改进

```python
# chatroom_poll_service.py
async def _handle_execution_error(...):
    for task_id in task_ids:
        task = self._db.get_task(task_id)
        
        # 终态检查
        if not task:
            logger.warning("Task %s not found during error handling", task_id)
            continue
        if task.status in ("completed", "cancelled", "failed"):
            logger.debug("Task %s already in terminal state (%s), skipping", task_id, task.status)
            continue
        
        # 更新任务
        task.status = "failed"
        task.error = error_message
        task.error_type = "exception"
        task.error_time = datetime.now()
        task.updated_at = datetime.now()
        
        self._db.update_task(task)
        self._db.add_task_log_entry(task_id, "failed", f"Execution error: {error_message[:200]}")
        
        # 检查是否已通知
        if not task.failure_notified:
            await self._notify_leader_task_failed(room_id, task, error_message)
            task.failure_notified = True
            self._db.update_task(task)
```

### 5.3 结构化失败通知

```python
# models/chatroom.py
class TaskFailureNotification(BaseModel):
    """任务失败通知"""
    type: Literal["task_failure"] = "task_failure"
    task_id: str
    task_subject: str
    agent_id: str
    error_type: str
    error_message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3

# chatroom_poll_service.py
async def _notify_leader_task_failed(...):
    notification = TaskFailureNotification(
        task_id=task.id,
        task_subject=task.subject,
        agent_id=task.owner,
        error_type=task.error_type or "unknown",
        error_message=reason,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
    )
    
    message = MailboxMessage(
        room_id=room_id,
        from_agent="system",
        to_agent=room.lead_agent_id,
        content=json.dumps(notification.model_dump()),
        message_type="task_failure",  # 新增类型
    )
    self._db.save_message(message)
```

---

## 六、总结

### CoPaw 已做好的方面

1. ✅ 超时检测机制（比 free-code 更完善）
2. ✅ 任务日志追踪
3. ✅ 通知 Leader 机制
4. ✅ 数据库事务保护
5. ✅ 原子任务认领

### 需要改进的方面

1. ❌ **终态检查** - 防止重复处理已失败/取消的任务
2. ❌ **错误字段** - 使用专门的 `error` 字段而非写入 description
3. ❌ **结构化通知** - 便于程序解析而非纯文本
4. ❌ **工作中断区分** - 区分"工作中断"和"生命周期终止"
5. ❌ **工具层错误分类** - 提供恢复建议

### 核心改进方向

```
从"文本描述错误"转向"结构化错误追踪"
├── Task.error 字段（而非写入 description）
├── 终态检查（防止重复处理）
├── 结构化通知（机器可解析）
└── 错误分类（提供恢复建议）
```

---

*报告基于 CoPaw chatroom_poll_service.py, task_management.py 与 free-code inProcessRunner.ts, teammateMailbox.ts 对比分析生成*
*分析日期: 2026-04-08*