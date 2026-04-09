import { Modal, Form, Input, Radio, Space, Alert } from "antd";
import { useTranslation } from "react-i18next";
import type { ChatRoom } from "@/api/types/chatroom";
import { useEffect, useState } from "react";
import { AgentSelector } from "./AgentSelector";
import { AgentRolesEditor } from "./AgentRolesEditor";
import { useAgentStore } from "@/stores/agentStore";

interface ChatroomModalProps {
  open: boolean;
  editingChatroom: ChatRoom | null;
  form: any;
  onSave: (values: any) => void;
  onCancel: () => void;
}

// Matrix alias validation: only [a-zA-Z0-9._=-] allowed, min 3 chars
const MATRIX_ALIAS_REGEX = /^[a-zA-Z0-9._=-]+$/;
const MIN_ALIAS_LENGTH = 3;

function validateMatrixAlias(alias: string): { valid: boolean; error?: string } {
  if (!alias) {
    return { valid: true }; // Empty is OK (will use auto-generated)
  }
  if (alias.length < MIN_ALIAS_LENGTH) {
    return { valid: false, error: "minLength" };
  }
  if (alias.startsWith("_")) {
    return { valid: false, error: "startsWithUnderscore" };
  }
  if (!MATRIX_ALIAS_REGEX.test(alias)) {
    return { valid: false, error: "invalidChars" };
  }
  return { valid: true };
}

export function ChatroomModal({
  open,
  editingChatroom,
  form,
  onSave,
  onCancel,
}: ChatroomModalProps) {
  const { t } = useTranslation();
  const { agents } = useAgentStore();
  const [leadAgentId, setLeadAgentId] = useState<string | undefined>();
  const [workerAgentIds, setWorkerAgentIds] = useState<string[]>([]);
  const [agentRoles, setAgentRoles] = useState<Record<string, string>>({});
  const [matrixMode, setMatrixMode] = useState<string>("none");
  const [matrixAlias, setMatrixAlias] = useState<string>("");
  const [aliasError, setAliasError] = useState<string | null>(null);

  useEffect(() => {
    if (editingChatroom) {
      setLeadAgentId(editingChatroom.lead_agent_id ?? undefined);
      setWorkerAgentIds(editingChatroom.agent_ids || []);
      setAgentRoles(editingChatroom.agent_roles || {});
      // Set matrix mode based on existing data
      if (editingChatroom.matrix_room_id) {
        setMatrixMode("linked");
      } else {
        setMatrixMode("none");
      }
    } else {
      setLeadAgentId(undefined);
      setWorkerAgentIds([]);
      setAgentRoles({});
      setMatrixMode("none");
      setMatrixAlias("");
      setAliasError(null);
    }
  }, [editingChatroom]);

  const title = editingChatroom
    ? t("chatroom.editChatroom")
    : t("chatroom.createChatroom");

  const handleAliasChange = (value: string) => {
    setMatrixAlias(value);
    const result = validateMatrixAlias(value);
    if (!result.valid && result.error) {
      setAliasError(result.error);
    } else {
      setAliasError(null);
    }
  };

  const handleSave = () => {
    // Don't submit if there's an alias error
    if (aliasError) {
      return;
    }
    // Validate alias before submit
    if (matrixMode === "create_new") {
      // If alias is provided, validate it
      if (matrixAlias) {
        const result = validateMatrixAlias(matrixAlias);
        if (!result.valid) {
          return; // Don't submit if alias is invalid
        }
      }
    } else if (matrixMode === "link_existing") {
      // For linking, alias is required
      if (!matrixAlias) {
        return;
      }
    }
    form.submit();
  };

  const handleFinish = (values: any) => {
    onSave({
      ...values,
      lead_agent_id: leadAgentId,
      agent_ids: workerAgentIds,
      agent_roles: agentRoles,
      matrix_mode: matrixMode,
      matrix_alias: matrixAlias || null,
    });
  };

  const getAliasErrorMessage = () => {
    if (!aliasError) return null;
    switch (aliasError) {
      case "minLength":
        return t("chatroom.matrixAliasMinLength");
      case "startsWithUnderscore":
        return t("chatroom.matrixAliasUnderscore");
      case "invalidChars":
        return t("chatroom.matrixAliasInvalidChars");
      default:
        return null;
    }
  };

  return (
    <Modal
      title={title}
      open={open}
      onOk={handleSave}
      onCancel={onCancel}
      width={700}
      okText={t("common.save")}
      cancelText={t("common.cancel")}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
      >
        <Form.Item
          name="name"
          label={t("chatroom.name")}
          rules={[{ required: true, message: t("chatroom.nameRequired") }]}
        >
          <Input placeholder={t("chatroom.namePlaceholder")} />
        </Form.Item>

        <Form.Item label={t("chatroom.agents")} tooltip={t("chatroom.agentsTooltip")}>
          <AgentSelector
            leadAgentId={leadAgentId}
            workerAgentIds={workerAgentIds}
            onLeadAgentChange={setLeadAgentId}
            onWorkerAgentsChange={setWorkerAgentIds}
            matrixMode={matrixMode}
          />
        </Form.Item>

        {/* Agent Roles Editor - only show when agents are selected */}
        {(leadAgentId || workerAgentIds.length > 0) && (
          <Form.Item label={t("chatroom.agentRoles")} tooltip={t("chatroom.agentRolesTooltip")}>
            <AgentRolesEditor
              agents={[
                ...agents
                  .filter(a => a.id === leadAgentId || workerAgentIds.includes(a.id))
                  .map(a => ({
                    id: a.id,
                    name: a.name || a.id,
                    description: a.description,
                  })),
              ]}
              agentRoles={agentRoles}
              leadAgentId={leadAgentId}
              onChange={setAgentRoles}
            />
          </Form.Item>
        )}

        {!editingChatroom && (
          <Form.Item label={t("chatroom.matrixRoom")} tooltip={t("chatroom.matrixRoomTooltip")}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Radio.Group
                value={matrixMode}
                onChange={(e) => {
                  setMatrixMode(e.target.value);
                  if (e.target.value === "none") {
                    setMatrixAlias("");
                    setAliasError(null);
                  }
                }}
              >
                <Radio value="none">{t("chatroom.matrixNone")}</Radio>
                <Radio value="create_new">{t("chatroom.matrixCreate")}</Radio>
                <Radio value="link_existing">{t("chatroom.matrixLink")}</Radio>
              </Radio.Group>

              {matrixMode === "create_new" && (
                <>
                  <Input
                    placeholder={t("chatroom.matrixAliasPlaceholder")}
                    value={matrixAlias}
                    onChange={(e) => handleAliasChange(e.target.value)}
                    status={aliasError ? "error" : undefined}
                  />
                  {aliasError && (
                    <Alert message={getAliasErrorMessage()} type="error" showIcon style={{ marginTop: 4 }} />
                  )}
                </>
              )}

              {matrixMode === "link_existing" && (
                <Input
                  placeholder={t("chatroom.matrixExistingPlaceholder")}
                  value={matrixAlias}
                  onChange={(e) => setMatrixAlias(e.target.value)}
                />
              )}
            </Space>
          </Form.Item>
        )}

        {editingChatroom && editingChatroom.matrix_room_id && (
          <Form.Item label={t("chatroom.matrixRoom")}>
            <Space>
              <span style={{ color: "#52c41a" }}>{t("chatroom.matrixLinked")}</span>
              <code style={{ fontSize: 12, background: "#f5f5f5", padding: "2px 6px", borderRadius: 4 }}>
                {editingChatroom.matrix_alias || editingChatroom.matrix_room_id}
              </code>
            </Space>
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}