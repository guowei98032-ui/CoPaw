import { List, Switch, Tag, Space, Tooltip, Alert } from "antd";
import { useTranslation } from "react-i18next";
import { useAgents } from "@/hooks/useAgents";
import { CrownOutlined, UserOutlined } from "@ant-design/icons";
import type { AgentSummary } from "@/api/types/agents";

interface AgentSelectorProps {
  leadAgentId?: string;
  workerAgentIds: string[];
  onLeadAgentChange: (id?: string) => void;
  onWorkerAgentsChange: (ids: string[]) => void;
  matrixMode?: string;  // "none" | "create_new" | "link_existing"
}

export function AgentSelector({
  leadAgentId,
  workerAgentIds,
  onLeadAgentChange,
  onWorkerAgentsChange,
  matrixMode = "none",
}: AgentSelectorProps) {
  const { t } = useTranslation();
  const { agents, loading } = useAgents();

  const handleLeadAgentSelect = (agentId?: string) => {
    // If selecting as lead agent, remove from worker agents
    if (agentId && workerAgentIds.includes(agentId)) {
      onWorkerAgentsChange(workerAgentIds.filter((id) => id !== agentId));
    }
    onLeadAgentChange(agentId);
  };

  const handleWorkerAgentToggle = (agentId: string, checked: boolean) => {
    // If adding as worker agent, ensure it's not the current lead agent
    if (checked && agentId === leadAgentId) {
      onLeadAgentChange(undefined);
    }
    onWorkerAgentsChange(
      checked
        ? [...workerAgentIds, agentId]
        : workerAgentIds.filter((id) => id !== agentId)
    );
  };

  const isLeadAgent = (agent: AgentSummary) => agent.id === leadAgentId;
  const isWorkerAgent = (agent: AgentSummary) => workerAgentIds.includes(agent.id);

  // Filter agents based on Matrix mode
  const requireMatrix = matrixMode !== "none";
  const availableAgents = agents.filter((a) => {
    if (!a.enabled) return false;
    if (requireMatrix && !a.matrix_enabled) return false;
    return true;
  });

  // Agents without Matrix (for warning)
  const agentsWithoutMatrix = agents.filter((a) => a.enabled && !a.matrix_enabled);
  const showMatrixWarning = requireMatrix && agentsWithoutMatrix.length > 0;

  if (loading) {
    return <div style={{ textAlign: "center", padding: "20px" }}>Loading agents...</div>;
  }

  if (agents.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "20px", color: "#999" }}>
        <UserOutlined style={{ fontSize: 24, marginBottom: 8, display: "block" }} />
        {t("chatroom.noAgentsAvailable")}
      </div>
    );
  }

  if (requireMatrix && availableAgents.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "20px" }}>
        <Alert
          type="warning"
          message={t("chatroom.noMatrixAgentsTitle")}
          description={t("chatroom.noMatrixAgentsDesc")}
          showIcon
        />
      </div>
    );
  }

  return (
    <div style={{ border: "1px solid #f0f0f0", borderRadius: 8, padding: 16 }}>
      {/* Matrix warning */}
      {showMatrixWarning && (
        <Alert
          type="info"
          message={t("chatroom.matrixAgentsFilter", { count: agentsWithoutMatrix.length })}
          style={{ marginBottom: 16 }}
          showIcon
        />
      )}

      {/* Lead Agent Section */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontWeight: 600, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <CrownOutlined style={{ color: "#faad14" }} />
          {t("chatroom.leadAgent")}
          <Tooltip title={t("chatroom.leadAgentTooltip")}>
            <Tag color="gold">{t("chatroom.owner")}</Tag>
          </Tooltip>
        </div>
        <List
          dataSource={availableAgents}
          bordered
          size="small"
          locale={{ emptyText: t("chatroom.noEnabledAgents") }}
          renderItem={(agent) => (
            <List.Item
              style={{
                background: isLeadAgent(agent) ? "#fffbe6" : "transparent",
                borderColor: isLeadAgent(agent) ? "#ffe58f" : "#f0f0f0",
              }}
              actions={[
                <Switch
                  key="toggle"
                  size="small"
                  checked={isLeadAgent(agent)}
                  onChange={(checked) => handleLeadAgentSelect(checked ? agent.id : undefined)}
                  checkedChildren={t("chatroom.selected")}
                  unCheckedChildren={t("chatroom.select")}
                />,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <span>{agent.name || agent.id}</span>
                    {agent.matrix_enabled && <Tag color="green">Matrix</Tag>}
                  </Space>
                }
                description={
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <span style={{ color: "#666" }}>{agent.description || agent.id}</span>
                    <Space size="small">
                      <Tag>ID: {agent.id}</Tag>
                      {isWorkerAgent(agent) && (
                        <Tag color="blue">{t("chatroom.alsoWorker")}</Tag>
                      )}
                    </Space>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </div>

      {/* Worker Agents Section */}
      <div>
        <div style={{ fontWeight: 600, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <UserOutlined style={{ color: "#1890ff" }} />
          {t("chatroom.workerAgents")}
          <Tooltip title={t("chatroom.workerAgentsTooltip")}>
            <Tag color="blue">{t("chatroom.workers")}</Tag>
          </Tooltip>
        </div>
        <List
          dataSource={availableAgents}
          bordered
          size="small"
          locale={{ emptyText: t("chatroom.noEnabledAgents") }}
          renderItem={(agent) => (
            <List.Item
              style={{
                background: isWorkerAgent(agent) ? "#e6f7ff" : "transparent",
                borderColor: isWorkerAgent(agent) ? "#91d5ff" : "#f0f0f0",
              }}
              actions={[
                <Switch
                  key="toggle"
                  size="small"
                  checked={isWorkerAgent(agent)}
                  onChange={(checked) => handleWorkerAgentToggle(agent.id, checked)}
                  disabled={isLeadAgent(agent)}
                  checkedChildren={t("chatroom.selected")}
                  unCheckedChildren={t("chatroom.select")}
                />,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <span>{agent.name || agent.id}</span>
                    {agent.matrix_enabled && <Tag color="green">Matrix</Tag>}
                  </Space>
                }
                description={
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <span style={{ color: "#666" }}>{agent.description || agent.id}</span>
                    <Space size="small">
                      <Tag>ID: {agent.id}</Tag>
                      {isLeadAgent(agent) && (
                        <Tag color="gold">{t("chatroom.isLeadAgent")}</Tag>
                      )}
                    </Space>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </div>

      {/* Summary */}
      <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid #f0f0f0" }}>
        <Space wrap>
          <Tag color="gold">
            {t("chatroom.leadAgent")}: {leadAgentId ? (agents.find(a => a.id === leadAgentId)?.name || leadAgentId) : t("common.none")}
          </Tag>
          <Tag color="blue">
            {t("chatroom.workerAgents")}: {workerAgentIds.length}
          </Tag>
        </Space>
      </div>
    </div>
  );
}
