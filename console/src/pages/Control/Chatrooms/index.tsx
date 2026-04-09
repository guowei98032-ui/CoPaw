import { useState, useEffect } from "react";
import { Card, Button, Form } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useChatroomStore } from "@/stores/chatroomStore";
import { chatroomApi } from "@/api/modules/chatroom";
import { useAppMessage } from "@/hooks/useAppMessage";
import type { ChatRoom, CreateChatRoomRequest } from "@/api/types/chatroom";
import { ChatroomTable } from "./components/ChatroomTable";
import { ChatroomModal } from "./components/ChatroomModal";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

export default function ChatroomsPage() {
  const { t } = useTranslation();
  const { message } = useAppMessage();
  const { chatrooms, loading, loadChatrooms, addChatroom, updateChatroom, removeChatroom } =
    useChatroomStore();

  const [modalVisible, setModalVisible] = useState(false);
  const [editingChatroom, setEditingChatroom] = useState<ChatRoom | null>(null);
  const [form] = Form.useForm();

  // 页面加载时自动获取数据
  useEffect(() => {
    loadChatrooms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefresh = async () => {
    await loadChatrooms();
    message.success(t("common.refreshed"));
  };

  const handleCreate = () => {
    setEditingChatroom(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (chatroom: ChatRoom) => {
    setEditingChatroom(chatroom);
    form.setFieldsValue({
      name: chatroom.name,
      layout: chatroom.layout,
    });
    setModalVisible(true);
  };

  const handleDelete = async (chatroomId: string) => {
    try {
      await chatroomApi.deleteChatRoom(chatroomId);
      removeChatroom(chatroomId);
      message.success(t("chatroom.deleteSuccess"));
    } catch (error: any) {
      console.error("Failed to delete chatroom:", error);
      message.error(error.message || t("chatroom.deleteFailed"));
    }
  };

  const handleSubmit = async (values: any) => {
    try {
      const payload: CreateChatRoomRequest = {
        name: values.name,
        lead_agent_id: values.lead_agent_id || null,
        agent_ids: values.agent_ids || [],
        agent_roles: values.agent_roles || {},
        layout: values.layout || "tiles",
        matrix_mode: values.matrix_mode || "none",
        matrix_alias: values.matrix_alias || null,
      };

      if (editingChatroom) {
        const updated = await chatroomApi.updateChatRoom(
          editingChatroom.id,
          payload,
        );
        updateChatroom(updated);
        message.success(t("chatroom.updateSuccess"));
      } else {
        const result = await chatroomApi.createChatRoom(payload);
        addChatroom(result.room);
        message.success(t("chatroom.createSuccess"));

        // Show Matrix warning if present
        if (result.matrix_warning) {
          message.warning(result.matrix_warning);
        }
      }

      setModalVisible(false);
      form.resetFields();
    } catch (error: any) {
      console.error("Failed to save chatroom:", error);
      // Display the detailed error message from backend
      message.error(error.message || t("chatroom.saveFailed"));
    }
  };

  return (
    <div className={styles.chatroomsPage}>
      <PageHeader
        parent="Multi-Agent"
        current="ChatRooms"
        extra={
          <div className={styles.headerRight}>
            <Button onClick={handleRefresh}>Refresh</Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              Create ChatRoom
            </Button>
          </div>
        }
      />

      <Card className={styles.tableCard}>
        <ChatroomTable
          chatrooms={chatrooms}
          loading={loading}
          onEdit={handleEdit}
          onDelete={handleDelete}
        />
      </Card>

      <ChatroomModal
        open={modalVisible}
        editingChatroom={editingChatroom}
        form={form}
        onSave={handleSubmit}
        onCancel={() => setModalVisible(false)}
      />
    </div>
  );
}
