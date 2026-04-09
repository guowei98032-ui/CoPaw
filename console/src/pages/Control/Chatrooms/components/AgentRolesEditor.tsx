import { useTranslation } from "react-i18next";
import { Table, Input, Button, Space, Tooltip } from "antd";
import { EditOutlined, CheckOutlined, CloseOutlined } from "@ant-design/icons";
import { useState } from "react";

interface AgentRolesEditorProps {
  agents: Array<{ id: string; name: string; description?: string }>;
  agentRoles: Record<string, string>;
  leadAgentId?: string | null;
  onChange: (agentRoles: Record<string, string>) => void;
}

export function AgentRolesEditor({
  agents,
  agentRoles,
  leadAgentId,
  onChange,
}: AgentRolesEditorProps) {
  const { t } = useTranslation();
  const [editingAgentId, setEditingAgentId] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState<string>("");

  const handleEdit = (agentId: string, currentRole: string) => {
    setEditingAgentId(agentId);
    setEditingValue(currentRole);
  };

  const handleSave = (agentId: string) => {
    onChange({
      ...agentRoles,
      [agentId]: editingValue,
    });
    setEditingAgentId(null);
    setEditingValue("");
  };

  const handleCancel = () => {
    setEditingAgentId(null);
    setEditingValue("");
  };

  const handleReset = (agentId: string, originalDescription?: string) => {
    onChange({
      ...agentRoles,
      [agentId]: originalDescription || "",
    });
  };

  const columns = [
    {
      title: t("chatroom.agentName"),
      dataIndex: "name",
      key: "name",
      width: 150,
      render: (name: string, record: { id: string }) => {
        const isLead = record.id === leadAgentId;
        return (
          <Space>
            <span>{name}</span>
            {isLead && (
              <Tooltip title={t("chatroom.leadAgent")}>
                <span style={{ color: "#faad14" }}>★</span>
              </Tooltip>
            )}
          </Space>
        );
      },
    },
    {
      title: t("chatroom.roleDescription"),
      dataIndex: "id",
      key: "role",
      render: (agentId: string, record: { description?: string }) => {
        const currentRole = agentRoles[agentId] ?? record.description ?? "";
        const originalDescription = record.description || "";

        if (editingAgentId === agentId) {
          return (
            <Space.Compact style={{ width: "100%" }}>
              <Input.TextArea
                value={editingValue}
                onChange={(e) => setEditingValue(e.target.value)}
                autoSize={{ minRows: 2, maxRows: 4 }}
                style={{ flex: 1 }}
              />
              <Button
                type="primary"
                icon={<CheckOutlined />}
                onClick={() => handleSave(agentId)}
              />
              <Button
                icon={<CloseOutlined />}
                onClick={handleCancel}
              />
            </Space.Compact>
          );
        }

        const hasCustomRole = agentRoles[agentId] !== undefined &&
          agentRoles[agentId] !== originalDescription;

        return (
          <Space direction="vertical" style={{ width: "100%" }}>
            <div style={{
              minHeight: 32,
              padding: "4px 11px",
              background: "#fafafa",
              borderRadius: 6,
              border: hasCustomRole ? "1px solid #1890ff" : "1px solid #d9d9d9",
            }}>
              {currentRole || <span style={{ color: "#999" }}>{t("chatroom.noRoleDescription")}</span>}
            </div>
            <Space size="small">
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => handleEdit(agentId, currentRole)}
              >
                {t("common.edit")}
              </Button>
              {hasCustomRole && (
                <Button
                  size="small"
                  type="text"
                  onClick={() => handleReset(agentId, originalDescription)}
                >
                  {t("chatroom.resetToOriginal")}
                </Button>
              )}
            </Space>
          </Space>
        );
      },
    },
  ];

  return (
    <Table
      dataSource={agents}
      columns={columns}
      rowKey="id"
      pagination={false}
      size="small"
      locale={{ emptyText: t("chatroom.noAgentsSelected") }}
    />
  );
}