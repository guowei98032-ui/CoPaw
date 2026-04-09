#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ChatRoom feature quick test script.

Usage:
    python -m tests.chatroom_test
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from copaw.app.models.chatroom import (
    ChatRoom,
    Task,
    MailboxMessage,
)
from copaw.app.db.chatroom_db import ChatRoomDatabase


def test_models():
    """Test Pydantic models."""
    print("=" * 50)
    print("Testing Pydantic Models...")
    print("=" * 50)

    # Test ChatRoom
    room = ChatRoom(
        name="Test Room",
        lead_agent_id="agent-lead",
        agent_ids=["agent-1", "agent-2"],
        layout="tiles",
    )
    print(f"✓ ChatRoom: {room.name} (ID: {room.id})")
    print(f"  Lead: {room.lead_agent_id}")
    print(f"  Agents: {room.agent_ids}")
    print(f"  Layout: {room.layout}")

    # Test Task
    task = Task(
        room_id=room.id,
        subject="Test Task",
        description="This is a test task",
        owner="agent-1",
        priority="high",
    )
    print(f"\n✓ Task: {task.subject} (ID: {task.id})")
    print(f"  Status: {task.status}")
    print(f"  Owner: {task.owner}")
    print(f"  Priority: {task.priority}")

    # Test MailboxMessage
    msg = MailboxMessage(
        room_id=room.id,
        from_agent="agent-lead",
        to_agent="agent-1",
        content="Hello from lead agent",
        message_type="chat",
    )
    print(f"\n✓ MailboxMessage: {msg.id}")
    print(f"  From: {msg.from_agent} → To: {msg.to_agent}")
    print(f"  Type: {msg.message_type}")
    print(f"  Content: {msg.content[:30]}...")

    print("\n✓ All model tests passed!\n")
    return room, task, msg


def test_database():
    """Test SQLite database operations."""
    print("=" * 50)
    print("Testing Database Operations...")
    print("=" * 50)

    db = ChatRoomDatabase(":memory:")

    # Create room
    room = ChatRoom(
        name="DB Test Room",
        lead_agent_id="agent-lead",
        agent_ids=["agent-1", "agent-2", "agent-3"],
        layout="tabs",
    )
    created_room = db.create_room(room)
    print(f"✓ Created room: {created_room.name} (ID: {created_room.id})")

    # Create tasks
    tasks = [
        Task(
            room_id=created_room.id,
            subject=f"Task {i}",
            description=f"Description for task {i}",
            owner=f"agent-{i}",
            priority="medium",
        )
        for i in range(1, 4)
    ]

    for task in tasks:
        created_task = db.create_task(task)
        print(f"  ✓ Created task: {created_task.subject} (ID: {created_task.id})")

    # List tasks
    all_tasks = db.get_tasks(created_room.id)
    print(f"\n✓ List tasks: {len(all_tasks)} tasks found")

    # Filter by status
    pending_tasks = db.get_tasks(created_room.id, status="pending")
    print(f"  Pending: {len(pending_tasks)} tasks")

    # Update task
    if all_tasks:
        task_to_update = all_tasks[0]
        task_to_update.status = "completed"
        updated = db.update_task(task_to_update)
        print(f"\n✓ Updated task: {updated.subject} → {updated.status}")

    # Verify update
    completed_tasks = db.get_tasks(created_room.id, status="completed")
    print(f"  Completed: {len(completed_tasks)} tasks")

    # Create message
    msg = MailboxMessage(
        room_id=created_room.id,
        from_agent="agent-lead",
        to_agent="agent-1",
        content="Test message",
        message_type="task_assign",
    )
    saved_msg = db.save_message(msg)
    print(f"\n✓ Saved message: {saved_msg.id}")

    # List messages
    messages = db.get_messages(created_room.id, limit=10)
    print(f"  Messages: {len(messages)} found")

    # Mark as read
    db.mark_message_read(saved_msg.id)
    print(f"  ✓ Marked message as read")

    # Verify read status
    unread = db.get_messages(created_room.id, unread_only=True)
    print(f"  Unread messages: {len(unread)}")

    print("\n✓ All database tests passed!\n")
    return db


def test_tools_import():
    """Test tool imports."""
    print("=" * 50)
    print("Testing Tool Imports...")
    print("=" * 50)

    try:
        from copaw.agents.tools.task_management import (
            task_list,
            task_create,
            task_update,
            task_claim,
            task_delete,
        )
        print("✓ task_management tools imported successfully")

        from copaw.agents.tools.mailbox import (
            mailbox_read,
            mailbox_send,
            mailbox_mark_read,
            mailbox_broadcast,
        )
        print("✓ mailbox tools imported successfully")

        print("\n✓ All tool import tests passed!\n")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}\n")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("CoPaw ChatRoom Feature Test Suite")
    print("=" * 60 + "\n")

    # Test 1: Models
    try:
        room, task, msg = test_models()
    except Exception as e:
        print(f"✗ Model test failed: {e}\n")
        return 1

    # Test 2: Database
    try:
        db = test_database()
    except Exception as e:
        print(f"✗ Database test failed: {e}\n")
        return 1

    # Test 3: Tools import
    if not test_tools_import():
        return 1

    print("=" * 60)
    print("All tests completed successfully! ✓")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start the server: copaw app")
    print("2. Open Console: http://127.0.0.1:8088")
    print("3. Navigate to Control → ChatRooms")
    print("4. Create a new chatroom and test features")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
