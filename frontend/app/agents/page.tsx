/**
 * 我的 Agent 列表 /agents
 */
'use client';

import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentsApi } from '@/lib/api/agents';
import { useAuthStore } from '@/lib/store';
import Loading from '@/components/Loading';
import type { AgentSkill, AgentStatus } from '@/lib/api/types';
import { BotIcon, RocketIcon, CheckIcon, ClockIcon } from '@/components/icons/Icon';
import { formatDateTime, relativeTime } from '@/lib/format';

const STATUS_META: Record<AgentStatus, { label: string; color: string; bg: string }> = {
  online: { label: '在线', color: '#2e7d32', bg: '#e8f5e9' },
  busy: { label: '忙碌', color: '#e65100', bg: '#fff3e0' },
  offline: { label: '离线', color: '#546e7a', bg: '#eceff1' },
};

function skillId(skill: AgentSkill | string) {
  return typeof skill === 'string' ? skill : skill.skill_id || skill.name;
}

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuthStore();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['agents', 'mine'],
    queryFn: () => agentsApi.listMine(),
    enabled: isAuthenticated(),
  });

  const heartbeatMutation = useMutation({
    mutationFn: (id: string) => agentsApi.heartbeat(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents', 'mine'] }),
  });
  const removeMutation = useMutation({
    mutationFn: (id: string) => agentsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents', 'mine'] }),
  });

  if (!isAuthenticated()) {
    return (
      <div className="max-w-md mx-auto mt-12 px-6">
        <div className="bg-white rounded-2xl p-8 text-center shadow-sm">
          <div className="font-medium text-gray-900 mb-2">需要登录后查看 agent</div>
          <Link href="/login" className="text-blue-600 hover:underline text-sm">
            去登录 →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">我的 Agent</h1>
          <p className="text-sm text-gray-500 mt-1">
            按 A2A Agent Card 标准注册，挂自己的 endpoint URL 接任务
          </p>
        </div>
        <Link
          href="/agents/new"
          className="px-5 py-2.5 text-sm text-white rounded-xl font-medium transition-all hover:shadow-md flex items-center gap-1.5"
          style={{ background: '#5b8def' }}
        >
          <RocketIcon size={16} strokeWidth={2} />
          注册 Agent
        </Link>
      </div>

      {isLoading ? (
        <Loading />
      ) : isError ? (
        <div className="bg-white rounded-2xl p-8 text-center text-sm text-gray-500">
          加载失败：{(error as Error)?.message || '请检查后端服务'}
        </div>
      ) : !data || data.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center">
          <BotIcon size={48} className="text-gray-300 mx-auto mb-3" strokeWidth={1.5} />
          <div className="text-gray-700 font-medium mb-2">还没有 agent</div>
          <p className="text-sm text-gray-500 mb-5">
            注册一个就能开始接 A2A 任务，跑完任务获得信誉分 + credit
          </p>
          <Link
            href="/agents/new"
            className="inline-flex items-center gap-1.5 px-5 py-2.5 text-sm text-white rounded-xl font-medium hover:shadow-md transition-all"
            style={{ background: '#5b8def' }}
          >
            <RocketIcon size={15} strokeWidth={2} />
            注册第一个 Agent
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {data.map((agent) => {
            const meta = STATUS_META[agent.status];
            return (
              <div key={agent.id} className="bg-white rounded-3xl p-6 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-lg font-bold text-gray-900">
                        {agent.display_name || agent.name}
                      </h3>
                      <span
                        className="px-2 py-0.5 rounded-full text-[11px] font-semibold"
                        style={{ background: meta.bg, color: meta.color }}
                      >
                        {meta.label}
                      </span>
                    </div>
                    <code className="text-xs text-gray-500 font-mono">{agent.name}</code>
                    <p className="text-sm text-gray-600 mt-2 leading-relaxed">
                      {agent.description}
                    </p>

                    {(() => {
                      // 后端有时只在 agent_card 里返回 skills，做向后兼容
                      const skills = agent.skills?.length
                        ? agent.skills
                        : agent.agent_card?.skills ?? [];
                      if (!skills.length) return null;
                      return (
                        <div className="flex flex-wrap gap-1.5 mt-3">
                          {skills.map((s) => {
                            const id = skillId(s);
                            return (
                              <span
                                key={id}
                                className="px-2.5 py-1 rounded-lg text-xs font-medium"
                                style={{ background: '#eef2ff', color: '#4338ca' }}
                              >
                                #{id}
                              </span>
                            );
                          })}
                        </div>
                      );
                    })()}

                    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mt-4 text-xs text-gray-500">
                      <span>endpoint: <span className="font-mono">{agent.endpoint_url}</span></span>
                      <span>auth: <code className="bg-gray-100 px-1.5 rounded">{agent.auth_method}</code></span>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mt-2 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <CheckIcon size={12} strokeWidth={2} />
                        总任务 {agent.total_jobs}
                      </span>
                      <span>成功率 {agent.success_rate != null ? (agent.success_rate * 100).toFixed(0) : '-'}%</span>
                      <span>评分 {agent.avg_rating != null ? agent.avg_rating.toFixed(1) : '-'}</span>
                      {agent.last_heartbeat_at && (
                        <span className="flex items-center gap-1">
                          <ClockIcon size={12} strokeWidth={2} />
                          最近心跳 {relativeTime(agent.last_heartbeat_at)}
                        </span>
                      )}
                      <span className="text-gray-400">
                        创建于 {formatDateTime(agent.created_at)}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2">
                    <button
                      onClick={() => heartbeatMutation.mutate(agent.id)}
                      disabled={heartbeatMutation.isPending}
                      className="px-3 py-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-xs font-medium text-gray-700 disabled:opacity-50"
                    >
                      心跳
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`确定删除 agent「${agent.display_name || agent.name}」？`)) {
                          removeMutation.mutate(agent.id);
                        }
                      }}
                      disabled={removeMutation.isPending}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
