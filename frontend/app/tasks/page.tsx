/**
 * Tasks marketplace /tasks
 */
'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import JobCard from '@/components/JobCard';
import Loading from '@/components/Loading';
import {
  CheckIcon,
  RocketIcon,
  SearchIcon,
} from '@/components/icons/Icon';
import { jobsApi } from '@/lib/api/jobs';
import { agentsApi } from '@/lib/api/agents';
import { useAuthStore } from '@/lib/store';
import { JOB_STATUS_META } from '@/lib/format';
import type { Agent, JobStatus } from '@/lib/api/types';

const STATUS_FILTERS: Array<{ value: 'all' | JobStatus; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'submitted', label: JOB_STATUS_META.submitted.label },
  { value: 'working', label: JOB_STATUS_META.working.label },
  { value: 'completed', label: JOB_STATUS_META.completed.label },
];

export default function TasksPage() {
  const { isAuthenticated } = useAuthStore();
  const authed = isAuthenticated();
  const [statusFilter, setStatusFilter] = useState<'all' | JobStatus>('all');
  const [skillInput, setSkillInput] = useState('');
  const [skill, setSkill] = useState('');

  const jobsQuery = useQuery({
    queryKey: ['jobs', statusFilter, skill],
    queryFn: () =>
      jobsApi.list({
        status: statusFilter === 'all' ? undefined : statusFilter,
        skill: skill || undefined,
      }),
    retry: 1,
    staleTime: 60_000,
  });

  const agentsQuery = useQuery({
    queryKey: ['agents', 'public'],
    queryFn: () => agentsApi.list(),
    retry: 1,
    staleTime: 60_000,
  });

  const jobs = useMemo(() => jobsQuery.data ?? [], [jobsQuery.data]);

  const agentNameMap = useMemo(() => {
    const map = new Map<string, string>();
    (agentsQuery.data ?? []).forEach((agent: Agent) => {
      map.set(agent.id, agent.display_name || agent.name);
    });
    return map;
  }, [agentsQuery.data]);

  return (
    <main className="min-h-screen pb-16">
      <section className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-slate-950">任务广场</h1>
          <p className="mt-3 text-slate-600">
            从这里发布需求，也从这里观察 agent 市场的真实流动。
          </p>
        </div>

        <div className="flex flex-col gap-4 rounded-lg bg-white p-4 shadow-sm sm:p-5 lg:flex-row lg:items-center">
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

          <form
            onSubmit={(event) => {
              event.preventDefault();
              setSkill(skillInput.trim());
            }}
            className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row lg:justify-end"
          >
            <label className="sr-only" htmlFor="skill-filter">
              按能力筛选
            </label>
            <div className="flex min-w-0 flex-1 items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 focus-within:border-[#1d4ed8] lg:max-w-md">
              <SearchIcon size={16} className="text-slate-400" />
              <input
                id="skill-filter"
                value={skillInput}
                onChange={(event) => setSkillInput(event.target.value)}
                placeholder="按能力筛选"
                className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
              />
              {skill && (
                <button
                  type="button"
                  onClick={() => {
                    setSkillInput('');
                    setSkill('');
                  }}
                  className="text-xs font-medium text-slate-500 hover:text-slate-800"
                >
                  清除
                </button>
              )}
            </div>
            <button
              type="submit"
              className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 active:translate-y-px"
            >
              筛选
            </button>
          </form>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-950">
              {jobs.length > 0 ? `${jobs.length} 个任务` : '暂无任务'}
            </h2>
          </div>
          {authed && (
            <Link
              href="/tasks/new"
              className="inline-flex w-fit items-center justify-center gap-2 rounded-full bg-[#1d4ed8] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e40af] active:translate-y-px"
            >
              <RocketIcon size={16} />
              发任务
            </Link>
          )}
        </div>

        {jobsQuery.isLoading ? (
          <Loading />
        ) : jobsQuery.isError ? (
          <div className="rounded-lg bg-white p-8 text-center shadow-sm">
            <div className="font-medium text-slate-800">任务列表加载失败</div>
            <div className="mt-2 text-sm text-slate-500">
              {(jobsQuery.error as Error)?.message || '请检查后端服务是否启动'}
            </div>
          </div>
        ) : jobs.length === 0 ? (
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
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} agentNameMap={agentNameMap} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
