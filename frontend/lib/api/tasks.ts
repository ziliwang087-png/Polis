/**
 * Task MVP API —— 发布 / 查询 / 接单 / 完成 / 失败 / 评分
 */
import { apiClient } from './client';
import type {
  Task,
  TaskCreatePayload,
  TaskCreateResponse,
  Notification,
  AgentStats,
  Leaderboard,
  LeaderboardResponse,
  TaskDeliverable,
} from './types';

export const tasksApi = {
  list: async (params: { status?: Task['status']; category?: string } = {}) => {
    const { data } = await apiClient.get<Task[]>('/tasks', { params });
    return data;
  },
  pending: async () => {
    const { data } = await apiClient.get<Task[]>('/tasks/pending');
    return data;
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<Task>(`/tasks/${id}`);
    return data;
  },
  create: async (payload: TaskCreatePayload) => {
    const { data } = await apiClient.post<TaskCreateResponse>('/tasks', payload);
    return data;
  },
  claim: async (id: string, agentId?: string) => {
    const body = agentId && agentId.trim() ? { agent_id: agentId } : undefined;
    const { data } = await apiClient.post<Task>(`/tasks/${id}/claim`, body);
    return data;
  },
  start: async (id: string) => {
    const { data } = await apiClient.post<Task>(`/tasks/${id}/start`);
    return data;
  },
  submit: async (id: string, payload: { content?: string; deliverable_url?: string } = {}) => {
    const { data } = await apiClient.post<{ submission_id: string; result_hash: string | null }>(`/tasks/${id}/submit`, payload);
    return data;
  },
  accept: async (id: string) => {
    const { data } = await apiClient.post<Task>(`/tasks/${id}/accept`);
    return data;
  },
  requestRevision: async (id: string) => {
    const { data } = await apiClient.post<Task>(`/tasks/${id}/request-revision`);
    return data;
  },
  cancel: async (id: string) => {
    const { data } = await apiClient.post<Task>(`/tasks/${id}/cancel`);
    return data;
  },
  complete: async (id: string, result?: unknown) => {
    const { data } = await apiClient.post<Task>(`/tasks/${id}/complete`, { result });
    return data;
  },
  fail: async (id: string, error?: string) => {
    const { data } = await apiClient.post<Task>(`/tasks/${id}/fail`, { error });
    return data;
  },
  rate: async (id: string, rating: number, comment?: string) => {
    const { data } = await apiClient.post(`/tasks/${id}/rate`, null, {
      params: { rating, comment }
    });
    return data;
  },
};

export const notificationsApi = {
  list: async (read?: boolean) => {
    const { data } = await apiClient.get<Notification[]>('/notifications', {
      params: { read }
    });
    return data;
  },
  unreadCount: async () => {
    const { data } = await apiClient.get<{ count: number }>('/notifications/unread-count');
    return data;
  },
  markRead: async (id: string) => {
    const { data } = await apiClient.post(`/notifications/${id}/read`);
    return data;
  },
  markAllRead: async () => {
    const { data } = await apiClient.post('/notifications/read-all');
    return data;
  },
};

export const gamificationApi = {
  getAgentStats: async (agentId: string) => {
    const { data } = await apiClient.get<AgentStats>(`/gamification/agents/${agentId}/stats`);
    return data;
  },
  getLeaderboard: async (period: 'week' | 'month' | 'all' = 'all', limit: number = 10) => {
    const { data } = await apiClient.get<Leaderboard>('/gamification/leaderboard', {
      params: { period, limit }
    });
    return data;
  },
};

export const leaderboardApi = {
  xp: async () => {
    const { data } = await apiClient.get<LeaderboardResponse>('/leaderboard/xp');
    return data;
  },
  agents: async () => {
    const { data } = await apiClient.get<LeaderboardResponse>('/leaderboard/agents');
    return data;
  },
  tasks: async () => {
    const { data } = await apiClient.get<LeaderboardResponse>('/leaderboard/tasks');
    return data;
  },
};

export const deliverablesApi = {
  list: async (taskId: string) => {
    const { data } = await apiClient.get<TaskDeliverable[]>(`/tasks/${taskId}/deliverables`);
    return data;
  },
  upload: async (taskId: string, file: File, description?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (description?.trim()) formData.append('description', description.trim());
    const { data } = await apiClient.post<TaskDeliverable>(`/tasks/${taskId}/deliverables`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
  remove: async (taskId: string, deliverableId: string) => {
    const { data } = await apiClient.delete<{ deleted: boolean }>(`/tasks/${taskId}/deliverables/${deliverableId}`);
    return data;
  },
};
