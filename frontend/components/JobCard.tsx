/**
 * JobCard —— 任务卡片（用于广场和 dashboard）。
 *
 * 没有任何社交功能（点赞 / 收藏 / 评论），只展示任务关键信息 + 状态。
 */
'use client';

import Link from 'next/link';
import type { Job } from '@/lib/api/types';
import { JOB_STATUS_META, relativeTime } from '@/lib/format';
import { ClockIcon, UsersIcon, BotIcon, BriefcaseIcon } from './icons/Icon';

export default function JobCard({ job }: { job: Job }) {
  const statusMeta = JOB_STATUS_META[job.status];

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
          <span className="font-medium text-gray-700">
            {job.from_user?.display_name || job.from_user?.username || job.from_user_id.slice(0, 8)}
          </span>
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
        {job.to_agent ? (
          <span className="flex items-center gap-1.5 text-gray-700">
            <BotIcon size={13} strokeWidth={1.8} />
            {job.to_agent.display_name || job.to_agent.name}
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
