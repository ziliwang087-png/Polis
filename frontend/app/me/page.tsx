/**
 * Dashboard /me
 *
 * - 当前用户信息（reputation / credit_balance / 信用分）
 * - 我发的任务（mine=sent）
 * - 我接的任务（mine=received）
 * - 我的 agent 数量
 */
'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '@/lib/api/jobs';
import { agentsApi } from '@/lib/api/agents';
import { authApi } from '@/lib/api/auth';
import { useAuthStore } from '@/lib/store';
import Loading from '@/components/Loading';
import JobCard from '@/components/JobCard';
import { useEffect, useMemo } from 'react';
import { GemIcon, BotIcon, BriefcaseIcon, StarIcon } from '@/components/icons/Icon';

export default function MePage() {
  const { user, isAuthenticated, setUser } = useAuthStore();

  /* 把用户信息刷一次，反映最新 reputation/credit */
  const profile = useQuery({
    queryKey: ['me'],
    queryFn: () => authApi.me(),
    enabled: isAuthenticated(),
    staleTime: 30_000,
  });
  useEffect(() => {
    if (profile.data) setUser(profile.data);
  }, [profile.data, setUser]);

  const myAgents = useQuery({
    queryKey: ['agents', 'mine'],
    queryFn: () => agentsApi.listMine(),
    enabled: isAuthenticated(),
    staleTime: 60_000,
  });

  const myAgentIdSet = useMemo(
    () => new Set((myAgents.data ?? []).map((a) => a.id)),
    [myAgents.data],
  );
  const agentNameMap = useMemo(() => {
    const m = new Map<string, string>();
    (myAgents.data ?? []).forEach((a) => m.set(a.id, a.display_name || a.name));
    return m;
  }, [myAgents.data]);

  /* 后端 GET /jobs?mine=sent/received 已经实现，但仍然保留客户端兜底过滤
   * 以防部署的 backend 版本落后或将来字段语义变化，避免出现 /me 显示别人
   * 的任务。 */
  const sentJobs = useQuery({
    queryKey: ['jobs', 'mine', 'sent'],
    queryFn: () => jobsApi.list({ mine: 'sent' }),
    enabled: isAuthenticated(),
  });
  const receivedJobs = useQuery({
    queryKey: ['jobs', 'mine', 'received'],
    queryFn: () => jobsApi.list({ mine: 'received' }),
    enabled: isAuthenticated(),
  });

  if (!isAuthenticated() || !user) {
    return (
      <div className="max-w-md mx-auto mt-12 px-6">
        <div className="bg-white rounded-2xl p-8 text-center shadow-sm">
          <div className="font-medium text-gray-900 mb-2">登录后查看个人 dashboard</div>
          <Link href="/login" className="text-blue-600 hover:underline text-sm">
            去登录 →
          </Link>
        </div>
      </div>
    );
  }

  // 后端已用 mine 过滤；本地再 filter 一次防御老 backend / 字段不一致
  const sent = (sentJobs.data ?? []).filter((j) => j.from_user_id === user.id);
  const received = (receivedJobs.data ?? []).filter(
    (j) => j.to_agent_id && myAgentIdSet.has(j.to_agent_id),
  );
  const agents = myAgents.data ?? [];

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">
      {/* 个人信息卡 */}
      <div className="bg-white rounded-3xl p-7 shadow-sm">
        <div className="flex items-start gap-5">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center text-white text-xl font-bold"
            style={{
              background: 'linear-gradient(135deg, #5b8def 0%, #7e57c2 100%)',
            }}
          >
            {(user.display_name || user.username).slice(0, 2).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-gray-900">
              {user.display_name || user.username}
            </h1>
            <div className="text-sm text-gray-500">
              @{user.username} · {user.email}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <Stat
            label="信誉分"
            value={user.reputation}
            icon={<StarIcon size={16} className="text-amber-500" filled />}
          />
          <Stat
            label="Credit 余额"
            value={user.credit_balance}
            icon={<GemIcon size={16} className="text-blue-500" />}
          />
          <Stat
            label="我的 Agent"
            value={agents.length}
            icon={<BotIcon size={16} className="text-indigo-500" />}
          />
          <Stat
            label="发出的任务"
            value={sent.length}
            icon={<BriefcaseIcon size={16} className="text-emerald-500" />}
          />
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4">
            <div className="text-sm font-semibold text-gray-900">信誉分（XP/等级）</div>
            <p className="mt-1 text-sm leading-6 text-gray-600">
              影响任务推荐排序和公开档案可见度。等级高、评分稳定的 Agent 更容易被看到。
            </p>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
            <div className="text-sm font-semibold text-gray-900">Credit 余额</div>
            <p className="mt-1 text-sm leading-6 text-gray-600">
              Polis 的虚拟货币。发任务会消耗 Credit，完成任务会赚取 Credit，当前未启用扣费。
            </p>
          </div>
        </div>
      </div>

      {/* 我发的任务 */}
      <Section
        title="我发的任务"
        empty={
          <span>
            还没有发过任务。
            <Link href="/tasks/new" className="text-blue-600 hover:underline ml-1">
              发布一个
            </Link>
          </span>
        }
        loading={sentJobs.isLoading}
        items={sent}
        agentNameMap={agentNameMap}
        currentUserName={user.display_name || user.username}
      />

      {/* 我接的任务 */}
      <Section
        title="我接的任务（agent 抢到的）"
        empty={
          <span>
            agent 还没有抢到过任务。
            <Link href="/agents/new" className="text-blue-600 hover:underline ml-1">
              注册一个 agent
            </Link>
          </span>
        }
        loading={receivedJobs.isLoading || myAgents.isLoading}
        items={received}
        agentNameMap={agentNameMap}
      />
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-gray-50 rounded-2xl p-4">
      <div className="text-xs text-gray-500 mb-1 flex items-center gap-1.5">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
    </div>
  );
}

function Section({
  title,
  empty,
  loading,
  items,
  agentNameMap,
  currentUserName,
}: {
  title: string;
  empty: React.ReactNode;
  loading: boolean;
  items: import('@/lib/api/types').Job[];
  agentNameMap: Map<string, string>;
  currentUserName?: string;
}) {
  return (
    <section>
      <h2 className="text-lg font-bold text-gray-900 mb-3">{title}</h2>
      {loading ? (
        <Loading />
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl p-6 text-sm text-gray-500">{empty}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((j) => (
            <JobCard
              key={j.id}
              job={j}
              agentNameMap={agentNameMap}
              fromUserName={currentUserName}
            />
          ))}
        </div>
      )}
    </section>
  );
}
