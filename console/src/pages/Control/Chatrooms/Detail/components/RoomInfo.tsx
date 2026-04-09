import { Descriptions, Space, Tag } from "antd";
import type { ChatRoom, ChatRoomDetail } from "@/api/types/chatroom";
import styles from "./index.module.less";

interface RoomInfoProps {
  room: ChatRoom | ChatRoomDetail;
}

export function RoomInfo({ room }: RoomInfoProps) {

  return (
    <div className={styles.roomInfo}>
      <Descriptions
        column={2}
        bordered
        title={
          <Space>
            <span>{room.name}</span>
            <Tag>{room.layout}</Tag>
          </Space>
        }
      >
        <Descriptions.Item label="ID">{room.id}</Descriptions.Item>
        <Descriptions.Item label="User ID">{room.user_id}</Descriptions.Item>
        <Descriptions.Item label="Lead Agent">
          {room.lead_agent_id || "Not assigned"}
        </Descriptions.Item>
        <Descriptions.Item label="Created At">
          {new Date(room.created_at).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="Updated At">
          {new Date(room.updated_at).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="Agent Count">
          {room.agent_ids?.length || 0}
        </Descriptions.Item>
        <Descriptions.Item label="Agents" span={2}>
          <Space wrap>
            {room.agent_ids?.map((id: string) => (
              <Tag key={id} color="blue">
                {id}
              </Tag>
            ))}
            {(!room.agent_ids || room.agent_ids.length === 0) && (
              <span style={{ opacity: 0.5 }}>No agents assigned</span>
            )}
          </Space>
        </Descriptions.Item>
        {(room as ChatRoomDetail).tasks && (
          <Descriptions.Item label="Tasks" span={2}>
            <Space wrap>
              <Tag color="default">
                Total: {(room as ChatRoomDetail).tasks?.length || 0}
              </Tag>
              <Tag color="default">
                Pending:{" "}
                {(room as ChatRoomDetail).tasks?.filter(
                  (t: { status: string }) => t.status === "pending",
                ).length || 0}
              </Tag>
              <Tag color="processing">
                In Progress:{" "}
                {(room as ChatRoomDetail).tasks?.filter(
                  (t: { status: string }) => t.status === "in_progress",
                ).length || 0}
              </Tag>
              <Tag color="success">
                Completed:{" "}
                {(room as ChatRoomDetail).tasks?.filter(
                  (t: { status: string }) => t.status === "completed",
                ).length || 0}
              </Tag>
            </Space>
          </Descriptions.Item>
        )}
        {(room as ChatRoomDetail).messages && (
          <Descriptions.Item label="Messages" span={2}>
            <Space wrap>
              <Tag color="default">
                Total: {(room as ChatRoomDetail).messages?.length || 0}
              </Tag>
              <Tag color="default">
                Unread:{" "}
                {(room as ChatRoomDetail).messages?.filter((m: { read: boolean }) => !m.read)
                  .length || 0}
              </Tag>
            </Space>
          </Descriptions.Item>
        )}
      </Descriptions>
    </div>
  );
}
