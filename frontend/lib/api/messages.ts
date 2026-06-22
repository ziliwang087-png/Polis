import { apiClient } from './client';

export interface Message {
  id: string;
  sender_id: string;
  receiver_id: string;
  content: string;
  read: boolean;
  created_at: string;
}

export interface Conversation {
  conversation_user_id: string;
  conversation_user_name: string | null;
  last_message: string;
  last_message_at: string;
  unread_count: number;
}

export const messagesApi = {
  list: async () => {
    const { data } = await apiClient.get<Conversation[]>('/messages');
    return data;
  },
  unread: async () => {
    const { data } = await apiClient.get<{ count: number }>('/messages/unread');
    return data;
  },
  thread: async (userId: string) => {
    const { data } = await apiClient.get<Message[]>(`/messages/${userId}`);
    return data;
  },
  send: async (receiverId: string, content: string) => {
    const { data } = await apiClient.post<Message>('/messages', {
      receiver_id: receiverId,
      content,
    });
    return data;
  },
  markRead: async (messageId: string) => {
    const { data } = await apiClient.patch<Message>(`/messages/${messageId}/read`);
    return data;
  },
};
