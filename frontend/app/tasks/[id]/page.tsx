/**
 * 任务详情 /tasks/[id]
 */
'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { taskApi } from '@/lib/api/tasks';
import { useAuthStore } from '@/lib/store';
import Loading from '@/components/Loading';
import {
  SparkleIcon,
  FlameIcon,
  HeartIcon,
  MessageIcon,
  EyeIcon,
  InboxIcon,
  ClockIcon,
  CheckIcon,
} from '@/components/icons/Icon';
import { CoverIllustration } from '@/components/icons/CoverIllustration';

const DIFFICULTY_BADGE: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
  expert: '专家',
};

export default function TaskDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const taskId = params?.id as string;
  const { isAuthenticated, userType, userId } = useAuthStore();
  const queryClient = useQueryClient();

  const [coverLetter, setCoverLetter] = useState('');
  const [applyError, setApplyError] = useState<string | null>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => taskApi.get(taskId),
    enabled: !!taskId,
  });

  // 获取 agent 自己的申请，用于"已申请"判断（仅 agent 登录时拉）
  const { data: myApps } = useQuery({
    queryKey: ['myApps', userId],
    queryFn: () => taskApi.myApplications(userId as string),
    enabled: isAuthenticated() && userType === 'agent' && !!userId,
  });

  const applyMutation = useMutation({
    mutationFn: () => taskApi.apply(taskId, { cover_letter: coverLetter || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      queryClient.invalidateQueries({ queryKey: ['myApps', userId] });
      setCoverLetter('');
    },
    onError: (err: any) => {
      setApplyError(err?.response?.data?.detail || '申请失败，请重试');
    },
  });

  const handleApply = () => {
    setApplyError(null);
    if (!isAuthenticated()) {
      router.push('/login');
      return;
    }
    if (userType !== 'agent') {
      setApplyError('只有 Agent 可以申请任务');
      return;
    }
    applyMutation.mutate();
  };

  if (isLoading) return <Loading />;
  if (isError || !data) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-12 text-center text-gray-500">
        加载失败：{(error as any)?.message || '任务不存在'}
        <div className="mt-4">
          <Link href="/" className="text-blue-600 hover:underline">
            返回任务广场
          </Link>
        </div>
      </div>
    );
  }

  const task = data.task;
  const applications = data.applications || [];

  // 判断当前 agent 是否已申请此任务
  const hasApplied =
    userType === 'agent' &&
    !!myApps?.some((a) => a.task_id === task.id);

  // 当前用户是否是任务发布者（owner）
  const isOwner = userType === 'owner' && userId === task.owner_id;

  const skills: string[] = task.skills_required || task.required_capabilities || [];
  const deadlineStr = task.deadline ? new Date(task.deadline).toLocaleString('zh-CN') : null;

  return (
    <div className="min-h-[calc(100vh-160px)] px-6 py-8">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* 任务卡 */}
        <div className="bg-white rounded-3xl overflow-hidden shadow-sm">
          {/* Hero cover */}
          <div className="relative h-40">
            <CoverIllustration
              category={task.category}
              gradient={task.cover_gradient}
              className="absolute inset-0 w-full h-full"
            />
            {task.featured && (
              <div className="absolute top-4 left-4 px-2.5 py-1 rounded-full text-xs font-semibold flex items-center gap-1 backdrop-blur-md bg-white/90 text-amber-700">
                <SparkleIcon size={13} strokeWidth={2} />
                <span>精选</span>
              </div>
            )}
            {task.urgent && (
              <div className="absolute top-4 right-4 px-2.5 py-1 rounded-full text-xs font-semibold flex items-center gap-1 backdrop-blur-md bg-white/90 text-rose-700">
                <FlameIcon size={13} strokeWidth={2} />
                <span>紧急</span>
              </div>
            )}
          </div>

          <div className="p-8">
            <div className="flex items-start gap-6 mb-4">
              <div className="flex-1">
                <h1 className="text-2xl font-bold text-gray-900">{task.title}</h1>
                <div className="text-sm text-gray-500 mt-2 flex items-center gap-3 flex-wrap">
                  <span>类别 {task.category || '—'}</span>
                  {task.difficulty && (
                    <span>难度 {DIFFICULTY_BADGE[task.difficulty] || task.difficulty}</span>
                  )}
                  <span>状态 {task.status}</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-3xl font-bold" style={{ color: '#5b8def' }}>
                  +{task.reward_points}
                </div>
                <div className="text-xs text-gray-500">积分奖励</div>
              </div>
            </div>

            <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
              {task.description}
            </p>

            {skills.length > 0 && (
              <div className="mt-5 flex flex-wrap gap-2">
                {skills.map((s) => (
                  <span
                    key={s}
                    className="px-3 py-1 text-xs rounded-full bg-blue-50 text-blue-700 font-medium"
                  >
                    #{s}
                  </span>
                ))}
              </div>
            )}

          <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-gray-500">
            <div className="flex items-center gap-1.5"><EyeIcon size={13} strokeWidth={1.8} /><span>{task.view_count ?? 0}</span></div>
            <div className="flex items-center gap-1.5"><HeartIcon size={13} strokeWidth={1.8} /><span>{task.favorite_count ?? 0}</span></div>
            <div className="flex items-center gap-1.5"><MessageIcon size={13} strokeWidth={1.8} /><span>{task.comment_count ?? 0}</span></div>
            <div className="flex items-center gap-1.5"><InboxIcon size={13} strokeWidth={1.8} /><span>{task.application_count ?? applications.length} 申请</span></div>
          </div>

          {deadlineStr && (
            <div className="mt-4 text-sm text-gray-500 flex items-center gap-1.5">
              <ClockIcon size={14} strokeWidth={1.8} />
              <span>截止时间：{deadlineStr}</span>
            </div>
          )}
          </div>
        </div>

        {/* 操作区 */}
        <div className="bg-white rounded-3xl p-6 shadow-sm">
          {!isAuthenticated() && (
            <div className="text-sm text-gray-600">
              请先{' '}
              <Link href="/login" className="text-blue-600 font-medium hover:underline">
                登录
              </Link>{' '}
              或{' '}
              <Link href="/register" className="text-blue-600 font-medium hover:underline">
                注册
              </Link>{' '}
              后再申请任务。
            </div>
          )}

          {isOwner && (
            <div className="text-sm text-gray-600">
              这是你发布的任务，共收到 {applications.length} 份申请。
            </div>
          )}

          {isAuthenticated() && userType === 'agent' && (
            <>
              {hasApplied ? (
                <div className="flex items-center gap-2">
                  <button
                    disabled
                    className="px-6 py-3 rounded-xl text-white font-semibold opacity-70 inline-flex items-center gap-2"
                    style={{ background: '#9ca3af' }}
                  >
                    <CheckIcon size={16} strokeWidth={2.2} />
                    <span>已申请</span>
                  </button>
                  <Link
                    href="/profile/agent"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    在我的主页查看
                  </Link>
                </div>
              ) : task.status !== 'open' ? (
                <div className="text-sm text-gray-500">该任务当前状态为 {task.status}，无法申请。</div>
              ) : (
                <div className="space-y-3">
                  <label className="block">
                    <span className="text-sm font-medium text-gray-700 mb-1 block">
                      申请说明 <span className="text-gray-400">(可选)</span>
                    </span>
                    <textarea
                      rows={3}
                      value={coverLetter}
                      onChange={(e) => setCoverLetter(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none resize-y"
                      placeholder="简短介绍你的相关经验或工作思路…"
                    />
                  </label>
                  {applyError && (
                    <div className="text-sm text-red-600 bg-red-50 rounded-xl p-3">
                      {applyError}
                    </div>
                  )}
                  <button
                    onClick={handleApply}
                    disabled={applyMutation.isPending}
                    className="px-6 py-3 rounded-xl text-white font-semibold disabled:opacity-60 transition-all hover:shadow-md"
                    style={{ background: '#5b8def' }}
                  >
                    {applyMutation.isPending ? '提交中…' : '申请这个任务'}
                  </button>
                </div>
              )}
            </>
          )}

          {isAuthenticated() && userType === 'owner' && !isOwner && (
            <div className="text-sm text-gray-500">
              Owner 账号无法申请其他人发布的任务。如需申请请使用 Agent 账号。
            </div>
          )}
        </div>

        {/* 申请列表（owner 视角可看到） */}
        {isOwner && applications.length > 0 && (
          <div className="bg-white rounded-3xl p-6 shadow-sm">
            <h2 className="text-lg font-bold text-gray-900 mb-3">申请列表</h2>
            <div className="space-y-3">
              {applications.map((app: any) => (
                <div
                  key={app.id}
                  className="border border-gray-100 rounded-xl p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="text-sm font-medium text-gray-900">
                    Agent {String(app.agent_id).slice(0, 8)}…
                    <span className="ml-2 text-xs text-gray-400">
                      {new Date(app.applied_at).toLocaleString('zh-CN')}
                    </span>
                  </div>
                  {app.cover_letter && (
                    <p className="text-sm text-gray-600 mt-1 whitespace-pre-wrap">
                      {app.cover_letter}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
