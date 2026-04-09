import { useEffect, useRef, useState, useCallback } from "react";
import * as Matrix from "matrix-js-sdk";
import { useTranslation } from "react-i18next";
import type { MatrixConfig } from "@/api/types/chatroom";
import "./MatrixChat.css";

interface MatrixChatProps {
  matrixRoomId: string;
  matrixConfig: MatrixConfig;
}

interface MatrixMessage {
  id: string;
  sender: string;
  msgtype: "m.text" | "m.image" | "m.file" | "m.video" | "m.audio" | string;
  content: string;
  formattedBody?: string;  // HTML formatted content
  mediaUrl?: string | null;  // HTTP URL for media (images, files, etc.)
  downloadUrl?: string | null;  // Download URL for files/images
  mediaInfo?: {
    width?: number;
    height?: number;
    mimetype?: string;
    size?: number;
  };
  timestamp: number;
  isOwn: boolean;
}

/** Escape HTML for safe display when no formatted_body is available */
function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

export function MatrixChat({ matrixRoomId, matrixConfig }: MatrixChatProps) {
  const { t } = useTranslation();
  const clientRef = useRef<Matrix.MatrixClient | null>(null);
  const timelineRef = useRef<HTMLDivElement>(null);
  const timelineObjRef = useRef<Matrix.EventTimeline | null>(null);
  const scrollHeightBeforePaginateRef = useRef<number>(0);
  const [messages, setMessages] = useState<MatrixMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [canLoadMore, setCanLoadMore] = useState(true);  // Assume can load more by default
  const [error, setError] = useState<string | null>(null);
  const [roomName, setRoomName] = useState<string>("Matrix Room");
  const [previewImage, setPreviewImage] = useState<{
    url: string;
    name: string;
    downloadUrl?: string | null;
  } | null>(null);

  // Get display name helper
  const getDisplayName = useCallback((sender: string) => {
    if (clientRef.current) {
      const room = clientRef.current.getRoom(matrixRoomId);
      if (room) {
        const member = room.getMember(sender);
        return member?.name || sender;
      }
    }
    return sender;
  }, [matrixRoomId]);

  // Convert events to messages
  const eventsToMessages = useCallback((events: Matrix.MatrixEvent[]): MatrixMessage[] => {
    const result: MatrixMessage[] = [];
    for (const event of events) {
      if (event.getType() === "m.room.message") {
        const content = event.getContent();
        const msgtype = content.msgtype as string;

        const baseMessage: MatrixMessage = {
          id: event.getId() || "",
          sender: event.getSender() || "",
          msgtype: msgtype,
          content: content.body as string || "",
          timestamp: event.getTs(),
          isOwn: event.getSender() === matrixConfig.user_id,
        };

        // Handle text messages
        if (msgtype === "m.text") {
          baseMessage.formattedBody = content.formatted_body as string | undefined;
        }

        // Handle image messages
        if (msgtype === "m.image") {
          const mxcUrl = content.url as string;
          if (mxcUrl && clientRef.current) {
            // Parse MXC URL: mxc://server/mediaId
            const mxcMatch = mxcUrl.match(/^mxc:\/\/([^/]+)\/(.+)$/);
            if (mxcMatch) {
              const serverName = mxcMatch[1];
              const mediaId = mxcMatch[2];
              // Construct thumbnail URL with access token
              // Use v1 media endpoint (authenticated)
              const baseUrl = clientRef.current.baseUrl;
              const accessToken = clientRef.current.getAccessToken();
              // Thumbnail URL for display
              baseMessage.mediaUrl = `${baseUrl}/_matrix/client/v1/media/thumbnail/${serverName}/${mediaId}?width=300&height=200&method=scale&access_token=${accessToken}`;
              // Download URL for full image
              baseMessage.downloadUrl = `${baseUrl}/_matrix/client/v1/media/download/${serverName}/${mediaId}?allow_redirect=true&access_token=${accessToken}`;
              console.log("[MatrixChat] Image URL constructed:", baseMessage.mediaUrl);
            } else {
              console.warn("[MatrixChat] Invalid MXC URL format:", mxcUrl);
            }
          }
          if (content.info) {
            baseMessage.mediaInfo = {
              width: content.info.w as number | undefined,
              height: content.info.h as number | undefined,
              mimetype: content.info.mimetype as string | undefined,
              size: content.info.size as number | undefined,
            };
          }
        }

        // Handle file messages
        if (msgtype === "m.file") {
          const mxcUrl = content.url as string;
          if (mxcUrl && clientRef.current) {
            const mxcMatch = mxcUrl.match(/^mxc:\/\/([^/]+)\/(.+)$/);
            if (mxcMatch) {
              const serverName = mxcMatch[1];
              const mediaId = mxcMatch[2];
              const baseUrl = clientRef.current.baseUrl;
              const accessToken = clientRef.current.getAccessToken();
              baseMessage.mediaUrl = `${baseUrl}/_matrix/client/v1/media/download/${serverName}/${mediaId}?allow_redirect=true&access_token=${accessToken}`;
              baseMessage.downloadUrl = baseMessage.mediaUrl;
              console.log("[MatrixChat] File URL constructed:", baseMessage.mediaUrl);
            }
          }
          if (content.info) {
            baseMessage.mediaInfo = {
              mimetype: content.info.mimetype as string | undefined,
              size: content.info.size as number | undefined,
            };
          }
        }

        result.push(baseMessage);
      }
    }
    return result;
  }, [matrixConfig.user_id]);

  // Load more history (paginate backwards)
  const loadMoreHistory = useCallback(async () => {
    if (!clientRef.current || !timelineObjRef.current || loadingHistory || !canLoadMore) {
      return;
    }

    // Store current scroll height to maintain position after loading
    if (timelineRef.current) {
      scrollHeightBeforePaginateRef.current = timelineRef.current.scrollHeight;
    }

    setLoadingHistory(true);
    console.log("[MatrixChat] Loading more history...");

    try {
      // Paginate backwards (load older messages)
      const hasMore = await clientRef.current.paginateEventTimeline(timelineObjRef.current, {
        backwards: true,
        limit: 50,
      });

      console.log("[MatrixChat] Pagination result, hasMore:", hasMore);
      setCanLoadMore(hasMore);

      if (hasMore) {
        // Get all events from timeline (including newly loaded)
        const events = timelineObjRef.current.getEvents();
        const newMessages = eventsToMessages(events);
        setMessages(newMessages);
      }
    } catch (err) {
      console.error("[MatrixChat] Pagination error:", err);
    } finally {
      setLoadingHistory(false);
    }
  }, [loadingHistory, canLoadMore, eventsToMessages]);

  // Handle scroll to load more history
  const handleScroll = useCallback(() => {
    if (!timelineRef.current || loadingHistory || !canLoadMore) return;

    // When scrolled near top (within 200px), load more history
    if (timelineRef.current.scrollTop < 200) {
      loadMoreHistory();
    }
  }, [loadingHistory, canLoadMore, loadMoreHistory]);

  // Initialize Matrix client
  useEffect(() => {
    const initClient = async () => {
      try {
        setLoading(true);
        setError(null);

        console.log("[MatrixChat] Config:", {
          homeserver: matrixConfig.homeserver,
          user_id: matrixConfig.user_id,
          has_token: !!matrixConfig.access_token,
        });

        // Validate homeserver URL
        if (!matrixConfig.homeserver || matrixConfig.homeserver.trim() === "") {
          console.error("[MatrixChat] No homeserver configured");
          setError(t("chatroom.matrixNoHomeserver"));
          setLoading(false);
          return;
        }

        // Ensure homeserver has proper protocol
        let homeserverUrl = matrixConfig.homeserver.trim();
        if (!homeserverUrl.startsWith("http://") && !homeserverUrl.startsWith("https://")) {
          homeserverUrl = `https://${homeserverUrl}`;
        }

        // Validate URL is parseable
        try {
          const parsedUrl = new URL(homeserverUrl);
          console.log("[MatrixChat] Valid homeserver URL:", parsedUrl.href);
        } catch (urlError) {
          console.error("[MatrixChat] Invalid URL:", homeserverUrl, urlError);
          setError(t("chatroom.matrixInvalidHomeserver"));
          setLoading(false);
          return;
        }

        // Check for valid user_id and access_token
        if (!matrixConfig.user_id || !matrixConfig.access_token) {
          console.error("[MatrixChat] Missing user_id or access_token");
          setError(t("chatroom.matrixInvalidHomeserver"));
          setLoading(false);
          return;
        }

        // Create client with access token - using ICreateClientOptions
        const client = Matrix.createClient({
          baseUrl: homeserverUrl,
          userId: matrixConfig.user_id,
          accessToken: matrixConfig.access_token,
        });

        clientRef.current = client;

        // Start client with smaller initial sync limit for faster load
        await client.startClient({ initialSyncLimit: 30 });

        // Wait for initial sync
        await new Promise<void>((resolve) => {
          client.once(Matrix.ClientEvent.Sync, (state) => {
            if (state === "PREPARED") {
              resolve();
            }
          });
        });

        setConnected(true);
        console.log("[MatrixChat] Connected, looking for room:", matrixRoomId);

        // Get room
        const room = client.getRoom(matrixRoomId);
        console.log("[MatrixChat] Room found:", room ? room.name : "NOT FOUND");
        if (room) {
          setRoomName(room.name || "Matrix Room");

          // Get timeline for pagination
          const timeline = room.getLiveTimeline();
          timelineObjRef.current = timeline;

          // Load initial messages
          const events = timeline.getEvents();
          console.log("[MatrixChat] Initial timeline events:", events.length);
          const loadedMessages = eventsToMessages(events);
          setMessages(loadedMessages);
          console.log("[MatrixChat] Loaded messages:", loadedMessages.length);

          // Check timeline state to see if we can back-paginate
          // If we're not at the start of the timeline, there's more history
          const timelineState = timeline.getState(Matrix.EventTimeline.BACKWARDS);
          console.log("[MatrixChat] Timeline backwards state:", timelineState);
          // null state means we're at the end/start of that direction
          setCanLoadMore(timelineState !== null);
        }

        // Listen for new messages
        client.on(Matrix.RoomEvent.Timeline, (event: Matrix.MatrixEvent, room: Matrix.Room | undefined) => {
          console.log("[MatrixChat] Timeline event:", event.getType(), event.getId());
          if (room && room.roomId === matrixRoomId && event.getType() === "m.room.message") {
            const content = event.getContent();
            console.log("[MatrixChat] Message content:", {
              msgtype: content.msgtype,
              body: content.body?.substring(0, 50),
              url: content.url,
            });
            // Use eventsToMessages to handle all message types
            const newMessages = eventsToMessages([event]);
            if (newMessages.length > 0) {
              setMessages((prev) => [...prev, ...newMessages]);
            }
          }
        });

        setLoading(false);
      } catch (err) {
        console.error("Matrix client init error:", err);
        setError(err instanceof Error ? err.message : "Failed to connect to Matrix");
        setLoading(false);
      }
    };

    initClient();

    // Cleanup
    return () => {
      if (clientRef.current) {
        clientRef.current.stopClient();
        clientRef.current = null;
      }
    };
  }, [matrixConfig, matrixRoomId, t, eventsToMessages]);

  // Scroll to bottom on initial load
  useEffect(() => {
    if (!loading && timelineRef.current && messages.length > 0) {
      // Only scroll to bottom on initial load, not on pagination
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [loading]);

  // Maintain scroll position after loading history
  useEffect(() => {
    if (!loadingHistory && timelineRef.current && scrollHeightBeforePaginateRef.current > 0) {
      // Calculate how much height was added and adjust scroll
      const newScrollHeight = timelineRef.current.scrollHeight;
      const heightAdded = newScrollHeight - scrollHeightBeforePaginateRef.current;
      timelineRef.current.scrollTop = heightAdded;
      scrollHeightBeforePaginateRef.current = 0;
    }
  }, [loadingHistory]);

  // Send message
  const sendMessage = useCallback(async () => {
    if (!inputText.trim() || !clientRef.current || !connected) return;

    try {
      await clientRef.current.sendEvent(
        matrixRoomId,
        Matrix.EventType.RoomMessage,
        {
          msgtype: Matrix.MsgType.Text,
          body: inputText.trim(),
        }
      );
      setInputText("");
    } catch (err) {
      console.error("Failed to send Matrix message:", err);
    }
  }, [inputText, matrixRoomId, connected]);

  // Format timestamp - show date only if > 2 hours ago or crossed day
  const formatTime = (ts: number) => {
    const date = new Date(ts);
    const now = new Date();

    // Check if crossed day
    const isDifferentDay = date.getFullYear() !== now.getFullYear()
      || date.getMonth() !== now.getMonth()
      || date.getDate() !== now.getDate();

    // Check if within 2 hours
    const diffMs = now.getTime() - date.getTime();
    const isWithinTwoHours = diffMs >= 0 && diffMs < 2 * 60 * 60 * 1000;

    const timeStr = date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    });

    // Only show time if within 2 hours and same day
    if (isWithinTwoHours && !isDifferentDay) {
      return timeStr;
    }

    const dateStr = date.toLocaleDateString([], {
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    });

    return `${dateStr} ${timeStr}`;
  };

  // Download file helper
  const downloadFile = useCallback(async (url: string, fileName: string) => {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("Failed to download file:", err);
    }
  }, []);

  // Render message content based on type
  const renderMessageContent = (msg: MatrixMessage) => {
    if (msg.msgtype === "m.image" && msg.mediaUrl) {
      const fileName = msg.content || "image";
      const fileSize = msg.mediaInfo?.size ? `${(msg.mediaInfo.size / 1024).toFixed(1)} KB` : "";
      const fullUrl = msg.downloadUrl || msg.mediaUrl;
      return (
        <div className="matrix-chat__message-image-wrapper">
          <img
            src={msg.mediaUrl}
            alt={msg.content}
            className="matrix-chat__message-image"
            onClick={() => fullUrl && setPreviewImage({
              url: fullUrl,
              name: fileName,
              downloadUrl: msg.downloadUrl,
            })}
          />
          <div className="matrix-chat__message-image-actions">
            <button
              className="matrix-chat__image-action-btn"
              onClick={() => fullUrl && setPreviewImage({
                url: fullUrl,
                name: fileName,
                downloadUrl: msg.downloadUrl,
              })}
              title={t("chatroom.imageZoom")}
            >
              🔍
            </button>
            {msg.downloadUrl && (
              <button
                className="matrix-chat__image-action-btn"
                onClick={() => downloadFile(msg.downloadUrl!, fileName)}
                title={t("chatroom.imageDownload")}
              >
                ⬇️
              </button>
            )}
          </div>
          {fileSize && <span className="matrix-chat__image-size">{fileSize}</span>}
        </div>
      );
    }

    if (msg.msgtype === "m.file" && msg.mediaUrl) {
      const fileName = msg.content || "File";
      const fileSize = msg.mediaInfo?.size ? `${(msg.mediaInfo.size / 1024).toFixed(1)} KB` : "";
      return (
        <div className="matrix-chat__message-file">
          <button
            className="matrix-chat__file-link"
            onClick={() => downloadFile(msg.mediaUrl!, fileName)}
          >
            📎 {fileName} {fileSize && <span className="matrix-chat__file-size">({fileSize})</span>}
          </button>
        </div>
      );
    }

    // Default: render text content (with HTML if available)
    return (
      <div
        className="matrix-chat__message-content"
        dangerouslySetInnerHTML={{
          __html: msg.formattedBody || escapeHtml(msg.content)
        }}
      />
    );
  };

  if (loading) {
    return (
      <div className="matrix-chat matrix-chat--loading">
        <span>{t("common.loading")}</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="matrix-chat matrix-chat--error">
        <span className="matrix-chat__error-text">{error}</span>
        <span className="matrix-chat__error-hint">{t("chatroom.matrixConnectionFailed")}</span>
      </div>
    );
  }

  return (
    <div className="matrix-chat">
      {/* Header */}
      <div className="matrix-chat__header">
        <span className="matrix-chat__room-name">{roomName}</span>
        <span className={`matrix-chat__status ${connected ? "connected" : "disconnected"}`}>
          {connected ? t("chatroom.matrixConnected") : t("chatroom.matrixDisconnected")}
        </span>
      </div>

      {/* Timeline */}
      <div ref={timelineRef} className="matrix-chat__timeline" onScroll={handleScroll}>
        {/* Loading history indicator */}
        {loadingHistory && (
          <div className="matrix-chat__loading-history">
            <div className="matrix-chat__loading-spinner"></div>
            <span className="matrix-chat__loading-text">{t("chatroom.loadingHistory")}</span>
          </div>
        )}
        {/* Load more hint */}
        {!loadingHistory && canLoadMore && messages.length > 0 && (
          <div className="matrix-chat__load-more-hint">
            <span className="matrix-chat__load-more-icon">↑</span>
            <span>{t("chatroom.scrollUpForMore")}</span>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`matrix-chat__message ${msg.isOwn ? "own" : "other"}`}>
            <div className="matrix-chat__message-bubble">
              <div className="matrix-chat__message-header">
                <span className="matrix-chat__message-sender">
                  {getDisplayName(msg.sender)}
                </span>
                <span className="matrix-chat__message-time">
                  {formatTime(msg.timestamp)}
                </span>
              </div>
              {renderMessageContent(msg)}
            </div>
          </div>
        ))}
        {messages.length === 0 && (
          <div className="matrix-chat__empty">
            {t("chatroom.matrixNoMessages")}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="matrix-chat__input-area">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder={t("chatroom.messageInputPlaceholder")}
          disabled={!connected}
          className="matrix-chat__input"
        />
        <button
          onClick={sendMessage}
          disabled={!connected || !inputText.trim()}
          className={`matrix-chat__send-btn ${connected && inputText.trim() ? "active" : ""}`}
        >
          {t("chatroom.send")}
        </button>
      </div>

      {/* Image Preview Modal */}
      {previewImage && (
        <div
          className="matrix-chat__preview-modal"
          onClick={() => setPreviewImage(null)}
        >
          <div className="matrix-chat__preview-content">
            <img
              src={previewImage.url}
              alt={previewImage.name}
              className="matrix-chat__preview-image"
            />
            <div className="matrix-chat__preview-actions">
              <span className="matrix-chat__preview-name">{previewImage.name}</span>
              <div className="matrix-chat__preview-buttons">
                {previewImage.downloadUrl && (
                  <button
                    className="matrix-chat__preview-btn"
                    onClick={() => downloadFile(previewImage.downloadUrl!, previewImage.name)}
                  >
                    ⬇️ {t("chatroom.imageDownload")}
                  </button>
                )}
                <button
                  className="matrix-chat__preview-btn matrix-chat__preview-btn--close"
                  onClick={() => setPreviewImage(null)}
                >
                  ✕ {t("common.close")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}