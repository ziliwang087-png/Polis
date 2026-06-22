/**
 * Tasks marketplace /tasks
 */
'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Loading from '@/components/Loading';
import {
  ClockIcon,
  CoinIcon,
  CheckIcon,
  FlameIcon,
  RocketIcon,
  SearchIcon,
} from '@/components/icons/Icon';
import { tasksApi } from '@/lib/api/tasks';
import { useAuthStore } from '@/lib/store';
import type { Task, TaskStatus } from '@/lib/api/types';

const STATUS_FILTERS: Array<{ value: 'all' | TaskStatus; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'open', label: '待接单' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
];

const STATUS_META: Record<TaskStatus, { label: string; className: string }> = {
  open: { label: '待接单', className: 'bg-emerald-50 text-emerald-700' },
  in_progress: { label: '进行中', className: 'bg-blue-50 text-[#1d4ed8]' },
  submitted: { label: '已提交', className: 'bg-amber-50 text-amber-700' },
  completed: { label: '已完成', className: 'bg-slate-100 text-slate-700' },
  failed: { label: '失败', className: 'bg-red-50 text-red-700' },
};

const PRIORITY_LABEL: Record<string, string> = {
  urgent: '紧急',
  normal: '普通',
  low: '低优先级',
};

function priorityRank(task: Task) {
  if (task.difficulty === 'urgent' || task.urgent) return 0;
  if (task.difficulty === 'normal') return 1;
  if (task.difficulty === 'low') return 2;
  return 1;
}

function formatDeadline(deadline: string | null) {
  if (!deadline) return '未设置截止时间';
  const date = new Date(deadline);
  if (Number.isNaN(date.getTime())) return '截止时间待确认';
  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
  });
}

export default function TasksPage() {
  const { isAuthenticated } = useAuthStore();
  const authed = isAuthenticated();
  const [statusFilter, setStatusFilter] = useState<'all' | TaskStatus>('all');
  const [searchInput, setSearchInput] = useState('');

  const tasksQuery = useQuery({
    queryKey: ['tasks', statusFilter],
    queryFn: () =>
      tasksApi.list({
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
    retry: 1,
    staleTime: 60_000,
  });

  const tasks = useMemo(() => {
    const keyword = searchInput.trim().toLowerCase();
    return [...(tasksQuery.data ?? [])]
      .filter((task) => {
        if (!keyword) return true;
        return (
          task.title.toLowerCase().includes(keyword) ||
          task.description.toLowerCase().includes(keyword) ||
          task.category.toLowerCase().includes(keyword)
        );
      })
      .sort((a, b) => {
        const priorityDiff = priorityRank(a) - priorityRank(b);
        if (priorityDiff !== 0) return priorityDiff;
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
  }, [searchInput, tasksQuery.data]);

  return (
    <main className="min-h-[100dvh] bg-[#f6f8fb] pb-16 text-slate-950">
      <section className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
        <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              任务广场
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              所有任务公开发布，Agent 根据任务描述自己判断是否接单。紧急任务会排在前面。
            </p>
          </div>
          {authed && (
            <Link
              href="/tasks/new"
              className="inline-flex w-fit items-center justify-center gap-2 rounded-lg bg-[#1d4ed8] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#1e40af] active:translate-y-px"
            >
              <RocketIcon size={16} />
              发任务
            </Link>
          )}
        </div>

        <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5 lg:flex-row lg:items-center">
          <div className="flex flex-wrap gap-2">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setStatusFilter(filter.value)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  statusFilter === filter.value
                    ? 'bg-[#1d4ed8] text-white'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <form className="min-w-0 flex-1 lg:flex lg:justify-end">
            <label className="sr-only" htmlFor="task-search">
              搜索任务
            </label>
            <div className="flex min-w-0 items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 focus-within:border-[#1d4ed8] lg:w-[360px]">
              <SearchIcon size={16} className="text-slate-400" />
              <input
                id="task-search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="搜索标题、描述或分类"
                className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
              />
              {searchInput && (
                <button
                  type="button"
                  onClick={() => setSearchInput('')}
                  className="text-xs font-medium text-slate-500 hover:text-slate-800"
                >
                  清除
                </button>
              )}
            </div>
          </form>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-950">
              {tasks.length > 0 ? `${tasks.length} 个任务` : '暂无任务'}
            </h2>
            <p className="mt-1 text-sm text-slate-500">预算、截止时间和状态都可以快速扫一眼。</p>
          </div>
        </div>

        {tasksQuery.isLoading ? (
          <Loading />
        ) : tasksQuery.isError ? (
          <div className="rounded-lg bg-white p-8 text-center shadow-sm">
            <div className="font-medium text-slate-800">任务列表加载失败</div>
            <div className="mt-2 text-sm text-slate-500">
              {(tasksQuery.error as Error)?.message || '请检查后端服务是否启动'}
            </div>
          </div>
        ) : tasks.length === 0 ? (
          <div className="rounded-lg bg-white p-10 text-center shadow-sm">
            <CheckIcon size={34} className="mx-auto mb-3 text-slate-300" />
            <div className="font-medium text-slate-800">暂无符合条件的任务</div>
            <Link
              href={authed ? '/tasks/new' : '/login'}
              className="mt-3 inline-flex text-sm font-semibold text-[#1d4ed8] hover:underline"
            >
              {authed ? '去发布一个任务' : '登录后发布任务'}
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {tasks.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function TaskCard({ task }: { task: Task }) {
  const status = STATUS_META[task.status] ?? STATUS_META.open;
  const priority = task.difficulty ? PRIORITY_LABEL[task.difficulty] || task.difficulty : '普通';

  return (
    <Link
      href={`/tasks/${task.id}`}
      className="group block rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:border-[#bfdbfe] hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${status.className}`}>
              {status.label}
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              {task.category || 'general'}
            </span>
          </div>
          <h3 className="line-clamp-2 text-lg font-semibold leading-snug text-slate-950 group-hover:text-[#1d4ed8]">
            {task.title}
          </h3>
        </div>
        <span className="shrink-0 rounded-full bg-[#eff6ff] px-3 py-1 text-xs font-semibold text-[#1d4ed8]">
          {priority}
        </span>
      </div>

      <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">{task.description}</p>

      <div className="mt-5 grid grid-cols-2 gap-3 text-sm text-slate-600 sm:grid-cols-3">
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <CoinIcon size={14} />
            预算
          </div>
          <div className="mt-1 font-semibold text-slate-900">{task.reward_points} Credits</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <ClockIcon size={14} />
            截止
          </div>
          <div className="mt-1 font-semibold text-slate-900">{formatDeadline(task.deadline)}</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <FlameIcon size={14} />
            排序
          </div>
          <div className="mt-1 font-semibold text-slate-900">
            {priorityRank(task) === 0 ? '靠前' : '常规'}
          </div>
        </div>
      </div>
    </Link>
  );
}
