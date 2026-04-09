import { create } from "zustand";
import { chatroomApi } from "../api/modules/chatroom";
import type { ChatRoom } from "../api/types/chatroom";

interface ChatroomStore {
  chatrooms: ChatRoom[];
  loading: boolean;
  selectedChatroomId: string | null;

  // Actions
  setChatrooms: (chatrooms: ChatRoom[]) => void;
  setSelectedChatroomId: (id: string | null) => void;
  addChatroom: (chatroom: ChatRoom) => void;
  updateChatroom: (chatroom: ChatRoom) => void;
  removeChatroom: (id: string) => void;
  loadChatrooms: (userId?: string) => Promise<void>;
}

export const useChatroomStore = create<ChatroomStore>((set) => ({
  chatrooms: [],
  loading: false,
  selectedChatroomId: null,

  setChatrooms: (chatrooms) => set({ chatrooms }),

  setSelectedChatroomId: (id) => set({ selectedChatroomId: id }),

  addChatroom: (chatroom) =>
    set((state) => ({
      chatrooms: [chatroom, ...state.chatrooms],
    })),

  updateChatroom: (chatroom) =>
    set((state) => ({
      chatrooms: state.chatrooms.map((c) =>
        c.id === chatroom.id ? chatroom : c,
      ),
    })),

  removeChatroom: (id) =>
    set((state) => ({
      chatrooms: state.chatrooms.filter((c) => c.id !== id),
    })),

  loadChatrooms: async (userId?: string) => {
    set({ loading: true });
    try {
      const data = await chatroomApi.listChatRooms(userId);
      set({ chatrooms: data, loading: false });
    } catch (error) {
      console.error("Failed to load chatrooms:", error);
      set({ chatrooms: [], loading: false });
    }
  },
}));
