/**
 * 任务详情 /jobs/[id]
 *
 * - useQuery 拉 JobDetail
 * - EventSource 订阅 /jobs/{id}/events，收到事件 invalidate 缓存
 * - 根据用户角色（发起人 / 抢单 agent 的 owner / 路人）显示不同操作
 *
 * 严格按规格：
 *   - 状态时间线
 *   - 抢单：选自己有相应 skill 的 agent
 *   - 提交结果：text / json / file_url
 *   - 评分：1-5 星 + feedback
 */
'use client';

import { use, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { jobsApi, jobEventsURL } from '@/lib/api/jobs';
import { agentsApi } from '@/lib/api/agents';
import { useAuthStore } from '@/lib/store';
import Loading from '@/components/Loading';
import { JOB_STATUS_META, formatDateTime, relativeTime } from '@/lib/format';
import type { JobEvent, ArtifactType, JobEventType, JobStatus } from '@/lib/api/types';
import {
  RocketIcon,
  CheckIcon,
  ClockIcon,
  StarIcon,
  BotIcon,
  PinIcon,
  TerminalIcon,
} from '@/components/icons/Icon';

const EVENT_LABEL: Record<JobEventType, string> = {
  created: '任务发布',
  claimed: 'agent 抢单',
  progress: '进度更新',
  delivered: '结果交付',
  rated: '已评分',
  canceled: '已取消',
};

export default function JobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { token, user, isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();

  const detail = useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(id),
  });

  const myAgents = useQuery({
    queryKey: ['agents', 'mine'],
    queryFn: () => agentsApi.listMine(),
    enabled: isAuthenticated(),
  });

  /* ---------- SSE 订阅 ---------- */
  useEffect(() => {
    if (!id) return;
    const es = new EventSource(jobEventsURL(id, token));
    const refresh = () => {
      queryClient.invalidateQueries({ queryKey: ['job', id] });
    };
    es.onmessage = refresh;
    // 后端可能用 named events
    (['created', 'claimed', 'progress', 'delivered', 'rated', 'canceled'] as JobEventType[]).forEach(
      (type) => es.addEventListener(type, refresh),
    );
    es.onerror = () => {
      // 静默 —— EventSource 会自动重连
    };
    return () => es.close();
  }, [id, token, queryClient]);

  /* ---------- mutations ---------- */
  const claimMutation = useMutation({
    mutationFn: (agentId: string) => jobsApi.claim(id, agentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['job', id] }),
  });
  const cancelMutation = useMutation({
    mutationFn: () => jobsApi.cancel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['job', id] }),
  });
  const submitArtifactMutation = useMutation({
    mutationFn: (payload: { type: ArtifactType; content?: string; file_url?: string }) =>
      jobsApi.submitArtifact(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['job', id] }),
  });
  const progressMutation = useMutation({
    mutationFn: (progress: string) => jobsApi.reportProgress(id, progress),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['job', id] }),
  });
  const rateMutation = useMutation({
    mutationFn: (payload: { stars: number; feedback?: string }) =>
      jobsApi.rate(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['job', id] }),
  });

  if (detail.isLoading) return <Loading />;
  if (detail.isError || !detail.data) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <div className="bg-white rounded-2xl p-8 text-center">
          <div className="font-medium text-gray-900 mb-2">任务加载失败</div>
          <Link href="/" className="text-blue-600 hover:underline text-sm">
            返回任务广场
          </Link>
        </div>
      </div>
    );
  }

  const { job, artifacts, rating, events } = detail.data;
  const statusMeta = JOB_STATUS_META[job.status];
  const isOwner = user?.id === job.from_user_id;
  // 我是不是抢单 agent 的所有者？
  const claimingAgent = (myAgents.data ?? []).find((a) => a.id === job.to_agent_id);
  const isAgentOwner = !!claimingAgent;
  const eligibleAgents = (myAgents.data ?? []).filter((a) =>
    a.skills.some((s) => s.skill_id === job.required_skill),
  );

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 主区 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 任务卡片 */}
          <div className="bg-white rounded-3xl p-7 shadow-sm">
            <div className="flex items-start justify-between gap-4 mb-3">
              <h1 className="text-2xl font-bold text-gray-900 leading-tight">
                {job.title}
              </h1>
              <span
                className="px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap"
                style={{ background: statusMeta.bg, color: statusMeta.color }}
              >
                {statusMeta.label}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 mb-5">
              <span>
                发起人：
                <span className="text-gray-700 font-medium">
                  {job.from_user?.display_name ||
                    job.from_user?.username ||
                    job.from_user_id.slice(0, 8)}
                </span>
              </span>
              <span>·</span>
              <span>{formatDateTime(job.created_at)}</span>
              <span>·</span>
              <span
                className="px-2 py-0.5 rounded-md font-medium"
                style={{ background: '#eef2ff', color: '#4338ca' }}
              >
                #{job.required_skill}
              </span>
            </div>

            <h3 className="text-sm font-semibold text-gray-700 mb-2">任务描述</h3>
            <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed bg-gray-50 rounded-xl p-4">
              {job.description}
            </div>

            {job.attachments.length > 0 && (
              <div className="mt-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                  <PinIcon size={15} strokeWidth={1.8} />
                  附件（{job.attachments.length}）
                </h3>
                <div className="space-y-2">
                  {job.attachments.map((a, i) => (
                    <a
                      key={i}
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5 text-sm hover:bg-gray-100 transition-colors"
                    >
                      <span className="font-medium text-gray-900 truncate">
                        {a.filename}
                      </span>
                      <span className="text-xs text-gray-500 ml-3 truncate">{a.mime}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {job.progress && (
              <div className="mt-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                  <TerminalIcon size={15} strokeWidth={1.8} />
                  最新进度
                </h3>
                <div className="text-sm text-gray-700 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3">
                  {job.progress}
                </div>
              </div>
            )}
          </div>

          {/* 抢单 / 操作区 —— 根据角色显示 */}
          <ActionPanel
            jobStatus={job.status}
            isOwner={isOwner}
            isAgentOwner={isAgentOwner}
            isLoggedIn={isAuthenticated()}
            eligibleAgents={eligibleAgents.map((a) => ({
              id: a.id,
              label: a.display_name || a.name,
            }))}
            onClaim={(agentId) => claimMutation.mutate(agentId)}
            onCancel={() => cancelMutation.mutate()}
            onSubmitArtifact={(payload) => submitArtifactMutation.mutate(payload)}
            onProgress={(text) => progressMutation.mutate(text)}
            claimPending={claimMutation.isPending}
            cancelPending={cancelMutation.isPending}
            submitPending={submitArtifactMutation.isPending}
            progressPending={progressMutation.isPending}
            requiredSkill={job.required_skill}
          />

          {/* 交付物 */}
          {artifacts.length > 0 && (
            <div className="bg-white rounded-3xl p-7 shadow-sm">
              <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                <CheckIcon size={18} className="text-green-600" strokeWidth={2} />
                交付物（{artifacts.length}）
              </h2>
              <div className="space-y-4">
                {artifacts.map((a) => (
                  <div key={a.id} className="border border-gray-100 rounded-2xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span
                        className="px-2 py-0.5 rounded-md text-[11px] font-semibold uppercase"
                        style={{ background: '#eef2ff', color: '#4338ca' }}
                      >
                        {a.type}
                      </span>
                      <span className="text-xs text-gray-400">
                        {relativeTime(a.created_at)}
                      </span>
                    </div>
                    {a.content && (
                      <pre className="text-sm text-gray-800 whitespace-pre-wrap bg-gray-50 rounded-lg p-3 leading-relaxed font-sans">
                        {a.content}
                      </pre>
                    )}
                    {a.file_url && (
                      <a
                        href={a.file_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 hover:underline text-sm break-all"
                      >
                        下载文件 → {a.file_url}
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 评分（owner 在 completed 状态下评分；其他人看已评分） */}
          {job.status === 'completed' && (
            <RatingSection
              isOwner={isOwner}
              existingRating={rating}
              pending={rateMutation.isPending}
              onRate={(stars, feedback) =>
                rateMutation.mutate({ stars, feedback: feedback || undefined })
              }
            />
          )}
        </div>

        {/* 侧栏：状态时间线 */}
        <aside className="space-y-6">
          <div className="bg-white rounded-3xl p-6 shadow-sm">
            <h2 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-1.5">
              <ClockIcon size={16} strokeWidth={2} />
              事件时间线
            </h2>
            {events.length === 0 ? (
              <div className="text-sm text-gray-500">暂无事件</div>
            ) : (
              <ol className="space-y-3 border-l-2 border-gray-100 pl-4">
                {events.map((evt) => (
                  <TimelineItem key={evt.id} event={evt} />
                ))}
              </ol>
            )}
          </div>

          {job.to_agent && (
            <div className="bg-white rounded-3xl p-6 shadow-sm">
              <h2 className="text-base font-bold text-gray-900 mb-3 flex items-center gap-1.5">
                <BotIcon size={16} strokeWidth={2} />
                抢单 Agent
              </h2>
              <Link
                href={`/agents/${job.to_agent.id}`}
                className="block text-sm font-medium text-blue-600 hover:underline"
              >
                {job.to_agent.display_name || job.to_agent.name}
              </Link>
              <div className="text-xs text-gray-500 mt-1">
                抢单时间：{formatDateTime(job.claimed_at)}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

/* ============== 子组件 ============== */

function TimelineItem({ event }: { event: JobEvent }) {
  return (
    <li className="relative">
      <span className="absolute -left-[22px] top-1.5 w-3 h-3 rounded-full bg-blue-500 ring-4 ring-white" />
      <div className="text-sm font-medium text-gray-800">
        {EVENT_LABEL[event.event_type] || event.event_type}
      </div>
      <div className="text-xs text-gray-500">{formatDateTime(event.created_at)}</div>
      {event.event_type === 'progress' &&
        typeof (event.payload as { progress?: string })?.progress === 'string' && (
          <div className="text-xs text-gray-600 mt-1 bg-gray-50 rounded-md px-2 py-1">
            {(event.payload as { progress: string }).progress}
          </div>
        )}
    </li>
  );
}

interface ActionPanelProps {
  jobStatus: JobStatus;
  isOwner: boolean;
  isAgentOwner: boolean;
  isLoggedIn: boolean;
  eligibleAgents: Array<{ id: string; label: string }>;
  requiredSkill: string;
  onClaim: (agentId: string) => void;
  onCancel: () => void;
  onSubmitArtifact: (payload: {
    type: ArtifactType;
    content?: string;
    file_url?: string;
  }) => void;
  onProgress: (text: string) => void;
  claimPending: boolean;
  cancelPending: boolean;
  submitPending: boolean;
  progressPending: boolean;
}

function ActionPanel(props: ActionPanelProps) {
  const {
    jobStatus,
    isOwner,
    isAgentOwner,
    isLoggedIn,
    eligibleAgents,
    requiredSkill,
    onClaim,
    onCancel,
    onSubmitArtifact,
    onProgress,
    claimPending,
    cancelPending,
    submitPending,
    progressPending,
  } = props;

  const [selectedAgent, setSelectedAgent] = useState('');
  const [progressText, setProgressText] = useState('');
  const [artifactType, setArtifactType] = useState<ArtifactType>('text');
  const [artifactContent, setArtifactContent] = useState('');
  const [artifactFileUrl, setArtifactFileUrl] = useState('');

  // owner 视角：取消按钮 + 提示
  // agent owner 视角：提交结果 + 进度
  // 路人 + 有匹配 agent：抢单
  const canClaim =
    isLoggedIn && !isOwner && jobStatus === 'submitted' && eligibleAgents.length > 0;
  const canSubmitArtifact =
    isAgentOwner && (jobStatus === 'claimed' || jobStatus === 'working');
  const canCancel =
    isOwner && (jobStatus === 'submitted' || jobStatus === 'claimed' || jobStatus === 'working');

  if (!canClaim && !canSubmitArtifact && !canCancel) {
    if (jobStatus === 'submitted' && isLoggedIn && !isOwner && eligibleAgents.length === 0) {
      return (
        <div className="bg-white rounded-3xl p-6 shadow-sm text-sm text-gray-500">
          你目前没有声明 <code className="bg-gray-100 px-1.5 rounded">{requiredSkill}</code>{' '}
          skill 的 agent，无法抢单。{' '}
          <Link href="/agents/new" className="text-blue-600 hover:underline">
            去注册一个 →
          </Link>
        </div>
      );
    }
    return null;
  }

  return (
    <div className="bg-white rounded-3xl p-7 shadow-sm space-y-5">
      <h2 className="text-lg font-bold text-gray-900">操作</h2>

      {canClaim && (
        <div className="space-y-3">
          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">
              选择你的 agent 抢单
            </span>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none bg-white"
            >
              <option value="">选择一个 agent…</option>
              {eligibleAgents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() => selectedAgent && onClaim(selectedAgent)}
            disabled={!selectedAgent || claimPending}
            className="px-5 py-3 rounded-xl text-white font-semibold transition-all hover:shadow-md disabled:opacity-60 flex items-center gap-2"
            style={{ background: '#5b8def' }}
          >
            <RocketIcon size={16} strokeWidth={2} />
            {claimPending ? '抢单中…' : '抢单'}
          </button>
        </div>
      )}

      {canSubmitArtifact && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-800 mb-2">推送进度</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={progressText}
                onChange={(e) => setProgressText(e.target.value)}
                placeholder="例如：正在调 LLM…"
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm"
              />
              <button
                onClick={() => {
                  if (progressText.trim()) {
                    onProgress(progressText.trim());
                    setProgressText('');
                  }
                }}
                disabled={progressPending || !progressText.trim()}
                className="px-4 rounded-xl bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-40"
              >
                {progressPending ? '推送中…' : '推送'}
              </button>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-4">
            <h3 className="text-sm font-semibold text-gray-800 mb-2">提交交付物</h3>
            <div className="space-y-2">
              <select
                value={artifactType}
                onChange={(e) => setArtifactType(e.target.value as ArtifactType)}
                className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm bg-white"
              >
                <option value="text">text</option>
                <option value="json">json</option>
                <option value="image">image (file_url)</option>
                <option value="file">file (file_url)</option>
              </select>

              {(artifactType === 'text' || artifactType === 'json') && (
                <textarea
                  rows={6}
                  value={artifactContent}
                  onChange={(e) => setArtifactContent(e.target.value)}
                  placeholder={artifactType === 'json' ? '{"…": "…"}' : '交付内容'}
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm font-mono resize-y"
                />
              )}

              {(artifactType === 'image' || artifactType === 'file') && (
                <input
                  type="url"
                  value={artifactFileUrl}
                  onChange={(e) => setArtifactFileUrl(e.target.value)}
                  placeholder="文件 URL"
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm"
                />
              )}

              <button
                onClick={() => {
                  if (artifactType === 'text' || artifactType === 'json') {
                    if (!artifactContent.trim()) return;
                    onSubmitArtifact({ type: artifactType, content: artifactContent.trim() });
                    setArtifactContent('');
                  } else {
                    if (!artifactFileUrl.trim()) return;
                    onSubmitArtifact({ type: artifactType, file_url: artifactFileUrl.trim() });
                    setArtifactFileUrl('');
                  }
                }}
                disabled={submitPending}
                className="px-5 py-3 rounded-xl text-white font-semibold transition-all hover:shadow-md disabled:opacity-60 flex items-center gap-2"
                style={{ background: '#5b8def' }}
              >
                <CheckIcon size={16} strokeWidth={2} />
                {submitPending ? '提交中…' : '提交交付物'}
              </button>
            </div>
          </div>
        </div>
      )}

      {canCancel && (
        <div className="border-t border-gray-100 pt-4">
          <button
            onClick={() => {
              if (confirm('确定取消这个任务？此操作不可撤销。')) onCancel();
            }}
            disabled={cancelPending}
            className="px-5 py-2.5 rounded-xl text-red-600 font-medium hover:bg-red-50 transition-colors text-sm disabled:opacity-60"
          >
            {cancelPending ? '取消中…' : '取消任务'}
          </button>
        </div>
      )}
    </div>
  );
}

function RatingSection({
  isOwner,
  existingRating,
  onRate,
  pending,
}: {
  isOwner: boolean;
  existingRating: { stars: number; feedback: string | null } | null;
  onRate: (stars: number, feedback: string) => void;
  pending: boolean;
}) {
  const [stars, setStars] = useState(0);
  const [feedback, setFeedback] = useState('');

  const display = useMemo(() => existingRating, [existingRating]);

  if (display) {
    return (
      <div className="bg-white rounded-3xl p-7 shadow-sm">
        <h2 className="text-lg font-bold text-gray-900 mb-3">评分</h2>
        <div className="flex items-center gap-1 mb-2">
          {[1, 2, 3, 4, 5].map((n) => (
            <StarIcon
              key={n}
              size={22}
              filled={n <= display.stars}
              className={n <= display.stars ? 'text-amber-400' : 'text-gray-200'}
            />
          ))}
          <span className="ml-2 text-sm text-gray-700 font-medium">{display.stars} / 5</span>
        </div>
        {display.feedback && (
          <div className="text-sm text-gray-600 bg-gray-50 rounded-xl p-3 whitespace-pre-wrap">
            {display.feedback}
          </div>
        )}
      </div>
    );
  }

  if (!isOwner) return null;

  return (
    <div className="bg-white rounded-3xl p-7 shadow-sm">
      <h2 className="text-lg font-bold text-gray-900 mb-3">为这次交付评分</h2>
      <div className="flex items-center gap-1 mb-3">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => setStars(n)}
            aria-label={`${n} 星`}
            className="p-1"
          >
            <StarIcon
              size={26}
              filled={n <= stars}
              className={n <= stars ? 'text-amber-400' : 'text-gray-300 hover:text-amber-300'}
            />
          </button>
        ))}
        <span className="ml-2 text-sm text-gray-500">{stars > 0 ? `${stars} / 5` : '请选择'}</span>
      </div>
      <textarea
        rows={3}
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        placeholder="可选反馈：哪里做得好 / 哪里可以改进"
        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm resize-y"
      />
      <button
        onClick={() => stars > 0 && onRate(stars, feedback.trim())}
        disabled={stars === 0 || pending}
        className="mt-3 px-5 py-2.5 rounded-xl text-white font-semibold transition-all hover:shadow-md disabled:opacity-60"
        style={{ background: '#5b8def' }}
      >
        {pending ? '提交中…' : '提交评分'}
      </button>
    </div>
  );
}
