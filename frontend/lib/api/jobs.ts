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
 *
 * 兼容层注解：
 *   - 后端 GET /jobs/:id 把 artifacts/events/rating 平铺在 job 顶层，前端把它
 *     重组成 JobDetail 嵌套结构。
 *   - 后端 JobResponse 只返回 from_user_id / to_agent_id（UUID），不 join；
 *     前端的 from_user/to_agent 字段始终是 undefined，UI 用 UUID 前 8 位兜底。
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

export interface JobListParams {
  status?: JobStatus;
  skill?: string;
  /** 后端过滤：sent = 我发的；received = 我的 agents 抢到的 */
  mine?: 'sent' | 'received';
}

export const jobsApi = {
  list: async (params: JobListParams = {}) => {
    const { data } = await apiClient.get<Job[]>('/jobs', { params });
    return data;
  },
  get: async (id: string): Promise<JobDetail> => {
    const { data } = await apiClient.get<Record<string, unknown>>(`/jobs/${id}`);
    // 后端 GET /jobs/:id 把 artifacts/events/rating 平铺在 job 顶层，
    // 前端期望嵌套结构，这里重组一次
    const { artifacts, events, rating, ...job } = data as Record<string, unknown>;
    return {
      job: job as unknown as JobDetail['job'],
      artifacts: (artifacts as JobDetail['artifacts']) ?? [],
      events: (events as JobDetail['events']) ?? [],
      rating: (rating as JobDetail['rating']) ?? null,
    } as JobDetail;
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
    const { data } = await apiClient.post<Job>(`/jobs/${id}/artifacts`, payload);
    return data;
  },
  reportProgress: async (id: string, progress: string) => {
    const { data } = await apiClient.post<Job>(`/jobs/${id}/progress`, {
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
 */
export function jobEventsURL(jobId: string) {
  return `${API_BASE_URL}/jobs/${jobId}/events`;
}
