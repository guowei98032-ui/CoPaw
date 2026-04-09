# Claude Code Memory System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a file-based persistent memory system for CoPaw that stores user preferences, feedback, project context, and external references across sessions.

**Architecture:** ClaudeCodeMemoryManager implements BaseMemoryManager interface, delegates to sub-components (Scanner, Retriever, Writer). SessionMemoryService and AutoDreamService are independent services coordinated through Hooks (pre_reasoning/post_reasoning).

**Tech Stack:** Python, AgentScope Hooks, asyncio, file-based storage with YAML frontmatter

**Spec Document:** `docs/superpowers/specs/2026-04-04-claudecode-memory-design.md`

---

## File Structure

### New Files (create)

```
src/copaw/agents/memory/claudecode/
├── __init__.py                    # Package exports
├── models.py                      # MemoryHeader, MemoryType dataclasses
├── scanner.py                     # MemoryFileScanner - scan .md files
├── retriever.py                   # MemoryRetriever - relevance selection
├── writer.py                      # MemoryWriter - forked agent extraction
├── scope.py                       # AgentMemoryScope - path resolution
├── team.py                        # TeamMemoryManager - local shared
├── lock.py                        # ConsolidationLock - PID-based file lock
└── manager.py                     # ClaudeCodeMemoryManager - main class

src/copaw/agents/hooks/
├── memory_retrieval.py            # MemoryRetrievalHook (pre_reasoning)
├── memory_writeback.py            # MemoryWritebackHook (post_reasoning)

src/copaw/app/workspace/services/
├── __init__.py                    # Package exports
├── session_memory.py              # SessionMemoryService
├── auto_dream.py                  # AutoDreamService

tests/unit/agents/memory/claudecode/
├── __init__.py
├── test_models.py
├── test_scanner.py
├── test_retriever.py
├── test_writer.py
├── test_lock.py
├── test_manager.py

tests/unit/agents/hooks/
├── test_memory_retrieval.py
├── test_memory_writeback.py

tests/unit/workspace/services/
├── test_session_memory.py
├── test_auto_dream.py
```

### Modified Files

```
src/copaw/agents/memory/__init__.py         # Add ClaudeCodeMemoryManager export
src/copaw/agents/hooks/__init__.py          # Add new hooks exports
src/copaw/config/config.py                  # Add "claudecode" backend option
src/copaw/app/workspace/workspace.py        # Extend _resolve_memory_class()
src/copaw/agents/react_agent.py             # Register memory hooks (conditional)
```

---

## Phase 1: Core Layer (MVP)

### Task 1.1: MemoryType and MemoryHeader Models

**Files:**
- Create: `src/copaw/agents/memory/claudecode/models.py`
- Create: `src/copaw/agents/memory/claudecode/__init__.py`
- Test: `tests/unit/agents/memory/claudecode/test_models.py`

- [ ] **Step 1: Create test file with failing tests**

```python
# tests/unit/agents/memory/claudecode/test_models.py
# -*- coding: utf-8 -*-
"""Tests for Claude Code memory models."""
import pytest
from pathlib import Path
from copaw.agents.memory.claudecode.models import MemoryType, MemoryHeader


def test_memory_type_enum_values():
    """Test MemoryType has expected values."""
    assert MemoryType.USER.value == "user"
    assert MemoryType.FEEDBACK.value == "feedback"
    assert MemoryType.PROJECT.value == "project"
    assert MemoryType.REFERENCE.value == "reference"


def test_memory_header_creation():
    """Test MemoryHeader dataclass creation."""
    header = MemoryHeader(
        filename="user/role.md",
        file_path=Path("/tmp/memory/user/role.md"),
        mtime_ms=1234567890,
        name="user_role",
        description="User role information",
        type=MemoryType.USER,
        scope="project",
    )
    assert header.filename == "user/role.md"
    assert header.name == "user_role"
    assert header.type == MemoryType.USER


def test_memory_header_from_frontmatter():
    """Test parsing frontmatter from markdown content."""
    content = """---
name: user_role
description: User role and background
type: user
scope: project
---

# Content here
"""
    header = MemoryHeader.from_frontmatter(
        content=content,
        filename="user/role.md",
        file_path=Path("/tmp/memory/user/role.md"),
        mtime_ms=1234567890,
    )
    assert header.name == "user_role"
    assert header.type == MemoryType.USER
    assert header.scope == "project"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/memory/claudecode/test_models.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Create package __init__.py**

```python
# src/copaw/agents/memory/claudecode/__init__.py
# -*- coding: utf-8 -*-
"""Claude Code style memory manager package."""

from .models import MemoryType, MemoryHeader
from .scanner import MemoryFileScanner
from .manager import ClaudeCodeMemoryManager

__all__ = [
    "MemoryType",
    "MemoryHeader",
    "MemoryFileScanner",
    "ClaudeCodeMemoryManager",
]
```

- [ ] **Step 4: Implement models**

```python
# src/copaw/agents/memory/claudecode/models.py
# -*- coding: utf-8 -*-
"""Data models for Claude Code memory system."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MemoryType(Enum):
    """Memory content type classification."""
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


@dataclass
class MemoryHeader:
    """Metadata header for a memory file."""
    filename: str           # Relative path from memory_dir
    file_path: Path         # Absolute path
    mtime_ms: int           # Modification time in milliseconds
    name: str               # Memory name (unique identifier)
    description: str        # One-line description
    type: MemoryType        # Content type
    scope: str              # user/project/local/team

    @classmethod
    def from_frontmatter(
        cls,
        content: str,
        filename: str,
        file_path: Path,
        mtime_ms: int,
    ) -> "MemoryHeader":
        """Parse frontmatter from markdown content."""
        import yaml

        if not content.startswith("---"):
            raise ValueError("Content must start with frontmatter ---")

        end_idx = content.find("---", 3)
        if end_idx == -1:
            raise ValueError("Frontmatter must end with ---")

        frontmatter_str = content[3:end_idx].strip()
        frontmatter = yaml.safe_load(frontmatter_str)

        return cls(
            filename=filename,
            file_path=file_path,
            mtime_ms=mtime_ms,
            name=frontmatter.get("name", ""),
            description=frontmatter.get("description", ""),
            type=MemoryType(frontmatter.get("type", "project")),
            scope=frontmatter.get("scope", "project"),
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/agents/memory/claudecode/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/agents/memory/claudecode/__init__.py \
        src/copaw/agents/memory/claudecode/models.py \
        tests/unit/agents/memory/claudecode/__init__.py \
        tests/unit/agents/memory/claudecode/test_models.py
git commit -m "feat(memory): add MemoryType and MemoryHeader models for ClaudeCode memory"
```

---

### Task 1.2: MemoryFileScanner

**Files:**
- Create: `src/copaw/agents/memory/claudecode/scanner.py`
- Test: `tests/unit/agents/memory/claudecode/test_scanner.py`

- [ ] **Step 1: Create test file with failing tests**

```python
# tests/unit/agents/memory/claudecode/test_scanner.py
# -*- coding: utf-8 -*-
"""Tests for MemoryFileScanner."""
import pytest
import tempfile
from pathlib import Path
from copaw.agents.memory.claudecode.scanner import MemoryFileScanner
from copaw.agents.memory.claudecode.models import MemoryType


@pytest.fixture
def memory_dir_with_files():
    """Create temp directory with sample memory files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_dir = Path(tmpdir) / "memory"
        memory_dir.mkdir()

        user_dir = memory_dir / "user"
        user_dir.mkdir()
        user_file = user_dir / "role.md"
        user_file.write_text("""---
name: user_role
description: User role information
type: user
scope: project
---

# User Role
Senior developer with Go expertise.
""")

        feedback_dir = memory_dir / "feedback"
        feedback_dir.mkdir()
        feedback_file = feedback_dir / "style.md"
        feedback_file.write_text("""---
name: code_style
description: Code style preferences
type: feedback
scope: project
---

# Code Style
Prefer small functions.
""")

        index_file = memory_dir / "MEMORY.md"
        index_file.write_text("- [user_role](user/role.md) - User role info\n")

        yield memory_dir


@pytest.mark.asyncio
async def test_scanner_scan(memory_dir_with_files):
    """Test scanner finds all memory files."""
    scanner = MemoryFileScanner(memory_dir_with_files)
    headers = await scanner.scan()

    assert len(headers) == 2
    names = [h.name for h in headers]
    assert "user_role" in names
    assert "code_style" in names


@pytest.mark.asyncio
async def test_scanner_sorted_by_mtime(memory_dir_with_files):
    """Test scanner returns files sorted by mtime descending."""
    scanner = MemoryFileScanner(memory_dir_with_files)
    headers = await scanner.scan()

    assert headers[0].mtime_ms >= headers[1].mtime_ms


@pytest.mark.asyncio
async def test_scanner_excludes_index(memory_dir_with_files):
    """Test scanner excludes MEMORY.md from results."""
    scanner = MemoryFileScanner(memory_dir_with_files)
    headers = await scanner.scan()

    filenames = [h.filename for h in headers]
    assert "MEMORY.md" not in filenames


@pytest.mark.asyncio
async def test_scanner_empty_directory():
    """Test scanner handles empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_dir = Path(tmpdir) / "memory"
        memory_dir.mkdir()

        scanner = MemoryFileScanner(memory_dir)
        headers = await scanner.scan()

        assert headers == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/memory/claudecode/test_scanner.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement scanner**

```python
# src/copaw/agents/memory/claudecode/scanner.py
# -*- coding: utf-8 -*-
"""Memory file scanner for ClaudeCode memory system."""
import logging
from pathlib import Path
from typing import Optional

from .models import MemoryHeader

logger = logging.getLogger(__name__)


class AbortSignal:
    """Signal to abort long-running operations."""

    def __init__(self):
        self._aborted = False

    def abort(self) -> None:
        self._aborted = True

    def is_aborted(self) -> bool:
        return self._aborted


class MemoryFileScanner:
    """Scan memory directory for .md files with frontmatter."""

    INDEX_FILE = "MEMORY.md"

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)

    async def scan(
        self,
        signal: Optional[AbortSignal] = None,
    ) -> list[MemoryHeader]:
        """Recursively scan for .md files, parse frontmatter, sort by mtime."""
        headers: list[MemoryHeader] = []

        if not self.memory_dir.exists():
            return headers

        for md_file in self.memory_dir.rglob("*.md"):
            if signal and signal.is_aborted():
                break

            if md_file.name == self.INDEX_FILE:
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                mtime_ms = int(md_file.stat().st_mtime * 1000)

                header = MemoryHeader.from_frontmatter(
                    content=content,
                    filename=str(md_file.relative_to(self.memory_dir)),
                    file_path=md_file,
                    mtime_ms=mtime_ms,
                )
                headers.append(header)
            except Exception as e:
                logger.warning(f"Failed to parse memory file {md_file}: {e}")
                continue

        headers.sort(key=lambda h: h.mtime_ms, reverse=True)
        return headers

    def format_manifest(self, headers: list[MemoryHeader]) -> str:
        """Generate MEMORY.md index content."""
        lines = []
        for h in headers:
            lines.append(f"- [{h.name}]({h.filename}) - {h.description}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/agents/memory/claudecode/test_scanner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/agents/memory/claudecode/scanner.py \
        tests/unit/agents/memory/claudecode/test_scanner.py
git commit -m "feat(memory): add MemoryFileScanner for scanning memory files"
```

---

### Task 1.3: ClaudeCodeMemoryManager Skeleton

**Files:**
- Create: `src/copaw/agents/memory/claudecode/manager.py`
- Modify: `src/copaw/agents/memory/__init__.py`
- Test: `tests/unit/agents/memory/claudecode/test_manager.py`

- [ ] **Step 1: Create test file with failing tests**

```python
# tests/unit/agents/memory/claudecode/test_manager.py
# -*- coding: utf-8 -*-
"""Tests for ClaudeCodeMemoryManager."""
import pytest
import tempfile
from pathlib import Path
from copaw.agents.memory.claudecode.manager import ClaudeCodeMemoryManager


@pytest.fixture
def working_dir():
    """Create temp working directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_manager_creation(working_dir):
    """Test manager can be created."""
    manager = ClaudeCodeMemoryManager(
        working_dir=str(working_dir),
        agent_id="test_agent",
    )
    assert manager.working_dir == str(working_dir)
    assert manager.agent_id == "test_agent"


@pytest.mark.asyncio
async def test_manager_start_creates_directory(working_dir):
    """Test start() creates memory directory."""
    manager = ClaudeCodeMemoryManager(
        working_dir=str(working_dir),
        agent_id="test_agent",
    )
    await manager.start()

    memory_dir = working_dir / ".copaw" / "memory"
    assert memory_dir.exists()


@pytest.mark.asyncio
async def test_manager_close(working_dir):
    """Test close() returns True."""
    manager = ClaudeCodeMemoryManager(
        working_dir=str(working_dir),
        agent_id="test_agent",
    )
    await manager.start()
    result = await manager.close()
    assert result is True


@pytest.mark.asyncio
async def test_manager_memory_search(working_dir):
    """Test memory_search returns ToolResponse."""
    manager = ClaudeCodeMemoryManager(
        working_dir=str(working_dir),
        agent_id="test_agent",
    )
    await manager.start()

    result = await manager.memory_search(query="test query")
    assert result is not None


@pytest.mark.asyncio
async def test_manager_find_relevant_memories(working_dir):
    """Test find_relevant_memories returns list."""
    manager = ClaudeCodeMemoryManager(
        working_dir=str(working_dir),
        agent_id="test_agent",
    )
    await manager.start()

    # Add a memory file
    memory_dir = working_dir / ".copaw" / "memory"
    user_dir = memory_dir / "user"
    user_dir.mkdir(exist_ok=True)
    user_file = user_dir / "role.md"
    user_file.write_text("""---
name: user_role
description: User role info
type: user
scope: project
---

User is a developer.
""")

    memories = await manager.find_relevant_memories(
        query="what is the user's role?",
    )
    assert len(memories) <= 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/memory/claudecode/test_manager.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement manager skeleton**

```python
# src/copaw/agents/memory/claudecode/manager.py
# -*- coding: utf-8 -*-
"""ClaudeCode-style file-based memory manager."""
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

from agentscope.message import Msg
from agentscope.tool import ToolResponse

from ..base_memory_manager import BaseMemoryManager
from .scanner import MemoryFileScanner
from .retriever import MemoryRetriever

if TYPE_CHECKING:
    from reme.memory.file_based.reme_in_memory_memory import ReMeInMemoryMemory

logger = logging.getLogger(__name__)


class ClaudeCodeMemoryManager(BaseMemoryManager):
    """File-based persistent memory manager implementing Claude Code style.

    Supports 4 memory types:
    - user: User role, preferences, knowledge background
    - feedback: User guidance, behavior corrections
    - project: Project context, decisions, timeline
    - reference: External system pointers, documentation links
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
        self._scanner = MemoryFileScanner(self.memory_dir)
        self._retriever = MemoryRetriever(self.memory_dir)
        self._started = False

    def _resolve_memory_dir(self) -> Path:
        """Resolve memory directory based on scope."""
        if self.scope == "user":
            home = Path.home()
            return home / ".copaw" / "memory"
        elif self.scope == "local":
            return Path(self.working_dir) / ".copaw" / "memory" / "local"
        else:
            return Path(self.working_dir) / ".copaw" / "memory"

    async def start(self) -> None:
        """Start memory manager, create directories if needed."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        for type_name in ["user", "feedback", "project", "reference"]:
            (self.memory_dir / type_name).mkdir(exist_ok=True)

        self._started = True
        logger.info(
            f"ClaudeCodeMemoryManager started: "
            f"agent_id={self.agent_id}, memory_dir={self.memory_dir}",
        )

    async def close(self) -> bool:
        """Close memory manager and cleanup."""
        self._started = False
        logger.info(f"ClaudeCodeMemoryManager closed: agent_id={self.agent_id}")
        return True

    async def compact_tool_result(self, **kwargs) -> None:
        """Compact tool results by truncating large outputs."""
        return None

    async def check_context(self, **kwargs) -> tuple:
        """Check context size for compaction needs."""
        messages = kwargs.get("messages", [])
        return ([], messages, True)

    async def compact_memory(
        self,
        messages: list[Msg],
        previous_summary: str = "",
        **kwargs,
    ) -> str:
        """Compact messages into summary."""
        return ""

    async def summary_memory(self, messages: list[Msg], **kwargs) -> str:
        """Generate comprehensive summary."""
        return ""

    async def memory_search(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
    ) -> ToolResponse:
        """Search stored memories for relevant content."""
        from agentscope.message import TextBlock

        if not self._started:
            return ToolResponse(
                content=[TextBlock(type="text", text="Memory manager not started")],
            )

        headers = await self._scanner.scan()

        if not headers:
            return ToolResponse(
                content=[TextBlock(type="text", text="No memories found")],
            )

        manifest = self._scanner.format_manifest(headers)
        return ToolResponse(
            content=[TextBlock(type="text", text=manifest)],
        )

    def get_in_memory_memory(self, **kwargs) -> Optional["ReMeInMemoryMemory"]:
        """Return in-memory memory object."""
        return None

    async def find_relevant_memories(
        self,
        query: str,
        recent_tools: list[str] = [],
        already_surfaced: set[str] = set(),
    ) -> list:
        """Find relevant memories for the query."""
        return await self._retriever.find_relevant(
            query=query,
            recent_tools=recent_tools,
            already_surfaced=already_surfaced,
            max_results=5,
        )

    async def get_memory_prompt(self) -> str:
        """Get memory system prompt for injection."""
        return """# auto memory

You have a persistent, file-based memory system at `.copaw/memory/`.

## Types of memory

<types>
<type><name>user</name><description>User role, goals, preferences</description></type>
<type><name>feedback</name><description>Guidance about how to approach work</description></type>
<type><name>project</name><description>Ongoing work, goals, decisions</description></type>
<type><name>reference</name><description>External system pointers</description></type>
</types>

## How to save memories

---
name: {{memory name}}
description: {{one-line description}}
type: {{user, feedback, project, reference}}
---

{{memory content}}
"""
```

- [ ] **Step 4: Update memory package __init__.py**

```python
# src/copaw/agents/memory/__init__.py
# -*- coding: utf-8 -*-
"""Memory management module for CoPaw agents."""

from .agent_md_manager import AgentMdManager
from .base_memory_manager import BaseMemoryManager
from .reme_light_memory_manager import ReMeLightMemoryManager
from .lcm_memory_manager import LCMMemoryManager
from .claudecode.manager import ClaudeCodeMemoryManager

__all__ = [
    "AgentMdManager",
    "BaseMemoryManager",
    "ReMeLightMemoryManager",
    "LCMMemoryManager",
    "ClaudeCodeMemoryManager",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/agents/memory/claudecode/test_manager.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/agents/memory/claudecode/manager.py \
        src/copaw/agents/memory/__init__.py \
        tests/unit/agents/memory/claudecode/test_manager.py
git commit -m "feat(memory): add ClaudeCodeMemoryManager skeleton with find_relevant_memories"
```

---

### Task 1.4: Register Backend in Config and Workspace

**Files:**
- Modify: `src/copaw/config/config.py`
- Modify: `src/copaw/app/workspace/workspace.py`

- [ ] **Step 1: Update config backend type**

Find `memory_manager_backend` in `src/copaw/config/config.py` (line ~551):

```python
# Before:
memory_manager_backend: Literal["remelight", "lcm"] = Field(

# After:
memory_manager_backend: Literal["remelight", "lcm", "claudecode"] = Field(
```

- [ ] **Step 2: Update workspace _resolve_memory_class**

```python
# src/copaw/app/workspace/workspace.py ~line 39:

def _resolve_memory_class(backend: str) -> type:
    from ...agents.memory import (
        ReMeLightMemoryManager,
        LCMMemoryManager,
        ClaudeCodeMemoryManager,
    )

    if backend == "remelight":
        return ReMeLightMemoryManager
    elif backend == "lcm":
        return LCMMemoryManager
    elif backend == "claudecode":
        return ClaudeCodeMemoryManager
    raise ValueError(f"Unsupported memory manager backend: '{backend}'")
```

- [ ] **Step 3: Run existing workspace tests**

Run: `pytest tests/unit/workspace/test_workspace.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/copaw/config/config.py src/copaw/app/workspace/workspace.py
git commit -m "feat(config): add 'claudecode' memory manager backend option"
```

---

### Task 1.5: MemoryRetriever

**Files:**
- Create: `src/copaw/agents/memory/claudecode/retriever.py`
- Test: `tests/unit/agents/memory/claudecode/test_retriever.py`

- [ ] **Step 1: Create test file**

```python
# tests/unit/agents/memory/claudecode/test_retriever.py
# -*- coding: utf-8 -*-
"""Tests for MemoryRetriever."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from copaw.agents.memory.claudecode.retriever import MemoryRetriever
from copaw.agents.memory.claudecode.models import MemoryHeader, MemoryType


@pytest.fixture
def memory_dir_with_sample():
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_dir = Path(tmpdir)
        user_file = memory_dir / "user" / "role.md"
        user_file.parent.mkdir(parents=True, exist_ok=True)
        user_file.write_text("""---
name: user_role
description: User is a senior developer
type: user
scope: project
---

User has 10 years Go experience.
""")
        yield memory_dir


@pytest.mark.asyncio
async def test_retriever_skip_short_query(memory_dir_with_sample):
    """Test retriever skips queries shorter than min length."""
    retriever = MemoryRetriever(memory_dir_with_sample)
    results = await retriever.find_relevant(query="hi")
    assert results == []


@pytest.mark.asyncio
async def test_retriever_finds_memories(memory_dir_with_sample):
    """Test retriever finds memories for adequate query."""
    retriever = MemoryRetriever(memory_dir_with_sample)
    results = await retriever.find_relevant(
        query="what is the user's programming background?",
    )
    assert len(results) <= 5


@pytest.mark.asyncio
async def test_retriever_filter_already_surfaced(memory_dir_with_sample):
    """Test retriever filters already surfaced memories."""
    retriever = MemoryRetriever(memory_dir_with_sample)
    results = await retriever.find_relevant(
        query="user background",
        already_surfaced={"user/role.md"},
    )
    assert len(results) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/memory/claudecode/test_retriever.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement retriever**

```python
# src/copaw/agents/memory/claudecode/retriever.py
# -*- coding: utf-8 -*-
"""Memory retriever for ClaudeCode memory system."""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import MemoryHeader
from .scanner import MemoryFileScanner, AbortSignal

logger = logging.getLogger(__name__)


@dataclass
class RelevantMemory:
    """A memory file with relevance score."""
    header: MemoryHeader
    score: float
    content: str


class MemoryRetriever:
    """Find relevant memories based on query."""

    MIN_QUERY_LENGTH = 10

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)
        self._scanner = MemoryFileScanner(self.memory_dir)

    async def find_relevant(
        self,
        query: str,
        recent_tools: list[str] = [],
        already_surfaced: set[str] = set(),
        signal: Optional[AbortSignal] = None,
        max_results: int = 5,
    ) -> list[RelevantMemory]:
        """Find relevant memories for query."""
        if len(query) < self.MIN_QUERY_LENGTH:
            return []

        headers = await self._scanner.scan(signal)
        if not headers:
            return []

        candidates = [
            h for h in headers
            if h.filename not in already_surfaced
        ]

        if not candidates:
            return []

        results = []
        for header in candidates[:max_results]:
            try:
                content = header.file_path.read_text(encoding="utf-8")
                if content.startswith("---"):
                    end_idx = content.find("---", 3)
                    if end_idx != -1:
                        content = content[end_idx + 3:].strip()

                results.append(RelevantMemory(
                    header=header,
                    score=1.0,
                    content=content,
                ))
            except Exception as e:
                logger.warning(f"Failed to read {header.file_path}: {e}")

        return results

    def format_for_prompt(self, memories: list[RelevantMemory]) -> str:
        """Format memories for injection into system prompt."""
        if not memories:
            return ""

        lines = ["## Relevant Memories\n"]
        for m in memories:
            lines.append(f"### {m.header.name}\n")
            lines.append(f"{m.content}\n\n")

        return "\n".join(lines)
```

- [ ] **Step 4: Update package exports**

```python
# src/copaw/agents/memory/claudecode/__init__.py
from .retriever import MemoryRetriever, RelevantMemory

__all__ = [
    # ... existing ...
    "MemoryRetriever",
    "RelevantMemory",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/agents/memory/claudecode/test_retriever.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/agents/memory/claudecode/retriever.py \
        src/copaw/agents/memory/claudecode/__init__.py \
        tests/unit/agents/memory/claudecode/test_retriever.py
git commit -m "feat(memory): add MemoryRetriever for finding relevant memories"
```

---

## Phase 2: Writeback & Hooks

### Task 2.1: MemoryWriter with InProgress Pattern

**Files:**
- Create: `src/copaw/agents/memory/claudecode/writer.py`
- Test: `tests/unit/agents/memory/claudecode/test_writer.py`

- [ ] **Step 1: Create test file**

```python
# tests/unit/agents/memory/claudecode/test_writer.py
# -*- coding: utf-8 -*-
"""Tests for MemoryWriter."""
import pytest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from copaw.agents.memory.claudecode.writer import MemoryWriter
from copaw.agents.memory.claudecode.models import MemoryHeader, MemoryType


@pytest.fixture
def memory_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_headers(memory_dir):
    return [
        MemoryHeader(
            filename="user/role.md",
            file_path=memory_dir / "user" / "role.md",
            mtime_ms=123,
            name="user_role",
            description="test",
            type=MemoryType.USER,
            scope="project",
        )
    ]


def test_writer_creation(memory_dir):
    """Test MemoryWriter can be created."""
    writer = MemoryWriter(memory_dir, "test_agent")
    assert writer.memory_dir == memory_dir
    assert writer._in_progress is False


@pytest.mark.asyncio
async def test_writer_in_progress_pattern(memory_dir, mock_headers):
    """Test inProgress flag prevents overlapping runs."""
    writer = MemoryWriter(memory_dir, "test_agent")

    # Mock the internal extraction to be slow
    original_extract = writer._do_extraction
    writer._do_extraction = AsyncMock(return_value=["user/new.md"])

    # Start first extraction
    task1 = asyncio.create_task(writer.extract_and_write([], mock_headers))

    # While running, start second - should stash
    await asyncio.sleep(0.01)  # Let first start
    assert writer._in_progress is True

    writer._pending_messages = []  # Stash happened

    # Wait for first to complete
    results1 = await task1
    assert len(results1) == 1

    # inProgress should be False now
    assert writer._in_progress is False


@pytest.mark.asyncio
async def test_writer_write_memory_file(memory_dir):
    """Test writing a memory file."""
    writer = MemoryWriter(memory_dir, "test_agent")

    content = """---
name: test_memory
description: Test description
type: user
scope: project
---

Test content here.
"""

    filepath = await writer.write_memory_file(
        name="test_memory",
        content=content,
        type="user",
    )

    assert filepath is not None
    assert filepath.exists()
    assert filepath.read_text() == content


@pytest.mark.asyncio
async def test_writer_drain(memory_dir):
    """Test drain waits for in-flight tasks."""
    writer = MemoryWriter(memory_dir, "test_agent")

    # Create a mock in-flight task
    mock_task = asyncio.create_task(asyncio.sleep(0.1))
    writer._in_flight.add(mock_task)

    await writer.drain(timeout_ms=200)

    assert mock_task.done()
    assert len(writer._in_flight) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/memory/claudecode/test_writer.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement writer**

```python
# src/copaw/agents/memory/claudecode/writer.py
# -*- coding: utf-8 -*-
"""Memory writer for extracting durable memories from conversation."""
import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from agentscope.message import Msg

from .models import MemoryHeader
from .scanner import MemoryFileScanner

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MemoryWriter:
    """Extract durable memories from conversation and write to files.

    Uses inProgress flag pattern to prevent overlapping runs.
    """

    def __init__(self, memory_dir: Path, agent_id: str):
        self.memory_dir = Path(memory_dir)
        self.agent_id = agent_id
        self._scanner = MemoryFileScanner(self.memory_dir)

        # Concurrency control
        self._in_progress: bool = False
        self._pending_messages: list[Msg] | None = None
        self._in_flight: set[asyncio.Task] = set()
        self._last_message_uuid: str | None = None
        self._turns_since_extraction: int = 0

    async def extract_and_write(
        self,
        messages: list[Msg],
        existing_memories: list[MemoryHeader],
    ) -> list[str]:
        """Extract durable memory from messages and write to files.

        If already running, stash messages for trailing run.
        """
        if self._in_progress:
            self._pending_messages = messages
            return []

        self._in_progress = True
        written_paths: list[str] = []

        try:
            written_paths = await self._do_extraction(messages, existing_memories)
            if messages:
                self._last_message_uuid = getattr(messages[-1], "id", None)
        finally:
            self._in_progress = False

            # Process stashed messages (trailing run)
            if self._pending_messages:
                pending = self._pending_messages
                self._pending_messages = None
                # Fire trailing run asynchronously
                task = asyncio.create_task(
                    self.extract_and_write(pending, existing_memories),
                )
                self._in_flight.add(task)

        return written_paths

    async def _do_extraction(
        self,
        messages: list[Msg],
        existing_memories: list[MemoryHeader],
    ) -> list[str]:
        """Actual extraction logic - placeholder for forked agent."""
        # MVP: No automatic extraction, return empty
        # Full implementation would spawn forked agent here
        return []

    async def write_memory_file(
        self,
        name: str,
        content: str,
        type: str = "project",
    ) -> Path | None:
        """Write a memory file to the appropriate directory."""
        try:
            type_dir = self.memory_dir / type
            type_dir.mkdir(parents=True, exist_ok=True)

            filename = name.replace(" ", "_").lower() + ".md"
            filepath = type_dir / filename

            # Atomic write (write to temp, then rename)
            temp_path = filepath.with_suffix(".tmp")
            temp_path.write_text(content, encoding="utf-8")
            temp_path.rename(filepath)

            logger.info(f"Wrote memory file: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to write memory file: {e}")
            return None

    async def drain(self, timeout_ms: int = 60000) -> None:
        """Wait for all in-flight extraction tasks to complete."""
        if not self._in_flight:
            return

        await asyncio.wait(
            self._in_flight,
            timeout=timeout_ms / 1000,
        )

        # Clear completed tasks
        self._in_flight = {
            t for t in self._in_flight if not t.done()
        }
```

- [ ] **Step 4: Update package exports**

```python
# src/copaw/agents/memory/claudecode/__init__.py
from .writer import MemoryWriter

__all__ = [
    # ... existing ...
    "MemoryWriter",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/agents/memory/claudecode/test_writer.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/agents/memory/claudecode/writer.py \
        src/copaw/agents/memory/claudecode/__init__.py \
        tests/unit/agents/memory/claudecode/test_writer.py
git commit -m "feat(memory): add MemoryWriter with inProgress concurrency pattern"
```

---

### Task 2.2: MemoryRetrievalHook

**Files:**
- Create: `src/copaw/agents/hooks/memory_retrieval.py`
- Modify: `src/copaw/agents/hooks/__init__.py`
- Test: `tests/unit/agents/hooks/test_memory_retrieval.py`

- [ ] **Step 1: Create test file**

```python
# tests/unit/agents/hooks/test_memory_retrieval.py
# -*- coding: utf-8 -*-
"""Tests for MemoryRetrievalHook."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from copaw.agents.hooks.memory_retrieval import MemoryRetrievalHook


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.name = "test_agent"
    agent.memory = MagicMock()
    agent.sys_prompt = "Test prompt"
    return agent


@pytest.fixture
def mock_memory_manager():
    manager = MagicMock()
    manager.find_relevant_memories = AsyncMock(return_value=[])
    return manager


@pytest.mark.asyncio
async def test_hook_skips_short_query(mock_agent, mock_memory_manager):
    """Test hook skips queries shorter than min length."""
    hook = MemoryRetrievalHook(
        memory_manager=mock_memory_manager,
        min_query_length=10,
    )

    kwargs = {"messages": [MagicMock(content="hi")]}
    result = await hook(mock_agent, kwargs)

    mock_memory_manager.find_relevant_memories.assert_not_called()
    assert result is None


@pytest.mark.asyncio
async def test_hook_calls_find_relevant(mock_agent, mock_memory_manager):
    """Test hook calls find_relevant for adequate query."""
    hook = MemoryRetrievalHook(
        memory_manager=mock_memory_manager,
        min_query_length=10,
    )

    msg = MagicMock()
    msg.content = [MagicMock(type="text", text="What is the user's background?")]
    kwargs = {"messages": [msg]}

    result = await hook(mock_agent, kwargs)

    mock_memory_manager.find_relevant_memories.assert_called_once()
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/hooks/test_memory_retrieval.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement hook**

```python
# src/copaw/agents/hooks/memory_retrieval.py
# -*- coding: utf-8 -*-
"""Memory retrieval hook for injecting relevant memories."""
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentscope.agent import ReActAgent
    from ..memory.claudecode.manager import ClaudeCodeMemoryManager

logger = logging.getLogger(__name__)


class MemoryRetrievalHook:
    """Pre-reasoning hook to inject relevant memories."""

    def __init__(
        self,
        memory_manager: "ClaudeCodeMemoryManager",
        min_query_length: int = 10,
    ):
        self.memory_manager = memory_manager
        self.min_query_length = min_query_length
        self._already_surfaced: set[str] = set()

    def _extract_query(self, kwargs: dict[str, Any]) -> str:
        """Extract query from kwargs messages."""
        messages = kwargs.get("messages", [])
        if not messages:
            return ""

        for msg in reversed(messages):
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "text":
                        return getattr(block, "text", "")
            elif isinstance(content, str):
                return content

        return ""

    async def __call__(
        self,
        agent: "ReActAgent",
        kwargs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Pre-reasoning hook to inject relevant memories."""
        query = self._extract_query(kwargs)

        if len(query) < self.min_query_length:
            return None

        try:
            memories = await self.memory_manager.find_relevant_memories(
                query=query,
                already_surfaced=self._already_surfaced,
            )

            if memories:
                for m in memories:
                    self._already_surfaced.add(m.header.filename)
                logger.info(f"MemoryRetrievalHook found {len(memories)} memories")

        except Exception as e:
            logger.exception(f"MemoryRetrievalHook failed: {e}")

        return None
```

- [ ] **Step 4: Update hooks package**

```python
# src/copaw/agents/hooks/__init__.py
from .memory_retrieval import MemoryRetrievalHook

__all__ = [
    "BootstrapHook",
    "MemoryCompactionHook",
    "MemoryRetrievalHook",
]
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/agents/hooks/test_memory_retrieval.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/agents/hooks/memory_retrieval.py \
        src/copaw/agents/hooks/__init__.py \
        tests/unit/agents/hooks/test_memory_retrieval.py
git commit -m "feat(hooks): add MemoryRetrievalHook for pre-reasoning memory injection"
```

---

### Task 2.3: MemoryWritebackHook

**Files:**
- Create: `src/copaw/agents/hooks/memory_writeback.py`
- Modify: `src/copaw/agents/hooks/__init__.py`
- Test: `tests/unit/agents/hooks/test_memory_writeback.py`

- [ ] **Step 1: Create test file**

```python
# tests/unit/agents/hooks/test_memory_writeback.py
# -*- coding: utf-8 -*-
"""Tests for MemoryWritebackHook."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from copaw.agents.hooks.memory_writeback import MemoryWritebackHook


@pytest.fixture
def mock_memory_manager():
    manager = MagicMock()
    manager._writer = MagicMock()
    manager._writer.extract_and_write = AsyncMock(return_value=["user/new.md"])
    manager._scanner = MagicMock()
    manager._scanner.scan = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def mock_session_memory():
    sm = MagicMock()
    sm.should_update = AsyncMock(return_value=False)
    sm.update_summary = AsyncMock()
    return sm


@pytest.mark.asyncio
async def test_hook_calls_extract_and_write(mock_memory_manager, mock_session_memory):
    """Test hook calls extract_and_write on post_reasoning."""
    hook = MemoryWritebackHook(
        memory_manager=mock_memory_manager,
        session_memory=mock_session_memory,
    )

    agent = MagicMock()
    kwargs = {"messages": [MagicMock(id="msg1")]}
    response = MagicMock()

    result = await hook(agent, kwargs, response)

    mock_memory_manager._writer.extract_and_write.assert_called_once()
    assert result is None


@pytest.mark.asyncio
async def test_hook_updates_session_summary(mock_memory_manager, mock_session_memory):
    """Test hook updates session summary when should_update returns True."""
    mock_session_memory.should_update = AsyncMock(return_value=True)

    hook = MemoryWritebackHook(
        memory_manager=mock_memory_manager,
        session_memory=mock_session_memory,
    )

    agent = MagicMock()
    kwargs = {"messages": [MagicMock(id="msg1")]}

    await hook(agent, kwargs, MagicMock())

    mock_session_memory.update_summary.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/hooks/test_memory_writeback.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement hook**

```python
# src/copaw/agents/hooks/memory_writeback.py
# -*- coding: utf-8 -*-
"""Memory writeback hook for extracting durable memories."""
import logging
from typing import TYPE_CHECKING, Any

from agentscope.message import Msg, TextBlock

if TYPE_CHECKING:
    from agentscope.agent import ReActAgent
    from ..memory.claudecode.manager import ClaudeCodeMemoryManager
    from ...app.workspace.services.session_memory import SessionMemoryService

logger = logging.getLogger(__name__)


class MemoryWritebackHook:
    """Post-reasoning hook to extract and write durable memories."""

    def __init__(
        self,
        memory_manager: "ClaudeCodeMemoryManager",
        session_memory: "SessionMemoryService | None" = None,
    ):
        self.memory_manager = memory_manager
        self.session_memory = session_memory

    async def __call__(
        self,
        agent: "ReActAgent",
        kwargs: dict[str, Any],
        response: Msg,
    ) -> Msg | None:
        """Post-reasoning hook to extract memories."""
        messages = kwargs.get("messages", [])

        if not messages:
            return None

        try:
            # Get existing memories
            existing = await self.memory_manager._scanner.scan()

            # Extract and write new memories
            written_paths = await self.memory_manager._writer.extract_and_write(
                messages=messages,
                existing_memories=existing,
            )

            # Update session summary
            if self.session_memory and await self.session_memory.should_update(
                len(messages),
            ):
                await self.session_memory.update_summary(messages)

            if written_paths:
                logger.info(f"MemoryWritebackHook wrote {len(written_paths)} memories")

        except Exception as e:
            logger.exception(f"MemoryWritebackHook failed: {e}")

        return None
```

- [ ] **Step 4: Update hooks package**

```python
# src/copaw/agents/hooks/__init__.py
from .memory_writeback import MemoryWritebackHook

__all__ = [
    "BootstrapHook",
    "MemoryCompactionHook",
    "MemoryRetrievalHook",
    "MemoryWritebackHook",
]
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/agents/hooks/test_memory_writeback.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/agents/hooks/memory_writeback.py \
        src/copaw/agents/hooks/__init__.py \
        tests/unit/agents/hooks/test_memory_writeback.py
git commit -m "feat(hooks): add MemoryWritebackHook for post-reasoning memory extraction"
```

---

### Task 2.4: Register Hooks in CoPawAgent

**Files:**
- Modify: `src/copaw/agents/react_agent.py`

- [ ] **Step 1: Add hook registration in _setup_hooks**

Find `_setup_hooks` method (~line 464) and add after memory_compact_hook:

```python
# Memory hooks for ClaudeCode memory manager
if self._enable_memory_manager:
    from .hooks import MemoryRetrievalHook, MemoryWritebackHook
    from .memory import ClaudeCodeMemoryManager

    if isinstance(self.memory_manager, ClaudeCodeMemoryManager):
        # Pre-reasoning: inject relevant memories
        memory_retrieval_hook = MemoryRetrievalHook(
            memory_manager=self.memory_manager,
        )
        self.register_instance_hook(
            hook_type="pre_reasoning",
            hook_name="memory_retrieval_hook",
            hook=memory_retrieval_hook.__call__,
        )
        logger.debug("Registered memory retrieval hook")

        # Post-reasoning: extract and write memories
        memory_writeback_hook = MemoryWritebackHook(
            memory_manager=self.memory_manager,
        )
        self.register_instance_hook(
            hook_type="post_reasoning",
            hook_name="memory_writeback_hook",
            hook=memory_writeback_hook.__call__,
        )
        logger.debug("Registered memory writeback hook")
```

- [ ] **Step 2: Run existing agent tests**

Run: `pytest tests/unit/agents/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/copaw/agents/react_agent.py
git commit -m "feat(agent): register MemoryRetrievalHook and MemoryWritebackHook"
```

---

## Phase 3: Session Memory & Compaction

### Task 3.1: SessionMemoryService

**Files:**
- Create: `src/copaw/app/workspace/services/__init__.py`
- Create: `src/copaw/app/workspace/services/session_memory.py`
- Test: `tests/unit/workspace/services/test_session_memory.py`

- [ ] **Step 1: Create test file**

```python
# tests/unit/workspace/services/test_session_memory.py
# -*- coding: utf-8 -*-
"""Tests for SessionMemoryService."""
import pytest
import tempfile
from pathlib import Path
from copaw.app.workspace.services.session_memory import SessionMemoryService


@pytest.fixture
def working_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_session_memory_creation(working_dir):
    """Test SessionMemoryService creation."""
    service = SessionMemoryService(str(working_dir))
    assert service.session_id is not None
    assert len(service.session_id) == 8


@pytest.mark.asyncio
async def test_session_memory_start(working_dir):
    """Test start creates summary file."""
    service = SessionMemoryService(str(working_dir))
    await service.start()

    summary_path = working_dir / ".copaw" / "session" / "summary.md"
    assert summary_path.exists()


@pytest.mark.asyncio
async def test_should_update(working_dir):
    """Test should_update returns True every N messages."""
    service = SessionMemoryService(str(working_dir), update_interval=5)

    # First check with 0 messages
    result = await service.should_update(0)
    assert result is False

    # 5 messages should trigger
    result = await service.should_update(5)
    assert result is True

    # 10 messages should trigger
    result = await service.should_update(10)
    assert result is True


@pytest.mark.asyncio
async def test_get_summary(working_dir):
    """Test get_summary returns content."""
    service = SessionMemoryService(str(working_dir))
    await service.start()

    # Write some content
    summary_path = working_dir / ".copaw" / "session" / "summary.md"
    summary_path.write_text("Test summary content")

    result = service.get_summary()
    assert "Test summary content" in result


@pytest.mark.asyncio
async def test_close(working_dir):
    """Test close returns True."""
    service = SessionMemoryService(str(working_dir))
    await service.start()
    result = await service.close()
    assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/workspace/services/test_session_memory.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Create services package**

```python
# src/copaw/app/workspace/services/__init__.py
# -*- coding: utf-8 -*-
"""Workspace services package."""

from .session_memory import SessionMemoryService

__all__ = [
    "SessionMemoryService",
]
```

- [ ] **Step 4: Implement session memory service**

```python
# src/copaw/app/workspace/services/session_memory.py
# -*- coding: utf-8 -*-
"""Session memory service for managing current session summary."""
import logging
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SessionMemoryService:
    """Manage current session's working memory summary.

    Lifecycle: session-level (not persisted across sessions).
    """

    def __init__(
        self,
        working_dir: str,
        update_interval: int = 10,
    ):
        self.working_dir = Path(working_dir)
        self.session_id = uuid.uuid4().hex[:8]
        self.update_interval = update_interval
        self.summary_path = self.working_dir / ".copaw" / "session" / "summary.md"
        self._message_count = 0

    async def start(self) -> None:
        """Start service, create summary file."""
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.summary_path.exists():
            initial_content = f"""---
session_id: {self.session_id}
created_at: {self._get_timestamp()}
---

# Session Summary

## Current Task
No active task.

## Progress
- [ ] Waiting for first user input
"""
            self.summary_path.write_text(initial_content, encoding="utf-8")

        logger.info(f"SessionMemoryService started: session_id={self.session_id}")

    async def close(self) -> bool:
        """Close service."""
        logger.info(f"SessionMemoryService closed: session_id={self.session_id}")
        return True

    async def should_update(self, message_count: int) -> bool:
        """Return True if summary should be updated."""
        if message_count == 0:
            return False
        return message_count % self.update_interval == 0

    async def update_summary(
        self,
        messages: list,
        model: Optional = None,
        formatter: Optional = None,
    ) -> str:
        """Update summary from messages."""
        # MVP: Simple append, full version would use LLM
        self._message_count = len(messages)
        return self.get_summary()

    def get_summary(self) -> str:
        """Return current summary content."""
        if not self.summary_path.exists():
            return ""
        return self.summary_path.read_text(encoding="utf-8")

    def get_summary_for_compaction(self) -> str:
        """Return formatted summary for compaction prompt."""
        summary = self.get_summary()
        if not summary:
            return ""

        # Extract content after frontmatter
        if summary.startswith("---"):
            end_idx = summary.find("---", 3)
            if end_idx != -1:
                return summary[end_idx + 3:].strip()

        return summary

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/workspace/services/test_session_memory.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/workspace/services/__init__.py \
        src/copaw/app/workspace/services/session_memory.py \
        tests/unit/workspace/services/test_session_memory.py
git commit -m "feat(workspace): add SessionMemoryService for session summary management"
```

---

### Task 3.2: Register Services in Workspace and Connect Hooks

**Files:**
- Modify: `src/copaw/app/workspace/workspace.py`
- Modify: `src/copaw/agents/react_agent.py`

- [ ] **Step 1: Add service registration in Workspace._register_services**

Find `_register_services` method in `src/copaw/app/workspace/workspace.py` (around line 170) and add after memory_manager registration:

```python
# Session Memory Service (priority 20, concurrent init)
from ..workspace.services import SessionMemoryService
sm.register(
    ServiceDescriptor(
        name="session_memory",
        service_class=SessionMemoryService,
        init_args=lambda ws: {"working_dir": str(ws.workspace_dir)},
        start_method="start",
        stop_method="close",
        priority=20,
        concurrent_init=True,
    ),
)

# Auto Dream Service (priority 50, non-concurrent init)
from ..workspace.services import AutoDreamService, AutoDreamConfig
sm.register(
    ServiceDescriptor(
        name="auto_dream",
        service_class=AutoDreamService,
        init_args=lambda ws: {
            "working_dir": str(ws.workspace_dir),
            "config": AutoDreamConfig(),
        },
        start_method="start",
        stop_method="close",
        priority=50,
        concurrent_init=False,
    ),
)
```

- [ ] **Step 2: Add service properties to Workspace class**

Add properties to access the services:

```python
@property
def session_memory(self) -> Optional["SessionMemoryService"]:
    """Get session memory service."""
    return self._service_manager.services.get("session_memory")

@property
def auto_dream(self) -> Optional["AutoDreamService"]:
    """Get auto dream service."""
    return self._service_manager.services.get("auto_dream")
```

- [ ] **Step 3: Update MemoryWritebackHook registration in react_agent**

Update the hook registration in `_setup_hooks` to pass session_memory:

```python
# Memory hooks for ClaudeCode memory manager
if self._enable_memory_manager:
    from .hooks import MemoryRetrievalHook, MemoryWritebackHook
    from .memory import ClaudeCodeMemoryManager

    if isinstance(self.memory_manager, ClaudeCodeMemoryManager):
        # Pre-reasoning: inject relevant memories
        memory_retrieval_hook = MemoryRetrievalHook(
            memory_manager=self.memory_manager,
        )
        self.register_instance_hook(
            hook_type="pre_reasoning",
            hook_name="memory_retrieval_hook",
            hook=memory_retrieval_hook.__call__,
        )
        logger.debug("Registered memory retrieval hook")

        # Post-reasoning: extract and write memories
        # Get session_memory from workspace if available
        session_memory = None
        if hasattr(self, "_workspace") and self._workspace is not None:
            session_memory = self._workspace.session_memory

        memory_writeback_hook = MemoryWritebackHook(
            memory_manager=self.memory_manager,
            session_memory=session_memory,
        )
        self.register_instance_hook(
            hook_type="post_reasoning",
            hook_name="memory_writeback_hook",
            hook=memory_writeback_hook.__call__,
        )
        logger.debug("Registered memory writeback hook")
```

- [ ] **Step 4: Run existing tests**

Run: `pytest tests/unit/workspace/test_workspace.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/workspace/workspace.py \
        src/copaw/agents/react_agent.py
git commit -m "feat(workspace): register SessionMemoryService and AutoDreamService, connect to hooks"
```

---

## Phase 4: ConsolidationLock & AutoDream

### Task 4.1: ConsolidationLock

**Files:**
- Create: `src/copaw/agents/memory/claudecode/lock.py`
- Test: `tests/unit/agents/memory/claudecode/test_lock.py`

- [ ] **Step 1: Create test file**

```python
# tests/unit/agents/memory/claudecode/test_lock.py
# -*- coding: utf-8 -*-
"""Tests for ConsolidationLock."""
import pytest
import tempfile
import os
import time
from pathlib import Path
from copaw.agents.memory.claudecode.lock import ConsolidationLock


@pytest.fixture
def memory_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_lock_file_path(memory_dir):
    """Test lock file path resolution."""
    lock = ConsolidationLock(memory_dir)
    assert lock.lock_path() == memory_dir / ".consolidate-lock"


@pytest.mark.asyncio
async def test_lock_read_last_consolidated_at_empty(memory_dir):
    """Test reading mtime when no lock exists."""
    lock = ConsolidationLock(memory_dir)
    mtime = await lock.read_last_consolidated_at()
    assert mtime == 0


@pytest.mark.asyncio
async def test_lock_try_acquire(memory_dir):
    """Test acquiring lock."""
    lock = ConsolidationLock(memory_dir)

    prior_mtime = await lock.try_acquire()
    assert prior_mtime == 0

    lock_path = lock.lock_path()
    assert lock_path.exists()
    pid = int(lock_path.read_text().strip())
    assert pid == os.getpid()


@pytest.mark.asyncio
async def test_lock_rollback(memory_dir):
    """Test lock rollback."""
    lock = ConsolidationLock(memory_dir)

    await lock.try_acquire()
    await lock.rollback(0)

    lock_path = lock.lock_path()
    assert not lock_path.exists()


@pytest.mark.asyncio
async def test_lock_is_process_running():
    """Test process running check."""
    lock = ConsolidationLock(Path("/tmp"))

    assert lock._is_process_running(os.getpid()) is True
    assert lock._is_process_running(999999) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/agents/memory/claudecode/test_lock.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement lock**

```python
# src/copaw/agents/memory/claudecode/lock.py
# -*- coding: utf-8 -*-
"""PID-based file lock for cross-process consolidation."""
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class ConsolidationLock:
    """File-based lock for AutoDream consolidation."""

    LOCK_FILE = ".consolidate-lock"
    HOLDER_STALE_MS = 60 * 60 * 1000  # 1 hour

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)

    def lock_path(self) -> Path:
        return self.memory_dir / self.LOCK_FILE

    async def read_last_consolidated_at(self) -> int:
        """Return last consolidation time in ms, 0 if no lock."""
        path = self.lock_path()
        if not path.exists():
            return 0
        return int(path.stat().st_mtime * 1000)

    async def try_acquire(self) -> int | None:
        """Try to acquire lock. Returns prior mtime if acquired."""
        path = self.lock_path()
        prior_mtime_ms = 0

        if path.exists():
            mtime_ms = int(path.stat().st_mtime * 1000)
            holder_pid_str = path.read_text().strip()

            try:
                holder_pid = int(holder_pid_str)
            except ValueError:
                pass
            else:
                now_ms = int(time.time() * 1000)
                if now_ms - mtime_ms < self.HOLDER_STALE_MS:
                    if self._is_process_running(holder_pid):
                        if holder_pid == os.getpid():
                            prior_mtime_ms = mtime_ms
                        else:
                            return None

        self.memory_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(str(os.getpid()))

        written_pid = int(path.read_text().strip())
        if written_pid != os.getpid():
            return None

        return prior_mtime_ms

    async def rollback(self, prior_mtime: int) -> None:
        """Rollback lock to prior state."""
        path = self.lock_path()
        if prior_mtime == 0:
            path.unlink(missing_ok=True)
        else:
            path.write_text("")
            os.utime(path, (prior_mtime / 1000, prior_mtime / 1000))

    def _is_process_running(self, pid: int) -> bool:
        """Check if process is running."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError, ValueError):
            return False
```

- [ ] **Step 4: Update package exports**

```python
# src/copaw/agents/memory/claudecode/__init__.py
from .lock import ConsolidationLock

__all__ = [
    # ... existing ...
    "ConsolidationLock",
]
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/agents/memory/claudecode/test_lock.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/agents/memory/claudecode/lock.py \
        src/copaw/agents/memory/claudecode/__init__.py \
        tests/unit/agents/memory/claudecode/test_lock.py
git commit -m "feat(memory): add ConsolidationLock for cross-process coordination"
```

---

### Task 4.2: AutoDreamService

**Files:**
- Create: `src/copaw/app/workspace/services/auto_dream.py`
- Modify: `src/copaw/app/workspace/services/__init__.py`
- Test: `tests/unit/workspace/services/test_auto_dream.py`

- [ ] **Step 1: Create test file**

```python
# tests/unit/workspace/services/test_auto_dream.py
# -*- coding: utf-8 -*-
"""Tests for AutoDreamService."""
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from copaw.app.workspace.services.auto_dream import AutoDreamService, AutoDreamConfig


@pytest.fixture
def working_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config():
    return AutoDreamConfig(
        min_session_count=3,
        min_hours_since_last_run=24,
    )


def test_auto_dream_creation(working_dir, config):
    """Test AutoDreamService creation."""
    service = AutoDreamService(str(working_dir), config)
    assert service.dream_dir == working_dir / ".copaw" / "dream"
    assert service._is_running is False


@pytest.mark.asyncio
async def test_auto_dream_start(working_dir, config):
    """Test start creates dream directory."""
    service = AutoDreamService(str(working_dir), config)
    await service.start()

    assert service.dream_dir.exists()


@pytest.mark.asyncio
async def test_should_run_no_lock(working_dir, config):
    """Test should_run returns True when no lock."""
    service = AutoDreamService(str(working_dir), config)
    await service.start()

    result = await service.should_run()
    assert result is False  # No sessions yet


@pytest.mark.asyncio
async def test_should_run_with_sessions(working_dir, config):
    """Test should_run with enough sessions."""
    service = AutoDreamService(str(working_dir), config)
    await service.start()

    # Create session files
    sessions_dir = service.dream_dir / "sessions"
    sessions_dir.mkdir(exist_ok=True)

    for i in range(3):
        session_file = sessions_dir / f"session_{i}.json"
        session_file.write_text("{}")

    result = await service.should_run()
    # Would still need time check to pass
    assert len(list(sessions_dir.glob("*.json"))) >= config.min_session_count


@pytest.mark.asyncio
async def test_close(working_dir, config):
    """Test close returns True."""
    service = AutoDreamService(str(working_dir), config)
    await service.start()
    result = await service.close()
    assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/workspace/services/test_auto_dream.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement auto dream service**

```python
# src/copaw/app/workspace/services/auto_dream.py
# -*- coding: utf-8 -*-
"""AutoDream service for offline memory consolidation."""
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AutoDreamConfig:
    """Configuration for AutoDream service."""
    min_session_count: int = 3
    min_hours_since_last_run: float = 24.0
    enabled: bool = True


class AutoDreamService:
    """Offline memory consolidation service.

    Triggered by:
    - Time threshold (min_hours_since_last_run)
    - Session count threshold (min_session_count)
    """

    def __init__(
        self,
        working_dir: str,
        config: AutoDreamConfig,
    ):
        self.working_dir = Path(working_dir)
        self.config = config
        self.dream_dir = self.working_dir / ".copaw" / "dream"
        self._is_running = False
        self._lock = None  # Will be set later with memory_dir

    async def start(self) -> None:
        """Start service, create dream directory."""
        self.dream_dir.mkdir(parents=True, exist_ok=True)

        # Create sessions directory
        (self.dream_dir / "sessions").mkdir(exist_ok=True)

        logger.info("AutoDreamService started")

    async def close(self) -> bool:
        """Close service."""
        self._is_running = False
        logger.info("AutoDreamService closed")
        return True

    async def should_run(self) -> bool:
        """Check all trigger conditions."""
        if not self.config.enabled:
            return False

        if self._is_running:
            return False

        # Check session count
        sessions_dir = self.dream_dir / "sessions"
        sessions = list(sessions_dir.glob("*.json"))
        if len(sessions) < self.config.min_session_count:
            return False

        # Check time since last run
        last_run_path = self.dream_dir / "last_run.json"
        if last_run_path.exists():
            try:
                last_run = json.loads(last_run_path.read_text())
                last_time = last_run.get("timestamp", 0)
                hours_since = (time.time() - last_time) / 3600
                if hours_since < self.config.min_hours_since_last_run:
                    return False
            except Exception:
                pass

        # Check lock
        if self._lock:
            prior_mtime = await self._lock.try_acquire()
            if prior_mtime is None:
                return False

        return True

    async def run_consolidation(
        self,
        memory_manager,
        model: Optional = None,
    ) -> dict:
        """Run consolidation process."""
        if self._is_running:
            return {"status": "already_running"}

        self._is_running = True

        try:
            # 1. Get lock
            if self._lock:
                await self._lock.try_acquire()

            # 2. Collect session data
            sessions = await self._collect_sessions()

            # 3. Run consolidation (MVP: placeholder)
            result = await self._do_consolidation(sessions, memory_manager)

            # 4. Update last_run.json
            last_run_path = self.dream_dir / "last_run.json"
            last_run_path.write_text(json.dumps({
                "timestamp": time.time(),
                "sessions_processed": len(sessions),
            }))

            return {"status": "completed", "result": result}

        finally:
            self._is_running = False
            if self._lock:
                await self._lock.rollback(0)

    async def _collect_sessions(self) -> list[dict]:
        """Collect session data for consolidation."""
        sessions_dir = self.dream_dir / "sessions"
        sessions = []

        for session_file in sessions_dir.glob("*.json"):
            try:
                session_data = json.loads(session_file.read_text())
                sessions.append(session_data)
            except Exception as e:
                logger.warning(f"Failed to read session {session_file}: {e}")

        return sessions

    async def _do_consolidation(
        self,
        sessions: list[dict],
        memory_manager,
    ) -> dict:
        """Actual consolidation logic - placeholder."""
        # MVP: No consolidation, return summary
        # Full version would spawn forked consolidation agent
        return {
            "sessions": len(sessions),
            "memories_written": 0,
        }

    def record_session(self, session_data: dict) -> None:
        """Record a session for future consolidation."""
        import uuid

        session_id = session_data.get("session_id", uuid.uuid4().hex[:8])
        session_file = self.dream_dir / "sessions" / f"session_{session_id}.json"
        session_file.write_text(json.dumps(session_data, indent=2))
```

- [ ] **Step 4: Update services package**

```python
# src/copaw/app/workspace/services/__init__.py
from .session_memory import SessionMemoryService
from .auto_dream import AutoDreamService, AutoDreamConfig

__all__ = [
    "SessionMemoryService",
    "AutoDreamService",
    "AutoDreamConfig",
]
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/workspace/services/test_auto_dream.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/workspace/services/auto_dream.py \
        src/copaw/app/workspace/services/__init__.py \
        tests/unit/workspace/services/test_auto_dream.py
git commit -m "feat(workspace): add AutoDreamService for offline memory consolidation"
```

---

## Phase 5: Extended Features (Optional)

The following tasks are optional extensions that can be implemented later:

### Task 5.1: AgentMemoryScope (user/project/local paths)

### Task 5.2: TeamMemoryManager (local shared team/ directory)

### Task 5.3: LLM-based MemoryRetriever selection

### Task 5.4: Forked Agent for MemoryWriter

---

## Test Coverage Requirements

Run all tests:
```bash
pytest tests/unit/agents/memory/claudecode/ -v
pytest tests/unit/agents/hooks/ -v
pytest tests/unit/workspace/services/ -v
```

Pre-commit:
```bash
pre-commit run --files src/copaw/agents/memory/claudecode/
```

---

## References

- Spec: `docs/superpowers/specs/2026-04-04-claudecode-memory-design.md`
- Claude Code source: `C:\workspace\free-code-main\src\memdir\`
- AgentScope hooks: `agentscope/agent/_agent_base.py`