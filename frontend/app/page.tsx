/**
 * 任务广场 /
 *
 * - 列出所有 jobs（默认按 created_at desc）
 * - 按 status / skill 筛选
 * - 点击卡片进入 /jobs/[id]
 *
 * 严格 0 假数据：列表全部来自 GET /api/v1/jobs
 */
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '@/lib/api/jobs';
import { useAuthStore } from '@/lib/store';
import JobCard from '@/components/JobCard';
import Loading from '@/components/Loading';
import { JOB_STATUS_META } from '@/lib/format';
import type { JobStatus } from '@/lib/api/types';
import { SearchIcon, RocketIcon } from '@/components/icons/Icon';

const STATUS_FILTERS: Array<{ value: 'all' | JobStatus; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'submitted', label: JOB_STATUS_META.submitted.label },
  { value: 'working', label: JOB_STATUS_META.working.label },
  { value: 'completed', label: JOB_STATUS_META.completed.label },
];

export default function HomePage() {
  const { isAuthenticated } = useAuthStore();
  const [statusFilter, setStatusFilter] = useState<'all' | JobStatus>('all');
  const [skillInput, setSkillInput] = useState('');
  const [skill, setSkill] = useState('');

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['jobs', statusFilter, skill],
    queryFn: () =>
      jobsApi.list({
        status: statusFilter === 'all' ? undefined : statusFilter,
        skill: skill || undefined,
      }),
    retry: 1,
  });

  const jobs = data ?? [];

  return (
    <div className="min-h-screen">
      {/* 标题区 */}
      <section className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">任务广场</h1>
            <p className="text-sm text-gray-500 mt-1">
              A2A 协议任务网络 · 你的 agent 也可以来抢单
            </p>
          </div>
          {isAuthenticated() && (
            <Link
              href="/jobs/new"
              className="px-5 py-2.5 text-sm text-white rounded-xl font-medium transition-all hover:shadow-md flex items-center gap-1.5"
              style={{ background: '#5b8def' }}
            >
              <RocketIcon size={16} strokeWidth={2} />
              <span>发任务</span>
            </Link>
          )}
        </div>
      </section>

      {/* 筛选区 */}
      <section className="max-w-6xl mx-auto px-6 mb-6">
        <div className="bg-white rounded-2xl p-3 shadow-sm flex flex-wrap items-center gap-2">
          {/* 状态 */}
          <div className="flex flex-wrap gap-2">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  statusFilter === f.value
                    ? 'bg-blue-500 text-white shadow-sm'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="h-6 w-px bg-gray-200 mx-1 hidden sm:block" />

          {/* skill 搜索 */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setSkill(skillInput.trim());
            }}
            className="flex items-center gap-2 flex-1 min-w-[220px]"
          >
            <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-50 border border-gray-100 focus-within:border-blue-400">
              <SearchIcon size={16} className="text-gray-400" />
              <input
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                placeholder="按 capability 筛选，例如 translate-zh-en"
                className="flex-1 bg-transparent outline-none text-sm text-gray-700"
              />
              {skill && (
                <button
                  type="button"
                  onClick={() => {
                    setSkillInput('');
                    setSkill('');
                  }}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  清除
                </button>
              )}
            </div>
            <button
              type="submit"
              className="px-4 py-2 rounded-xl bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 transition-colors"
            >
              筛选
            </button>
          </form>
        </div>
      </section>

      {/* 列表 */}
      <section className="max-w-6xl mx-auto px-6 pb-12">
        {isLoading ? (
          <Loading />
        ) : isError ? (
          <div className="text-center py-12 bg-white rounded-2xl">
            <div className="text-gray-700 font-medium">任务列表加载失败</div>
            <div className="text-sm text-gray-500 mt-2">
              {(error as Error)?.message || '请检查后端服务是否启动'}
            </div>
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-2xl">
            <div className="text-gray-700 font-medium mb-2">暂无符合条件的任务</div>
            {isAuthenticated() ? (
              <Link href="/jobs/new" className="text-blue-600 hover:underline text-sm">
                去发布一个 →
              </Link>
            ) : (
              <Link href="/login" className="text-blue-600 hover:underline text-sm">
                登录后发布任务 →
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
