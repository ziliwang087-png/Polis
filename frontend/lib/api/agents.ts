/**
 * Agent API —— 注册 / 列表 / 详情 / 心跳 / 删除
 *
 * 对应 POLIS_V1_PLAN §6.A.4：
 *   POST /api/v1/agents
 *   GET  /api/v1/agents          —— 平台所有 agent
 *   GET  /api/v1/agents/me       —— 当前用户的 agent
 *   GET  /api/v1/agents/:id
 *   POST /api/v1/agents/:id/heartbeat
 *   DELETE /api/v1/agents/:id
 */
import { apiClient } from './client';
import type { Agent, AgentCreatePayload } from './types';

export const agentsApi = {
  list: async (params: { mine?: boolean; skill?: string } = {}) => {
    const { data } = await apiClient.get<Agent[]>('/agents', { params });
    return data;
  },
  listMine: async () => {
    const { data } = await apiClient.get<Agent[]>('/agents', {
      params: { mine: true },
    });
    return data;
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<Agent>(`/agents/${id}`);
    return data;
  },
  create: async (payload: AgentCreatePayload) => {
    const { data } = await apiClient.post<Agent>('/agents', payload);
    return data;
  },
  heartbeat: async (id: string, status: Agent['status'] = 'online') => {
    const { data } = await apiClient.post<Agent>(`/agents/${id}/heartbeat`, { status });
    return data;
  },
  remove: async (id: string) => {
    const { data } = await apiClient.delete<{ ok: true }>(`/agents/${id}`);
    return data;
  },
};
