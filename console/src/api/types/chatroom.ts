// ChatRoom API types

export interface ChatRoom {
  id: string;
  name: string;
  user_id: string;
  lead_agent_id: string | null;
  agent_ids: string[];
  agent_roles: Record<string, string>;  // {agent_id: role_description}
  sessions: Record<string, SessionInfo>;
  layout: "tiles" | "tabs" | "list";
  matrix_room_id: string | null;
  matrix_alias: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionInfo {
  session_id: string;
  agent_id: string;
  user_id: string;
  channel: string;
  created_at: string;
}

export interface Task {
  id: string;
  room_id: string;
  subject: string;
  description: string | null;
  owner: string | null;
  status: "pending" | "in_progress" | "completed" | "failed" | "cancelled";
  blocked_by: string[];
  blocks: string[];
  priority: "low" | "medium" | "high";
  deadline: string | null;
  auto_mode: boolean;  // If true, agent acts autonomously
  retry_count: number;  // Current retry count
  max_retries: number;  // Max allowed retries
  progress: number;  // Execution progress 0-100
  timeout_minutes: number | null;  // Expected completion time in minutes
  started_at: string | null;  // When task was started
  execution_log: ExecutionLogEntry[];  // Execution history
  // Task tracing - link back to user conversation
  source_session_id: string | null;
  source_message_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ExecutionLogEntry {
  timestamp: string;
  event: string;  // started, progress, completed, failed, cancelled, retry, timeout_warning, note, update
  details: string | null;
}

export interface ChatRoomDetail extends ChatRoom {
  tasks: Task[];
  messages?: Array<{ id: string; read: boolean }>;
}

// Request/Response types
export interface CreateChatRoomRequest {
  name: string;
  lead_agent_id?: string | null;
  agent_ids?: string[];
  agent_roles?: Record<string, string>;
  layout?: string;
  matrix_mode?: "none" | "create_new" | "link_existing";
  matrix_alias?: string | null;
}

export interface CreateChatRoomResponse {
  room: ChatRoom;
  message: string;
  matrix_error?: string | null;
  matrix_warning?: string | null;
}

export interface UpdateChatRoomRequest {
  name?: string | null;
  lead_agent_id?: string | null;
  agent_ids?: string[] | null;
  agent_roles?: Record<string, string> | null;
  sessions?: Record<string, SessionInfo> | null;
  layout?: string | null;
  matrix_room_id?: string | null;
  matrix_alias?: string | null;
}

export interface CreateTaskRequest {
  subject: string;
  description?: string | null;
  owner?: string | null;
  priority?: string;
  blocked_by?: string[];
  auto_mode?: boolean;
  max_retries?: number;
  source_session_id?: string | null;
  source_message_id?: string | null;
}

export interface UpdateTaskRequest {
  status?: string | null;
  owner?: string | null;
  description?: string | null;
  auto_mode?: boolean | null;
  max_retries?: number | null;
  progress?: number | null;
}

export interface CancelTaskRequest {
  reason?: string | null;
  cancelled_by?: string | null;
}

export interface RetryTaskRequest {
  reset_owner?: boolean;
}

export interface SetAutoModeRequest {
  auto_mode: boolean;
}

// Batch operation types
export interface BatchTaskOperationRequest {
  task_ids: string[];
  operation: "cancel" | "delete" | "assign" | "set_status" | "set_priority";
  reason?: string | null;  // For cancel
  owner?: string | null;  // For assign
  status?: string | null;  // For set_status
  priority?: string | null;  // For set_priority
}

export interface BatchOperationResult {
  success_count: number;
  failed_count: number;
  failed_tasks: Array<{ task_id: string; reason: string }>;
}

// Task log entry
export interface TaskLogEntryRequest {
  event: string;
  details?: string | null;
}

export interface ChatRoomListResponse {
  agents: ChatRoom[];
}

// Matrix config for iframe integration
export interface MatrixConfig {
  enabled: boolean;
  homeserver: string;
  user_id: string;
  access_token: string;
}
