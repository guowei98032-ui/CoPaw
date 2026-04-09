// ChatRoom Store Tests
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useChatroomStore } from "./chatroomStore";
import type { ChatRoom } from "../api/types/chatroom";

// Mock the API module
vi.mock("../api/modules/chatroom", () => ({
  chatroomApi: {
    listChatRooms: vi.fn(),
  },
}));

import { chatroomApi } from "../api/modules/chatroom";

describe("ChatroomStore", () => {
  beforeEach(() => {
    // Reset store state before each test
    useChatroomStore.setState({
      chatrooms: [],
      loading: false,
      selectedChatroomId: null,
    });
    vi.clearAllMocks();
  });

  it("should have initial state", () => {
    const state = useChatroomStore.getState();
    expect(state.chatrooms).toEqual([]);
    expect(state.loading).toBe(false);
    expect(state.selectedChatroomId).toBeNull();
  });

  it("should set chatrooms", () => {
    const mockChatrooms: ChatRoom[] = [
      {
        id: "room-1",
        name: "Test Room",
        user_id: "user-1",
        lead_agent_id: "lead-1",
        agent_ids: ["worker-1", "worker-2"],
        agent_roles: { "lead-1": "Team Lead", "worker-1": "Developer" },
        sessions: {},
        layout: "tiles",
        matrix_room_id: null,
        matrix_alias: null,
        created_at: "2026-04-08T10:00:00",
        updated_at: "2026-04-08T10:00:00",
      },
    ];

    useChatroomStore.getState().setChatrooms(mockChatrooms);

    const state = useChatroomStore.getState();
    expect(state.chatrooms).toEqual(mockChatrooms);
  });

  it("should add a chatroom", () => {
    const existingRoom: ChatRoom = {
      id: "room-1",
      name: "Existing Room",
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

    useChatroomStore.getState().setChatrooms([existingRoom]);

    const newRoom: ChatRoom = {
      id: "room-2",
      name: "New Room",
      user_id: "user-1",
      lead_agent_id: "lead-2",
      agent_ids: ["worker-a"],
      agent_roles: {},
      sessions: {},
      layout: "tabs",
      matrix_room_id: null,
      matrix_alias: null,
      created_at: "2026-04-08T11:00:00",
      updated_at: "2026-04-08T11:00:00",
    };

    useChatroomStore.getState().addChatroom(newRoom);

    const state = useChatroomStore.getState();
    expect(state.chatrooms).toHaveLength(2);
    expect(state.chatrooms[0]).toEqual(newRoom); // Added at beginning
    expect(state.chatrooms[1]).toEqual(existingRoom);
  });

  it("should update a chatroom", () => {
    const room: ChatRoom = {
      id: "room-1",
      name: "Original Name",
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

    useChatroomStore.getState().setChatrooms([room]);

    const updatedRoom: ChatRoom = {
      ...room,
      name: "Updated Name",
      agent_ids: ["worker-1"],
    };

    useChatroomStore.getState().updateChatroom(updatedRoom);

    const state = useChatroomStore.getState();
    expect(state.chatrooms[0].name).toBe("Updated Name");
    expect(state.chatrooms[0].agent_ids).toEqual(["worker-1"]);
  });

  it("should remove a chatroom", () => {
    const room1: ChatRoom = {
      id: "room-1",
      name: "Room 1",
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

    const room2: ChatRoom = {
      id: "room-2",
      name: "Room 2",
      user_id: "user-1",
      lead_agent_id: "lead-2",
      agent_ids: [],
      agent_roles: {},
      sessions: {},
      layout: "tiles",
      matrix_room_id: null,
      matrix_alias: null,
      created_at: "2026-04-08T10:00:00",
      updated_at: "2026-04-08T10:00:00",
    };

    useChatroomStore.getState().setChatrooms([room1, room2]);
    useChatroomStore.getState().removeChatroom("room-1");

    const state = useChatroomStore.getState();
    expect(state.chatrooms).toHaveLength(1);
    expect(state.chatrooms[0].id).toBe("room-2");
  });

  it("should set selected chatroom id", () => {
    useChatroomStore.getState().setSelectedChatroomId("room-1");

    const state = useChatroomStore.getState();
    expect(state.selectedChatroomId).toBe("room-1");
  });

  it("should load chatrooms from API", async () => {
    const mockChatrooms: ChatRoom[] = [
      {
        id: "room-1",
        name: "API Room",
        user_id: "user-1",
        lead_agent_id: "lead-1",
        agent_ids: ["worker-1", "worker-2"],
        agent_roles: {},
        sessions: {},
        layout: "tiles",
        matrix_room_id: null,
        matrix_alias: null,
        created_at: "2026-04-08T10:00:00",
        updated_at: "2026-04-08T10:00:00",
      },
    ];

    vi.mocked(chatroomApi.listChatRooms).mockResolvedValue(mockChatrooms);

    await useChatroomStore.getState().loadChatrooms("user-1");

    const state = useChatroomStore.getState();
    expect(state.chatrooms).toEqual(mockChatrooms);
    expect(state.loading).toBe(false);
    expect(chatroomApi.listChatRooms).toHaveBeenCalledWith("user-1");
  });

  it("should handle load chatrooms error", async () => {
    vi.mocked(chatroomApi.listChatRooms).mockRejectedValue(new Error("API Error"));

    await useChatroomStore.getState().loadChatrooms();

    const state = useChatroomStore.getState();
    expect(state.chatrooms).toEqual([]);
    expect(state.loading).toBe(false);
  });
});