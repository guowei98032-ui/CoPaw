# CoPaw Sub-Agent (Fork) 设计方案

**设计日期**: 2026-04-08
**参考项目**: free-code Sub-Agent机制
**目标**: 为CoPaw实现Sub-Agent(Fork)功能，多Agent机制在其他地方单独设计

---

## 一、设计原则优先级

| 原则 | 优先级 | 说明 |
|------|--------|------|
| **上下文连续性** | P0 | Sub-Agent继承父Agent的memory状态和request_context |
| **任务委托** | P0 | 父Agent决策，Sub-Agent执行，返回结果 |
| **噪声隔离** | P1 | 父Agent只收到最终结果，不看到中间过程 |
| **并行执行** | P1 | 多个Sub-Agent可同时运行 |
| **工具继承** | P2 | Sub-Agent共享父Agent的Toolkit |

> **注意**: 缓存共享(Cache Sharing)不是设计目的，而是副作用。即使禁用缓存，Sub-Agent的核心价值依然存在。

---

## 二、模块设计

### 2.1 新增文件

```
src/copaw/agents/
├── fork_agent.py          # ForkAgent + ForkManager 实现
├── tools/
│   └── fork.py            # fork_task, fork_parallel 工具
└── config/
    └── context.py         # 扩展: agent context变量
```

### 2.2 ForkConfig 配置类

```python
@dataclass
class ForkConfig:
    """Configuration for fork sub-agent."""

    # Task specification
    task_id: str              # Fork任务唯一标识
    directive: str            # 要执行的任务描述

    # Context inheritance (what to share/clone)
    inherit_memory: bool = True       # 克隆父Agent的Memory副本
    inherit_toolkit: bool = True      # 共享父Agent的Toolkit (工具无状态)
    inherit_skills: bool = True       # 继承Skills配置
    inherit_request_context: bool = True  # 克隆request_context
    # CRITICAL: MCP Clients should NEVER be shared
    inherit_mcp_clients: bool = False  # 必须为False!

    # Behavior control
    max_iters: int = 10              # Fork最大迭代次数
    timeout_seconds: float = 300.0   # 任务超时时间
    report_max_words: int = 500      # 结果报告最大字数

    # Recursion control
    max_fork_depth: int = 1          # 最大fork深度，默认禁止递归

    # Isolation options
    isolated_memory_write: bool = True  # Fork写入隔离Memory
```

### 2.3 ForkResult 结果类

```python
@dataclass
class ForkResult:
    """Result returned from fork sub-agent."""

    task_id: str
    status: str               # "completed", "failed", "timeout", "cancelled"
    summary: str              # 任务摘要
    result: str               # 实际结果/输出
    key_files: List[str]      # 相关文件路径
    files_changed: List[str]  # 修改的文件列表
    issues: List[str]         # 遇到的问题
    usage: dict               # token使用统计
    error: Optional[str]      # 错误信息
```

---

## 三、核心实现

### 3.1 ForkAgent 类

```python
class ForkAgent:
    """Sub-Agent that inherits parent context and executes delegated tasks.

    Key features:
    1. Context Continuity: Inherits parent's memory state at fork time
    2. Task Delegation: Parent specifies directive, fork executes
    3. Noise Isolation: Only returns ForkResult to parent
    4. Parallel Execution: Multiple forks can run concurrently
    5. Tool Inheritance: Shares parent's toolkit (tool functions are stateless)

    Component Sharing Strategy:
    - Toolkit: SHARED (tool functions are stateless, only references)
    - MCP Clients: NOT SHARED (connection state cannot be shared)
    - Memory: CLONED COPY (write isolation from parent)
    - ContextVar: AUTO-ISOLATED (Python coroutine level isolation)
    """

    def __init__(self, parent: "CoPawAgent", config: ForkConfig):
        self.parent = parent
        self.config = config
        self.task_id = config.task_id

        # Create isolated context (with recursion check)
        self._fork_context = self._create_fork_context()

        # Create fork agent instance
        self._fork_agent = self._create_fork_agent()

    def _create_fork_context(self) -> dict:
        """Create isolated context for fork with recursion protection."""
        context = {}

        if self.config.inherit_request_context:
            parent_ctx = getattr(self.parent, "_request_context", {})

            # CRITICAL: Detect if already in Fork context
            if parent_ctx.get("is_fork", False):
                raise RecursiveForkError(
                    "Nested fork is not allowed. "
                    "Fork agents cannot create their own forks."
                )

            context["request_context"] = dict(parent_ctx)
            context["request_context"]["is_fork"] = True
            context["request_context"]["fork_task_id"] = self.task_id
            context["request_context"]["fork_depth"] = parent_ctx.get("fork_depth", 0) + 1

        context["workspace_dir"] = getattr(self.parent, "_workspace_dir", None)
        context["agent_config"] = getattr(self.parent, "_agent_config", None)
        context["language"] = getattr(self.parent, "_language", "zh")

        return context

    def _clone_memory_state(self) -> InMemoryMemory:
        """Clone parent's memory state for fork.

        Fork inherits the conversation history up to fork point,
        but writes to isolated memory (not affecting parent).
        """
        fork_memory = InMemoryMemory()

        if self.config.inherit_memory and self.parent.memory:
            for msg, marks in self.parent.memory.content:
                cloned_msg = self._clone_message(msg)
                fork_memory.add(cloned_msg)

        return fork_memory

    def _create_fork_agent(self) -> "CoPawAgent":
        """Create fork CoPawAgent instance.

        Critical design decisions:
        - Toolkit: Share parent's toolkit (tools are stateless functions)
        - MCP Clients: Empty list (connection state cannot be shared!)
        - Memory: Cloned copy from parent
        """
        from .react_agent import CoPawAgent

        fork_context = self._fork_context
        config = self.config

        # Create fork agent WITHOUT MCP clients
        fork_agent = CoPawAgent(
            agent_config=fork_context.get("agent_config"),
            env_context=self._build_fork_prompt(),
            enable_memory_manager=False,  # Fork doesn't need memory persistence
            mcp_clients=[],  # CRITICAL: Do NOT share MCP clients!
            memory_manager=None,  # Fork doesn't need memory manager
            request_context=fork_context.get("request_context"),
            workspace_dir=fork_context.get("workspace_dir"),
        )

        # Share parent's Toolkit (tools are stateless)
        if config.inherit_toolkit:
            fork_agent.toolkit = self.parent.toolkit

        # Override memory with cloned state
        fork_agent.memory = self._clone_memory_state()

        # Override max_iters
        fork_agent.max_iters = config.max_iters

        return fork_agent

    def _build_fork_prompt(self) -> str:
        """Build fork-specific prompt with directive and rules."""
        boilerplate = """
STOP. READ THIS FIRST.

You are a forked worker process. You are NOT the main agent.

RULES (non-negotiable):
1. Do NOT spawn sub-agents; execute directly
2. Do NOT use fork_task or fork_parallel tools
3. Do NOT converse, ask questions, or suggest next steps
4. USE your tools directly: shell, read_file, write_file, etc.
5. Keep your report under {max_words} words
6. Your response MUST begin with "Scope:"
7. Focus on completing the assigned directive efficiently

Output format:
  Scope: <assigned scope in one sentence>
  Result: <the answer or key findings>
  Key files: <relevant file paths>
  Files changed: <list of modified files>
  Issues: <list if any>
"""
        return f"{boilerplate}\n\n<directive>\n{self.config.directive}\n</directive>"


class RecursiveForkError(Exception):
    """Raised when a fork attempts to create another fork."""
    pass
```

### 3.2 ForkManager 类

```python
class ForkManager:
    """Manages multiple concurrent fork sub-agents."""

    def __init__(self, parent: "CoPawAgent"):
        self.parent = parent
        self._forks: dict[str, ForkAgent] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def fork(self, directive: str, config: Optional[ForkConfig] = None) -> ForkResult:
        """Create and execute a single fork sub-agent."""
        if config is None:
            config = ForkConfig(directive=directive)

        fork_agent = ForkAgent(self.parent, config)
        self._forks[fork_agent.task_id] = fork_agent

        result = await fork_agent.execute()
        return result

    async def fork_parallel(
        self,
        directives: List[str],
        shared_config: Optional[ForkConfig] = None,
    ) -> List[ForkResult]:
        """Create and execute multiple fork sub-agents in parallel."""
        fork_agents = [ForkAgent(self.parent, ForkConfig(directive=d)) for d in directives]

        for fa in fork_agents:
            self._forks[fa.task_id] = fa

        results = await asyncio.gather(
            *[fa.execute() for fa in fork_agents],
            return_exceptions=True,
        )

        return results

    def cancel_fork(self, task_id: str) -> bool:
        """Cancel a specific fork."""
        fork = self._forks.get(task_id)
        if fork:
            fork.cancel()
            return True
        return False

    def list_active(self) -> List[str]:
        """List all active fork task IDs."""
        return [
            task_id for task_id, fork in self._forks.items()
            if fork._task and not fork._task.done()
        ]
```

---

## 四、工具集成

### 4.1 fork_task 工具

```python
async def fork_task(
    directive: str,
    max_iters: int = 10,
    timeout_seconds: float = 300.0,
) -> ToolResponse:
    """Execute a task in a fork sub-agent.

    The fork sub-agent inherits your context (memory, tools, workspace)
    but executes in isolation. You will only see the final result.

    Args:
        directive: Task description for fork to execute
        max_iters: Maximum iterations for fork (default: 10)
        timeout_seconds: Task timeout in seconds (default: 300)

    Returns:
        ToolResponse: Fork result with status and output
    """
    from ...config.context import get_current_agent
    parent = get_current_agent()

    if parent is None:
        return ToolResponse(content=[
            TextBlock(type="text", text="Error: No parent agent context available."),
        ])

    # Detect if in Fork context - prevent recursion
    request_context = getattr(parent, "_request_context", {})
    if request_context.get("is_fork", False):
        return ToolResponse(content=[
            TextBlock(
                type="text",
                text=(
                    "Error: Cannot create fork from a fork agent. "
                    "Execute your task directly without delegating to sub-agents."
                ),
            ),
        ])

    fork_manager = ForkManager(parent)
    config = ForkConfig(directive=directive, max_iters=max_iters, timeout_seconds=timeout_seconds)
    result = await fork_manager.fork(directive, config)

    response_text = _format_fork_result(result)
    return ToolResponse(content=[TextBlock(type="text", text=response_text)])
```

### 4.2 fork_parallel 工具

```python
async def fork_parallel(
    directives: List[str],
    max_iters: int = 10,
    timeout_seconds: float = 300.0,
) -> ToolResponse:
    """Execute multiple tasks in parallel fork sub-agents.

    Args:
        directives: List of task descriptions
        max_iters: Maximum iterations per fork (default: 10)
        timeout_seconds: Timeout per fork (default: 300)

    Returns:
        ToolResponse: Combined results from all forks
    """
    parent = get_current_agent()
    fork_manager = ForkManager(parent)
    shared_config = ForkConfig(max_iters=max_iters, timeout_seconds=timeout_seconds)

    results = await fork_manager.fork_parallel(directives, shared_config=shared_config)

    response_text = "# Parallel Fork Results\n\n"
    for i, result in enumerate(results):
        response_text += f"## Fork {i+1}\n{_format_fork_result(result)}\n\n"

    return ToolResponse(content=[TextBlock(type="text", text=response_text)])
```

---

## 五、Context支持

### 5.1 扩展 context.py

```python
# src/copaw/config/context.py

import contextvars
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.react_agent import CoPawAgent

# Python equivalent of AsyncLocalStorage
_current_agent: contextvars.ContextVar[Optional["CoPawAgent"]] = (
    contextvars.ContextVar("current_agent", default=None)
)

def set_current_agent(agent: Optional["CoPawAgent"]) -> None:
    """Set current agent instance in context."""
    _current_agent.set(agent)

def get_current_agent() -> Optional["CoPawAgent"]:
    """Get current agent instance from context.

    Used by fork tools to access parent agent.
    """
    return _current_agent.get()
```

### 5.2 集成到 CoPawAgent

```python
# src/copaw/agents/react_agent.py 修改

async def reply(self, msg: Msg | list[Msg] | None = None, ...) -> Msg:
    # Set agent context for fork tools
    from ..config.context import set_current_agent
    set_current_agent(self)

    # ... existing reply logic ...
```

---

## 六、使用示例

### 6.1 单任务Fork

```python
# Agent通过工具调用
await fork_task(
    directive="Search for authentication implementation in src/auth/",
    max_iters=5,
)
```

### 6.2 并行Fork (MapReduce模式)

```python
# 同时执行多个研究任务
await fork_parallel(
    directives=[
        "Find all API endpoints that require authentication",
        "List all database models related to user accounts",
        "Check security vulnerabilities in login flow",
    ],
)
```

---

## 七、与free-code对比

| 特性 | free-code (Fork) | CoPaw (ForkAgent) |
|------|-----------------|-------------------|
| **上下文继承** | buildForkedMessages + CacheSafeParams | `_clone_memory_state()` 克隆Memory副本 |
| **工具继承** | 继承父agent的tools (通过options) | 共享父agent.toolkit (工具函数无状态) |
| **MCP隔离** | 每个fork独立的MCP服务器 | `mcp_clients=[]` 不继承 |
| **递归防护** | prompt约束 | 代码层面检测+异常抛出 |
| **隔离机制** | createSubagentContext | ForkConfig + `_create_fork_context` |
| **通信方式** | placeholder + directive | ForkResult结构化返回 |
| **并行执行** | 多Agent调用并行 | `fork_parallel` + asyncio.gather |
| **上下文存储** | AsyncLocalStorage | `contextvars.ContextVar` |
| **任务追踪** | Task Framework + LocalAgentTask | ForkManager + asyncio.Task |
| **缓存共享** | placeholder实现90%命中 | 未实现(非核心目的) |

---

## 八、核心价值实现对照

| 核心价值 | free-code实现 | CoPaw实现 |
|---------|--------------|-----------|
| **上下文连续性** | 完整继承父agent的messages prefix | `_clone_memory_state()`克隆全部memory.content |
| **任务委托** | FORK_PLACEHOLDER + directive | `_build_fork_prompt()`生成规则+指令 |
| **噪声隔离** | 子agent无法修改父state | ForkResult结构化返回，无中间输出 |
| **并行执行** | 多Agent调用同一消息 | `fork_parallel()`使用asyncio.gather |
| **工具继承** | 相同tools配置 | 共享父agent的Toolkit |

---

## 九、后续扩展

### 9.1 短期
- 实现完整的`fork_agent.py`模块
- 在`react_agent.py`中集成context设置
- 注册`fork_task`和`fork_parallel`工具

### 9.2 中期
- 添加Fork进度追踪(类似free-code的LocalAgentTask)
- 实现Fork任务持久化(可选)
- 添加Fork结果缓存机制

### 9.3 长期(可选)
- 实现Prompt缓存共享(类似free-code的placeholder机制)
- Fork间的轻量通信(Mailbox简化版)
- Fork任务优先级管理

---

## 十、Session冲突风险分析

### 10.1 Memory隔离验证

AgentScope的ReActAgent在`_acting`中记录工具结果：

```python
# agentscope/agent/_react_agent.py:714
async def _acting(self, tool_call):
    ...
    finally:
        await self.memory.add(tool_res_msg)  # 记录到自己的memory
```

**结论**：ForkAgent有独立的`self.memory`实例，其工具调用结果自动隔离。

### 10.2 ContextVar隔离验证

Python的`contextvars.ContextVar`特性：
- 每个`asyncio.Task`有独立的context副本
- 父任务设置的值不会泄漏到子任务
- 子任务修改不影响父任务

```python
# 父Agent.reply() 设置:
set_current_workspace_dir(workspace_a)

# ForkAgent.reply() 设置(独立context):
set_current_workspace_dir(workspace_b)

# 工具函数读取时，各自读到自己的值
```

**结论**：ContextVar天然协程安全，无需额外处理。

### 10.3 Session保存路径分析

```
runner.query_handler():
    1. load_session_state(session_id, agent=父Agent)
    2. 父Agent.reply()
       └─ fork_task 工具被调用
          └─ ForkAgent.execute()
             └─ ForkAgent.reply()  # 不经过runner，不触发session保存
    3. save_session_state(session_id, agent=父Agent)  # 只保存父Agent
```

**结论**：Fork不经过runner，不会污染session文件。

### 10.4 风险矩阵

| 风险点 | 风险等级 | 说明 | 解决方案 |
|--------|----------|------|----------|
| Memory隔离 | ✅ 安全 | ForkAgent克隆memory副本 | 配置`inherit_memory=True`克隆 |
| ContextVar隔离 | ✅ 安全 | 协程天然隔离 | 无需处理 |
| Session保存 | ✅ 安全 | Fork不经过runner | 无需处理 |
| **Toolkit共享** | ✅ 安全 | 工具函数无状态 | 直接共享父Agent.toolkit |
| **Skills共享** | ✅ 安全 | 只读配置 | 直接共享 |
| **MCP Clients共享** | ❌ 高危 | 连接状态不能共享 | 强制`mcp_clients=[]` |
| Memory Manager | ⚠️ 中 | Fork不需要持久化 | 设置`memory_manager=None` |
| 文件系统竞争 | ⚠️ 中 | 父子同时修改同一文件 | 文档说明风险 |

### 10.5 组件共享决策表

| 组件 | 共享? | 原因 |
|------|-------|------|
| Toolkit | ✅ 共享 | 工具函数无状态，只是schema和函数引用 |
| Skills | ✅ 共享 | 只读配置，无状态 |
| workspace_dir | ✅ 共享 | 通过ContextVar传递，协程安全 |
| MCP Clients | ❌ 不共享 | 有连接状态，并发访问危险 |
| Memory | ❌ 克隆副本 | 写入隔离，否则污染父会话 |
| Memory Manager | ❌ 不共享 | Fork不需要持久化 |
| request_context | ✅ 克隆 | 创建副本，标记is_fork=True |

### 10.6 为什么Toolkit可以共享？

```python
# Toolkit内部结构（简化）
class Toolkit:
    tools: dict[str, ToolFunction]  # 只是函数引用
    schemas: dict[str, dict]        # JSON Schema

# 工具函数执行时的状态来源
async def execute_shell_command(cmd: str):
    workspace = get_current_workspace_dir()  # 从ContextVar读取
    # 工具函数本身没有实例状态
```

关键点：
1. **工具函数是无状态的** - 状态通过ContextVar传递
2. **ContextVar协程隔离** - Fork设置自己的context不影响父
3. **MCP是有状态的** - 连接、会话状态不能共享

### 10.7 Fork结果处理流程

```
Fork执行完成后，ForkResult如何处理？

选项A: 自动追加到父Agent.memory
  - 违背噪声隔离原则
  - 不推荐

选项B: 仅作为工具返回值，由父Agent决定
  - 符合噪声隔离
  - 父Agent可选择是否纳入记忆
  - 推荐 ✓

当前设计采用选项B：
- fork_task返回ToolResponse
- 父Agent的_acting将其作为tool_result记录
- 父Agent可以在下一轮reasoning中看到ForkResult
- 但Fork内部的详细过程不进入父Agent.memory
```

---

## 十一、递归Fork防护

### 11.1 问题分析

```
潜在风险：子Agent再次fork → 无限递归

父Agent
  └─ Fork 1: "分析代码库"
      └─ Fork 1-1: "分析模块A"
          └─ Fork 1-1-1: "分析文件a.py"
              └─ Fork 1-1-1-1: ...  // 深度不可控！
```

风险：
- 资源爆炸：API调用、token消耗指数增长
- 死循环：某些任务可能无限fork
- 超时：父级等待子级，子级等待子子级

### 11.2 防护策略

**策略：代码层面禁止递归Fork**

```python
class ForkAgent:
    def _create_fork_context(self) -> dict:
        context = {}

        if self.config.inherit_request_context:
            parent_ctx = getattr(self.parent, "_request_context", {})

            # 关键：检测是否已在Fork上下文中
            if parent_ctx.get("is_fork", False):
                raise RecursiveForkError(
                    "Nested fork is not allowed. "
                    "Fork agents cannot create their own forks."
                )

            context["request_context"] = dict(parent_ctx)
            context["request_context"]["is_fork"] = True
            context["request_context"]["fork_task_id"] = self.task_id
            context["request_context"]["fork_depth"] = parent_ctx.get("fork_depth", 0) + 1

        return context
```

### 11.3 防护层级

| 层级 | 防护方式 | 可靠性 | 代码位置 |
|------|----------|--------|----------|
| Prompt约束 | Directive中明确禁止 | 低（模型可能忽略） | `_build_fork_prompt()` |
| 工具检测 | fork_task检测is_fork标记 | 高 | `fork_task()` 工具函数 |
| 异常抛出 | ForkAgent初始化时检查 | 最高 | `_create_fork_context()` |

### 11.4 可选：有限深度递归

如果未来需要支持有限深度递归（如最多2层）：

```python
class ForkConfig:
    max_fork_depth: int = 1  # 默认禁止递归

class ForkAgent:
    def _create_fork_context(self) -> dict:
        parent_ctx = getattr(self.parent, "_request_context", {})
        current_depth = parent_ctx.get("fork_depth", 0)

        max_depth = self.config.max_fork_depth
        if current_depth >= max_depth:
            raise RecursiveForkError(
                f"Fork depth {current_depth} exceeds maximum {max_depth}"
            )

        context["request_context"]["fork_depth"] = current_depth + 1
        return context
```

当前设计：**默认禁止递归Fork**（max_fork_depth=1）

---

## 十二、实现检查清单

### 12.1 必须确保

- [x] ForkAgent克隆父Agent的Memory副本（`inherit_memory=True`）
- [x] ForkAgent共享父Agent的Toolkit（`inherit_toolkit=True`）
- [x] ForkAgent **不**继承MCP Clients（`mcp_clients=[]`）
- [x] ForkAgent不通过runner执行（直接调用`agent.reply()`）
- [x] ForkAgent执行完成后不调用session保存
- [x] ForkAgent设置独立的ContextVar值（协程自动隔离）
- [x] ForkAgent禁止递归Fork（检测`is_fork`标记）

### 12.2 组件共享决策速查表

```
ForkAgent 应该:
  ✅ 共享 Toolkit        (工具函数无状态)
  ✅ 共享 Skills配置     (只读)
  ✅ 共享 workspace_dir  (ContextVar传递)
  ✅ 克隆 Memory副本     (继承历史，写入隔离)
  ❌ 不共享 MCP Clients  (有连接状态)
  ❌ 不共享 Memory Manager (Fork不持久化)
  ❌ 不允许递归Fork      (代码层面禁止)
```

### 12.3 可选配置

- [ ] 支持配置`inherit_memory=True/False`
- [ ] 支持配置`max_iters`限制迭代次数
- [ ] 支持配置`timeout_seconds`超时
- [ ] 支持配置`report_max_words`限制输出
- [ ] 支持配置`max_fork_depth`有限递归

### 12.4 测试用例

```python
# 测试Memory隔离（写入不污染父）
async def test_fork_memory_write_isolation():
    parent = CoPawAgent(...)
    await parent.memory.add(Msg("user", "父消息", "user"))
    initial_len = len(parent.memory.content)

    fork_manager = ForkManager(parent)
    result = await fork_manager.fork("执行一些操作")

    # Fork的内部执行不进入父memory
    assert len(parent.memory.content) == initial_len + 1  # 只有fork_task的tool_result

# 测试Toolkit共享（工具可用）
async def test_fork_toolkit_shared():
    parent = CoPawAgent(...)
    parent_tool_count = len(parent.toolkit.tools)

    fork_manager = ForkManager(parent)
    result = await fork_manager.fork("使用read_file读取README.md")

    assert result.status == "completed"
    fork_agent = fork_manager._forks[result.task_id]._fork_agent
    assert fork_agent.toolkit is parent.toolkit  # 共享同一实例

# 测试MCP隔离（不共享连接）
async def test_fork_mcp_isolation():
    parent = CoPawAgent(..., mcp_clients=[mcp_client])

    fork_manager = ForkManager(parent)
    result = await fork_manager.fork("测试任务")

    fork_agent = fork_manager._forks[result.task_id]._fork_agent
    assert len(fork_agent._mcp_clients) == 0  # Fork没有MCP
    assert len(parent._mcp_clients) == 1      # 父Agent保留MCP

# 测试递归Fork防护
async def test_recursive_fork_blocked():
    parent = CoPawAgent(...)

    fork_manager = ForkManager(parent)
    result = await fork_manager.fork("执行任务")

    # 尝试在Fork中再创建Fork
    fork_agent = fork_manager._forks[result.task_id]._fork_agent
    inner_fork_manager = ForkManager(fork_agent)

    with pytest.raises(RecursiveForkError):
        await inner_fork_manager.fork("内部任务")
```

---

## 十三、执行流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    父Agent (session_id: "abc123")                │
│                                                                  │
│  1. _reasoning: "我需要研究auth模块"                              │
│  2. _acting: 调用 fork_task 工具                                  │
│     │                                                            │
│     │  fork_task 工具执行:                                        │
│     │  ┌────────────────────────────────────────────────────┐   │
│     │  │  ForkAgent (独立memory实例，共享toolkit)            │   │
│     │  │                                                     │   │
│     │  │  3. _reasoning: "执行shell命令"                      │   │
│     │  │  4. _acting: execute_shell_command                  │   │
│     │  │     → 结果记录到 ForkAgent.memory ✓                  │   │
│     │  │  5. _reasoning: "读取文件"                           │   │
│     │  │  6. _acting: read_file                             │   │
│     │  │     → 结果记录到 ForkAgent.memory ✓                  │   │
│     │  │  ... 多次迭代 ...                                    │   │
│     │  │  7. 返回 ForkResult                                 │   │
│     │  └────────────────────────────────────────────────────┘   │
│     │                                                            │
│  8. fork_task 返回 ToolResponse(ForkResult)                      │
│  9. 父Agent._acting finally:                                     │
│     → ToolResponse 记录到 父Agent.memory ✓                        │
│                                                                  │
│ 10. runner.session.save_session_state("abc123", agent)          │
│     → 保存父Agent.memory (包含fork_task的结果)                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 十四、超时机制设计

### 14.1 当前CoPaw超时现状

| 层级 | 超时机制 | 说明 |
|------|----------|------|
| **工具级** | 部分有 | `execute_shell_command(timeout=60)` 自己实现 |
| **框架级** | ❌ 无 | AgentScope Toolkit无统一超时 |
| **审批级** | ✅ 有 | `TOOL_GUARD_APPROVAL_TIMEOUT_SECONDS=600` |

```python
# AgentScope的call_tool_function没有超时包装
async def call_tool_function(self, tool_call):
    # 直接调用，没有超时保护
    res = await tool_func.original_func(**kwargs)
```

### 14.2 ForkAgent超时实现

```python
class ForkAgent:
    async def execute(self) -> ForkResult:
        """Execute the fork task with timeout protection."""
        config = self.config
        task_id = self.task_id

        try:
            # Create execution task
            self._task = asyncio.create_task(self._run_fork_agent())

            # Wait with timeout
            result = await asyncio.wait_for(
                self._task,
                timeout=config.timeout_seconds,
            )

            self._result = result
            logger.info(
                f"Fork task completed: task_id={task_id}, "
                f"status={result.status}"
            )
            return result

        except asyncio.TimeoutError:
            # Timeout handling - cancel and cleanup
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

            result = ForkResult(
                task_id=task_id,
                status="timeout",
                summary=f"Task timed out after {config.timeout_seconds}s",
                result="",
                error="Timeout",
            )
            self._result = result
            logger.warning(f"Fork task timed out: task_id={task_id}")
            return result

        except asyncio.CancelledError:
            # External cancellation
            result = ForkResult(
                task_id=task_id,
                status="cancelled",
                summary="Task was cancelled",
                result="",
                error="Cancelled",
            )
            self._result = result
            logger.info(f"Fork task cancelled: task_id={task_id}")
            return result

        except Exception as e:
            logger.error(
                f"Fork task failed: task_id={task_id}, error={e}",
                exc_info=True,
            )
            result = ForkResult(
                task_id=task_id,
                status="failed",
                summary="Task execution failed",
                result="",
                error=str(e),
            )
            self._result = result
            return result
```

### 14.3 工具级超时建议

为CoPaw的内置工具添加统一的超时参数：

```python
# 建议：为关键工具添加超时参数

async def read_file(
    path: str,
    timeout: float = 30.0,  # 新增
) -> ToolResponse:
    """Read file with timeout protection."""
    try:
        return await asyncio.wait_for(
            _read_file_impl(path),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return ToolResponse(content=[
            TextBlock(type="text", text=f"Error: Read timeout after {timeout}s"),
        ])

async def browser_use(
    url: str,
    timeout: float = 60.0,  # 新增
) -> ToolResponse:
    """Browser with timeout."""
    try:
        return await asyncio.wait_for(
            _browser_use_impl(url),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return ToolResponse(content=[
            TextBlock(type="text", text=f"Error: Browser timeout after {timeout}s"),
        ])
```

### 14.4 超时配置常量

```python
# constant.py 新增

# Default timeout for fork sub-agent (seconds)
FORK_DEFAULT_TIMEOUT_SECONDS = EnvVarLoader.get_float(
    "COPAW_FORK_DEFAULT_TIMEOUT_SECONDS",
    300.0,  # 5 minutes
    min_value=10.0,
)

# Default timeout for file operations (seconds)
FILE_OPERATION_TIMEOUT_SECONDS = EnvVarLoader.get_float(
    "COPAW_FILE_OPERATION_TIMEOUT_SECONDS",
    30.0,
    min_value=1.0,
)

# Default timeout for browser operations (seconds)
BROWSER_OPERATION_TIMEOUT_SECONDS = EnvVarLoader.get_float(
    "COPAW_BROWSER_OPERATION_TIMEOUT_SECONDS",
    60.0,
    min_value=10.0,
)
```

### 14.5 超时层级关系

```
Fork任务超时 (300s)
  └─ 工具执行超时 (各自独立)
      ├─ execute_shell_command: 60s
      ├─ read_file: 30s (建议添加)
      ├─ browser_use: 60s (建议添加)
      └─ write_file: 30s (建议添加)

如果单个工具超时 < Fork超时，工具先超时
如果所有工具执行时间总和 > Fork超时，Fork整体超时
```

---

*设计方案基于free-code graphify分析成果*
*设计日期: 2026-04-08*
*更新: Session冲突风险分析 + 递归Fork防护 + 超时机制设计*