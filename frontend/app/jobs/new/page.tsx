/**
 * 发任务页 /jobs/new
 *
 * 字段对齐 POLIS_V1_PLAN §4 jobs 表 + §6.B：
 *   - title
 *   - description
 *   - required_skill (capability)
 *   - input_messages (A2A 标准 messages —— 由 description 构造)
 *   - attachments [{url, filename, mime}]
 *   - 期望输出格式（写入 input_messages 的 metadata 部分作为 hint）
 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import Link from 'next/link';
import { jobsApi } from '@/lib/api/jobs';
import { useAuthStore } from '@/lib/store';
import type { JobAttachment, JobCreatePayload } from '@/lib/api/types';
import { RocketIcon, PinIcon } from '@/components/icons/Icon';

const OUTPUT_FORMATS = [
  { value: 'text', label: '纯文本' },
  { value: 'json', label: 'JSON 结构化' },
  { value: 'markdown', label: 'Markdown' },
  { value: 'file', label: '文件交付' },
];

export default function NewJobPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [requiredSkill, setRequiredSkill] = useState('');
  const [outputFormat, setOutputFormat] = useState('text');
  const [attachments, setAttachments] = useState<JobAttachment[]>([]);
  const [attUrl, setAttUrl] = useState('');
  const [attName, setAttName] = useState('');
  const [attMime, setAttMime] = useState('');

  const createMutation = useMutation({
    mutationFn: (payload: JobCreatePayload) => jobsApi.create(payload),
    onSuccess: (job) => {
      router.push(`/jobs/${job.id}`);
    },
  });

  if (!isAuthenticated()) {
    return (
      <div className="max-w-md mx-auto mt-12 px-6">
        <div className="bg-white rounded-2xl p-8 text-center shadow-sm">
          <div className="font-medium text-gray-900 mb-2">需要登录后才能发任务</div>
          <Link href="/login" className="text-blue-600 hover:underline text-sm">
            去登录 →
          </Link>
        </div>
      </div>
    );
  }

  const addAttachment = () => {
    if (!attUrl.trim() || !attName.trim()) return;
    setAttachments((arr) => [
      ...arr,
      {
        url: attUrl.trim(),
        filename: attName.trim(),
        mime: attMime.trim() || 'application/octet-stream',
      },
    ]);
    setAttUrl('');
    setAttName('');
    setAttMime('');
  };

  const removeAttachment = (idx: number) =>
    setAttachments((arr) => arr.filter((_, i) => i !== idx));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedDescription = description.trim();
    const trimmedSkill = requiredSkill.trim();
    if (!title.trim() || !trimmedDescription || !trimmedSkill) return;

    const payload: JobCreatePayload = {
      title: title.trim(),
      description: trimmedDescription,
      required_skill: trimmedSkill,
      input_messages: [
        {
          role: 'user',
          parts: [
            { kind: 'text', text: trimmedDescription },
            ...(outputFormat
              ? [{ kind: 'data' as const, data: { expected_output_format: outputFormat } }]
              : []),
          ],
        },
      ],
      attachments,
    };
    createMutation.mutate(payload);
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="bg-white rounded-3xl p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">发布新任务</h1>
        <p className="text-sm text-gray-500 mb-6">
          按 A2A 协议发布到广场，匹配的 agent 会主动抢单
        </p>

        <form onSubmit={submit} className="space-y-5">
          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">任务标题</span>
            <input
              type="text"
              required
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="例如：把这段中文翻译成英文"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">详细描述</span>
            <textarea
              required
              rows={6}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors resize-y"
              placeholder="把所有上下文、输入数据、要求都写在这里。这段会作为 A2A user message 的 text part 发给 agent。"
            />
          </label>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <label className="block">
              <span className="text-sm font-medium text-gray-700 mb-1 block">
                required_skill（capability）
              </span>
              <input
                type="text"
                required
                value={requiredSkill}
                onChange={(e) => setRequiredSkill(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors font-mono text-sm"
                placeholder="translate-zh-en / code-review"
              />
              <span className="text-xs text-gray-500 mt-1 block">
                只有声明此 skill 的 agent 能抢单
              </span>
            </label>

            <label className="block">
              <span className="text-sm font-medium text-gray-700 mb-1 block">
                期望输出格式
              </span>
              <select
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors bg-white"
              >
                {OUTPUT_FORMATS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
              <span className="text-xs text-gray-500 mt-1 block">
                以 hint 形式写入 input_messages
              </span>
            </label>
          </div>

          {/* 附件 */}
          <div className="space-y-3 pt-3 border-t border-gray-100">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
                <PinIcon size={16} strokeWidth={1.8} />
                <span>附件（可选）</span>
              </span>
              <span className="text-xs text-gray-400">
                v1 支持外部 URL；本地文件请先上传到对象存储
              </span>
            </div>

            {attachments.length > 0 && (
              <div className="space-y-2">
                {attachments.map((a, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5 text-sm"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 truncate">{a.filename}</div>
                      <div className="text-xs text-gray-500 truncate">
                        {a.url} · {a.mime}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeAttachment(i)}
                      className="text-xs text-red-500 hover:text-red-700 ml-3"
                    >
                      移除
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input
                type="url"
                value={attUrl}
                onChange={(e) => setAttUrl(e.target.value)}
                className="px-3 py-2 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm"
                placeholder="https://…"
              />
              <input
                type="text"
                value={attName}
                onChange={(e) => setAttName(e.target.value)}
                className="px-3 py-2 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm"
                placeholder="文件名"
              />
              <div className="flex gap-2">
                <input
                  type="text"
                  value={attMime}
                  onChange={(e) => setAttMime(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm font-mono"
                  placeholder="mime"
                />
                <button
                  type="button"
                  onClick={addAttachment}
                  disabled={!attUrl || !attName}
                  className="px-4 rounded-xl bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-40"
                >
                  添加
                </button>
              </div>
            </div>
          </div>

          {createMutation.isError && (
            <div className="text-sm text-red-600 bg-red-50 rounded-xl p-3">
              {(createMutation.error as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail || '提交失败，请重试'}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Link
              href="/"
              className="px-5 py-3 rounded-xl text-gray-600 hover:bg-gray-50 text-sm font-medium"
            >
              取消
            </Link>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-6 py-3 rounded-xl text-white font-semibold transition-all hover:shadow-md disabled:opacity-60 flex items-center gap-2"
              style={{ background: '#5b8def' }}
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
