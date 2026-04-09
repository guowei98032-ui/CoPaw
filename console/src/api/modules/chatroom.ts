import { request } from "../request";
import type {
  ChatRoom,
  ChatRoomDetail,
  CreateChatRoomRequest,
  CreateChatRoomResponse,
  UpdateChatRoomRequest,
  Task,
  CreateTaskRequest,
  UpdateTaskRequest,
  CancelTaskRequest,
  RetryTaskRequest,
  SetAutoModeRequest,
  MatrixConfig,
  BatchTaskOperationRequest,
  BatchOperationResult,
  TaskLogEntryRequest,
} from "../types/chatroom";

export const chatroomApi = {
  // ========== ChatRoom CRUD ==========

  /** Create a new chatroom */
  createChatRoom: (data: CreateChatRoomRequest) =>
    request<CreateChatRoomResponse>("/chatroom", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /** List all chatrooms */
  listChatRooms: (userId?: string) => {
    const params = new URLSearchParams();
    if (userId) params.append("user_id", userId);
    const query = params.toString();
    return request<ChatRoom[]>(`/chatroom${query ? `?${query}` : ""}`);
  },

  /** Get chatroom details */
  getChatRoom: (roomId: string) =>
    request<ChatRoomDetail>(`/chatroom/${encodeURIComponent(roomId)}`),

  /** Update a chatroom */
  updateChatRoom: (roomId: string, data: UpdateChatRoomRequest) =>
    request<ChatRoom>(`/chatroom/${encodeURIComponent(roomId)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  /** Delete a chatroom */
  deleteChatRoom: (roomId: string) =>
    request<{ success: boolean; message: string }>(
      `/chatroom/${encodeURIComponent(roomId)}`,
      {
        method: "DELETE",
      },
    ),

  // ========== Task Management ==========

  /** List tasks in a chatroom */
  listTasks: (
    roomId: string,
    options?: { status?: string; owner?: string },
  ) => {
    const params = new URLSearchParams();
    if (options?.status) params.append("status", options.status);
    if (options?.owner) params.append("owner", options.owner);
    const query = params.toString();
    return request<Task[]>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks${query ? `?${query}` : ""}`,
    );
  },

  /** Create a new task */
  createTask: (roomId: string, data: CreateTaskRequest) =>
    request<Task>(`/chatroom/${encodeURIComponent(roomId)}/tasks`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /** Get a specific task */
  getTask: (roomId: string, taskId: string) =>
    request<Task>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/${encodeURIComponent(taskId)}`,
    ),

  /** Update a task */
  updateTask: (roomId: string, taskId: string, data: UpdateTaskRequest) =>
    request<Task>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/${encodeURIComponent(taskId)}`,
      {
        method: "PUT",
        body: JSON.stringify(data),
      },
    ),

  /** Delete a task */
  deleteTask: (roomId: string, taskId: string) =>
    request<{ success: boolean; message: string }>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/${encodeURIComponent(taskId)}`,
      {
        method: "DELETE",
      },
    ),

  /** Cancel a task */
  cancelTask: (roomId: string, taskId: string, data?: CancelTaskRequest) =>
    request<Task>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/${encodeURIComponent(taskId)}/cancel`,
      {
        method: "POST",
        body: JSON.stringify(data || {}),
      },
    ),

  /** Retry a failed/cancelled task */
  retryTask: (roomId: string, taskId: string, data?: RetryTaskRequest) =>
    request<Task>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/${encodeURIComponent(taskId)}/retry`,
      {
        method: "POST",
        body: JSON.stringify(data || { reset_owner: true }),
      },
    ),

  /** Set task auto_mode */
  setTaskAutoMode: (roomId: string, taskId: string, data: SetAutoModeRequest) =>
    request<Task>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/${encodeURIComponent(taskId)}/auto-mode`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  /** Add task log entry */
  addTaskLog: (roomId: string, taskId: string, data: TaskLogEntryRequest) =>
    request<Task>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/${encodeURIComponent(taskId)}/log`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  /** Batch task operations */
  batchTaskOperation: (roomId: string, data: BatchTaskOperationRequest) =>
    request<BatchOperationResult>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/batch`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  /** Export tasks */
  exportTasks: (
    roomId: string,
    format: "csv" | "json" = "csv",
    status?: string,
  ) => {
    const params = new URLSearchParams();
    params.append("format", format);
    if (status) params.append("status", status);
    const query = params.toString();
    // Return URL for download
    return `/api/chatroom/${encodeURIComponent(roomId)}/tasks/export?${query}`;
  },

  /** Get timeout tasks */
  getTimeoutTasks: (roomId: string) =>
    request<Task[]>(
      `/chatroom/${encodeURIComponent(roomId)}/tasks/timeout`,
    ),

  /** Subscribe to task events (SSE) */
  subscribeTaskEvents: (roomId: string) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || "";
    return new EventSource(
      `${baseUrl}/chatroom/${encodeURIComponent(roomId)}/events`,
    );
  },

  // ========== Matrix Integration ==========

  /** Get Matrix config for an agent */
  getMatrixConfig: (agentId: string) =>
    request<MatrixConfig>(
      `/chatroom/agents/${encodeURIComponent(agentId)}/matrix-config`,
    ),
};
