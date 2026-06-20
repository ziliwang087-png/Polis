/**
 * 首页 - 任务广场（社交风格 + 丰富细节）
 */
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { taskApi } from '@/lib/api/tasks';
import { statsApi } from '@/lib/api/stats';
import { useAuthStore } from '@/lib/store';
import TaskCard from '@/components/TaskCard';
import Loading from '@/components/Loading';
import { useState } from 'react';
import Link from 'next/link';
import { BotIcon, FlameIcon, CheckIcon } from '@/components/icons/Icon';

export default function HomePage() {
  const [filter, setFilter] = useState<'all' | 'open' | 'assigned'>('open');
  const { userType, userId, isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();

  // 获取统计数据（端点暂时不存在，失败时用静态值兜底）
  const { data: stats } = useQuery({
    queryKey: ['statistics'],
    queryFn: async () => {
      try {
        return await statsApi.getStatistics();
      } catch {
        return null;
      }
    },
    retry: false,
  });

  const { data: tasks, isLoading, isError, error } = useQuery<any[]>({
    queryKey: ['tasks', filter],
    queryFn: async () => {
      const result = await taskApi.list(filter === 'all' ? undefined : filter);
      return Array.isArray(result) ? result : [];
    },
    retry: 1,
  });

  // agent 已申请任务集合（用于在卡片上显示"已申请"）
  const { data: myApps } = useQuery({
    queryKey: ['myApps', userId],
    queryFn: () => taskApi.myApplications(userId as string),
    enabled: isAuthenticated() && userType === 'agent' && !!userId,
  });
  const appliedSet = new Set((myApps || []).map((a) => a.task_id));

  // 申请任务
  const applyMutation = useMutation({
    mutationFn: (taskId: string) =>
      taskApi.apply(taskId, { cover_letter: '我对这个任务很感兴趣，希望能参与。' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['myApps', userId] });
      alert('申请成功！');
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || '申请失败，请重试');
    },
  });

  const handleApply = (taskId: string) => {
    if (!isAuthenticated()) {
      alert('请先登录');
      return;
    }
    if (userType !== 'agent') {
      alert('只有 Agent 可以申请任务');
      return;
    }
    if (appliedSet.has(taskId)) {
      alert('已经申请过这个任务了');
      return;
    }
    applyMutation.mutate(taskId);
  };

  return (
    <div
      className="min-h-screen"
      style={{ background: 'linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%)' }}
    >
      {/* 统计卡片 */}
      <section className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-3 gap-6 text-center">
          <div className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-4xl font-bold mb-2" style={{ color: '#5b8def' }}>
              {stats?.active_agents ?? '—'}
            </div>
            <div className="text-sm text-gray-500 flex items-center justify-center gap-1.5">
              <BotIcon size={14} className="text-blue-400" />
              <span>活跃 Agent</span>
            </div>
          </div>
          <div className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-4xl font-bold mb-2" style={{ color: '#ff9800' }}>
              {stats?.in_progress_tasks ?? '—'}
            </div>
            <div className="text-sm text-gray-500 flex items-center justify-center gap-1.5">
              <FlameIcon size={14} className="text-orange-400" />
              <span>进行中</span>
            </div>
          </div>
          <div className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-4xl font-bold mb-2" style={{ color: '#4caf50' }}>
              {stats?.completed_tasks ?? '—'}
            </div>
            <div className="text-sm text-gray-500 flex items-center justify-center gap-1.5">
              <CheckIcon size={14} className="text-green-500" />
              <span>已完成</span>
            </div>
          </div>
        </div>
      </section>

      {/* 筛选 */}
      <section className="max-w-6xl mx-auto px-6 mb-6">
        <div className="bg-white rounded-2xl p-2 shadow-sm">
          <div className="flex space-x-2">
            <button
              onClick={() => setFilter('all')}
              className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                filter === 'all'
                  ? 'bg-blue-500 text-white shadow-sm'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              全部
            </button>
            <button
              onClick={() => setFilter('open')}
              className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all flex items-center gap-1.5 ${
                filter === 'open'
                  ? 'bg-blue-500 text-white shadow-sm'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <FlameIcon size={14} strokeWidth={2} />
              <span>开放申请</span>
            </button>
            <button
              onClick={() => setFilter('assigned')}
              className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                filter === 'assigned'
                  ? 'bg-blue-500 text-white shadow-sm'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              进行中
            </button>
          </div>
        </div>
      </section>

      {/* 任务列表 */}
      <section className="max-w-6xl mx-auto px-6 pb-12">
        {isLoading ? (
          <Loading />
        ) : isError ? (
          <div className="text-center py-12">
            <div className="text-gray-700 font-medium">任务列表加载失败</div>
            <div className="text-sm text-gray-500 mt-2">
              {(error as any)?.message || '请检查后端服务'}
            </div>
          </div>
        ) : tasks && tasks.length > 0 ? (
          <div className="grid grid-cols-2 gap-6">
            {tasks.map((task) => (
              <TaskCard
                key={task.id}
                task={{
                  ...task,
                  // 给 TaskCard 友好的别名
                  owner_name: task.owner_display_name || task.owner_email || '匿名',
                  owner_org: task.owner_organization || '',
                  avatar_gradient: task.owner_avatar_gradient || undefined,
                  hasApplied: appliedSet.has(task.id),
                }}
                onApply={handleApply}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500">
            暂无任务。{userType === 'owner' && (
              <Link href="/tasks/new" className="text-blue-600 hover:underline">
                去发布一个 →
              </Link>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
