import { Table, Button, Space, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { EditOutlined, DeleteOutlined, MessageOutlined, CrownOutlined, ApiOutlined } from "@ant-design/icons";
import { ChatRoom } from "@/api/types/chatroom";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAgentStore } from "@/stores/agentStore";

interface ChatroomTableProps {
  chatrooms: ChatRoom[];
  loading: boolean;
  onEdit: (chatroom: ChatRoom) => void;
  onDelete: (chatroomId: string) => void;
}

export function ChatroomTable({
  chatrooms,
  loading,
  onEdit,
  onDelete,
}: ChatroomTableProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { agents } = useAgentStore();

  const getAgentName = (agentId: string): string => {
    const agent = agents.find(a => a.id === agentId);
    return agent?.name || agentId;
  };

  const columns: ColumnsType<ChatRoom> = [
    {
      title: t("chatroom.name"),
      dataIndex: "name",
      key: "name",
      width: 200,
      render: (text: string, record: ChatRoom) => (
        <Space>
          <MessageOutlined style={{ fontSize: 16 }} />
          <strong>
            <a onClick={() => navigate(`/chatrooms/${record.id}`)}>{text}</a>
          </strong>
          {record.matrix_room_id && (
            <Tooltip title={t("chatroom.matrixLinked") + (record.matrix_alias || record.matrix_room_id)}>
              <ApiOutlined style={{ color: "#52c41a", fontSize: 12 }} />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: t("chatroom.id"),
      dataIndex: "id",
      key: "id",
      width: 100,
      ellipsis: true,
    },
    {
      title: t("chatroom.leadAgent"),
      dataIndex: "lead_agent_id",
      key: "lead_agent_id",
      width: 150,
      render: (text: string | null) =>
        text ? (
          <Space>
            <CrownOutlined style={{ color: "#faad14" }} />
            <span>{getAgentName(text)}</span>
          </Space>
        ) : "-",
    },
    {
      title: t("chatroom.agents"),
      dataIndex: "agent_ids",
      key: "agent_ids",
      width: 200,
      render: (agentIds: string[], record: ChatRoom) => (
        <Space wrap>
          {agentIds.length === 0 ? (
            <span style={{ opacity: 0.5 }}>No agents</span>
          ) : (
            agentIds.map((id) => (
              <Tag
                key={id}
                color={id === record.lead_agent_id ? "gold" : "blue"}
              >
                {getAgentName(id)}
              </Tag>
            ))
          )}
        </Space>
      ),
    },
    {
      title: t("chatroom.updatedAt"),
      dataIndex: "updated_at",
      key: "updated_at",
      width: 180,
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 150,
      render: (_: any, record: ChatRoom) => (
        <Space>
          <Button
            type="text"
            size="middle"
            icon={<EditOutlined />}
            onClick={() => onEdit(record)}
          />
          <Button
            type="text"
            size="middle"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onDelete(record.id)}
          />
        </Space>
      ),
    },
  ];

  return (
    <Table
      dataSource={chatrooms}
      columns={columns}
      loading={loading}
      rowKey="id"
      pagination={{
        pageSize: 10,
        showSizeChanger: false,
      }}
    />
  );
}
