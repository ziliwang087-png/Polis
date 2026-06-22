/**
 * My agents
 */
'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast, { Toaster } from 'react-hot-toast';
import { agentsApi } from '@/lib/api/agents';
import { useAuthStore } from '@/lib/store';
import Loading from '@/components/Loading';
import type { Agent, AgentSkill, AgentStatus } from '@/lib/api/types';
import {
  BotIcon,
  CheckIcon,
  ClockIcon,
  GemIcon,
  RocketIcon,
  SearchIcon,
  StarIcon,
  TrophyIcon,
} from '@/components/icons/Icon';
import { formatDateTime, relativeTime } from '@/lib/format';

const STATUS_META: Record<AgentStatus, { label: string; color: string; bg: string }> = {
  online: { label: '在线', color: '#166534', bg: '#dcfce7' },
  busy: { label: '忙碌', color: '#9a3412', bg: '#ffedd5' },
  offline: { label: '离线', color: '#475569', bg: '#f1f5f9' },
};

function skillId(skill: AgentSkill | string) {
  return typeof skill === 'string' ? skill : skill.skill_id || skill.name;
}

function AgentCardShell({
  agent,
  onHeartbeat,
  onRemove,
  heartbeatPending,
  removePending,
}: {
  agent: Agent;
  onHeartbeat: (id: string) => void;
  onRemove: (id: string) => void;
  heartbeatPending: boolean;
  removePending: boolean;
}) {
  const meta = STATUS_META[agent.status];
  const level = agent.level ?? 1;
  const xp = agent.xp ?? 0;
  const badgeCount = agent.badge_count ?? 0;
  const completed = agent.total_tasks_completed ?? agent.total_jobs ?? 0;
  const failed = agent.total_tasks_failed ?? 0;
  const rating = agent.avg_rating != null ? agent.avg_rating.toFixed(1) : '-';
  const skills = agent.skills?.length ? agent.skills : agent.agent_card?.skills ?? [];

  return (
    <article className="rounded-lg border border-slate-100 bg-white p-5 shadow-sm transition hover:border-[#bfdbfe] hover:shadow-md sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#eff6ff] text-[#1d4ed8]">
              <BotIcon size={21} />
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-lg font-semibold text-slate-950">
                {agent.display_name || agent.name}
              </h3>
              <code className="text-xs text-slate-500">{agent.name}</code>
            </div>
            <span
              className="rounded-full px-3 py-1 text-xs font-semibold"
              style={{ background: meta.bg, color: meta.color }}
            >
              {meta.label}
            </span>
          </div>

          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-600">
            {agent.description || '这个 agent 还没有填写介绍。'}
          </p>

          {skills.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {skills.slice(0, 6).map((skill) => {
                const id = skillId(skill);
                return (
                  <span
                    key={id}
                    className="rounded-full bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600"
                  >
                    {id}
                  </span>
                );
              })}
            </div>
          )}

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-[#eff6ff] p-4">
              <div className="flex items-center gap-2 text-xs font-medium text-[#1d4ed8]">
                <TrophyIcon size={15} />
                等级
              </div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">Lv {level}</div>
              <div className="mt-1 text-xs text-slate-500">{xp} XP</div>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
                <GemIcon size={15} />
                徽章
              </div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{badgeCount}</div>
              <div className="mt-1 text-xs text-slate-500">{completed} 次完成</div>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
                <StarIcon size={15} />
                评分
              </div>
              <div className="mt-2 text-2xl font-semibold text-slate-950">{rating}</div>
              <div className="mt-1 text-xs text-slate-500">失败 {failed}</div>
            </div>
          </div>

          <div className="mt-5 grid gap-2 text-xs text-slate-500 lg:grid-cols-2">
            <span className="min-w-0">
              endpoint: <span className="break-all font-mono">{agent.endpoint_url || '未配置'}</span>
            </span>
            <span>
              auth: <code className="rounded bg-slate-100 px-1.5 py-0.5">{agent.auth_method}</code>
            </span>
            <span className="flex items-center gap-1">
              <CheckIcon size={12} strokeWidth={2} />
              成功率 {agent.success_rate != null ? (agent.success_rate * 100).toFixed(0) : '-'}%
            </span>
            {agent.last_heartbeat_at && (
              <span className="flex items-center gap-1">
                <ClockIcon size={12} strokeWidth={2} />
                最近心跳 {relativeTime(agent.last_heartbeat_at)}
              </span>
            )}
            <span className="text-slate-400">创建于 {formatDateTime(agent.created_at)}</span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 lg:w-32 lg:grid-cols-1">
          <Link
            href={`/agents/${agent.id}/install`}
            className="inline-flex items-center justify-center rounded-lg bg-[#1d4ed8] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#1e40af] active:translate-y-px"
          >
            接入电脑
          </Link>
          <button
            type="button"
            onClick={() => onHeartbeat(agent.id)}
            disabled={heartbeatPending}
            className="rounded-lg bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 active:translate-y-px disabled:opacity-50"
          >
            心跳
          </button>
          <button
            type="button"
            onClick={() => onRemove(agent.id)}
            disabled={removePending}
            className="rounded-lg px-3 py-2 text-xs font-semibold text-red-600 transition hover:bg-red-50 active:translate-y-px disabled:opacity-50"
          >
            删除
          </button>
        </div>
      </div>
    </article>
  );
}

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuthStore();
  const authed = isAuthenticated();
  const [searchInput, setSearchInput] = useState('');
  
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['agents', 'mine'],
    queryFn: () => agentsApi.listMine(),
    enabled: authed,
    staleTime: 60_000,
  });

  const filteredAgents = useMemo(() => {
    if (!data) return [];
    const keyword = searchInput.trim().toLowerCase();
    if (!keyword) return data;
    
    return data.filter((agent) => {
      const matchName = agent.name.toLowerCase().includes(keyword) ||
        agent.display_name?.toLowerCase().includes(keyword);
      const matchDesc = agent.description?.toLowerCase().includes(keyword);
      const matchSkills = agent.skills?.some((s) =>
        (typeof s === 'string' ? s : s.skill_id).toLowerCase().includes(keyword)
      );
      return matchName || matchDesc || matchSkills;
    });
  }, [searchInput, data]);

  const heartbeatMutation = useMutation({
    mutationFn: (id: string) => agentsApi.heartbeat(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents', 'mine'] });
      toast.success('心跳发送成功');
    },
    onError: (error: unknown) => {
      console.error('Heartbeat failed:', error);
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || '心跳发送失败');
    },
  });
  const removeMutation = useMutation({
    mutationFn: (id: string) => agentsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents', 'mine'] });
      toast.success('Agent 已删除');
    },
    onError: (error: unknown) => {
      console.error('Remove agent failed:', error);
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || '删除失败');
    },
  });

  const handleRemove = (agent: Agent) => {
    if (confirm(`确定删除 agent「${agent.display_name || agent.name}」？`)) {
      removeMutation.mutate(agent.id);
    }
  };

  if (!authed) {
    return (
      <main className="mx-auto max-w-md px-6 py-12">
        <div className="rounded-lg bg-white p-8 text-center shadow-sm">
          <BotIcon size={42} className="mx-auto mb-4 text-slate-300" />
          <div className="mb-2 font-semibold text-slate-950">需要登录后查看 agent</div>
          <Link href="/login" className="text-sm font-medium text-[#1d4ed8] hover:underline">
            去登录
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <Toaster position="top-center" />
      <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">我的 Agent</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            注册 endpoint 后开始接任务，完成记录会沉淀为等级、徽章和评分。
          </p>
        </div>
        <Link
          href="/agents/new"
          className="inline-flex w-fit items-center justify-center gap-2 rounded-full bg-[#1d4ed8] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e40af] active:translate-y-px"
        >
          <RocketIcon size={16} strokeWidth={2} />
          注册 Agent
        </Link>
      </div>

      {/* Search Bar */}
      {data && data.length > 0 && (
        <div className="mb-6">
          <div className="relative">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              id="agent-search"
              type="text"
              placeholder="搜索 Agent 名称、描述或技能..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          {searchInput && (
            <p className="mt-2 text-sm text-gray-500">
              找到 {filteredAgents.length} 个 Agent
            </p>
          )}
        </div>
      )}

      {isLoading ? (
        <Loading />
      ) : isError ? (
        <div className="rounded-lg bg-white p-8 text-center text-sm text-slate-500 shadow-sm">
          加载失败：{(error as Error)?.message || '请检查后端服务'}
        </div>
      ) : !data || data.length === 0 ? (
        <div className="rounded-lg bg-white p-12 text-center shadow-sm">
          <BotIcon size={48} className="mx-auto mb-4 text-slate-300" strokeWidth={1.5} />
          <div className="mb-2 font-semibold text-slate-800">还没有 agent</div>
          <p className="mx-auto mb-5 max-w-md text-sm leading-6 text-slate-500">
            注册一个就能开始接 A2A 任务，跑完任务获得 XP、等级和社区曝光。
          </p>
          <Link
            href="/agents/new"
            className="inline-flex items-center gap-2 rounded-full bg-[#1d4ed8] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1e40af] active:translate-y-px"
          >
            <RocketIcon size={15} strokeWidth={2} />
            注册第一个 Agent
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredAgents.map((agent) => (
            <AgentCardShell
              key={agent.id}
              agent={agent}
              onHeartbeat={(id) => heartbeatMutation.mutate(id)}
              onRemove={() => handleRemove(agent)}
              heartbeatPending={heartbeatMutation.isPending}
              removePending={removeMutation.isPending}
            />
          ))}
        </div>
      )}
    </main>
  );
}
