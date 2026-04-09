// ChatRoom API Tests
import { describe, it, expect, vi, beforeEach } from "vitest";
import { chatroomApi } from "./chatroom";
import { request } from "../request";

// Mock the request module
vi.mock("../request", () => ({
  request: vi.fn(),
}));

describe("ChatRoom API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("ChatRoom CRUD", () => {
    it("should create a chatroom", async () => {
      const mockResponse = {
        room: {
          id: "room-1",
          name: "Test Room",
          user_id: "user-1",
          lead_agent_id: "lead-1",
          agent_ids: ["worker-1"],
          agent_roles: {},
          sessions: {},
          layout: "tiles",
          matrix_room_id: null,
          matrix_alias: null,
          created_at: "2026-04-08T10:00:00",
          updated_at: "2026-04-08T10:00:00",
        },
        message: "ChatRoom created",
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.createChatRoom({
        name: "Test Room",
        lead_agent_id: "lead-1",
        agent_ids: ["worker-1"],
      });

      expect(request).toHaveBeenCalledWith("/chatroom", {
        method: "POST",
        body: JSON.stringify({
          name: "Test Room",
          lead_agent_id: "lead-1",
          agent_ids: ["worker-1"],
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it("should list chatrooms", async () => {
      const mockResponse = [
        {
          id: "room-1",
          name: "Room 1",
          user_id: "user-1",
          lead_agent_id: "lead-1",
          agent_ids: [],
          agent_roles: {},
          sessions: {},
          layout: "tiles",
          matrix_room_id: null,
          matrix_alias: null,
          created_at: "2026-04-08T10:00:00",
          updated_at: "2026-04-08T10:00:00",
        },
      ];

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.listChatRooms("user-1");

      expect(request).toHaveBeenCalledWith("/chatroom?user_id=user-1");
      expect(result).toEqual(mockResponse);
    });

    it("should get chatroom details", async () => {
      const mockResponse = {
        id: "room-1",
        name: "Room 1",
        user_id: "user-1",
        lead_agent_id: "lead-1",
        agent_ids: ["worker-1", "worker-2"],
        agent_roles: { "lead-1": "Team Lead" },
        sessions: {},
        layout: "tiles",
        matrix_room_id: null,
        matrix_alias: null,
        created_at: "2026-04-08T10:00:00",
        updated_at: "2026-04-08T10:00:00",
        messages: [],
        tasks: [],
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.getChatRoom("room-1");

      expect(request).toHaveBeenCalledWith("/chatroom/room-1");
      expect(result).toEqual(mockResponse);
    });

    it("should update a chatroom", async () => {
      const mockResponse = {
        id: "room-1",
        name: "Updated Name",
        user_id: "user-1",
        lead_agent_id: "lead-1",
        agent_ids: ["worker-1", "worker-2"],
        agent_roles: {},
        sessions: {},
        layout: "tabs",
        matrix_room_id: null,
        matrix_alias: null,
        created_at: "2026-04-08T10:00:00",
        updated_at: "2026-04-08T11:00:00",
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.updateChatRoom("room-1", {
        name: "Updated Name",
        agent_ids: ["worker-1", "worker-2"],
      });

      expect(request).toHaveBeenCalledWith("/chatroom/room-1", {
        method: "PUT",
        body: JSON.stringify({
          name: "Updated Name",
          agent_ids: ["worker-1", "worker-2"],
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it("should delete a chatroom", async () => {
      const mockResponse = { success: true, message: "ChatRoom deleted" };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.deleteChatRoom("room-1");

      expect(request).toHaveBeenCalledWith("/chatroom/room-1", {
        method: "DELETE",
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("Task Management", () => {
    it("should create a task", async () => {
      const mockResponse = {
        id: "task-1",
        room_id: "room-1",
        subject: "Fix bug",
        description: "Fix the login bug",
        owner: "worker-1",
        status: "pending",
        blocked_by: [],
        blocks: [],
        priority: "high",
        deadline: null,
        auto_mode: false,
        retry_count: 0,
        max_retries: 3,
        progress: 0,
        timeout_minutes: null,
        started_at: null,
        execution_log: [],
        source_session_id: null,
        source_message_id: null,
        created_by: "system",
        created_at: "2026-04-08T10:00:00",
        updated_at: "2026-04-08T10:00:00",
        completed_at: null,
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.createTask("room-1", {
        subject: "Fix bug",
        owner: "worker-1",
        priority: "high",
      });

      expect(request).toHaveBeenCalledWith("/chatroom/room-1/tasks", {
        method: "POST",
        body: JSON.stringify({
          subject: "Fix bug",
          owner: "worker-1",
          priority: "high",
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it("should list tasks with filters", async () => {
      const mockResponse = [
        {
          id: "task-1",
          room_id: "room-1",
          subject: "Task 1",
          status: "pending",
          owner: "worker-1",
        },
      ];

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.listTasks("room-1", {
        status: "pending",
        owner: "worker-1",
      });

      expect(request).toHaveBeenCalledWith(
        "/chatroom/room-1/tasks?status=pending&owner=worker-1"
      );
      expect(result).toEqual(mockResponse);
    });

    it("should update a task", async () => {
      const mockResponse = {
        id: "task-1",
        room_id: "room-1",
        subject: "Task 1",
        status: "completed",
        progress: 100,
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.updateTask("room-1", "task-1", {
        status: "completed",
      });

      expect(request).toHaveBeenCalledWith("/chatroom/room-1/tasks/task-1", {
        method: "PUT",
        body: JSON.stringify({ status: "completed" }),
      });
      expect(result).toEqual(mockResponse);
    });

    it("should cancel a task", async () => {
      const mockResponse = {
        id: "task-1",
        status: "cancelled",
        owner: null,
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.cancelTask("room-1", "task-1", {
        reason: "Requirements changed",
      });

      expect(request).toHaveBeenCalledWith(
        "/chatroom/room-1/tasks/task-1/cancel",
        {
          method: "POST",
          body: JSON.stringify({ reason: "Requirements changed" }),
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it("should retry a failed task", async () => {
      const mockResponse = {
        id: "task-1",
        status: "pending",
        retry_count: 1,
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.retryTask("room-1", "task-1");

      expect(request).toHaveBeenCalledWith(
        "/chatroom/room-1/tasks/task-1/retry",
        {
          method: "POST",
          body: JSON.stringify({ reset_owner: true }),
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it("should perform batch task operations", async () => {
      const mockResponse = {
        success_count: 2,
        failed_count: 0,
        failed_tasks: [],
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.batchTaskOperation("room-1", {
        task_ids: ["task-1", "task-2"],
        operation: "cancel",
        reason: "Batch cancel",
      });

      expect(request).toHaveBeenCalledWith("/chatroom/room-1/tasks/batch", {
        method: "POST",
        body: JSON.stringify({
          task_ids: ["task-1", "task-2"],
          operation: "cancel",
          reason: "Batch cancel",
        }),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("Multi-Agent Scenarios", () => {
    it("should create a chatroom with multiple agents", async () => {
      const mockResponse = {
        room: {
          id: "team-room",
          name: "Development Team",
          user_id: "user-1",
          lead_agent_id: "lead-1",
          agent_ids: ["worker-a", "worker-b", "worker-c"],
          agent_roles: {
            "lead-1": "Team Lead - oversees all tasks",
            "worker-a": "Frontend Developer",
            "worker-b": "Backend Developer",
            "worker-c": "QA Engineer",
          },
          sessions: {},
          layout: "tiles",
          matrix_room_id: null,
          matrix_alias: null,
          created_at: "2026-04-08T10:00:00",
          updated_at: "2026-04-08T10:00:00",
        },
        message: "ChatRoom created",
      };

      vi.mocked(request).mockResolvedValue(mockResponse);

      const result = await chatroomApi.createChatRoom({
        name: "Development Team",
        lead_agent_id: "lead-1",
        agent_ids: ["worker-a", "worker-b", "worker-c"],
        agent_roles: {
          "lead-1": "Team Lead - oversees all tasks",
          "worker-a": "Frontend Developer",
          "worker-b": "Backend Developer",
          "worker-c": "QA Engineer",
        },
      });

      expect(result.room.agent_ids).toHaveLength(3);
      expect(result.room.agent_roles["worker-a"]).toBe("Frontend Developer");
    });

    it("should assign tasks to different workers", async () => {
      const task1 = {
        id: "task-1",
        room_id: "team-room",
        subject: "Implement UI",
        owner: "worker-a",
        status: "pending",
      };

      const task2 = {
        id: "task-2",
        room_id: "team-room",
        subject: "Implement API",
        owner: "worker-b",
        status: "pending",
      };

      vi.mocked(request)
        .mockResolvedValueOnce(task1)
        .mockResolvedValueOnce(task2);

      const result1 = await chatroomApi.createTask("team-room", {
        subject: "Implement UI",
        owner: "worker-a",
      });

      const result2 = await chatroomApi.createTask("team-room", {
        subject: "Implement API",
        owner: "worker-b",
      });

      expect(result1.owner).toBe("worker-a");
      expect(result2.owner).toBe("worker-b");
    });
  });
});