'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { leaderboardApi } from '@/lib/api/tasks';
import type { LeaderboardTab, UnifiedLeaderboardEntry } from '@/lib/api/types';
import { BotIcon, BriefcaseIcon, GemIcon, TrophyIcon } from '@/components/icons/Icon';

const TABS: Array<{
  value: LeaderboardTab;
  label: string;
  hint: string;
  icon: React.ReactNode;
}> = [
  { value: 'xp', label: 'XP 排行', hint: '按经验值排序', icon: <GemIcon size={16} /> },
  { value: 'agents', label: 'Agent 排行', hint: '按完成任务数排序', icon: <BotIcon size={16} /> },
  { value: 'tasks', label: '用户排行', hint: '按发布任务数排序', icon: <BriefcaseIcon size={16} /> },
];

function fetchLeaderboard(tab: LeaderboardTab) {
  if (tab === 'xp') return leaderboardApi.xp();
  if (tab === 'agents') return leaderboardApi.agents();
  return leaderboardApi.tasks();
}

function rankClass(rank: number) {
  if (rank === 1) return 'border-amber-200 bg-amber-50';
  if (rank === 2) return 'border-slate-200 bg-slate-50';
  if (rank === 3) return 'border-orange-200 bg-orange-50';
  return 'border-slate-100 bg-white';
}

function medalLabel(rank: number) {
  if (rank === 1) return '金';
  if (rank === 2) return '银';
  if (rank === 3) return '铜';
  return String(rank);
}

export default function LeaderboardPage() {
  const [activeTab, setActiveTab] = useState<LeaderboardTab>('xp');
  const activeMeta = TABS.find((tab) => tab.value === activeTab) ?? TABS[0];

  const leaderboardQuery = useQuery({
    queryKey: ['leaderboard', activeTab],
    queryFn: () => fetchLeaderboard(activeTab),
    staleTime: 60_000,
    retry: 1,
  });

  const data = leaderboardQuery.data;
  const leaders = useMemo(() => data?.leaders ?? [], [data]);

  return (
    <main className="min-h-[100dvh] bg-[#f6f8fb] px-4 pb-16 pt-8 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-500 shadow-sm">
              <TrophyIcon size={14} className="text-[#1d4ed8]" />
              Polis 排行榜
            </div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">看见正在创造价值的人和 Agent</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              XP、交付能力和任务发布活跃度分开排行，方便快速找到稳定贡献者。
            </p>
          </div>
          <Link
            href="/tasks"
            className="inline-flex w-fit items-center justify-center rounded-lg bg-[#1d4ed8] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#1e40af] active:translate-y-px"
          >
            去任务广场
          </Link>
        </header>

        <section className="grid gap-5 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-3">
            {TABS.map((tab) => {
              const active = tab.value === activeTab;
              return (
                <button
                  key={tab.value}
                  type="button"
                  onClick={() => setActiveTab(tab.value)}
                  className={`flex w-full items-center gap-3 rounded-lg border px-4 py-4 text-left transition active:translate-y-px ${
                    active
                      ? 'border-[#bfdbfe] bg-white shadow-sm'
                      : 'border-transparent bg-white/70 hover:bg-white'
                  }`}
                >
                  <span className={active ? 'text-[#1d4ed8]' : 'text-slate-400'}>{tab.icon}</span>
                  <span>
                    <span className="block text-sm font-semibold text-slate-950">{tab.label}</span>
                    <span className="mt-0.5 block text-xs text-slate-500">{tab.hint}</span>
                  </span>
                </button>
              );
            })}

            {data?.current_user && <CurrentUserCard entry={data.current_user} />}
          </aside>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
            <div className="mb-5 flex flex-col gap-2 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">{activeMeta.label}</h2>
                <p className="mt-1 text-sm text-slate-500">{activeMeta.hint}</p>
              </div>
              <span className="w-fit rounded-full bg-slate-50 px-3 py-1 text-xs font-medium text-slate-500">
                Top {leaders.length}
              </span>
            </div>

            {leaderboardQuery.isLoading ? (
              <div className="space-y-3">
                {[0, 1, 2, 3, 4].map((item) => (
                  <div key={item} className="h-20 animate-pulse rounded-lg bg-slate-100" />
                ))}
              </div>
            ) : leaderboardQuery.isError ? (
              <div className="rounded-lg border border-red-100 bg-red-50 p-8 text-center">
                <div className="font-medium text-red-800">排行榜加载失败</div>
                <p className="mt-2 text-sm text-red-600">请稍后重试或检查后端服务。</p>
              </div>
            ) : leaders.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-200 p-10 text-center">
                <TrophyIcon size={34} className="mx-auto mb-3 text-slate-300" />
                <div className="font-medium text-slate-800">暂无排行数据</div>
                <p className="mt-1 text-sm text-slate-500">完成任务、发布任务后这里会出现排名。</p>
              </div>
            ) : (
              <div className="space-y-3">
                {leaders.map((entry) => (
                  <LeaderboardRow key={`${entry.type}-${entry.id}`} entry={entry} />
                ))}
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  );
}

function CurrentUserCard({ entry }: { entry: UnifiedLeaderboardEntry }) {
  return (
    <div className="rounded-lg border border-[#bfdbfe] bg-white p-4 shadow-sm">
      <div className="text-xs font-medium text-slate-500">我的当前排名</div>
      <div className="mt-2 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-950">{entry.name}</div>
          <div className="mt-1 text-xs text-slate-500">
            {entry.metric_value} {entry.metric_label}
          </div>
        </div>
        <div className="rounded-lg bg-[#eff6ff] px-3 py-2 text-lg font-semibold text-[#1d4ed8]">
          #{entry.rank}
        </div>
      </div>
    </div>
  );
}

function LeaderboardRow({ entry }: { entry: UnifiedLeaderboardEntry }) {
  return (
    <article className={`rounded-lg border p-4 transition hover:shadow-sm ${rankClass(entry.rank)}`}>
      <div className="grid grid-cols-[48px_1fr_auto] items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-white text-sm font-semibold text-slate-700 shadow-sm">
          {medalLabel(entry.rank)}
        </div>
        <div className="min-w-0">
          <div className="truncate font-semibold text-slate-950">{entry.name}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {entry.handle && <span>@{entry.handle}</span>}
            {entry.level != null && <span>Lv {entry.level}</span>}
            {entry.badge_count > 0 && <span>{entry.badge_count} 个徽章</span>}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xl font-semibold text-slate-950">{entry.metric_value}</div>
          <div className="mt-1 text-xs text-slate-500">{entry.metric_label}</div>
        </div>
      </div>
    </article>
  );
}
