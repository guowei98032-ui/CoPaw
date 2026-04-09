import { useMemo, useRef, useEffect, useState, useCallback } from "react";
import { AgentScopeRuntimeWebUI, IAgentScopeRuntimeWebUIOptions, type IAgentScopeRuntimeWebUIRef, type IAgentScopeRuntimeWebUISession, type IAgentScopeRuntimeWebUISessionAPI, type IAgentScopeRuntimeWebUIMessage } from "@agentscope-ai/chat";
import { useTheme } from "@/contexts/ThemeContext";
import { useTranslation } from "react-i18next";
import { getApiUrl } from "@/api/config";
import { buildAuthHeaders } from "@/api/authHeaders";
import { chatApi } from "@/api/modules/chat";
import { SparkCopyLine } from "@agentscope-ai/icons";
import { extractCopyableText } from "@/pages/Chat/utils";
import type { CopyableResponse } from "@/pages/Chat/utils";
import type { Message } from "@/api/types";
import { getDefaultConfig } from "@/pages/Chat/OptionsPanel/defaultConfig";

/** Push message from backend */
interface PushMessage {
  id: string;
  text: string;
  sticky?: boolean;
}

/** Track seen push message IDs to avoid duplicates */
const seenPushMessageIds = new Set<string>();

/** Extended session with additional fields from backend */
interface ExtendedChatroomSession extends IAgentScopeRuntimeWebUISession {
  sessionId?: string;
  userId?: string;
  channel?: string;
  meta?: Record<string, unknown>;
}

/** Custom window interface for current session tracking */
interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

interface AgentChatProps {
  roomId: string;
  agentId: string;
  matrixRoomId?: string | null;
}

const DEFAULT_USER_ID = "default";
const DEFAULT_CHANNEL = "console";
const ROLE_USER = "user";
const ROLE_ASSISTANT = "assistant";
const CARD_RESPONSE = "AgentScopeRuntimeResponseCard";

/** Generate unique ID */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/** Convert content to request parts format */
function contentToRequestParts(content: unknown): Array<Record<string, unknown>> {
  if (typeof content === "string") {
    return [{ type: "text", text: content, status: "created" }];
  }
  if (!Array.isArray(content)) {
    return [{ type: "text", text: String(content || ""), status: "created" }];
  }
  const parts = (content as Array<{ type: string; text?: string }>).map((c) => ({
    ...c,
    status: "created",
  }));
  if (parts.length === 0) {
    return [{ type: "text", text: "", status: "created" }];
  }
  return parts;
}

/** Build user card from message */
function buildUserCard(msg: Message): IAgentScopeRuntimeWebUIMessage {
  const contentParts = contentToRequestParts(msg.content);
  return {
    id: (msg.id as string) || generateId(),
    role: "user",
    cards: [
      {
        code: "AgentScopeRuntimeRequestCard",
        data: {
          input: [
            {
              role: "user",
              type: "message",
              content: contentParts,
            },
          ],
        },
      },
    ],
  };
}

/** Build response card from output messages */
const buildResponseCard = (
  outputMessages: Message[],
): IAgentScopeRuntimeWebUIMessage => {
  const now = Math.floor(Date.now() / 1000);
  const maxSeq = outputMessages.reduce(
    (max, m) => Math.max(max, (m.sequence_number as number) || 0),
    0,
  );

  // Normalize content: if it's an object with _content array, extract it
  const normalizeContent = (content: unknown): unknown => {
    if (typeof content === "string") return content;
    if (!content || typeof content !== "object") return content;
    // Check if it's a Message-like object with _content array
    const obj = content as Record<string, unknown>;
    if (Array.isArray(obj._content)) {
      return obj._content;
    }
    // If it's already an array, return as-is
    if (Array.isArray(obj)) return obj;
    return content;
  };

  return {
    id: generateId(),
    role: ROLE_ASSISTANT,
    cards: [
      {
        code: CARD_RESPONSE,
        data: {
          id: `response_${generateId()}`,
          output: outputMessages.map((msg) => ({
            ...msg,
            content: normalizeContent(msg.content),
            metadata: null,
          })),
          object: "response",
          status: "completed",
          created_at: now,
          sequence_number: maxSeq + 1,
          error: null,
          completed_at: now,
          usage: null,
        },
      },
    ],
    msgStatus: "finished",
  };
};

/** Convert flat backend messages to card format */
const convertMessages = (
  messages: Message[],
): IAgentScopeRuntimeWebUIMessage[] => {
  const result: IAgentScopeRuntimeWebUIMessage[] = [];
  let i = 0;

  while (i < messages.length) {
    if (messages[i].role === ROLE_USER) {
      result.push(buildUserCard(messages[i++]));
    } else {
      const outputMsgs: Message[] = [];
      while (i < messages.length && messages[i].role !== ROLE_USER) {
        outputMsgs.push({
          ...messages[i],
          role: messages[i].type === "plugin_call_output" && messages[i].role === "system"
            ? "tool"
            : messages[i].role,
        });
        i++;
      }
      if (outputMsgs.length) result.push(buildResponseCard(outputMsgs));
    }
  }

  return result;
};

/**
 * Build a response card from push message text.
 * This creates an assistant message from backend polling.
 */
const buildPushMessageCard = (text: string): IAgentScopeRuntimeWebUIMessage => {
  const now = Math.floor(Date.now() / 1000);
  return {
    id: generateId(),
    role: ROLE_ASSISTANT,
    cards: [
      {
        code: CARD_RESPONSE,
        data: {
          id: `push_${generateId()}`,
          output: [
            {
              id: generateId(),
              type: "message",
              role: "assistant",
              content: [{ type: "text", text, status: "created" }],
              created_at: now,
              object: "message",
              status: "completed",
            },
          ],
          object: "response",
          status: "completed",
          created_at: now,
          completed_at: now,
        },
      },
    ],
    msgStatus: "finished",
  };
};

/**
 * Append push messages to chatroom history cache.
 * Returns true if any messages were added.
 */
const appendPushMessagesToCache = (
  historyKey: string,
  messages: PushMessage[]
): boolean => {
  // Create cache entry if it doesn't exist
  let cached = chatroomHistoryCache.get(historyKey);
  if (!cached) {
    cached = {
      chatId: null,
      messages: [],
      lastLoaded: Date.now(),
    };
    chatroomHistoryCache.set(historyKey, cached);
    console.log("[AgentChat] Created new cache entry for %s", historyKey);
  }

  let added = false;
  for (const msg of messages) {
    // Use historyKey + msg.id as unique key to allow same message in different sessions
    const uniqueKey = `${historyKey}:${msg.id}`;
    if (seenPushMessageIds.has(uniqueKey)) continue;
    seenPushMessageIds.add(uniqueKey);

    // Build response card and append to cache
    const card = buildPushMessageCard(msg.text);
    cached.messages.push(card);
    added = true;
  }

  if (added) {
    cached.lastLoaded = Date.now();
    console.log(
      "[AgentChat] Added %d push messages to cache %s, total: %d",
      messages.length,
      historyKey,
      cached.messages.length
    );
  }
  return added;
};

/**
 * Hook for polling push messages from backend.
 * Appends new messages to chatroom history cache.
 */
const usePushMessagesPolling = (
  sessionId: string,
  historyKey: string,
  onNewMessages: () => void,
  enabled: boolean = true
) => {
  useEffect(() => {
    if (!enabled || !sessionId) return;

    const pollMessages = async () => {
      try {
        const response = await fetch(
          getApiUrl(`/console/push-messages?session_id=${encodeURIComponent(sessionId)}`),
          {
            method: "GET",
            headers: buildAuthHeaders(),
          }
        );

        if (!response.ok) return;

        const data = await response.json();
        const messages: PushMessage[] = data.messages || [];

        if (messages.length > 0) {
          const added = appendPushMessagesToCache(historyKey, messages);
          if (added) {
            onNewMessages();
          }
        }
      } catch (error) {
        console.warn("[AgentChat] Push messages poll error:", error);
      }
    };

    // Initial poll
    pollMessages();

    // Poll every 3 seconds
    const interval = setInterval(pollMessages, 3000);

    return () => clearInterval(interval);
  }, [sessionId, historyKey, onNewMessages, enabled]);
};

/**
 * Global cache for chatroom chat history, keyed by roomId-agentId.
 * This allows each agent to have its own chat history in the chatroom.
 */
const chatroomHistoryCache = new Map<string, {
  chatId: string | null;
  messages: IAgentScopeRuntimeWebUIMessage[];
  lastLoaded: number;
}>();

/**
 * Singleton sessionApi class for chatroom chat.
 * Uses shared sessionId (chatroom-{roomId}) for all agents to share chat history.
 */
class ChatroomSessionApi implements IAgentScopeRuntimeWebUISessionAPI {
  private roomId: string;
  private agentId: string;
  private sessionId: string;
  private session: ExtendedChatroomSession | null = null;
  private isLoading = false;

  constructor(roomId: string, agentId: string, sessionId: string) {
    this.roomId = roomId;
    this.agentId = agentId;
    this.sessionId = sessionId;

    // Load session from cache immediately on construction
    const cachedHistory = chatroomHistoryCache.get(sessionId);
    if (cachedHistory && cachedHistory.messages.length > 0) {
      this.session = {
        id: cachedHistory.chatId || sessionId,
        name: `Chat with ${agentId}`,
        sessionId: sessionId,
        userId: DEFAULT_USER_ID,
        channel: DEFAULT_CHANNEL,
        messages: cachedHistory.messages,
        meta: { roomId: roomId, agentId: agentId },
      };
      console.log(
        "[AgentChat] constructor: loaded %d messages from cache for %s",
        cachedHistory.messages.length,
        sessionId
      );
    }
  }

  /** Update agentId and sessionId (called when switching agents) */
  updateAgentId(agentId: string, sessionId: string) {
    // Update IDs first
    const prevAgentId = this.agentId;
    const prevSessionId = this.sessionId;
    this.agentId = agentId;
    this.sessionId = sessionId;

    // If agent changed, load session from the NEW cache immediately
    if (prevAgentId !== agentId || prevSessionId !== sessionId) {
      const cachedHistory = chatroomHistoryCache.get(sessionId);
      if (cachedHistory && cachedHistory.messages.length > 0) {
        this.session = {
          id: cachedHistory.chatId || sessionId,
          name: `Chat with ${agentId}`,
          sessionId: sessionId,
          userId: DEFAULT_USER_ID,
          channel: DEFAULT_CHANNEL,
          messages: cachedHistory.messages,
          meta: { roomId: this.roomId, agentId: agentId },
        };
        console.log(
          "[AgentChat] updateAgentId: loaded %d messages from cache for %s",
          cachedHistory.messages.length,
          sessionId
        );
      } else {
        // No cache for this agent - clear session
        this.session = null;
        this.isLoading = false;
      }
    }
  }

  private updateWindowVariables(): void {
    const cw = window as unknown as CustomWindow;
    cw.currentSessionId = this.sessionId;
    cw.currentUserId = DEFAULT_USER_ID;
    cw.currentChannel = DEFAULT_CHANNEL;
  }

  private createEmptySession(): ExtendedChatroomSession {
    this.updateWindowVariables();
    return {
      id: this.sessionId,
      name: `Chat with ${this.agentId}`,
      sessionId: this.sessionId,
      userId: DEFAULT_USER_ID,
      channel: DEFAULT_CHANNEL,
      messages: [],
      meta: { roomId: this.roomId, agentId: this.agentId },
    };
  }

  async getSessionList() {
    // Use sessionId (includes agentId) as history key for per-agent history
    const historyKey = this.sessionId;
    const cachedHistory = chatroomHistoryCache.get(historyKey);

    console.log(
      "[AgentChat] getSessionList: sessionId=%s, cachedMessages=%d",
      historyKey,
      cachedHistory?.messages?.length || 0
    );

    // Return cached session if it exists with messages loaded
    if (cachedHistory && cachedHistory.messages.length > 0) {
      const session: ExtendedChatroomSession = {
        id: cachedHistory.chatId || this.sessionId,
        name: `Chat with ${this.agentId}`,
        sessionId: this.sessionId,
        userId: DEFAULT_USER_ID,
        channel: DEFAULT_CHANNEL,
        messages: cachedHistory.messages,
        meta: { roomId: this.roomId, agentId: this.agentId },
      };
      this.session = session;
      return [session];
    }

    // Return session without messages - let getSession load them
    // This triggers the component to call getSession to fetch history
    const session: ExtendedChatroomSession = {
      id: this.sessionId,
      name: `Chat with ${this.agentId}`,
      sessionId: this.sessionId,
      userId: DEFAULT_USER_ID,
      channel: DEFAULT_CHANNEL,
      messages: [], // Empty - getSession will load the actual messages
      meta: { roomId: this.roomId, agentId: this.agentId },
    };
    this.session = session;
    return [session];
  }

  async getSession(_id: string) {
    // Use sessionId (includes agentId) as history key for per-agent history
    const historyKey = this.sessionId;
    const cachedHistory = chatroomHistoryCache.get(historyKey);

    console.log(
      "[AgentChat] getSession: sessionId=%s, cachedMessages=%d, isLoading=%s",
      historyKey,
      cachedHistory?.messages?.length || 0,
      this.isLoading
    );

    // Return cached session if we have messages in the per-agent cache
    if (cachedHistory && cachedHistory.messages.length > 0) {
      const session: ExtendedChatroomSession = {
        id: cachedHistory.chatId || this.sessionId,
        name: `Chat with ${this.agentId}`,
        sessionId: this.sessionId,
        userId: DEFAULT_USER_ID,
        channel: DEFAULT_CHANNEL,
        messages: cachedHistory.messages,
        meta: { roomId: this.roomId, agentId: this.agentId },
      };
      this.session = session;
      this.updateWindowVariables();
      return session;
    }

    // If already loading, return cached or empty session
    if (this.isLoading) {
      console.log("[AgentChat] getSession: already loading, returning cached/empty");
      return this.session ?? this.createEmptySession();
    }

    this.isLoading = true;

    try {
      // Always fetch from backend to get the latest history
      const agentHeaders = { "X-Agent-Id": this.agentId };
      const chats = await chatApi.listChats(undefined, agentHeaders);
      const matchingChat = chats.find(
        (chat) => chat.session_id === this.sessionId
      );

      console.log(
        "[AgentChat] getSession: found %d chats, matchingChat=%s",
        chats.length,
        matchingChat ? matchingChat.id : "none"
      );

      if (!matchingChat) {
        // Create empty cache entry so push messages can be appended later
        chatroomHistoryCache.set(historyKey, {
          chatId: null,
          messages: [],
          lastLoaded: Date.now(),
        });
        console.log("[AgentChat] getSession: no chat found, created empty cache for %s", historyKey);
        this.isLoading = false;
        return this.createEmptySession();
      }

      const chatHistory = await chatApi.getChat(matchingChat.id, agentHeaders);
      const messages = convertMessages(chatHistory.messages || []);

      console.log(
        "[AgentChat] getSession: loaded %d messages from backend",
        messages.length
      );

      // Cache the messages for this agent in the chatroom
      chatroomHistoryCache.set(historyKey, {
        chatId: matchingChat.id,
        messages,
        lastLoaded: Date.now(),
      });

      const session: ExtendedChatroomSession = {
        id: matchingChat.id,
        name: `Chat with ${this.agentId}`,
        sessionId: this.sessionId,
        userId: DEFAULT_USER_ID,
        channel: DEFAULT_CHANNEL,
        messages,
        meta: { roomId: this.roomId, agentId: this.agentId },
      };
      this.session = session;
      this.isLoading = false;
      this.updateWindowVariables();
      return session;
    } catch (error) {
      console.warn("[AgentChat] getSession failed:", error);
      this.isLoading = false;
      return this.createEmptySession();
    }
  }

  async updateSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    if (this.session && session.id) {
      this.session = { ...this.session, ...session };
      return [this.session];
    }
    return [];
  }

  async createSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    session.id = this.sessionId;
    const newSession: ExtendedChatroomSession = {
      id: this.sessionId,
      name: `Chat with ${this.agentId}`,
      sessionId: this.sessionId,
      userId: DEFAULT_USER_ID,
      channel: DEFAULT_CHANNEL,
      messages: [],
      meta: { roomId: this.roomId, agentId: this.agentId },
    };
    this.session = newSession;
    this.updateWindowVariables();
    return [newSession];
  }

  async removeSession() {
    this.session = null;
    return [];
  }
}

// Global singleton cache keyed by sessionId to persist across agent switches
const sessionApiCache = new Map<string, ChatroomSessionApi>();

/**
 * Get or create a singleton sessionApi instance for a given sessionId.
 * This ensures session data persists when switching between agents.
 *
 * Note: Each agent in the chatroom has its own session and history.
 * The sessionId format is: chatroom-{roomId}-{agentId}
 */
const getChatroomSessionApi = (roomId: string, agentId: string): IAgentScopeRuntimeWebUISessionAPI => {
  // Use per-agent sessionId so each agent has its own history
  const sessionId = `chatroom-${roomId}-${agentId}`;

  let api = sessionApiCache.get(sessionId);
  if (!api) {
    api = new ChatroomSessionApi(roomId, agentId, sessionId);
    sessionApiCache.set(sessionId, api);
  } else {
    // Update both agentId and sessionId for the existing instance
    api.updateAgentId(agentId, sessionId);
  }
  return api;
};

export function AgentChat({ roomId, agentId, matrixRoomId }: AgentChatProps) {
  const { t } = useTranslation();
  const { isDark } = useTheme();
  const chatRef = useRef<IAgentScopeRuntimeWebUIRef>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // 为聊天室生成唯一的 session ID
  const sessionId = useMemo(() => `chatroom-${roomId}-${agentId}`, [roomId, agentId]);

  // 创建聊天室专用的 sessionApi (singleton pattern)
  const sessionApi = useMemo(() => getChatroomSessionApi(roomId, agentId), [roomId, agentId]);

  // Callback when new push messages arrive - triggers UI refresh
  const handleNewPushMessages = useCallback(() => {
    setRefreshKey((prev) => prev + 1);
  }, []);

  // Poll for push messages from backend (background agent execution)
  usePushMessagesPolling(
    sessionId,
    sessionId, // historyKey is same as sessionId
    handleNewPushMessages,
    true // enabled
  );

  // 自定义 fetch 函数，注入 Agent ID
  const customFetch = useMemo(() => {
    return async (data: {
      input?: Array<Record<string, unknown>>;
      biz_params?: Record<string, unknown>;
      signal?: AbortSignal;
    }): Promise<Response> => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...buildAuthHeaders(),
        "X-Agent-Id": agentId,
      };

      const { input = [], biz_params } = data;

      // Only send the last message (same as Chat page)
      const lastInput = input.slice(-1);

      const requestBody = {
        input: lastInput,
        session_id: sessionId,
        user_id: DEFAULT_USER_ID,
        channel: DEFAULT_CHANNEL,
        stream: true,
        // Pass room_id and matrix_room_id for forwarding to Matrix
        meta: {
          room_id: roomId,
          matrix_room_id: matrixRoomId || null,
        },
        ...biz_params,
      };

      return fetch(getApiUrl("/console/chat"), {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
        signal: data.signal,
      });
    };
  }, [agentId, sessionId, roomId, matrixRoomId]);

  // options 配置
  const options = useMemo(() => {
    const i18nConfig = getDefaultConfig(t);

    return {
      ...i18nConfig,
      theme: {
        ...i18nConfig.theme,
        darkMode: isDark,
      },
      welcome: {
        ...i18nConfig.welcome,
        nick: "CoPaw",
        avatar: "https://gw.alicdn.com/imgextra/i2/O1CN01pyXzjQ1EL1PuZMlSd_!!6000000000334-2-tps-288-288.png",
      },
      sender: {
        ...i18nConfig.sender,
        placeholder: t("chatroom.messageInputPlaceholder"),
        suggestions: [],
        attachments: false,
      },
      session: {
        multiple: false,
        hideBuiltInSessionList: true,
        api: sessionApi,
      },
      api: {
        ...i18nConfig.api,  // 继承 defaultConfig 中的 api 配置 (baseURL, token)
        fetch: customFetch,
        replaceMediaURL: (url: string) => url,
        cancel: () => {
          // Use customFetch to include X-Agent-Id header
          const headers: Record<string, string> = {
            "Content-Type": "application/json",
            ...buildAuthHeaders(),
            "X-Agent-Id": agentId,
          };
          fetch(getApiUrl("/console/chat/stop?chat_id=" + encodeURIComponent(sessionId)), {
            method: "POST",
            headers,
          }).catch((err) => {
            console.error("Failed to stop chat:", err);
          });
        },
        reconnect: async (data: { session_id: string; signal?: AbortSignal }) => {
          const headers: Record<string, string> = {
            "Content-Type": "application/json",
            ...buildAuthHeaders(),
            "X-Agent-Id": agentId,
          };

          return fetch(getApiUrl("/console/chat"), {
            method: "POST",
            headers,
            body: JSON.stringify({
              reconnect: true,
              session_id: sessionId,
              user_id: DEFAULT_USER_ID,
              channel: DEFAULT_CHANNEL,
            }),
            signal: data.signal,
          });
        },
      },
      actions: {
        list: [
          {
            icon: (
              <span title={t("common.copy")}>
                <SparkCopyLine />
              </span>
            ),
            onClick: ({ data }: { data: CopyableResponse }) => {
              const text = extractCopyableText(data);
              navigator.clipboard.writeText(text).catch(() => {});
            },
          },
        ],
        replace: true,
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [agentId, sessionId, isDark, t, customFetch]);

  // 强制刷新组件当 agentId 变化
  useEffect(() => {
    console.log(
      "[AgentChat] agentId changed to %s, incrementing refreshKey",
      agentId
    );
    setRefreshKey((prev) => prev + 1);
  }, [agentId]);

  // Debug: log cache state when sessionId changes
  useEffect(() => {
    const cached = chatroomHistoryCache.get(sessionId);
    console.log(
      "[AgentChat] sessionId=%s, cache exists=%s, cached messages=%d",
      sessionId,
      !!cached,
      cached?.messages?.length || 0
    );
  }, [sessionId]);

  // Always show AgentScopeRuntimeWebUI (Matrix chat is shown separately in Detail page)
  return (
    <div
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <AgentScopeRuntimeWebUI
        ref={chatRef}
        key={refreshKey}
        options={options}
      />
    </div>
  );
}
