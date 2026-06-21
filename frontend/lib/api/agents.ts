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
  /**
   * BYOA install token —— 给 agent.py 的"一行命令"用。
   * 后端返回长效 JWT 打包成 base64 bundle + 现成的 install_command。
   * LLM key 不在 bundle 里，由用户本机 env 提供。
   */
  issueInstallToken: async (id: string) => {
    const { data } = await apiClient.post<{
      install_token: string;
      agent_id: string;
      agent_name: string;
      expires_in_days: number;
      install_command: string;
    }>(`/agents/${id}/install-token`);
    return data;
  },
};
