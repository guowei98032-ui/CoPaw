import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, Tabs, Spin, Button, Space, Tag, Tooltip } from "antd";
import { ArrowLeftOutlined, SyncOutlined, CrownOutlined, ExpandOutlined, CompressOutlined } from "@ant-design/icons";
import { chatroomApi } from "@/api/modules/chatroom";
import type { ChatRoomDetail, MatrixConfig } from "@/api/types/chatroom";
import { TaskList } from "./components/TaskList";
import { RoomInfo } from "./components/RoomInfo";
import { AgentChat } from "./components/AgentChat";
import { MatrixChat } from "./components/MatrixChat";
import { useAgentStore } from "@/stores/agentStore";
import styles from "./index.module.less";

export default function ChatroomDetailPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<ChatRoomDetail | null>(null);
  const [matrixConfig, setMatrixConfig] = useState<MatrixConfig | null>(null);
  const { agents } = useAgentStore();
  const [leaderExpanded, setLeaderExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");

  const loadDetail = async () => {
    if (!roomId) return;
    setLoading(true);
    try {
      const data = await chatroomApi.getChatRoom(roomId);
      setDetail(data);
    } catch (error) {
      console.error("Failed to load chatroom detail:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [roomId]);

  // Auto-refresh tasks every 5 seconds when on tasks tab (silent, no loading state)
  useEffect(() => {
    if (!roomId || activeTab !== "tasks") return;

    const interval = setInterval(async () => {
      try {
        const data = await chatroomApi.getChatRoom(roomId);
        setDetail(data);
      } catch (error) {
        console.error("Failed to refresh tasks:", error);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [roomId, activeTab]);

  // Fetch Matrix config if chatroom has Matrix room
  useEffect(() => {
    if (detail?.matrix_room_id && detail.lead_agent_id) {
      chatroomApi.getMatrixConfig(detail.lead_agent_id)
        .then((config) => {
          if (config.enabled) {
            setMatrixConfig(config);
          } else {
            setMatrixConfig(null);
          }
        })
        .catch((err) => {
          console.warn("Failed to get Matrix config:", err);
          setMatrixConfig(null);
        });
    } else {
      setMatrixConfig(null);
    }
  }, [detail?.matrix_room_id, detail?.lead_agent_id]);

  // 获取 agent 名字
  const getAgentName = (agentId: string): string => {
    const agent = agents.find(a => a.id === agentId);
    return agent?.name || agentId;
  };

  // 分离 lead agent 和其他 agents
  const { leadAgentId, otherAgentIds } = useMemo(() => {
    if (!detail) return { leadAgentId: null, otherAgentIds: [] };
    const others = (detail.agent_ids || []).filter(id => id !== detail.lead_agent_id);
    return { leadAgentId: detail.lead_agent_id, otherAgentIds: others };
  }, [detail]);

  const toggleLeaderExpand = () => {
    setLeaderExpanded(!leaderExpanded);
  };

  if (loading) {
    return (
      <div className={styles.detailPage}>
        <div className={styles.loadingState}>
          <Spin size="large" tip="Loading chatroom..." />
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className={styles.detailPage}>
        <Card>
          <div className={styles.emptyState}>
            <h3>ChatRoom not found</h3>
            <Button onClick={() => navigate("/chatrooms")}>
              Back to ChatRooms
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const hasMatrix = detail.matrix_room_id && matrixConfig;
  const hasOtherAgents = otherAgentIds.length > 0;

  const tabItems = [
    {
      key: "chat",
      label: `Chat (${(leadAgentId ? 1 : 0) + otherAgentIds.length} Agents)`,
      children: (
        <div className={styles.chatContainer}>
          {/* 第一排：Leader + Matrix */}
          {leadAgentId && (
            <div className={styles.firstRowSection}>
              <div className={styles.firstRowHeader}>
                <span>Leader & Matrix</span>
              </div>
              <div className={`${styles.firstRow} ${leaderExpanded ? styles.leaderExpanded : ""}`}>
                <div className={styles.leaderSection}>
                  <div className={styles.agentChatWrapper}>
                    <div className={styles.agentChatHeader}>
                      <span className={styles.agentName}>
                        <CrownOutlined style={{ color: "#faad14", marginRight: 4 }} />
                        {getAgentName(leadAgentId)}
                      </span>
                      <Space>
                        <Tag color="gold">Lead</Tag>
                        <Tooltip title={leaderExpanded ? "恢复比例" : "放大 Leader"}>
                          <Button
                            type="text"
                            size="small"
                            icon={leaderExpanded ? <CompressOutlined /> : <ExpandOutlined />}
                            onClick={toggleLeaderExpand}
                          />
                        </Tooltip>
                      </Space>
                    </div>
                    <div className={styles.agentChatContent}>
                      <AgentChat
                        roomId={detail.id}
                        agentId={leadAgentId}
                        matrixRoomId={detail.matrix_room_id}
                      />
                    </div>
                  </div>
                </div>
                {hasMatrix && (
                  <div className={styles.matrixSection}>
                    <div className={styles.matrixPanel}>
                      <div className={styles.matrixPanelHeader}>
                        <span className={styles.matrixPanelTitle}>Matrix Room</span>
                      </div>
                      <div className={styles.matrixPanelContent}>
                        <MatrixChat
                          matrixRoomId={detail.matrix_room_id!}
                          matrixConfig={matrixConfig!}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 其他成员：每排3个 */}
          {hasOtherAgents && (
            <div className={styles.otherAgentsSection}>
              <div className={styles.otherAgentsHeader}>
                <span>Other Agents ({otherAgentIds.length})</span>
              </div>
              <div className={styles.otherAgentsGrid}>
                {otherAgentIds.map((agentId) => (
                  <div key={agentId} className={styles.agentChatWrapper}>
                    <div className={styles.agentChatHeader}>
                      <span className={styles.agentName}>
                        {getAgentName(agentId)}
                      </span>
                    </div>
                    <div className={styles.agentChatContent}>
                      <AgentChat
                        roomId={detail.id}
                        agentId={agentId}
                        matrixRoomId={detail.matrix_room_id}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ),
    },
    {
      key: "tasks",
      label: `Tasks (${detail.tasks?.length || 0})`,
      children: (
        <TaskList
          roomId={detail.id}
          tasks={detail.tasks || []}
          onRefresh={loadDetail}
        />
      ),
    },
    {
      key: "info",
      label: "Room Info",
      children: <RoomInfo room={detail} />,
    },
  ];

  return (
    <div className={styles.detailPage}>
      <div className={styles.headerBar}>
        <Space>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate("/chatrooms")}
          />
          <span className={styles.title}>{detail.name}</span>
        </Space>
        <Button icon={<SyncOutlined spin={loading} />} onClick={loadDetail}>
          Refresh
        </Button>
      </div>

      <Card className={styles.tabCard}>
        <Tabs
          items={tabItems}
          activeKey={activeTab}
          onChange={setActiveTab}
        />
      </Card>
    </div>
  );
}
