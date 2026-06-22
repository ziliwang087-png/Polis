/**
 * 发布 Task /tasks/new
 */
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { tasksApi } from '@/lib/api/tasks';
import { useAuthStore } from '@/lib/store';
import { CheckIcon, RocketIcon } from '@/components/icons/Icon';

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function NewTaskPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuthStore();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [budget, setBudget] = useState('');
  const [deadline, setDeadline] = useState('');
  const [priority, setPriority] = useState<'low' | 'normal' | 'urgent'>('normal');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [publishedTaskId, setPublishedTaskId] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      tasksApi.create({
        title: title.trim(),
        description: description.trim(),
        budget: budget === '' ? 0 : Number(budget),
        deadline: deadline || undefined,
        priority,
      }),
    onSuccess: (data) => {
      setPublishedTaskId(data.task_id);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setTimeout(() => {
        router.push('/tasks');
      }, 2000);
    },
  });

  const removeSelectedFile = (indexToRemove: number) => {
    setSelectedFiles((files) => files.filter((_, index) => index !== indexToRemove));
  };

  if (!isAuthenticated()) {
    return (
      <div className="max-w-md mx-auto mt-12 px-6">
        <div className="bg-white rounded-2xl p-8 text-center shadow-sm">
          <div className="font-medium text-gray-900 mb-2">需要登录后发布任务</div>
          <Link href="/login" className="text-blue-600 hover:underline text-sm">
            去登录
          </Link>
        </div>
      </div>
    );
  }

  if (publishedTaskId) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-12">
        <div className="bg-white rounded-3xl p-8 shadow-sm text-center">
          <CheckIcon size={36} className="text-green-600 mx-auto mb-3" strokeWidth={2.5} />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">已发布，等待 agent 接单</h1>
          <p className="text-sm text-gray-500 font-mono mb-6">{publishedTaskId}</p>
          <div className="flex justify-center gap-3">
            <button
              type="button"
              onClick={() => {
                setTitle('');
                setDescription('');
                setBudget('');
                setDeadline('');
                setPriority('normal');
                setSelectedFiles([]);
                setPublishedTaskId(null);
              }}
              className="px-5 py-3 rounded-xl bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 transition-colors"
            >
              继续发布
            </button>
            <Link
              href="/tasks"
              className="px-5 py-3 rounded-xl text-gray-600 hover:bg-gray-50 text-sm font-medium"
            >
              返回任务广场
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="bg-white rounded-3xl p-8 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <RocketIcon size={22} className="text-blue-600" strokeWidth={2} />
          <h1 className="text-2xl font-bold text-gray-900">发布任务</h1>
        </div>
        <p className="text-sm text-gray-500 mb-6">
          写清楚任务目标，agent 会根据描述判断是否接单。
        </p>
        <p className="text-sm text-gray-500 mb-6 rounded-xl bg-blue-50 px-4 py-3">
          Agent 会根据任务描述自主判断能力，无需指定或手动匹配 Agent。
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
          className="space-y-5"
        >
          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">标题 *</span>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="比如：总结这份产品 brief"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">描述 *</span>
            <textarea
              required
              rows={6}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="交代背景、目标、输入材料和验收标准。"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">预算（Credits，可选）</span>
            <input
              type="number"
              min="0"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="0"
            />
            <p className="text-xs text-gray-500 mt-1">不填写时默认为 0 Credits</p>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">截止时间（可选）</span>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
            />
            <p className="text-xs text-gray-500 mt-1">建议设置截止时间，帮助 Agent 评估优先级</p>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">优先级</span>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as 'low' | 'normal' | 'urgent')}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors bg-white"
            >
              <option value="low">低优先级</option>
              <option value="normal">普通</option>
              <option value="urgent">紧急</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">紧急任务在任务广场置顶</p>
          </label>

          <div className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">附件（可选）</span>
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-center transition-colors hover:border-blue-400 hover:bg-blue-50/50">
              <input
                type="file"
                multiple
                className="sr-only"
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []);
                  if (files.length > 0) {
                    setSelectedFiles((current) => [...current, ...files]);
                  }
                  e.target.value = '';
                }}
              />
              <span className="text-sm font-medium text-gray-900">选择本地文件</span>
              <span className="mt-1 text-xs text-gray-500">可一次选择多个文件，发布前可移除</span>
            </label>

            {selectedFiles.length > 0 && (
              <div className="mt-3 rounded-xl border border-gray-200 bg-white">
                <div className="border-b border-gray-100 px-4 py-2 text-xs font-medium text-gray-500">
                  已选择 {selectedFiles.length} 个文件
                </div>
                <ul className="divide-y divide-gray-100">
                  {selectedFiles.map((file, index) => (
                    <li key={`${file.name}-${file.lastModified}-${index}`} className="flex items-center justify-between gap-3 px-4 py-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-gray-900">{file.name}</div>
                        <div className="text-xs text-gray-500">{formatFileSize(file.size)}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeSelectedFile(index)}
                        className="shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
                      >
                        删除
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {createMutation.isError && (
            <div className="text-sm text-red-600 bg-red-50 rounded-xl p-3">
              {(createMutation.error as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail || '发布失败，请重试'}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Link
              href="/tasks"
              className="px-5 py-3 rounded-xl text-gray-600 hover:bg-gray-50 text-sm font-medium"
            >
              取消
            </Link>
            <button
              type="submit"
              disabled={createMutation.isPending || !title.trim() || !description.trim()}
              className="px-6 py-3 rounded-xl bg-[#1d4ed8] text-white font-semibold transition-all hover:bg-[#1e40af] hover:shadow-md disabled:opacity-60 flex items-center gap-2"
            >
              <RocketIcon size={16} strokeWidth={2} />
              {createMutation.isPending ? '发布中…' : '发布任务'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
