import { useState } from "react";
import {
  Card,
  Button,
  Space,
  Tag,
  Tooltip,
  Badge,
  Progress,
  Dropdown,
  Modal,
  Input,
} from "antd";
import type { MenuProps } from "antd";
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
  MoreOutlined,
  UserOutlined,
  ClockCircleOutlined,
  HistoryOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import type { Task } from "@/api/types/chatroom";
import styles from "./index.module.less";

const { TextArea } = Input;

interface TaskKanbanProps {
  tasks: Task[];
  onCreateTask: () => void;
  onEditTask: (task: Task) => void;
  onViewTask: (task: Task) => void;
  onUpdateStatus: (task: Task, status: Task["status"]) => void;
  onCancelTask: (task: Task, reason?: string) => void;
  onRetryTask: (task: Task) => void;
  onRefresh: () => void;
}

interface KanbanColumn {
  key: string;
  title: string;
  status: Task["status"][];
  color: string;
  icon: React.ReactNode;
}

const columns: KanbanColumn[] = [
  {
    key: "pending",
    title: "Pending",
    status: ["pending"],
    color: "#8c8c8c",
    icon: <ClockCircleOutlined />,
  },
  {
    key: "in_progress",
    title: "In Progress",
    status: ["in_progress"],
    color: "#1890ff",
    icon: <SyncOutlined spin />,
  },
  {
    key: "completed",
    title: "Completed",
    status: ["completed"],
    color: "#52c41a",
    icon: <CheckCircleOutlined />,
  },
  {
    key: "failed",
    title: "Failed",
    status: ["failed"],
    color: "#ff4d4f",
    icon: <CloseCircleOutlined />,
  },
  {
    key: "cancelled",
    title: "Cancelled",
    status: ["cancelled"],
    color: "#faad14",
    icon: <StopOutlined />,
  },
];

export function TaskKanban({
  tasks,
  onCreateTask,
  onEditTask,
  onViewTask,
  onUpdateStatus,
  onCancelTask,
  onRetryTask,
}: TaskKanbanProps) {
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [taskToCancel, setTaskToCancel] = useState<Task | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  const getTasksByStatus = (status: Task["status"][]) => {
    return tasks.filter((task) => status.includes(task.status));
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      high: "#ff4d4f",
      medium: "#faad14",
      low: "#8c8c8c",
    };
    return colors[priority] || "#8c8c8c";
  };

  const handleCancelClick = (task: Task) => {
    setTaskToCancel(task);
    setCancelReason("");
    setCancelModalVisible(true);
  };

  const handleConfirmCancel = () => {
    if (taskToCancel) {
      onCancelTask(taskToCancel, cancelReason || undefined);
      setCancelModalVisible(false);
      setTaskToCancel(null);
    }
  };

  const getTaskMenuItems = (task: Task): MenuProps["items"] => {
    const items: MenuProps["items"] = [];

    items.push({
      key: "view",
      icon: <EyeOutlined />,
      label: "View Details",
      onClick: () => onViewTask(task),
    });

    items.push({
      key: "edit",
      icon: <EditOutlined />,
      label: "Edit",
      onClick: () => onEditTask(task),
    });

    if (task.status === "pending") {
      items.push({
        key: "start",
        icon: <ThunderboltOutlined />,
        label: "Start Task",
        onClick: () => onUpdateStatus(task, "in_progress"),
      });
    }

    if (task.status === "in_progress") {
      items.push({
        key: "complete",
        icon: <CheckCircleOutlined />,
        label: "Mark Complete",
        onClick: () => onUpdateStatus(task, "completed"),
      });
      items.push({
        key: "fail",
        icon: <CloseCircleOutlined />,
        label: "Mark Failed",
        onClick: () => onUpdateStatus(task, "failed"),
      });
    }

    if (task.status === "pending" || task.status === "in_progress") {
      items.push({
        key: "cancel",
        icon: <StopOutlined />,
        label: "Cancel Task",
        danger: true,
        onClick: () => handleCancelClick(task),
      });
    }

    if (
      (task.status === "failed" || task.status === "cancelled") &&
      task.retry_count < task.max_retries
    ) {
      items.push({
        key: "retry",
        icon: <ReloadOutlined />,
        label: `Retry (${task.retry_count}/${task.max_retries})`,
        onClick: () => onRetryTask(task),
      });
    }

    return items;
  };

  const renderTaskCard = (task: Task) => {
    return (
      <Card
        key={task.id}
        className={styles.kanbanCard}
        size="small"
        title={
          <div className={styles.cardTitle}>
            <span className={styles.taskId}>#{task.id.slice(0, 6)}</span>
            {task.auto_mode && (
              <Tooltip title="Auto Mode">
                <Tag icon={<RocketOutlined />} color="purple" style={{ marginLeft: 4 }}>
                  Auto
                </Tag>
              </Tooltip>
            )}
          </div>
        }
        extra={
          <Dropdown menu={{ items: getTaskMenuItems(task) }} trigger={["click"]}>
            <Button type="text" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        }
      >
        <div className={styles.cardContent}>
          <div className={styles.taskSubject}>{task.subject}</div>

          {/* Priority */}
          <div className={styles.cardRow}>
            <Tag color={getPriorityColor(task.priority)}>{task.priority}</Tag>
          </div>

          {/* Owner */}
          <div className={styles.cardRow}>
            {task.owner ? (
              <Tag icon={<UserOutlined />}>{task.owner}</Tag>
            ) : (
              <span style={{ color: "#999" }}>Unassigned</span>
            )}
          </div>

          {/* Progress (for in_progress tasks) */}
          {task.status === "in_progress" && task.progress > 0 && (
            <div className={styles.cardRow}>
              <Progress
                percent={task.progress}
                size="small"
                status={task.progress === 100 ? "success" : "active"}
              />
            </div>
          )}

          {/* Dependencies */}
          {(task.blocked_by?.length > 0 || task.blocks?.length > 0) && (
            <div className={styles.cardRow}>
              {task.blocked_by?.length > 0 && (
                <Tooltip title={`Blocked by ${task.blocked_by.length} task(s)`}>
                  <Tag color="orange">⏳ {task.blocked_by.length}</Tag>
                </Tooltip>
              )}
              {task.blocks?.length > 0 && (
                <Tooltip title={`Blocks ${task.blocks.length} task(s)`}>
                  <Tag color="blue">→ {task.blocks.length}</Tag>
                </Tooltip>
              )}
            </div>
          )}

          {/* Retry count */}
          {task.retry_count > 0 && (
            <div className={styles.cardRow}>
              <Tooltip title={`Retried ${task.retry_count} times`}>
                <Badge count={task.retry_count} size="small" color="orange">
                  <HistoryOutlined style={{ fontSize: 14 }} />
                </Badge>
                <span style={{ marginLeft: 8, color: "#999" }}>
                  {task.retry_count}/{task.max_retries} retries
                </span>
              </Tooltip>
            </div>
          )}

          {/* Timestamp */}
          <div className={styles.cardFooter}>
            <span style={{ color: "#999", fontSize: 12 }}>
              {new Date(task.updated_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </Card>
    );
  };

  const renderColumn = (column: KanbanColumn) => {
    const columnTasks = getTasksByStatus(column.status);

    return (
      <div key={column.key} className={styles.kanbanColumn}>
        <div className={styles.kanbanColumnHeader}>
          <Space>
            <span style={{ color: column.color }}>{column.icon}</span>
            <span className={styles.kanbanColumnTitle}>{column.title}</span>
            <Badge count={columnTasks.length} color={column.color} />
          </Space>
          {column.key === "pending" && (
            <Button
              type="text"
              size="small"
              icon={<PlusOutlined />}
              onClick={onCreateTask}
            />
          )}
        </div>
        <div className={styles.kanbanColumnContent}>
          {columnTasks.length === 0 ? (
            <div className={styles.kanbanEmpty}>No tasks</div>
          ) : (
            columnTasks.map(renderTaskCard)
          )}
        </div>
      </div>
    );
  };

  return (
    <div className={styles.kanbanBoard}>
      {columns.map(renderColumn)}

      {/* Cancel Modal */}
      <Modal
        title="Cancel Task"
        open={cancelModalVisible}
        onOk={handleConfirmCancel}
        onCancel={() => setCancelModalVisible(false)}
        okText="Cancel Task"
        okButtonProps={{ danger: true }}
      >
        <p>Are you sure you want to cancel this task?</p>
        <p style={{ color: "#999", marginBottom: 12 }}>
          The task owner will be notified and dependent tasks will be unblocked.
        </p>
        <TextArea
          placeholder="Optional: Provide a reason for cancellation"
          value={cancelReason}
          onChange={(e) => setCancelReason(e.target.value)}
          rows={3}
        />
      </Modal>
    </div>
  );
}