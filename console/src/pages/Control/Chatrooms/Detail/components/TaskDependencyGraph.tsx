import { useMemo } from "react";
import { Tag, Empty, Space } from "antd";
import {
  LinkOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  StopOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import type { Task } from "@/api/types/chatroom";
import styles from "./index.module.less";

interface TaskDependencyGraphProps {
  tasks: Task[];
  onTaskClick?: (task: Task) => void;
}

interface GraphNode {
  task: Task;
  level: number;
  x: number;
  y: number;
}

interface GraphEdge {
  from: string;
  to: string;
  type: "blocked_by" | "blocks";
}

export function TaskDependencyGraph({
  tasks,
  onTaskClick,
}: TaskDependencyGraphProps) {
  // Build dependency graph
  const { nodes, edges, hasDependencies } = useMemo(() => {
    const taskMap = new Map(tasks.map((t) => [t.id, t]));
    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];

    // Find tasks with dependencies
    const tasksWithDeps = tasks.filter(
      (t) => (t.blocked_by?.length > 0) || (t.blocks?.length > 0)
    );

    if (tasksWithDeps.length === 0) {
      return { nodes: [], edges: [], hasDependencies: false };
    }

    // Build adjacency lists
    const inDegree = new Map<string, number>();
    const adjacency = new Map<string, string[]>();

    tasks.forEach((task) => {
      inDegree.set(task.id, 0);
      adjacency.set(task.id, []);
    });

    tasks.forEach((task) => {
      task.blocked_by?.forEach((depId) => {
        if (taskMap.has(depId)) {
          edges.push({ from: depId, to: task.id, type: "blocked_by" });
          adjacency.get(depId)?.push(task.id);
          inDegree.set(task.id, (inDegree.get(task.id) || 0) + 1);
        }
      });
    });

    // Topological sort to determine levels
    const levels: string[][] = [];
    const queue: string[] = [];
    const visited = new Set<string>();

    // Start with nodes that have no dependencies
    inDegree.forEach((degree, taskId) => {
      if (degree === 0 && tasksWithDeps.some((t) => t.id === taskId)) {
        queue.push(taskId);
      }
    });

    while (queue.length > 0) {
      const level: string[] = [];
      const nextQueue: string[] = [];

      queue.forEach((taskId) => {
        if (visited.has(taskId)) return;
        visited.add(taskId);
        level.push(taskId);

        adjacency.get(taskId)?.forEach((nextId) => {
          const newDegree = (inDegree.get(nextId) || 1) - 1;
          inDegree.set(nextId, newDegree);
          if (newDegree === 0) {
            nextQueue.push(nextId);
          }
        });
      });

      if (level.length > 0) {
        levels.push(level);
      }
      queue.length = 0;
      queue.push(...nextQueue);
    }

    // Calculate positions
    const nodeWidth = 200;
    const nodeHeight = 80;
    const horizontalGap = 100;
    const verticalGap = 30;

    let maxWidth = 0;
    levels.forEach((level) => {
      if (level.length > maxWidth) maxWidth = level.length;
    });

    levels.forEach((level, levelIndex) => {
      const totalWidth = level.length * nodeWidth + (level.length - 1) * verticalGap;
      const startX = (maxWidth * nodeWidth + (maxWidth - 1) * verticalGap - totalWidth) / 2;

      level.forEach((taskId, nodeIndex) => {
        const task = taskMap.get(taskId);
        if (task) {
          nodes.push({
            task,
            level: levelIndex,
            x: startX + nodeIndex * (nodeWidth + verticalGap),
            y: levelIndex * (nodeHeight + horizontalGap),
          });
        }
      });
    });

    return { nodes, edges, hasDependencies: true };
  }, [tasks]);

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: "#8c8c8c",
      in_progress: "#1890ff",
      completed: "#52c41a",
      failed: "#ff4d4f",
      cancelled: "#faad14",
    };
    return colors[status] || "#8c8c8c";
  };

  const getStatusIcon = (status: string) => {
    const icons: Record<string, React.ReactNode> = {
      pending: <ClockCircleOutlined />,
      in_progress: <SyncOutlined spin />,
      completed: <CheckCircleOutlined />,
      failed: <CloseCircleOutlined />,
      cancelled: <StopOutlined />,
    };
    return icons[status] || <ClockCircleOutlined />;
  };

  const getPriorityBorderColor = (priority: string) => {
    const colors: Record<string, string> = {
      high: "#ff4d4f",
      medium: "#faad14",
      low: "#d9d9d9",
    };
    return colors[priority] || "#d9d9d9";
  };

  if (!hasDependencies) {
    return (
      <div className={styles.dependencyGraphEmpty}>
        <Empty description="No task dependencies found">
          <p style={{ color: "#999", fontSize: 12 }}>
            Tasks with dependencies will be shown here as a visual graph.
            Use "Blocked By" when creating tasks to set up dependencies.
          </p>
        </Empty>
      </div>
    );
  }

  const nodeWidth = 200;
  const nodeHeight = 80;
  // Gap values for future layout adjustments
  // const horizontalGap = 100;
  // const verticalGap = 30;

  // Calculate SVG dimensions
  const maxY = Math.max(...nodes.map((n) => n.y), 0);
  const maxX = Math.max(...nodes.map((n) => n.x), 0);

  const svgWidth = maxX + nodeWidth + 50;
  const svgHeight = maxY + nodeHeight + 50;

  return (
    <div className={styles.dependencyGraph}>
      <div className={styles.graphLegend}>
        <Space>
          <span>Legend:</span>
          <Tag color="#8c8c8c">Pending</Tag>
          <Tag color="#1890ff">In Progress</Tag>
          <Tag color="#52c41a">Completed</Tag>
          <Tag color="#ff4d4f">Failed</Tag>
          <Tag color="#faad14">Cancelled</Tag>
        </Space>
        <Space>
          <LinkOutlined /> = Dependency arrow
        </Space>
      </div>

      <div className={styles.graphContainer} style={{ overflow: "auto" }}>
        <svg width={svgWidth} height={svgHeight}>
          {/* Draw edges first (behind nodes) */}
          {edges.map((edge, index) => {
            const fromNode = nodes.find((n) => n.task.id === edge.from);
            const toNode = nodes.find((n) => n.task.id === edge.to);

            if (!fromNode || !toNode) return null;

            const x1 = fromNode.x + nodeWidth / 2;
            const y1 = fromNode.y + nodeHeight;
            const x2 = toNode.x + nodeWidth / 2;
            const y2 = toNode.y;

            return (
              <g key={`edge-${index}`}>
                <defs>
                  <marker
                    id={`arrow-${index}`}
                    markerWidth="10"
                    markerHeight="7"
                    refX="9"
                    refY="3.5"
                    orient="auto"
                  >
                    <polygon
                      points="0 0, 10 3.5, 0 7"
                      fill="#999"
                    />
                  </marker>
                </defs>
                <path
                  d={`M ${x1} ${y1} C ${x1} ${y1 + 40}, ${x2} ${y2 - 40}, ${x2} ${y2}`}
                  stroke="#999"
                  strokeWidth="2"
                  fill="none"
                  markerEnd={`url(#arrow-${index})`}
                />
              </g>
            );
          })}

          {/* Draw nodes */}
          {nodes.map((node) => (
            <g
              key={node.task.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onTaskClick?.(node.task)}
              style={{ cursor: onTaskClick ? "pointer" : "default" }}
            >
              <rect
                width={nodeWidth}
                height={nodeHeight}
                rx={8}
                ry={8}
                fill="#fff"
                stroke={getPriorityBorderColor(node.task.priority)}
                strokeWidth={2}
              />
              <rect
                width={nodeWidth}
                height={4}
                rx={2}
                fill={getStatusColor(node.task.status)}
              />
              <foreignObject x={8} y={12} width={nodeWidth - 16} height={nodeHeight - 20}>
                <div className={styles.graphNodeContent}>
                  <div className={styles.graphNodeId}>
                    #{node.task.id.slice(0, 6)}
                    {node.task.auto_mode && (
                      <Tag color="purple" style={{ marginLeft: 4 }}>Auto</Tag>
                    )}
                  </div>
                  <div className={styles.graphNodeSubject}>
                    {node.task.subject}
                  </div>
                  <div className={styles.graphNodeStatus}>
                    <Tag
                      icon={getStatusIcon(node.task.status)}
                      color={getStatusColor(node.task.status)}
                    >
                      {node.task.status}
                    </Tag>
                    {node.task.owner && (
                      <span style={{ color: "#666", fontSize: 11 }}>
                        {node.task.owner}
                      </span>
                    )}
                  </div>
                </div>
              </foreignObject>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}