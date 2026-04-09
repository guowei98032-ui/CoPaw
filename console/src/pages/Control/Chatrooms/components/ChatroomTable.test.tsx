// ChatroomTable Component Tests
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatroomTable } from "../components/ChatroomTable";
import type { ChatRoom } from "@/api/types/chatroom";

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

// Mock react-i18next
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

// Mock agent store
vi.mock("@/stores/agentStore", () => ({
  useAgentStore: () => ({
    agents: [
      { id: "lead-1", name: "Team Lead" },
      { id: "worker-a", name: "Frontend Dev" },
      { id: "worker-b", name: "Backend Dev" },
      { id: "worker-c", name: "QA Engineer" },
    ],
  }),
}));

describe("ChatroomTable", () => {
  const mockOnEdit = vi.fn();
  const mockOnDelete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render empty state when no chatrooms", () => {
    render(
      <ChatroomTable
        chatrooms={[]}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("chatroom.name")).toBeInTheDocument();
  });

  it("should render chatroom list with lead agent only", () => {
    const chatrooms: ChatRoom[] = [
      {
        id: "room-1",
        name: "Solo Team",
        user_id: "user-1",
        lead_agent_id: "lead-1",
        agent_ids: [],
        agent_roles: {},
        sessions: {},
        layout: "tiles",
        matrix_room_id: null,
        matrix_alias: null,
        created_at: "2026-04-08T10:00:00",
        updated_at: "2026-04-08T10:00:00",
      },
    ];

    render(
      <ChatroomTable
        chatrooms={chatrooms}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("Solo Team")).toBeInTheDocument();
    expect(screen.getByText("Team Lead")).toBeInTheDocument(); // Lead agent name
    expect(screen.getByText("No agents")).toBeInTheDocument(); // No participating agents
  });

  it("should render chatroom with multiple agents", () => {
    const chatrooms: ChatRoom[] = [
      {
        id: "team-room",
        name: "Development Team",
        user_id: "user-1",
        lead_agent_id: "lead-1",
        agent_ids: ["worker-a", "worker-b", "worker-c"],
        agent_roles: {
          "lead-1": "Team Lead",
          "worker-a": "Frontend Dev",
          "worker-b": "Backend Dev",
          "worker-c": "QA Engineer",
        },
        sessions: {},
        layout: "tiles",
        matrix_room_id: null,
        matrix_alias: null,
        created_at: "2026-04-08T10:00:00",
        updated_at: "2026-04-08T10:00:00",
      },
    ];

    render(
      <ChatroomTable
        chatrooms={chatrooms}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("Development Team")).toBeInTheDocument();
    expect(screen.getByText("Team Lead")).toBeInTheDocument();
    expect(screen.getByText("Frontend Dev")).toBeInTheDocument();
    expect(screen.getByText("Backend Dev")).toBeInTheDocument();
    expect(screen.getByText("QA Engineer")).toBeInTheDocument();
  });

  it("should call onEdit when edit button is clicked", () => {
    const chatroom: ChatRoom = {
      id: "room-1",
      name: "Test Room",
      user_id: "user-1",
      lead_agent_id: "lead-1",
      agent_ids: ["worker-a"],
      agent_roles: {},
      sessions: {},
      layout: "tiles",
      matrix_room_id: null,
      matrix_alias: null,
      created_at: "2026-04-08T10:00:00",
      updated_at: "2026-04-08T10:00:00",
    };

    render(
      <ChatroomTable
        chatrooms={[chatroom]}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    const editButton = screen.getByRole("button", { name: /edit/i });
    fireEvent.click(editButton);

    expect(mockOnEdit).toHaveBeenCalledWith(chatroom);
  });

  it("should call onDelete when delete button is clicked", () => {
    const chatroom: ChatRoom = {
      id: "room-1",
      name: "Test Room",
      user_id: "user-1",
      lead_agent_id: "lead-1",
      agent_ids: [],
      agent_roles: {},
      sessions: {},
      layout: "tiles",
      matrix_room_id: null,
      matrix_alias: null,
      created_at: "2026-04-08T10:00:00",
      updated_at: "2026-04-08T10:00:00",
    };

    render(
      <ChatroomTable
        chatrooms={[chatroom]}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    const deleteButton = screen.getByRole("button", { name: /delete/i });
    fireEvent.click(deleteButton);

    expect(mockOnDelete).toHaveBeenCalledWith("room-1");
  });

  it("should navigate to chatroom detail when name is clicked", () => {
    const chatroom: ChatRoom = {
      id: "room-1",
      name: "Test Room",
      user_id: "user-1",
      lead_agent_id: "lead-1",
      agent_ids: [],
      agent_roles: {},
      sessions: {},
      layout: "tiles",
      matrix_room_id: null,
      matrix_alias: null,
      created_at: "2026-04-08T10:00:00",
      updated_at: "2026-04-08T10:00:00",
    };

    render(
      <ChatroomTable
        chatrooms={[chatroom]}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    const roomLink = screen.getByText("Test Room");
    fireEvent.click(roomLink);

    expect(mockNavigate).toHaveBeenCalledWith("/chatrooms/room-1");
  });

  it("should show loading state", () => {
    render(
      <ChatroomTable
        chatrooms={[]}
        loading={true}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    // Ant Design Table shows loading spinner
    expect(document.querySelector(".ant-spin")).toBeInTheDocument();
  });

  it("should display matrix indicator for linked rooms", () => {
    const chatroom: ChatRoom = {
      id: "room-1",
      name: "Matrix Room",
      user_id: "user-1",
      lead_agent_id: "lead-1",
      agent_ids: [],
      agent_roles: {},
      sessions: {},
      layout: "tiles",
      matrix_room_id: "!room:matrix.org",
      matrix_alias: "#dev-team:matrix.org",
      created_at: "2026-04-08T10:00:00",
      updated_at: "2026-04-08T10:00:00",
    };

    render(
      <ChatroomTable
        chatrooms={[chatroom]}
        loading={false}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    // The ApiOutlined icon should be present
    const matrixIcon = document.querySelector('[style*="color: rgb(82, 196, 26)"]');
    expect(matrixIcon).toBeInTheDocument();
  });
});