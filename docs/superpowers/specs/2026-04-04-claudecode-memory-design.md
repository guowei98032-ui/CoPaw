# Claude Code风格Memory系统设计

## 1. 概述

### 1.1 目标

为CoPaw实现一套类似Claude Code的记忆系统，支持持久化跨会话知识存储和检索。

### 1.2 设计原则

- **分层架构**: 5层独立但有协作的memory层
- **Hook集成**: 充分利用AgentScope Hook扩展能力
- **文件优先**: 文件型存储，可解释、可审计
- **复用现有能力**: 适当复用reme_ai和AgentScope组件

### 1.3 与现有系统关系

CoPaw支持多套记忆系统共存，用户可通过配置选择：
- `remelight`: ReMeLightMemoryManager (向量检索)
- `lcm`: LCMMemoryManager (DAG压缩)
- `claudecode`: ClaudeCodeMemoryManager (新增，文件型)

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    ClaudeCodeMemorySystem                        │
│                    (协调层，非单一Manager)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              ClaudeCodeMemoryManager                     │    │
│  │              (BaseMemoryManager实现)                      │    │
│  │                                                          │    │
│  │  职责: 持久化跨会话记忆 (memdir)                          │    │
│  │  ├── memory_search()     # 语义检索                       │    │
│  │  ├── start/close()       # 生命周期                       │    │
│  │  └── get_memory_prompt() # 获取memory system prompt      │    │
│  │                                                          │    │
│  │  内部组件:                                                │    │
│  │  ├── MemdirManager       # 文件存储管理                   │    │
│  │  ├── MemoryRetriever     # 相关记忆召回                   │    │
│  │  ├── MemoryWriter        # 写回 (forked agent)            │    │
│  │  ├── AgentMemoryScope    # 作用域路径管理                 │    │
│  │  └── TeamMemoryManager   # 本地共享记忆                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SessionMemoryService                        │    │
│  │              (独立服务，非MemoryManager)                   │    │
│  │                                                          │    │
│  │  职责: 当前会话的工作记忆摘要                              │    │
│  │  ├── summary.md          # 会话摘要文件                   │    │
│  │  ├── update_summary()    # 更新摘要                       │    │
│  │  └── get_summary()       # 获取摘要内容                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              AutoDreamService                            │    │
│  │              (后台服务，跨session consolidation)          │    │
│  │                                                          │    │
│  │  职责: 离线记忆巩固                                        │    │
│  │  ├── 触发条件: 时间阈值 + session数量阈值                  │    │
│  │  ├── 运行方式: forked subagent (受限权限)                 │    │
│  │  └── 输出: 整理后的stable memory写入memdir                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Hooks (协调层)                               │    │
│  │                                                          │    │
│  │  MemoryRetrievalHook (pre_reasoning)                     │    │
│  │  MemoryCompactionHook (pre_reasoning)                    │    │
│  │  MemoryWritebackHook (post_reasoning)                    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 文件目录结构

```
working/.copaw/
├── memory/                        # ClaudeCodeMemoryManager管理
│   ├── MEMORY.md                  # 索引入口 (≤200行)
│   ├── user/                      # user scope memories
│   │   ├── user_role.md
│   │   └── preferences.md
│   ├── feedback/                  # feedback scope memories
│   │   └── code_style.md
│   ├── project/                   # project scope memories
│   │   └── architecture.md
│   ├── reference/                 # reference scope memories
│   │   └── external_apis.md
│   ├── team/                      # team memory (本地共享)
│   │   └── shared_conventions.md
│   ├── logs/                      # daily logs (assistant模式)
│   │   └── 2026/04/04.md
│   └── .consolidate-lock          # AutoDream文件锁
│
├── session/                       # SessionMemoryService管理
│   └── summary.md                 # 当前会话摘要
│
└── dream/                         # AutoDreamService管理
    ├── last_run.json              # 上次运行时间
    └── sessions/                  # 已处理的session记录
        └── session_xxx.json
```

---

## 4. ClaudeCodeMemoryManager 详细设计

### 4.1 类定义

```python
class ClaudeCodeMemoryManager(BaseMemoryManager):
    """文件型持久记忆管理器，实现Claude Code风格的memdir系统。
    
    支持4种memory类型:
    - user: 用户角色、偏好、知识背景
    - feedback: 用户指导、行为修正、成功/失败经验
    - project: 项目上下文、决策、时间线
    - reference: 外部系统指针、文档链接
    """
    
    def __init__(
        self,
        working_dir: str,
        agent_id: str,
        scope: Literal["user", "project", "local"] = "project",
    ):
        super().__init__(working_dir=working_dir, agent_id=agent_id)
        self.scope = scope
        self.memory_dir = self._resolve_memory_dir()
        
        # 子组件
        self._scanner = MemoryFileScanner(self.memory_dir)
        self._retriever = MemoryRetriever(self.memory_dir)
        self._writer = MemoryWriter(self.memory_dir, agent_id)
        self._agent_scope = AgentMemoryScope(working_dir, scope)
        self._team_memory = TeamMemoryManager(self.memory_dir)
```

### 4.2 配置项

```yaml
# config.yaml
memory_manager_backend: "claudecode"  # remelight/lcm/claudecode

claudecode_memory:
  enabled: true
  scope: "project"          # user/project/local
  
  memdir:
    memory_dir: ".copaw/memory"
    max_files: 200
    max_index_lines: 200
    
  retrieval:
    enabled: true
    max_results: 5
    min_query_length: 10
    
  extraction:
    enabled: true
    turn_threshold: 1       # 每N回合提取一次
    max_turns: 5            # forked agent最大turns
    
  team_memory:
    enabled: true
    dir: "team"

session_memory:
  enabled: true
  update_interval: 10

auto_dream:
  enabled: true
  min_session_count: 3
  min_hours_since_last_run: 24
```

### 4.3 BaseMemoryManager接口实现

| 方法 | 描述 |
|------|------|
| `start()` | 确保memory目录存在，初始化子组件，扫描现有memory文件 |
| `close()` | 等待pending写回任务，清理资源 |
| `compact_tool_result()` | 截断大文件工具结果 |
| `check_context()` | 返回需要压缩的消息 |
| `compact_memory()` | 生成session summary |
| `memory_search()` | 调用retriever检索相关记忆 |
| `get_in_memory_memory()` | 返回AgentScope InMemoryMemory实例 |

### 4.4 扩展接口

| 方法 | 描述 |
|------|------|
| `get_memory_prompt()` | 构建memory行为协议system prompt |
| `find_relevant_memories(query, recent_tools)` | 召回相关memory文件 |
| `extract_memories(messages)` | 启动forked agent提取durable memory |
| `scan_memory_files()` | 返回所有memory文件元信息 |

---

## 5. 子组件设计

### 5.1 MemoryFileScanner

**职责**: 扫描memory目录，读取frontmatter，返回memory列表

```python
@dataclass
class MemoryHeader:
    filename: str           # 相对路径
    file_path: Path         # 绝对路径
    mtime_ms: int           # 修改时间
    name: str               # memory名称
    description: str        # 一行描述
    type: MemoryType        # user/feedback/project/reference
    scope: str              # user/project/local/team

class MemoryFileScanner:
    async def scan(self, signal: AbortSignal) -> list[MemoryHeader]:
        """递归扫描.md文件，读取frontmatter，按mtime降序排序"""
        
    def format_manifest(self, headers: list[MemoryHeader]) -> str:
        """生成供LLM选择的列表"""
```

**Memory文件格式**:
```markdown
---
name: user_role
description: 用户角色和背景信息
type: user
scope: project
---

# 内容...
```

### 5.2 MemoryRetriever

**职责**: 根据当前查询召回相关memory

```python
class MemoryRetriever:
    async def find_relevant(
        self,
        query: str,
        recent_tools: list[str],    # 最近使用的工具
        already_surfaced: set[str], # 已展示过的memory
        signal: AbortSignal,
    ) -> list[RelevantMemory]:
        """
        流程:
        1. 调用Scanner获取memory列表
        2. 过滤已展示过的memory
        3. 调用LLM做relevance selection (side query)
        4. 返回top-k相关memory
        """
```

**优化策略**:
- 查询过短 (<10字符) 不触发召回
- 最近使用的工具相关文档memory做抑制
- 已展示过的memory去重

### 5.3 MemoryWriter (Forked Agent)

**职责**: 从对话中提取durable memory并写入文件

**触发时机**: post_reasoning hook (每回合结束时)

**运行方式**: forked subagent，共享prompt cache，严格受限的工具权限

**受限工具权限**:
| 工具 | 权限 |
|------|------|
| Read/Grep/Glob | 允许 |
| Bash | 仅允许只读命令 |
| Edit/Write | 仅允许在memory目录内 |

```python
class MemoryWriter:
    async def extract_and_write(
        self,
        messages: list[Msg],
        existing_memories: list[MemoryHeader],
    ) -> list[str]:
        """提取durable memory并写入文件"""
```

### 5.4 AgentMemoryScope

**职责**: 管理memory作用域路径

| scope | 路径 | 说明 |
|-------|------|------|
| user | ~/.copaw/memory/ | 跨项目 |
| project | working/.copaw/memory/ | 项目级 (默认) |
| local | working/.copaw/memory/local/ | 本地私有 |

### 5.5 TeamMemoryManager

**职责**: 管理本地共享的team memory

```python
class TeamMemoryManager:
    def __init__(self, memory_dir: Path):
        self.team_dir = memory_dir / "team"
    
    async def list_team_memories(self) -> list[MemoryHeader]:
        """列出team memory文件"""
    
    async def write_team_memory(self, name: str, content: str, type: str):
        """写入team memory"""
```

---

## 6. SessionMemoryService 详细设计

**职责**: 管理当前会话的工作记忆摘要

**生命周期**: 会话级 (不跨会话持久)

### 6.1 文件格式

```markdown
---
session_id: abc123
created_at: 2026-04-04T10:30:00
last_updated: 2026-04-04T12:45:00
message_count: 42
token_count: 8500
---

# Session Summary

## Current Task
用户正在实现Claude Code风格的memory系统...

## Key Decisions
- 选择方案C: 分层Hook-based架构
- Team Memory采用本地存储

## Progress
- [x] MemdirLayer设计
- [ ] AutoDreamService设计

## Pending
- 需要实现MemoryWriter组件
```

### 6.2 核心方法

```python
class SessionMemoryService:
    def __init__(self, working_dir: str):
        self.session_id = str(uuid.uuid4())[:8]
        self.summary_path = Path(working_dir) / ".copaw" / "session" / "summary.md"
        
    async def should_update(self, message_count: int) -> bool:
        """每N条消息更新一次"""
        
    async def update_summary(
        self,
        messages: list[Msg],
        model: ChatModelBase,
        formatter: FormatterBase,
    ) -> str:
        """调用LLM生成摘要，可复用reme_ai的message_compact_op"""
        
    def get_summary(self) -> str:
        """返回当前摘要内容"""
        
    def get_summary_for_compaction(self) -> str:
        """返回格式化后的摘要，用于compaction prompt"""
```

### 6.3 与Compaction集成

```
MemoryCompactionHook流程:
1. check_context
2. try_session_memory_compact()  # 新增: 优先用session summary
3. compact_memory()              # 回退到原有压缩
4. update_session_summary()      # 新增: 压缩后更新summary
```

---

## 7. AutoDreamService 详细设计

**职责**: 离线记忆巩固，跨多个session提炼stable memory

### 7.1 触发条件

| 条件 | 默认值 | 说明 |
|------|--------|------|
| 时间阈值 | 24小时 | 距上次运行时间 |
| Session数量 | 3个 | 新session数量 |
| 锁条件 | - | 没有正在进行的dream任务 |
| 静默时段 | 00:00-06:00 | 可配置 |

### 7.2 核心方法

```python
class AutoDreamService:
    def __init__(self, working_dir: str, config: AutoDreamConfig):
        self.working_dir = Path(working_dir)
        self.dream_dir = self.working_dir / ".copaw" / "dream"
        self._is_running = False
        self._lock = ConsolidationLock(self.working_dir)
        
    async def should_run(self) -> bool:
        """检查所有触发条件"""
        
    async def run_consolidation(
        self,
        memory_manager: ClaudeCodeMemoryManager,
        model: ChatModelBase,
    ) -> ConsolidationResult:
        """
        流程:
        1. 获取文件锁
        2. 收集待处理session数据
        3. 启动forked consolidation agent
        4. 写入consolidated memories
        5. 更新last_run.json
        6. 释放锁
        """
```

### 7.3 Consolidation Agent

**输入**:
- 多个session的对话记录
- 现有memory内容
- 时间范围

**输出**:
- 更新/新建memory文件
- 清理过时memory
- 更新MEMORY.md索引

**权限**: 与MemoryWriter相同，仅限memory目录读写

---

## 8. Hooks 集成设计

### 8.1 注册位置

```python
# CoPawAgent.__init__()
def _setup_hooks(self):
    # ... 现有hooks ...
    
    if isinstance(self.memory_manager, ClaudeCodeMemoryManager):
        # 注册memory retrieval hook
        self.register_instance_hook(
            hook_type="pre_reasoning",
            hook_name="memory_retrieval",
            hook=MemoryRetrievalHook(self.memory_manager),
        )
        
        # 注册memory writeback hook
        self.register_instance_hook(
            hook_type="post_reasoning",
            hook_name="memory_writeback",
            hook=MemoryWritebackHook(
                self.memory_manager,
                self.session_memory,
            ),
        )
```

### 8.2 Hook执行顺序

**pre_reasoning顺序**:
1. BootstrapHook - 注入初始上下文
2. MemoryRetrievalHook - 召回相关记忆，注入attachment
3. MemoryCompactionHook - 检查预算，优先用session summary压缩

**post_reasoning顺序**:
1. MemoryWritebackHook - 提取durable memory，更新session summary
2. AutoDreamTriggerHook - 检查并触发后台consolidation

### 8.3 MemoryRetrievalHook

```python
class MemoryRetrievalHook:
    def __init__(self, memory_manager, min_query_length=10):
        self.memory_manager = memory_manager
        self.min_query_length = min_query_length
    
    async def __call__(self, agent, kwargs) -> dict | None:
        query = self._extract_query(kwargs)
        if len(query) < self.min_query_length:
            return None
        
        memories = await self.memory_manager.find_relevant_memories(
            query=query,
            recent_tools=self._get_recent_tools(agent),
        )
        
        if memories:
            self._inject_attachment(agent, memories)
        return None
```

### 8.4 MemoryWritebackHook

```python
class MemoryWritebackHook:
    def __init__(self, memory_manager, session_memory):
        self.memory_manager = memory_manager
        self.session_memory = session_memory
    
    async def __call__(self, agent, kwargs, response) -> Msg | None:
        messages = kwargs.get("messages", [])
        
        # 提取durable memory
        written_paths = await self.memory_manager.extract_memories(messages)
        
        # 更新session summary
        if await self.session_memory.should_update(len(messages)):
            await self.session_memory.update_summary(messages)
        
        # 返回系统消息
        if written_paths:
            return self._create_memory_saved_msg(written_paths)
        return None
```

---

## 9. 并发控制设计

### 9.1 两层并发控制

| 层级 | 控制机制 | 粒度 | 场景 |
|------|----------|------|------|
| 进程内 | `inProgress` flag + `pendingContext` | 单进程 | MemoryWriter重叠运行 |
| 进程内 | `inFlightExtractions` Set + `drain()` | 单进程 | MemoryWriter退出等待 |
| 跨进程 | 文件锁 `.consolidate-lock` | 跨进程 | AutoDream重叠运行 |
| 跨进程 | PID存活检测 + stale超时 | 跨进程 | AutoDream crash恢复 |
| 跨进程 | 乐观锁 (原子write) | 跨进程 | Memory文件写入冲突 |

### 9.2 MemoryWriter并发控制

```python
class MemoryWriter:
    def __init__(self):
        self._in_progress: bool = False
        self._pending_messages: list[Msg] | None = None
        self._in_flight: set[asyncio.Task] = set()
        self._last_message_uuid: str | None = None
        self._turns_since_extraction: int = 0
    
    async def extract_and_write(self, messages) -> list[str]:
        # 如果正在运行，stash上下文
        if self._in_progress:
            self._pending_messages = messages
            return []
        
        self._in_progress = True
        try:
            written_paths = await self._do_extraction(messages)
            self._last_message_uuid = messages[-1].id
        finally:
            self._in_progress = False
            # 处理stash的上下文 (trailing run)
            if self._pending_messages:
                pending = self._pending_messages
                self._pending_messages = None
                await self.extract_and_write(pending)
        return written_paths
    
    async def drain(self, timeout_ms: int = 60000) -> None:
        """等待所有进行中的提取完成"""
        if not self._in_flight:
            return
        await asyncio.wait(
            self._in_flight,
            timeout=timeout_ms / 1000,
        )
```

### 9.3 AutoDream文件锁

**锁文件位置**: `working/.copaw/memory/.consolidate-lock`

**锁文件内容**: `<PID>` (持有者进程ID)

**锁文件mtime**: lastConsolidatedAt (上次consolidation时间)

```python
class ConsolidationLock:
    LOCK_FILE = ".consolidate-lock"
    HOLDER_STALE_MS = 60 * 60 * 1000  # 1小时
    
    async def read_last_consolidated_at(self) -> int:
        """返回上次consolidation时间戳，0表示无锁"""
        path = self.lock_path()
        if not path.exists():
            return 0
        return int(path.stat().st_mtime * 1000)
    
    async def try_acquire(self) -> int | None:
        """尝试获取锁，返回之前的mtime或None(被占用)"""
        path = self.lock_path()
        
        # 检查现有锁
        if path.exists():
            mtime_ms = int(path.stat().st_mtime * 1000)
            holder_pid = int(path.read_text().strip())
            
            # 检查是否stale
            if time.time() * 1000 - mtime_ms < self.HOLDER_STALE_MS:
                # 检查PID是否存活
                if self._is_process_running(holder_pid):
                    return None  # 被占用
        
        # 写入新锁
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(str(os.getpid()))
        
        # 验证竞态条件
        if int(path.read_text().strip()) != os.getpid():
            return None  # 输了竞态
        
        return mtime_ms or 0
    
    async def rollback(self, prior_mtime: int) -> None:
        """回滚到之前的状态"""
        path = self.lock_path()
        if prior_mtime == 0:
            path.unlink(missing_ok=True)
        else:
            path.write_text("")
            os.utime(path, (prior_mtime/1000, prior_mtime/1000))
    
    def _is_process_running(self, pid: int) -> bool:
        """检查进程是否存活"""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
```

### 9.4 Memory文件写入冲突处理

**推荐方案**: 乐观锁

- 文件写入使用原子操作 (write + rename)
- 不加文件锁，冲突时后写覆盖
- MEMORY.md更新使用追加模式
- 依赖agent智能避免重复写入

**可选增强**: 读写锁 (portalocker)
- 读操作: 共享锁
- 写操作: 排他锁
- 增加复杂度，但更安全

---

## 10. 与Workspace集成

### 10.1 _resolve_memory_class扩展

```python
# workspace.py
def _resolve_memory_class(backend: str) -> type:
    from copaw.agents.memory import (
        ReMeLightMemoryManager,
        LCMMemoryManager,
        ClaudeCodeMemoryManager,  # 新增
    )
    
    if backend == "remelight":
        return ReMeLightMemoryManager
    elif backend == "lcm":
        return LCMMemoryManager
    elif backend == "claudecode":
        return ClaudeCodeMemoryManager
    raise ValueError(f"Unsupported memory manager backend: '{backend}'")
```

### 10.2 新增服务注册

```python
# Workspace._register_services()

# Session Memory Service
sm.register(ServiceDescriptor(
    name="session_memory",
    service_class=SessionMemoryService,
    init_args=lambda ws: {"working_dir": str(ws.workspace_dir)},
    start_method="start",
    stop_method="close",
    priority=20,
    concurrent_init=True,
))

# Auto Dream Service
sm.register(ServiceDescriptor(
    name="auto_dream",
    service_class=AutoDreamService,
    init_args=lambda ws: {
        "working_dir": str(ws.workspace_dir),
        "config": load_auto_dream_config(),
    },
    start_method="start",
    stop_method="close",
    priority=50,
    concurrent_init=False,
))
```

---

## 11. Memory System Prompt

注入到agent system prompt的memory行为协议：

```
# auto memory

You have a persistent, file-based memory system at `.copaw/memory/`. 
This directory already exists — write to it directly with the Write tool.

## Types of memory

<types>
<type>
    <name>user</name>
    <description>Information about the user's role, goals, preferences...</description>
    <when_to_save>When you learn details about the user...</when_to_save>
    <how_to_use>When your work should be informed by the user's profile...</how_to_use>
</type>
<type>
    <name>feedback</name>
    <description>Guidance the user has given you about how to approach work...</description>
    <when_to_save>Any time the user corrects your approach OR confirms...</when_to_save>
</type>
<type>
    <name>project</name>
    <description>Information about ongoing work, goals, decisions...</description>
    <when_to_save>When you learn who is doing what, why, or by when...</when_to_save>
</type>
<type>
    <name>reference</name>
    <description>Pointers to where information can be found in external systems...</description>
    <when_to_save>When you learn about resources in external systems...</when_to_save>
</type>
</types>

## What NOT to save in memory

- Code patterns, conventions, architecture — read from code
- Git history — use git log
- Anything already in CLAUDE.md files
- Ephemeral task details

## How to save memories

Write each memory to its own file using this format:

```markdown
---
name: {{memory name}}
description: {{one-line description}}
type: {{user, feedback, project, reference}}
---

{{memory content}}
```

## When to access memories

- When memories seem relevant to current task
- When user references prior-conversation work
- When user asks to check, recall, or remember
```

---

## 12. 实现计划

### 阶段1: 核心层 (MVP)
- [ ] MemoryFileScanner
- [ ] MemoryRetriever (基础版，无LLM selection)
- [ ] ClaudeCodeMemoryManager骨架
- [ ] MEMORY.md索引管理

### 阶段2: 写回与Hook
- [ ] MemoryWriter (forked agent)
- [ ] MemoryRetrievalHook
- [ ] MemoryWritebackHook
- [ ] 并发控制

### 阶段3: Session与Compaction
- [ ] SessionMemoryService
- [ ] Compaction集成
- [ ] 与MemoryCompactionHook协同

### 阶段4: AutoDream
- [ ] ConsolidationLock
- [ ] AutoDreamService
- [ ] Consolidation Agent

### 阶段5: 扩展功能
- [ ] AgentMemoryScope
- [ ] TeamMemoryManager
- [ ] Daily logs (assistant模式)
- [ ] 配置与文档

---

## 13. 参考资料

- Claude Code源码: `C:\workspace\free-code-main\src\memdir\`
- Claude Code Memory文档: `C:\workspace\Claude Code Memory系统详解.pdf`
- AgentScope Hook机制: `agentscope/agent/_agent_base.py`
- reme_ai: `C:\Users\win10\miniconda3\envs\AgentScope\Lib\site-packages\reme_ai\`
- CoPaw现有MemoryManager: `src/copaw/agents/memory/`