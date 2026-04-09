# -*- coding: utf-8 -*-
"""Agent tools for CoPaw.

LLM Tool (exposed to agents in chatroom):
- create_task: Create a new task (Leader only, during user conversation)

Backend APIs (not exposed to LLM, for system/frontend use):
- task_create: Create task with owner parameter
- task_list: List tasks
- task_claim: Claim a task
- task_update: Update task status/progress
- task_cancel: Cancel a task
- task_delete: Delete a task
- task_retry: Retry a failed task
- task_set_auto_mode: Set auto mode flag
- chatroom_context: Get chatroom context

Poll Service uses structured JSON output instead of tools:
- Leader: {"tasks_to_create": [...]} when unassigned tasks exist
- Worker (idle): {"task_to_claim": "id"} to claim a task
- Worker (busy): {"status": "completed|failed|cancelled", "reason": "..."}
"""
from agentscope.tool import (
    execute_python_code,
    view_text_file,
    write_text_file,
)

from .file_io import (
    read_file,
    write_file,
    edit_file,
    append_file,
)
from .file_search import (
    grep_search,
    glob_search,
)
from .shell import execute_shell_command
from .send_file import send_file_to_user
from .browser_control import browser_use
from .desktop_screenshot import desktop_screenshot
from .view_media import view_image, view_video
from .memory_search import create_memory_search_tool
from .get_current_time import get_current_time, set_user_timezone
from .get_token_usage import get_token_usage

# LLM Tool for chatroom (only create_task for Leader during user conversation)
from .task_management import create_task

# Backend APIs (for poll_service and frontend, not LLM)
from .task_management import (
    task_create,
    task_list,
    task_claim,
    task_update,
    task_cancel,
    task_delete,
    task_retry,
    task_set_auto_mode,
    chatroom_context,
)

# LLM-exposed tools
__all__ = [
    # Built-in tools
    "execute_python_code",
    "execute_shell_command",
    "view_text_file",
    "write_text_file",
    "read_file",
    "write_file",
    "edit_file",
    "append_file",
    "grep_search",
    "glob_search",
    "send_file_to_user",
    "desktop_screenshot",
    "view_image",
    "view_video",
    "browser_use",
    "create_memory_search_tool",
    "get_current_time",
    "set_user_timezone",
    "get_token_usage",
    # Chatroom LLM tool (only for Leader during user conversation)
    "create_task",
]
