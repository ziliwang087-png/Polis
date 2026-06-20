/**
 * TaskCard —— 全新图标版（已剔除 emoji）
 */
'use client';

import { Task } from '@/lib/types';
import { useAuthStore } from '@/lib/store';
import {
  StarIcon,
  HeartIcon,
  MessageIcon,
  EyeIcon,
  UsersIcon,
  ClockIcon,
  GemIcon,
  FlameIcon,
  CheckIcon,
  SparkleIcon,
} from './icons/Icon';
import { CoverIllustration } from './icons/CoverIllustration';

interface TaskCardProps {
  task: Task & {
    owner_name?: string;
    owner_org?: string;
    owner_rating?: number;
    owner_verified?: boolean;
    owner_display_name?: string;
    owner_organization?: string;
    owner_avatar_gradient?: string;
    view_count?: number;
    favorite_count?: number;
    comment_count?: number;
    difficulty?: 'easy' | 'medium' | 'hard' | 'expert' | string | null;
    deadline?: string | null;
    skills_required?: string[];
    cover_emoji?: string;
    cover_gradient?: string;
    avatar_gradient?: string;
    urgent?: boolean;
    featured?: boolean;
  };
  onApply?: (taskId: string) => void;
}

export default function TaskCard({ task, onApply }: TaskCardProps) {
  const { userType, isAuthenticated } = useAuthStore();

  const getDifficultyBadge = () => {
    if (!task.difficulty) return null;
    const styles: Record<string, { bg: string; color: string; text: string }> = {
      easy: { bg: '#e8f5e9', color: '#2e7d32', text: '简单' },
      medium: { bg: '#fff3e0', color: '#e65100', text: '中等' },
      hard: { bg: '#ffebee', color: '#c62828', text: '困难' },
      expert: { bg: '#fce4ec', color: '#ad1457', text: '专家' },
    };
    const style = styles[task.difficulty as string];
    if (!style) return null;
    return (
      <span
        className="px-2 py-1 rounded-lg text-xs font-semibold"
        style={{ background: style.bg, color: style.color }}
      >
        {style.text}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'open':
        return (
          <span
            className="px-3 py-1.5 rounded-full text-xs font-semibold"
            style={{ background: '#e8f5e9', color: '#2e7d32' }}
          >
            开放中
          </span>
        );
      case 'assigned':
      case 'in_progress':
      case 'submitted':
      case 'under_review':
        return (
          <span
            className="px-3 py-1.5 rounded-full text-xs font-semibold"
            style={{ background: '#e3f2fd', color: '#1565c0' }}
          >
            进行中
          </span>
        );
      case 'completed':
        return (
          <span className="px-3 py-1.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">
            已完成
          </span>
        );
      default:
        return null;
    }
  };

  const getTimeRemaining = () => {
    if (!task.deadline) return null;
    const now = new Date();
    const deadline = new Date(task.deadline);
    const diff = deadline.getTime() - now.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    if (days > 0) return `${days}天后截止`;
    if (hours > 0) return `${hours}小时后截止`;
    return '即将截止';
  };

  const getPublishTime = () => {
    const now = new Date();
    const created = new Date(task.created_at);
    const diff = now.getTime() - created.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days}天前`;
    if (hours > 0) return `${hours}小时前`;
    return '刚刚';
  };

  const canApply = isAuthenticated() && userType === 'agent' && task.status === 'open';

  return (
    <div
      className="bg-white rounded-3xl overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-1"
      style={{ boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)' }}
    >
      {/* 封面：几何图案 + 渐变 */}
      <div className="relative h-44">
        <CoverIllustration
          category={task.category}
          gradient={task.cover_gradient}
          className="absolute inset-0 w-full h-full"
        />

        {/* 推荐标记 */}
        {task.featured && (
          <div
            className="absolute top-3 left-3 px-2.5 py-1 rounded-full text-[11px] font-semibold flex items-center gap-1 backdrop-blur-md"
            style={{ background: 'rgba(255, 255, 255, 0.92)', color: '#92400e' }}
          >
            <SparkleIcon size={12} strokeWidth={2} />
            <span>推荐</span>
          </div>
        )}

        {/* 紧急标记 */}
        {task.urgent && (
          <div
            className="absolute top-3 right-3 px-2.5 py-1 rounded-full text-[11px] font-semibold flex items-center gap-1 backdrop-blur-md"
            style={{ background: 'rgba(255, 255, 255, 0.92)', color: '#b91c1c' }}
          >
            <FlameIcon size={12} strokeWidth={2} />
            <span>紧急</span>
          </div>
        )}

        {/* 浏览量 */}
        {!!task.view_count && (
          <div
            className="absolute bottom-3 right-3 px-2.5 py-1 rounded-full text-[11px] font-medium flex items-center gap-1 backdrop-blur-md"
            style={{ background: 'rgba(255, 255, 255, 0.92)', color: '#475569' }}
          >
            <EyeIcon size={12} strokeWidth={2} />
            <span>{task.view_count}</span>
          </div>
        )}
      </div>

      <div className="p-6">
        {/* 发布者 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div
              className="w-11 h-11 rounded-full flex items-center justify-center text-white font-semibold text-base"
              style={{
                background:
                  task.owner_avatar_gradient ||
                  task.avatar_gradient ||
                  'linear-gradient(135deg, #64b5f6, #42a5f5)',
              }}
            >
              {(
                (task.owner_display_name || task.owner_name || task.owner_id) as string
              )
                .slice(0, 2)
                .toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-1">
                <span className="text-sm font-semibold text-gray-900">
                  {task.owner_display_name ||
                    task.owner_name ||
                    (task.owner_id as string).slice(0, 8)}
                </span>
                {task.owner_verified && (
                  <CheckIcon size={14} strokeWidth={2.2} className="text-blue-500" />
                )}
              </div>
              <div className="text-xs text-gray-500 flex items-center gap-2">
                <span>{task.owner_organization || task.owner_org || '个人'}</span>
                {task.owner_rating != null && (
                  <>
                    <span>·</span>
                    <span className="flex items-center gap-0.5 text-amber-500">
                      <StarIcon size={11} strokeWidth={2} filled />
                      <span className="text-gray-700">
                        {Number(task.owner_rating).toFixed(1)}
                      </span>
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
          {getStatusBadge(task.status)}
        </div>

        {/* 标题 + 难度 */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-lg font-bold text-gray-900 flex-1 leading-tight">
            {task.title}
          </h3>
          {getDifficultyBadge()}
        </div>

        <p className="text-sm text-gray-600 mb-4 leading-relaxed line-clamp-2">
          {task.description}
        </p>

        {!!task.skills_required?.length && (
          <div className="flex flex-wrap gap-2 mb-4">
            {task.skills_required.slice(0, 3).map((skill, idx) => (
              <span
                key={idx}
                className="px-3 py-1 rounded-xl text-xs font-medium"
                style={{
                  background: ['#e3f2fd', '#fce4ec', '#fff3e0', '#e8f5e9', '#f3e5f5'][idx % 5],
                  color: ['#1976d2', '#c2185b', '#e65100', '#388e3c', '#7b1fa2'][idx % 5],
                }}
              >
                #{skill}
              </span>
            ))}
          </div>
        )}

        {/* 底部 */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-100">
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span className="flex items-center gap-1.5 font-semibold text-gray-900">
              <GemIcon size={15} className="text-blue-500" strokeWidth={1.8} />
              <span>+{task.reward_points}</span>
            </span>
            {task.application_count !== undefined && task.application_count > 0 && (
              <span className="flex items-center gap-1 text-gray-500">
                <UsersIcon size={14} strokeWidth={1.8} />
                <span>{task.application_count}</span>
              </span>
            )}
            {task.deadline && (
              <span className="flex items-center gap-1 text-orange-600 font-medium">
                <ClockIcon size={14} strokeWidth={1.8} />
                <span>{getTimeRemaining()}</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-1">
            {task.favorite_count !== undefined && (
              <button
                className="w-9 h-9 rounded-full flex items-center justify-center text-gray-400 hover:text-rose-500 hover:bg-rose-50 transition-colors"
                title="收藏"
                aria-label="收藏"
              >
                <HeartIcon size={16} strokeWidth={1.75} />
              </button>
            )}
            {task.comment_count !== undefined && (
              <button
                className="w-9 h-9 rounded-full flex items-center justify-center text-gray-400 hover:text-blue-500 hover:bg-blue-50 transition-colors"
                title="评论"
                aria-label="评论"
              >
                <MessageIcon size={16} strokeWidth={1.75} />
              </button>
            )}
            {canApply && onApply && (
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onApply(task.id);
                }}
                className="ml-2 px-4 py-2 text-sm font-semibold text-white rounded-xl transition-all hover:shadow-md"
                style={{ background: '#5b8def' }}
              >
                申请
              </button>
            )}
          </div>
        </div>

        <div className="mt-3 text-xs text-gray-400">发布于 {getPublishTime()}</div>
      </div>
    </div>
  );
}
