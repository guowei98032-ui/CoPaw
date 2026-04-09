import { useState, useEffect } from "react";
import {
  Table,
  Button,
  Space,
  Tag,
  Input,
  Modal,
  Form,
  Select,
  Tooltip,
  Badge,
  Popconfirm,
  Tabs,
  Timeline,
  Drawer,
  Descriptions,
  Segmented,
  Dropdown,
  Progress,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  PlusOutlined,
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  StopOutlined,
  ReloadOutlined,
  RocketOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  UserOutlined,
  LinkOutlined,
  HistoryOutlined,
  EyeOutlined,
  AppstoreOutlined,
  TableOutlined,
  PartitionOutlined,
  DownloadOutlined,
  ExportOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { chatroomApi } from "@/api/modules/chatroom";
import type { Task, ExecutionLogEntry } from "@/api/types/chatroom";
import { useAppMessage } from "@/hooks/useAppMessage";
import { TaskKanban } from "./TaskKanban";
import { TaskDependencyGraph } from "./TaskDependencyGraph";
import styles from "./index.module.less";

const { TextArea } = Input;

interface TaskListProps {
  roomId: string;
  tasks: Task[];
  onRefresh: () => void;
}

export function TaskList({ roomId, tasks, onRefresh }: TaskListProps) {
  const { t } = useTranslation();
  const { message: appMessage } = useAppMessage();
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "kanban" | "graph">("table");
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchModalVisible, setBatchModalVisible] = useState(false);
  const [batchOperation, setBatchOperation] = useState<string>("cancel");
  const [form] = Form.useForm();

  // Real-time updates via SSE
  useEffect(() => {
    const eventSource = chatroomApi.subscribeTaskEvents(roomId);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "task_update") {
          onRefresh();
        }
      } catch (e) {
        // Ignore parse errors
      }
    };

    eventSource.onerror = () => {
      // Reconnect on error
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [roomId, onRefresh]);

  const handleCreate = () => {
    setEditingTask(null);
    form.resetFields();
    setCreateModalVisible(true);
  };

  const handleEdit = (task: Task) => {
    setEditingTask(task);
    form.setFieldsValue({
      subject: task.subject,
      description: task.description,
      status: task.status,
      owner: task.owner,
      auto_mode: task.auto_mode,
    });
    setCreateModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingTask) {
        await chatroomApi.updateTask(roomId, editingTask.id, {
          status: values.status,
          owner: values.owner,
          description: values.description,
          auto_mode: values.auto_mode,
        });
        appMessage.success(t("chatroom.taskUpdateSuccess"));
      } else {
        await chatroomApi.createTask(roomId, {
          subject: values.subject,
          description: values.description,
          owner: values.owner,
          priority: values.priority,
          auto_mode: values.auto_mode,
        });
        appMessage.success(t("chatroom.taskCreateSuccess"));
      }
      setCreateModalVisible(false);
      onRefresh();
    } catch (error: any) {
      appMessage.error(error.message || t("chatroom.saveFailed"));
    }
  };

  const handleStatusChange = async (task: Task, newStatus: Task["status"]) => {
    try {
      await chatroomApi.updateTask(roomId, task.id, { status: newStatus });
      appMessage.success(t("chatroom.taskUpdateSuccess"));
      onRefresh();
    } catch (error: any) {
      appMessage.error(error.message || t("chatroom.saveFailed"));
    }
  };

  const handleCancel = async (task: Task, reason?: string) => {
    try {
      await chatroomApi.cancelTask(roomId, task.id, { reason });
      appMessage.success("Task cancelled successfully");
      onRefresh();
    } catch (error: any) {
      appMessage.error(error.message || t("chatroom.saveFailed"));
    }
  };

  const handleRetry = async (task: Task) => {
    try {
      await chatroomApi.retryTask(roomId, task.id, { reset_owner: true });
      appMessage.success("Task reset for retry");
      onRefresh();
    } catch (error: any) {
      appMessage.error(error.message || t("chatroom.saveFailed"));
    }
  };

  const handleToggleAutoMode = async (task: Task) => {
    try {
      await chatroomApi.setTaskAutoMode(roomId, task.id, {
        auto_mode: !task.auto_mode,
      });
      appMessage.success(`Auto mode ${!task.auto_mode ? "enabled" : "disabled"}`);
      onRefresh();
    } catch (error: any) {
      appMessage.error(error.message || t("chatroom.saveFailed"));
    }
  };

  const showDetail = (task: Task) => {
    setSelectedTask(task);
    setDetailDrawerVisible(true);
  };

  // Batch operations
  const handleBatchOperation = async () => {
    if (selectedRowKeys.length === 0) {
      appMessage.warning("Please select at least one task");
      return;
    }

    try {
      const result = await chatroomApi.batchTaskOperation(roomId, {
        task_ids: selectedRowKeys as string[],
        operation: batchOperation as any,
        status: form.getFieldValue("batch_status"),
        priority: form.getFieldValue("batch_priority"),
        owner: form.getFieldValue("batch_owner"),
        reason: form.getFieldValue("batch_reason"),
      });

      appMessage.success(
        `Batch operation completed: ${result.success_count} succeeded, ${result.failed_count} failed`
      );

      if (result.failed_tasks.length > 0) {
        console.warn("Failed tasks:", result.failed_tasks);
      }

      setBatchModalVisible(false);
      setSelectedRowKeys([]);
      onRefresh();
    } catch (error: any) {
      appMessage.error(error.message || "Batch operation failed");
    }
  };

  // Export tasks
  const handleExport = (format: "csv" | "json") => {
    const url = chatroomApi.exportTasks(roomId, format);
    window.open(url, "_blank");
  };

  const getStatusConfig = (status: string) => {
    const configs: Record<string, { color: string; icon: React.ReactNode }> = {
      pending: { color: "default", icon: <ClockCircleOutlined /> },
      in_progress: { color: "processing", icon: <SyncOutlined spin /> },
      completed: { color: "success", icon: <CheckCircleOutlined /> },
      failed: { color: "error", icon: <CloseCircleOutlined /> },
      cancelled: { color: "warning", icon: <StopOutlined /> },
    };
    return configs[status] || configs.pending;
  };

  const getPriorityConfig = (priority: string) => {
    const configs: Record<string, { color: string }> = {
      low: { color: "default" },
      medium: { color: "blue" },
      high: { color: "red" },
    };
    return configs[priority] || configs.medium;
  };

  const getEventIcon = (event: string) => {
    const icons: Record<string, React.ReactNode> = {
      started: <ThunderboltOutlined style={{ color: "#1890ff" }} />,
      progress: <SyncOutlined style={{ color: "#1890ff" }} />,
      completed: <CheckCircleOutlined style={{ color: "#52c41a" }} />,
      failed: <CloseCircleOutlined style={{ color: "#ff4d4f" }} />,
      cancelled: <StopOutlined style={{ color: "#faad14" }} />,
      retry: <ReloadOutlined style={{ color: "#faad14" }} />,
      timeout_warning: <ClockCircleOutlined style={{ color: "#ff4d4f" }} />,
      stale_warning: <ClockCircleOutlined style={{ color: "#faad14" }} />,
      update: <EditOutlined style={{ color: "#1890ff" }} />,
      note: <EditOutlined style={{ color: "#8c8c8c" }} />,
    };
    return icons[event] || <ClockCircleOutlined />;
  };

  // Build dependency graph data
  const taskMap = new Map(tasks.map((t) => [t.id, t]));

  const columns: ColumnsType<Task> = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 80,
      render: (id: string) => (
        <Tooltip title={id}>
          <span style={{ fontFamily: "monospace" }}>#{id.slice(0, 6)}</span>
        </Tooltip>
      ),
    },
    {
      title: t("chatroom.taskSubject"),
      dataIndex: "subject",
      key: "subject",
      width: 200,
      ellipsis: true,
      render: (subject: string, record: Task) => (
        <Space>
          <span>{subject}</span>
          {record.auto_mode && (
            <Tooltip title="Auto Mode - Agent acts autonomously">
              <Tag icon={<RocketOutlined />} color="purple">
                Auto
              </Tag>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: t("chatroom.taskStatus"),
      dataIndex: "status",
      key: "status",
      width: 130,
      render: (status: string) => {
        const config = getStatusConfig(status);
        return (
          <Tag icon={config.icon} color={config.color}>
            {status.replace("_", " ")}
          </Tag>
        );
      },
    },
    {
      title: "Progress",
      dataIndex: "progress",
      key: "progress",
      width: 120,
      render: (progress: number, record: Task) => {
        if (record.status !== "in_progress") return null;
        return (
          <Progress
            percent={progress}
            size="small"
            status={progress === 100 ? "success" : "active"}
          />
        );
      },
    },
    {
      title: t("chatroom.taskOwner"),
      dataIndex: "owner",
      key: "owner",
      width: 120,
      render: (owner: string | null) =>
        owner ? (
          <Tag icon={<UserOutlined />}>{owner}</Tag>
        ) : (
          <span style={{ color: "#999" }}>Unassigned</span>
        ),
    },
    {
      title: t("chatroom.taskPriority"),
      dataIndex: "priority",
      key: "priority",
      width: 80,
      render: (priority: string) => {
        const config = getPriorityConfig(priority);
        return <Tag color={config.color}>{priority}</Tag>;
      },
    },
    {
      title: "Dependencies",
      key: "dependencies",
      width: 120,
      render: (_: any, record: Task) => {
        const blockedBy = record.blocked_by || [];
        const blocks = record.blocks || [];

        if (blockedBy.length === 0 && blocks.length === 0) {
          return <span style={{ color: "#999" }}>-</span>;
        }

        return (
          <Space direction="vertical" size={0}>
            {blockedBy.length > 0 && (
              <Tooltip title={`Blocked by: ${blockedBy.join(", ")}`}>
                <Tag color="orange" icon={<LinkOutlined />}>
                  ⏳ {blockedBy.length}
                </Tag>
              </Tooltip>
            )}
            {blocks.length > 0 && (
              <Tooltip title={`Blocks: ${blocks.join(", ")}`}>
                <Tag color="blue">→ {blocks.length}</Tag>
              </Tooltip>
            )}
          </Space>
        );
      },
    },
    {
      title: "Retry",
      dataIndex: "retry_count",
      key: "retry_count",
      width: 70,
      render: (retryCount: number, record: Task) =>
        retryCount > 0 ? (
          <Tooltip title={`Retried ${retryCount}/${record.max_retries} times`}>
            <Badge count={retryCount} size="small" color="orange">
              <HistoryOutlined style={{ fontSize: 16 }} />
            </Badge>
          </Tooltip>
        ) : (
          <span style={{ color: "#999" }}>-</span>
        ),
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 200,
      fixed: "right",
      render: (_: any, record: Task) => (
        <Space size="small">
          <Tooltip title="View Details">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => showDetail(record)}
            />
          </Tooltip>
          <Tooltip title="Edit">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          {record.status === "pending" && (
            <Tooltip title="Start Task">
              <Button
                type="text"
                size="small"
                icon={<ThunderboltOutlined />}
                onClick={() => handleStatusChange(record, "in_progress")}
              />
            </Tooltip>
          )}
          {record.status === "in_progress" && (
            <Tooltip title="Complete">
              <Button
                type="text"
                size="small"
                icon={<CheckCircleOutlined />}
                onClick={() => handleStatusChange(record, "completed")}
              />
            </Tooltip>
          )}
          {(record.status === "pending" || record.status === "in_progress") && (
            <Popconfirm
              title="Cancel this task?"
              description="This will notify the task owner and unblock dependent tasks."
              onConfirm={() => handleCancel(record)}
              okText="Yes, Cancel"
              cancelText="No"
            >
              <Tooltip title="Cancel">
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<StopOutlined />}
                />
              </Tooltip>
            </Popconfirm>
          )}
          {(record.status === "failed" || record.status === "cancelled") &&
            record.retry_count < record.max_retries && (
              <Tooltip title="Retry">
                <Button
                  type="text"
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={() => handleRetry(record)}
                />
              </Tooltip>
            )}
        </Space>
      ),
    },
  ];

  // Group tasks by status for summary
  const statusCounts = tasks.reduce(
    (acc, task) => {
      acc[task.status] = (acc[task.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  const renderTableView = () => (
    <div>
      <Table
        dataSource={tasks}
        columns={columns}
        rowKey="id"
        pagination={{ pageSize: 10, showSizeChanger: false }}
        scroll={{ x: 1200 }}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
      />
      {selectedRowKeys.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Space>
            <span>{selectedRowKeys.length} tasks selected</span>
            <Button onClick={() => setBatchModalVisible(true)}>
              Batch Operation
            </Button>
            <Button onClick={() => setSelectedRowKeys([])}>
              Clear Selection
            </Button>
          </Space>
        </div>
      )}
    </div>
  );

  const renderKanbanView = () => (
    <TaskKanban
      tasks={tasks}
      onCreateTask={handleCreate}
      onEditTask={handleEdit}
      onViewTask={showDetail}
      onUpdateStatus={handleStatusChange}
      onCancelTask={handleCancel}
      onRetryTask={handleRetry}
      onRefresh={onRefresh}
    />
  );

  const renderGraphView = () => (
    <TaskDependencyGraph
      tasks={tasks}
      onTaskClick={showDetail}
    />
  );

  // Render execution log
  const renderExecutionLog = (log: ExecutionLogEntry[]) => {
    if (!log || log.length === 0) {
      return <div style={{ color: "#999", padding: 16 }}>No execution log available.</div>;
    }

    return (
      <Timeline
        items={log.map((entry) => ({
          color: entry.event === "completed" ? "green" :
                 entry.event === "failed" || entry.event === "timeout_warning" ? "red" :
                 entry.event === "cancelled" ? "orange" : "blue",
          dot: getEventIcon(entry.event),
          children: (
            <div>
              <div style={{ fontWeight: 500, textTransform: "capitalize" }}>
                {entry.event.replace("_", " ")}
              </div>
              {entry.details && (
                <div style={{ color: "#666", fontSize: 12 }}>{entry.details}</div>
              )}
              <div style={{ color: "#999", fontSize: 11 }}>
                {new Date(entry.timestamp).toLocaleString()}
              </div>
            </div>
          ),
        }))}
      />
    );
  };

  return (
    <div className={styles.taskList}>
      {/* Task Summary */}
      <div className={styles.taskSummary}>
        <Space size="large">
          <span>
            <Badge color="default" /> Pending: {statusCounts.pending || 0}
          </span>
          <span>
            <Badge color="processing" /> In Progress:{" "}
            {statusCounts.in_progress || 0}
          </span>
          <span>
            <Badge color="success" /> Completed: {statusCounts.completed || 0}
          </span>
          <span>
            <Badge color="error" /> Failed: {statusCounts.failed || 0}
          </span>
          <span>
            <Badge color="warning" /> Cancelled: {statusCounts.cancelled || 0}
          </span>
        </Space>
        <Space>
          <Segmented
            value={viewMode}
            onChange={(value) => setViewMode(value as typeof viewMode)}
            options={[
              {
                value: "table",
                icon: <TableOutlined />,
                label: "Table",
              },
              {
                value: "kanban",
                icon: <AppstoreOutlined />,
                label: "Kanban",
              },
              {
                value: "graph",
                icon: <PartitionOutlined />,
                label: "Dependencies",
              },
            ]}
          />
          <Dropdown
            menu={{
              items: [
                { key: "csv", label: "Export as CSV", icon: <DownloadOutlined /> },
                { key: "json", label: "Export as JSON", icon: <DownloadOutlined /> },
              ],
              onClick: (e) => handleExport(e.key as "csv" | "json"),
            }}
          >
            <Button icon={<ExportOutlined />}>Export</Button>
          </Dropdown>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            {t("chatroom.createTask")}
          </Button>
        </Space>
      </div>

      {/* Conditional View Rendering */}
      {viewMode === "table" && renderTableView()}
      {viewMode === "kanban" && renderKanbanView()}
      {viewMode === "graph" && renderGraphView()}

      {/* Create/Edit Modal */}
      <Modal
        title={editingTask ? t("chatroom.editTask") : t("chatroom.createTask")}
        open={createModalVisible}
        onOk={handleSubmit}
        onCancel={() => setCreateModalVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          {!editingTask && (
            <Form.Item
              name="subject"
              label={t("chatroom.taskSubject")}
              rules={[
                { required: true, message: t("chatroom.taskSubjectRequired") },
              ]}
            >
              <Input placeholder={t("chatroom.taskSubjectPlaceholder")} />
            </Form.Item>
          )}
          <Form.Item
            name="description"
            label={t("chatroom.taskDescription")}
          >
            <TextArea
              rows={4}
              placeholder={t("chatroom.taskDescriptionPlaceholder")}
            />
          </Form.Item>
          <Form.Item name="owner" label={t("chatroom.taskOwner")}>
            <Input placeholder={t("chatroom.taskOwnerPlaceholder")} />
          </Form.Item>
          {!editingTask && (
            <Form.Item
              name="priority"
              label={t("chatroom.taskPriority")}
              initialValue="medium"
            >
              <Select>
                <Select.Option value="low">Low</Select.Option>
                <Select.Option value="medium">Medium</Select.Option>
                <Select.Option value="high">High</Select.Option>
              </Select>
            </Form.Item>
          )}
          {editingTask && (
            <Form.Item name="status" label={t("chatroom.taskStatus")}>
              <Select>
                <Select.Option value="pending">Pending</Select.Option>
                <Select.Option value="in_progress">In Progress</Select.Option>
                <Select.Option value="completed">Completed</Select.Option>
                <Select.Option value="failed">Failed</Select.Option>
                <Select.Option value="cancelled">Cancelled</Select.Option>
              </Select>
            </Form.Item>
          )}
          <Form.Item
            name="auto_mode"
            label="Auto Mode"
            valuePropName="checked"
            initialValue={false}
          >
            <Select>
              <Select.Option value={false}>
                Normal - Agent may ask for confirmation
              </Select.Option>
              <Select.Option value={true}>
                Auto - Agent acts autonomously
              </Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* Batch Operation Modal */}
      <Modal
        title="Batch Task Operation"
        open={batchModalVisible}
        onOk={handleBatchOperation}
        onCancel={() => setBatchModalVisible(false)}
        okText="Execute"
      >
        <p>{selectedRowKeys.length} tasks selected</p>
        <Form form={form} layout="vertical">
          <Form.Item label="Operation">
            <Select value={batchOperation} onChange={setBatchOperation}>
              <Select.Option value="cancel">Cancel Tasks</Select.Option>
              <Select.Option value="delete">Delete Tasks</Select.Option>
              <Select.Option value="assign">Assign Owner</Select.Option>
              <Select.Option value="set_status">Set Status</Select.Option>
              <Select.Option value="set_priority">Set Priority</Select.Option>
            </Select>
          </Form.Item>
          {batchOperation === "cancel" && (
            <Form.Item name="batch_reason" label="Reason (optional)">
              <Input placeholder="Reason for cancellation" />
            </Form.Item>
          )}
          {batchOperation === "assign" && (
            <Form.Item name="batch_owner" label="Owner" rules={[{ required: true }]}>
              <Input placeholder="Agent ID" />
            </Form.Item>
          )}
          {batchOperation === "set_status" && (
            <Form.Item name="batch_status" label="Status" rules={[{ required: true }]}>
              <Select>
                <Select.Option value="pending">Pending</Select.Option>
                <Select.Option value="in_progress">In Progress</Select.Option>
                <Select.Option value="completed">Completed</Select.Option>
                <Select.Option value="failed">Failed</Select.Option>
              </Select>
            </Form.Item>
          )}
          {batchOperation === "set_priority" && (
            <Form.Item name="batch_priority" label="Priority" rules={[{ required: true }]}>
              <Select>
                <Select.Option value="low">Low</Select.Option>
                <Select.Option value="medium">Medium</Select.Option>
                <Select.Option value="high">High</Select.Option>
              </Select>
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* Task Detail Drawer */}
      <Drawer
        title={`Task #${selectedTask?.id?.slice(0, 6)}`}
        placement="right"
        width={600}
        open={detailDrawerVisible}
        onClose={() => setDetailDrawerVisible(false)}
      >
        {selectedTask && (
          <Tabs
            items={[
              {
                key: "details",
                label: "Details",
                children: (
                  <div>
                    <Descriptions column={1} bordered size="small">
                      <Descriptions.Item label="Subject">
                        {selectedTask.subject}
                      </Descriptions.Item>
                      <Descriptions.Item label="Status">
                        <Tag color={getStatusConfig(selectedTask.status).color}>
                          {selectedTask.status}
                        </Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Priority">
                        <Tag color={getPriorityConfig(selectedTask.priority).color}>
                          {selectedTask.priority}
                        </Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Owner">
                        {selectedTask.owner || "Unassigned"}
                      </Descriptions.Item>
                      <Descriptions.Item label="Progress">
                        <Progress percent={selectedTask.progress} size="small" />
                      </Descriptions.Item>
                      <Descriptions.Item label="Auto Mode">
                        {selectedTask.auto_mode ? (
                          <Tag icon={<RocketOutlined />} color="purple">
                            Enabled
                          </Tag>
                        ) : (
                          <Tag>Disabled</Tag>
                        )}
                      </Descriptions.Item>
                      <Descriptions.Item label="Retry Count">
                        {selectedTask.retry_count} / {selectedTask.max_retries}
                      </Descriptions.Item>
                      {selectedTask.timeout_minutes && (
                        <Descriptions.Item label="Timeout">
                          {selectedTask.timeout_minutes} minutes
                        </Descriptions.Item>
                      )}
                      <Descriptions.Item label="Created By">
                        {selectedTask.created_by}
                      </Descriptions.Item>
                      <Descriptions.Item label="Created At">
                        {new Date(selectedTask.created_at).toLocaleString()}
                      </Descriptions.Item>
                      <Descriptions.Item label="Updated At">
                        {new Date(selectedTask.updated_at).toLocaleString()}
                      </Descriptions.Item>
                      {selectedTask.completed_at && (
                        <Descriptions.Item label="Completed At">
                          {new Date(selectedTask.completed_at).toLocaleString()}
                        </Descriptions.Item>
                      )}
                    </Descriptions>

                    {selectedTask.description && (
                      <div style={{ marginTop: 16 }}>
                        <h4>Description</h4>
                        <div
                          style={{
                            background: "#f5f5f5",
                            padding: 12,
                            borderRadius: 4,
                          }}
                        >
                          {selectedTask.description}
                        </div>
                      </div>
                    )}

                    {/* Dependencies */}
                    {(selectedTask.blocked_by?.length > 0 ||
                      selectedTask.blocks?.length > 0) && (
                      <div style={{ marginTop: 16 }}>
                        <h4>Dependencies</h4>
                        {selectedTask.blocked_by?.length > 0 && (
                          <div style={{ marginBottom: 8 }}>
                            <span style={{ fontWeight: 500 }}>Blocked by: </span>
                            {selectedTask.blocked_by.map((id) => {
                              const depTask = taskMap.get(id);
                              return (
                                <Tag key={id} color="orange">
                                  #{id.slice(0, 6)}{" "}
                                  {depTask ? `(${depTask.status})` : ""}
                                </Tag>
                              );
                            })}
                          </div>
                        )}
                        {selectedTask.blocks?.length > 0 && (
                          <div>
                            <span style={{ fontWeight: 500 }}>Blocks: </span>
                            {selectedTask.blocks.map((id) => {
                              const depTask = taskMap.get(id);
                              return (
                                <Tag key={id} color="blue">
                                  #{id.slice(0, 6)}{" "}
                                  {depTask ? `(${depTask.status})` : ""}
                                </Tag>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Actions */}
                    <div style={{ marginTop: 24 }}>
                      <Space>
                        <Button
                          icon={<EditOutlined />}
                          onClick={() => {
                            setDetailDrawerVisible(false);
                            handleEdit(selectedTask);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          icon={<RocketOutlined />}
                          onClick={() => handleToggleAutoMode(selectedTask)}
                        >
                          {selectedTask.auto_mode
                            ? "Disable Auto Mode"
                            : "Enable Auto Mode"}
                        </Button>
                        {(selectedTask.status === "failed" ||
                          selectedTask.status === "cancelled") && (
                          <Button
                            icon={<ReloadOutlined />}
                            onClick={() => handleRetry(selectedTask)}
                          >
                            Retry
                          </Button>
                        )}
                      </Space>
                    </div>
                  </div>
                ),
              },
              {
                key: "log",
                label: "Execution Log",
                children: renderExecutionLog(selectedTask.execution_log || []),
              },
            ]}
          />
        )}
      </Drawer>
    </div>
  );
}