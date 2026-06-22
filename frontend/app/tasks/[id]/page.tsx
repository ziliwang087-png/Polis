'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { tasksApi } from '@/lib/api/tasks';
import type { Task } from '@/lib/api/types';

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.id as string;

  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const taskQuery = useQuery({
    queryKey: ['tasks', taskId],
    queryFn: () => tasksApi.get(taskId),
    enabled: Boolean(taskId),
    retry: 1,
  });

  const task = taskQuery.data ?? null;

  const handleRate = async () => {
    if (rating === 0) {
      alert('请选择评分');
      return;
    }

      setSubmitting(true);
    try {
      await tasksApi.rate(taskId, rating, comment);
      alert('评分成功！');
      await taskQuery.refetch();
    } catch (error) {
      console.error('评分失败:', error);
      alert('评分失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (taskQuery.isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">加载中...</div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">任务不存在</div>
      </div>
    );
  }

  const statusColors: Record<Task['status'], string> = {
    open: 'bg-green-100 text-green-800',
    in_progress: 'bg-blue-100 text-blue-800',
    completed: 'bg-purple-100 text-purple-800',
    failed: 'bg-red-100 text-red-800',
    submitted: 'bg-yellow-100 text-yellow-800',
  };

  const statusText: Record<Task['status'], string> = {
    open: '待接单',
    in_progress: '进行中',
    completed: '已完成',
    failed: '已失败',
    submitted: '已提交',
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto py-8 px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">{task.title}</h1>
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <span className={`px-3 py-1 rounded-full font-medium ${statusColors[task.status]}`}>
                  {statusText[task.status]}
                </span>
                <span>分类: {task.category}</span>
                {task.difficulty && <span>难度: {task.difficulty}</span>}
                <span>奖励: {task.reward_points} 积分</span>
              </div>
            </div>
            <button
              onClick={() => router.back()}
              className="text-gray-600 hover:text-gray-900"
            >
              返回
            </button>
          </div>

          <div className="prose max-w-none">
            <h3 className="text-lg font-semibold mb-2">任务描述</h3>
            <p className="text-gray-700 whitespace-pre-wrap">{task.description}</p>
          </div>

          {task.required_capabilities && task.required_capabilities.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold mb-2">所需能力</h3>
              <div className="flex flex-wrap gap-2">
                {task.required_capabilities.map((cap, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                  >
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Agent Info */}
        {task.assigned_agent_id && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold mb-3">接单 Agent</h2>
            <div className="text-gray-700">
              <p>Agent ID: {task.assigned_agent_id}</p>
            </div>
          </div>
        )}

        {/* Timeline */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">时间线</h2>
          <div className="space-y-2 text-sm text-gray-600">
            <div>创建时间: {new Date(task.created_at).toLocaleString('zh-CN')}</div>
            {task.updated_at && (
              <div>更新时间: {new Date(task.updated_at).toLocaleString('zh-CN')}</div>
            )}
            {task.completed_at && (
              <div>完成时间: {new Date(task.completed_at).toLocaleString('zh-CN')}</div>
            )}
            {task.deadline && (
              <div>截止时间: {new Date(task.deadline).toLocaleString('zh-CN')}</div>
            )}
          </div>
        </div>

        {/* Rating Section - Only for completed tasks */}
        {task.status === 'completed' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">给任务评分</h2>

            {/* Star Rating */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                评分 (1-5 星)
              </label>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    onClick={() => setRating(star)}
                    className={`text-3xl ${
                      star <= rating ? 'text-yellow-400' : 'text-gray-300'
                    } hover:text-yellow-400 transition-colors`}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>

            {/* Comment */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                评价（可选）
              </label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={4}
                placeholder="说说你的感受..."
              />
            </div>

            {/* Submit Button */}
            <button
              onClick={handleRate}
              disabled={submitting || rating === 0}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? '提交中...' : '提交评分'}
            </button>
          </div>
        )}

        {/* Failed Info */}
        {task.status === 'failed' && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-red-900 mb-2">任务失败</h2>
            <p className="text-red-700">该任务执行失败，请查看错误信息或联系 Agent。</p>
          </div>
        )}
      </div>
    </div>
  );
}
