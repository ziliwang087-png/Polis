'use client';

import { useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deliverablesApi, tasksApi } from '@/lib/api/tasks';
import type { Task, TaskStatus } from '@/lib/api/types';
import { useAuthStore } from '@/lib/store';

const STATUS_STEPS: Array<{ status: TaskStatus; label: string }> = [
  { status: 'open', label: '已发布' },
  { status: 'claimed', label: '已接单' },
  { status: 'in_progress', label: '进行中' },
  { status: 'submitted', label: '已提交' },
  { status: 'completed', label: '已完成' },
];

const STATUS_LABEL: Record<TaskStatus, string> = {
  open: '已发布',
  claimed: '已接单',
  in_progress: '进行中',
  submitted: '已提交',
  completed: '已完成',
  cancelled: '已取消',
  failed: '失败',
};

const STATUS_CLASS: Record<TaskStatus, string> = {
  open: 'bg-emerald-50 text-emerald-700',
  claimed: 'bg-sky-50 text-sky-700',
  in_progress: 'bg-blue-50 text-[#1d4ed8]',
  submitted: 'bg-amber-50 text-amber-700',
  completed: 'bg-slate-100 text-slate-700',
  cancelled: 'bg-slate-100 text-slate-500',
  failed: 'bg-red-50 text-red-700',
};

type TaskDetailPayload = Task | { task: Task; submission?: unknown; applications?: unknown[]; review?: unknown };

function unwrapTask(payload: TaskDetailPayload | undefined): Task | null {
  if (!payload) return null;
  if ('task' in payload) return payload.task;
  return payload;
}

function stepIndex(status: TaskStatus) {
  if (status === 'cancelled' || status === 'failed') return -1;
  return STATUS_STEPS.findIndex((step) => step.status === status);
}

function formatDateTime(value: string | null) {
  if (!value) return '未设置';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '待确认';
  return date.toLocaleString('zh-CN');
}

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuthStore();
  const authed = isAuthenticated();
  const taskId = params.id as string;

  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [submissionText, setSubmissionText] = useState('');
  const [deliverableFile, setDeliverableFile] = useState<File | null>(null);
  const [deliverableDescription, setDeliverableDescription] = useState('');

  const taskQuery = useQuery({
    queryKey: ['tasks', taskId],
    queryFn: () => tasksApi.get(taskId) as Promise<TaskDetailPayload>,
    enabled: Boolean(taskId),
    retry: 1,
    staleTime: 30_000,
  });

  const task = unwrapTask(taskQuery.data);
  const currentStep = task ? stepIndex(task.status) : -1;

  const invalidateTask = () => queryClient.invalidateQueries({ queryKey: ['tasks', taskId] });

  const deliverablesQuery = useQuery({
    queryKey: ['tasks', taskId, 'deliverables'],
    queryFn: () => deliverablesApi.list(taskId),
    enabled: Boolean(taskId) && authed,
    staleTime: 30_000,
    retry: 1,
  });

  const actionMutation = useMutation({
    mutationFn: async (action: 'claim' | 'start' | 'submit' | 'accept' | 'revision' | 'cancel') => {
      if (action === 'claim') return tasksApi.claim(taskId);
      if (action === 'start') return tasksApi.start(taskId);
      if (action === 'submit') {
        return tasksApi.submit(taskId, { content: submissionText.trim() || '交付物已提交' });
      }
      if (action === 'accept') return tasksApi.accept(taskId);
      if (action === 'revision') return tasksApi.requestRevision(taskId);
      return tasksApi.cancel(taskId);
    },
    onSuccess: () => {
      setSubmissionText('');
      invalidateTask();
    },
  });

  const rateMutation = useMutation({
    mutationFn: () => tasksApi.rate(taskId, rating, comment),
    onSuccess: () => invalidateTask(),
  });

  const uploadDeliverable = useMutation({
    mutationFn: () => {
      if (!deliverableFile) throw new Error('请选择文件');
      return deliverablesApi.upload(taskId, deliverableFile, deliverableDescription);
    },
    onSuccess: () => {
      setDeliverableFile(null);
      setDeliverableDescription('');
      queryClient.invalidateQueries({ queryKey: ['tasks', taskId, 'deliverables'] });
    },
  });

  const deleteDeliverable = useMutation({
    mutationFn: (deliverableId: string) => deliverablesApi.remove(taskId, deliverableId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks', taskId, 'deliverables'] }),
  });

  const actionError = useMemo(() => {
    const error = actionMutation.error as { response?: { data?: { detail?: string } } } | null;
    return error?.response?.data?.detail || null;
  }, [actionMutation.error]);

  if (taskQuery.isLoading) {
    return (
      <main className="min-h-[100dvh] bg-[#f6f8fb] px-4 py-10">
        <div className="mx-auto max-w-5xl rounded-lg bg-white p-10 text-center text-slate-500 shadow-sm">
          加载中...
        </div>
      </main>
    );
  }

  if (!task) {
    return (
      <main className="min-h-[100dvh] bg-[#f6f8fb] px-4 py-10">
        <div className="mx-auto max-w-5xl rounded-lg bg-white p-10 text-center text-slate-500 shadow-sm">
          任务不存在
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-[100dvh] bg-[#f6f8fb] px-4 pb-16 pt-8 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_CLASS[task.status]}`}>
                  {STATUS_LABEL[task.status]}
                </span>
                <span className="text-slate-500">分类: {task.category}</span>
                {task.difficulty && <span className="text-slate-500">优先级: {task.difficulty}</span>}
                <span className="text-slate-500">奖励: {task.reward_points} 积分</span>
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
                {task.title}
              </h1>
            </div>
            <button
              type="button"
              onClick={() => router.back()}
              className="w-fit rounded-lg bg-slate-50 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
            >
              返回
            </button>
          </div>

          <div className="mt-6 border-t border-slate-100 pt-5">
            <h2 className="text-sm font-semibold text-slate-900">任务描述</h2>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-600">{task.description}</p>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-950">任务状态</h2>
            <span className="text-sm text-slate-500">{STATUS_LABEL[task.status]}</span>
          </div>

          <div className="grid gap-3 md:grid-cols-5">
            {STATUS_STEPS.map((step, index) => {
              const done = currentStep >= index;
              const active = currentStep === index;
              return (
                <div
                  key={step.status}
                  className={`rounded-lg border p-3 ${
                    active
                      ? 'border-[#bfdbfe] bg-[#eff6ff]'
                      : done
                        ? 'border-emerald-100 bg-emerald-50'
                        : 'border-slate-100 bg-slate-50'
                  }`}
                >
                  <div className={`mb-2 h-2 rounded-full ${done ? 'bg-[#1d4ed8]' : 'bg-slate-200'}`} />
                  <div className="text-sm font-semibold text-slate-900">{step.label}</div>
                </div>
              );
            })}
          </div>

          {(task.status === 'cancelled' || task.status === 'failed') && (
            <div className="mt-4 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              这个任务已经结束，不能继续推进状态。
            </div>
          )}
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-950">操作</h2>
          {actionError && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">{actionError}</div>
          )}
          <div className="flex flex-wrap gap-3">
            {task.status === 'open' && (
              <>
                <ActionButton pending={actionMutation.isPending} onClick={() => actionMutation.mutate('claim')}>
                  接单
                </ActionButton>
                <GhostButton pending={actionMutation.isPending} onClick={() => actionMutation.mutate('cancel')}>
                  取消任务
                </GhostButton>
              </>
            )}
            {task.status === 'claimed' && (
              <ActionButton pending={actionMutation.isPending} onClick={() => actionMutation.mutate('start')}>
                开始工作
              </ActionButton>
            )}
            {task.status === 'in_progress' && (
              <div className="w-full space-y-3">
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-slate-700">提交说明</span>
                  <textarea
                    value={submissionText}
                    onChange={(event) => setSubmissionText(event.target.value)}
                    rows={4}
                    className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-[#1d4ed8]"
                    placeholder="说明交付内容、文件链接或验收要点。"
                  />
                </label>
                <ActionButton pending={actionMutation.isPending} onClick={() => actionMutation.mutate('submit')}>
                  提交交付物
                </ActionButton>
              </div>
            )}
            {task.status === 'submitted' && (
              <>
                <ActionButton pending={actionMutation.isPending} onClick={() => actionMutation.mutate('accept')}>
                  验收通过
                </ActionButton>
                <GhostButton pending={actionMutation.isPending} onClick={() => actionMutation.mutate('revision')}>
                  打回重做
                </GhostButton>
              </>
            )}
            {task.status === 'completed' && (
              <div className="w-full rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
                任务已完成。发布者可以继续补充评分。
              </div>
            )}
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <h2 className="mb-4 text-lg font-semibold text-slate-950">时间线</h2>
            <div className="space-y-2 text-sm text-slate-600">
              <div>创建时间: {formatDateTime(task.created_at)}</div>
              <div>更新时间: {formatDateTime(task.updated_at)}</div>
              <div>完成时间: {formatDateTime(task.completed_at)}</div>
              <div>截止时间: {formatDateTime(task.deadline)}</div>
            </div>
          </div>

          {task.assigned_agent_id && (
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <h2 className="mb-3 text-lg font-semibold text-slate-950">接单 Agent</h2>
              <p className="break-all text-sm text-slate-600">{task.assigned_agent_id}</p>
            </div>
          )}
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">交付物</h2>
              <p className="mt-1 text-sm text-slate-500">支持多个文件，最大 50MB。</p>
            </div>
          </div>

          {(task.status === 'in_progress' || task.status === 'submitted') && (
            <div className="mb-5 grid gap-3 rounded-lg bg-slate-50 p-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">上传文件</span>
                <input
                  type="file"
                  onChange={(event) => setDeliverableFile(event.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-white file:px-4 file:py-2 file:text-sm file:font-semibold file:text-slate-700"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">描述</span>
                <input
                  value={deliverableDescription}
                  onChange={(event) => setDeliverableDescription(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-[#1d4ed8]"
                  placeholder="比如：最终代码包、设计稿或说明文档"
                />
              </label>
              {uploadDeliverable.isError && (
                <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">上传失败，请确认权限和文件大小。</div>
              )}
              <ActionButton pending={uploadDeliverable.isPending} disabled={!deliverableFile} onClick={() => uploadDeliverable.mutate()}>
                上传交付物
              </ActionButton>
            </div>
          )}

          {deliverablesQuery.isLoading ? (
            <div className="rounded-lg bg-slate-50 p-5 text-sm text-slate-500">交付物加载中...</div>
          ) : deliverablesQuery.isError ? (
            <div className="rounded-lg bg-red-50 p-5 text-sm text-red-600">交付物列表加载失败</div>
          ) : (deliverablesQuery.data ?? []).length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">
              暂无交付物
            </div>
          ) : (
            <div className="space-y-3">
              {(deliverablesQuery.data ?? []).map((item) => (
                <div key={item.id} className="flex flex-col gap-3 rounded-lg border border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-950">{item.file_name}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {formatFileSize(item.file_size)} · {formatDateTime(item.created_at)}
                    </div>
                    {item.description && <p className="mt-2 text-sm text-slate-600">{item.description}</p>}
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <a
                      href={item.file_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg bg-[#1d4ed8] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#1e40af]"
                    >
                      下载
                    </a>
                    <button
                      type="button"
                      onClick={() => deleteDeliverable.mutate(item.id)}
                      disabled={deleteDeliverable.isPending}
                      className="rounded-lg bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 disabled:opacity-60"
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {task.status === 'completed' && (
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <h2 className="mb-4 text-lg font-semibold text-slate-950">给任务评分</h2>
            <div className="mb-4">
              <label className="mb-2 block text-sm font-medium text-slate-700">评分 (1-5 星)</label>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    className={`text-3xl transition ${star <= rating ? 'text-amber-400' : 'text-slate-300'}`}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>
            <label className="mb-4 block">
              <span className="mb-2 block text-sm font-medium text-slate-700">评价（可选）</span>
              <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-[#1d4ed8]"
                rows={4}
                placeholder="说说你的感受..."
              />
            </label>
            <ActionButton
              pending={rateMutation.isPending}
              disabled={rating === 0}
              onClick={() => rateMutation.mutate()}
            >
              提交评分
            </ActionButton>
          </section>
        )}
      </div>
    </main>
  );
}

function ActionButton({
  children,
  pending,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  pending: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending || disabled}
      className="inline-flex items-center justify-center rounded-lg bg-[#1d4ed8] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#1e40af] active:translate-y-px disabled:opacity-60"
    >
      {pending ? '处理中...' : children}
    </button>
  );
}

function formatFileSize(bytes: number) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function GhostButton({
  children,
  pending,
  onClick,
}: {
  children: React.ReactNode;
  pending: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className="inline-flex items-center justify-center rounded-lg bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 active:translate-y-px disabled:opacity-60"
    >
      {children}
    </button>
  );
}
