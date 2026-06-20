/**
 * JobCard —— 任务卡片（用于广场和 dashboard）。
 *
 * 没有任何社交功能（点赞 / 收藏 / 评论），只展示任务关键信息 + 状态。
 *
 * 名字解析：
 * - 后端 GET /jobs 不 join users/agents，只返回 UUID。
 * - 调用方传入 `agentNameMap`（agent_id → display name）和可选 `fromUserName`。
 * - 解析失败时退化成 UUID 前 8 位 + 友好前缀。
 */
'use client';

import Link from 'next/link';
import type { Job } from '@/lib/api/types';
import { JOB_STATUS_META, relativeTime } from '@/lib/format';
import { ClockIcon, UsersIcon, BotIcon, BriefcaseIcon } from './icons/Icon';

type Props = {
  job: Job;
  /** agent_id → display 名 的映射，没匹配上时退化为短 UUID */
  agentNameMap?: Map<string, string>;
  /** 调用方知道发起人的友好名（例如在 /me 页发起人就是当前用户） */
  fromUserName?: string;
};

function shortId(id: string | null | undefined) {
  return (id ?? '').slice(0, 8);
}

export default function JobCard({ job, agentNameMap, fromUserName }: Props) {
  const statusMeta = JOB_STATUS_META[job.status];
  const fromLabel =
    fromUserName ||
    job.from_user?.display_name ||
    job.from_user?.username ||
    `user ${shortId(job.from_user_id)}`;
  const agentDisplay = job.to_agent_id
    ? agentNameMap?.get(job.to_agent_id) ||
      job.to_agent?.display_name ||
      job.to_agent?.name ||
      `agent ${shortId(job.to_agent_id)}`
    : null;

  return (
    <Link
      href={`/jobs/${job.id}`}
      className="block bg-white rounded-3xl p-6 transition-all duration-300 hover:shadow-xl hover:-translate-y-0.5"
      style={{ boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)' }}
    >
      {/* 顶部：发布者 + 状态 */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <BriefcaseIcon size={15} strokeWidth={1.8} className="text-gray-400" />
          <span className="font-medium text-gray-700">{fromLabel}</span>
        </div>
        <span
          className="px-3 py-1 rounded-full text-xs font-semibold"
          style={{ background: statusMeta.bg, color: statusMeta.color }}
        >
          {statusMeta.label}
        </span>
      </div>

      <h3 className="text-lg font-bold text-gray-900 leading-tight mb-2 line-clamp-1">
        {job.title}
      </h3>
      <p className="text-sm text-gray-600 leading-relaxed line-clamp-2 mb-4 min-h-[2.5em]">
        {job.description}
      </p>

      <div className="flex flex-wrap items-center gap-3 text-xs">
        <span
          className="px-2.5 py-1 rounded-lg font-medium"
          style={{ background: '#eef2ff', color: '#4338ca' }}
        >
          #{job.required_skill}
        </span>
        {(job.attachments?.length ?? 0) > 0 && (
          <span className="text-gray-500">{job.attachments?.length ?? 0} 个附件</span>
        )}
      </div>

      <div className="flex items-center justify-between pt-4 mt-4 border-t border-gray-100 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <ClockIcon size={13} strokeWidth={1.8} />
          {relativeTime(job.created_at)}
        </span>
        {agentDisplay ? (
          <span className="flex items-center gap-1.5 text-gray-700">
            <BotIcon size={13} strokeWidth={1.8} />
            {agentDisplay}
          </span>
        ) : (
          <span className="flex items-center gap-1.5">
            <UsersIcon size={13} strokeWidth={1.8} />
            等待 agent 抢单
          </span>
        )}
      </div>
    </Link>
  );
}
