import { create } from 'zustand';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ChatState {
  messages: Message[];
  selectedModel: string;
  serverUrl: string;
  isLoading: boolean;
  liveMode: boolean;

  // Actions
  addMessage: (role: 'user' | 'assistant', content: string) => void;
  setMessages: (messages: Message[]) => void;
  clearMessages: () => void;
  setSelectedModel: (model: string) => void;
  setServerUrl: (url: string) => void;
  setIsLoading: (loading: boolean) => void;
  setLiveMode: (enabled: boolean) => void;
  updateLastMessage: (content: string) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  selectedModel: 'gemini/gemini-2.0-flash',
  serverUrl: 'http://localhost:8501',
  isLoading: false,
  liveMode: true,

  addMessage: (role, content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: Date.now().toString(),
          role,
          content,
          timestamp: Date.now(),
        },
      ],
    })),

  setMessages: (messages) => set({ messages }),
  clearMessages: () => set({ messages: [] }),
  setSelectedModel: (model) => set({ selectedModel: model }),
  setServerUrl: (url) => set({ serverUrl: url }),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setLiveMode: (enabled) => set({ liveMode: enabled }),

  updateLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0) {
        messages[messages.length - 1].content = content;
      }
      return { messages };
    }),
}));
