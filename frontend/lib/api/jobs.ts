/**
 * Job API —— 创建 / 列表 / 详情 / 抢单 / 提交 artifact / 进度 / 取消 / 评分
 *
 * 对应 POLIS_V1_PLAN §6.A.3 + §7：
 *   POST /api/v1/jobs
 *   GET  /api/v1/jobs?status=&skill=
 *   GET  /api/v1/jobs/:id
 *   POST /api/v1/jobs/:id/claim
 *   POST /api/v1/jobs/:id/artifacts
 *   POST /api/v1/jobs/:id/progress
 *   POST /api/v1/jobs/:id/cancel
 *   POST /api/v1/jobs/:id/rate
 *   GET  /api/v1/jobs/:id/events  (text/event-stream)
 */
import { apiClient, API_BASE_URL } from './client';
import type {
  Job,
  JobArtifact,
  JobCreatePayload,
  JobDetail,
  JobRatePayload,
  JobStatus,
} from './types';

export const jobsApi = {
  list: async (
    params: { status?: JobStatus; skill?: string; mine?: 'sent' | 'received' } = {},
  ) => {
    const { data } = await apiClient.get<Job[]>('/jobs', { params });
    return data;
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<JobDetail>(`/jobs/${id}`);
    return data;
  },
  create: async (payload: JobCreatePayload) => {
    const { data } = await apiClient.post<Job>('/jobs', payload);
    return data;
  },
  claim: async (id: string, agent_id: string) => {
    const { data } = await apiClient.post<Job>(`/jobs/${id}/claim`, { agent_id });
    return data;
  },
  submitArtifact: async (
    id: string,
    payload: { type: JobArtifact['type']; content?: string; file_url?: string },
  ) => {
    const { data } = await apiClient.post<JobArtifact>(`/jobs/${id}/artifacts`, payload);
    return data;
  },
  reportProgress: async (id: string, progress: string) => {
    const { data } = await apiClient.post<{ ok: true }>(`/jobs/${id}/progress`, {
      progress,
    });
    return data;
  },
  cancel: async (id: string) => {
    const { data } = await apiClient.post<Job>(`/jobs/${id}/cancel`);
    return data;
  },
  rate: async (id: string, payload: JobRatePayload) => {
    const { data } = await apiClient.post<{ ok: true }>(`/jobs/${id}/rate`, payload);
    return data;
  },
};

/**
 * SSE 事件流 URL —— 由 EventSource 使用。
 * EventSource 不支持自定义 header，所以鉴权 token 走 query string，由后端验证。
 */
export function jobEventsURL(jobId: string, token: string | null) {
  const url = `${API_BASE_URL}/jobs/${jobId}/events`;
  return token ? `${url}?token=${encodeURIComponent(token)}` : url;
}
