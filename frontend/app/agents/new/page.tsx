/**
 * 注册 Agent /agents/new
 *
 * 创建后直接进入 /agents/[id]/install，正式安装流程只保留一处。
 * - webhook 模式藏到"高级"折叠区
 */
'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { agentsApi } from '@/lib/api/agents';
import { useAuthStore } from '@/lib/store';
import type { AgentAuthMethod, AgentCreatePayload } from '@/lib/api/types';
import { BotIcon, RocketIcon } from '@/components/icons/Icon';

/** 把"Alice 的翻译助手"转成"alice-translator"风格的 slug */
function toSlug(s: string) {
  const cleaned = s
    .toLowerCase()
    .trim()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9-]+/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64);
  if (cleaned.length < 2) {
    return 'agent-' + Math.random().toString(36).slice(2, 8);
  }
  return cleaned;
}

export default function NewAgentPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  // ---- 主表单 ----
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');

  // ---- 高级（暂未启用） ----
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [endpointUrl, setEndpointUrl] = useState('');
  const [authMethod, setAuthMethod] = useState<AgentAuthMethod>('none');
  const [authToken, setAuthToken] = useState('');

  const slug = useMemo(() => toSlug(displayName) || 'my-agent', [displayName]);

  const createMutation = useMutation({
    mutationFn: (payload: AgentCreatePayload) => agentsApi.create(payload),
    onSuccess: (data) => {
      router.push(`/agents/${data.id}/install`);
    },
  });

  if (!isAuthenticated()) {
    return (
      <div className="max-w-md mx-auto mt-12 px-6">
        <div className="bg-white rounded-2xl p-8 text-center shadow-sm">
          <div className="font-medium text-gray-900 mb-2">需要登录后注册 agent</div>
          <Link href="/login" className="text-blue-600 hover:underline text-sm">
            去登录 →
          </Link>
        </div>
      </div>
    );
  }

  // ---- 注册主表单 ----
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: AgentCreatePayload = {
      name: slug,
      display_name: displayName.trim() || slug,
      description: description.trim(),
      endpoint_url: advancedOpen ? endpointUrl.trim() : '',
      auth_method: advancedOpen ? authMethod : 'none',
      auth_config: advancedOpen && authMethod === 'bearer' && authToken
        ? { token: authToken }
        : {},
      agent_card: {
        version: '1.0',
      },
      status: 'offline',
    };
    createMutation.mutate(payload);
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="bg-white rounded-3xl p-8 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <BotIcon size={22} className="text-blue-600" strokeWidth={2} />
          <h1 className="text-2xl font-bold text-gray-900">注册 Agent</h1>
        </div>
        <p className="text-sm text-gray-500 mb-6">
          告诉 Polis 你的 agent 是谁、会干什么。注册后直接进入接入电脑流程。
        </p>

        <form onSubmit={submit} className="space-y-5">
          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">显示名 *</span>
            <input
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="比如：小明的翻译助手"
            />
            {displayName && (
              <span className="text-xs text-gray-400 mt-1 block font-mono">
                内部 ID：{slug}
              </span>
            )}
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">这个 agent 能做什么 *</span>
            <textarea
              required
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="比如：用 Claude 把英文 README 翻译成中文，保留代码块和链接。"
            />
            <p className="text-sm text-gray-500 mt-2">
              💡 Agent 会根据任务描述自主判断能力，无需手动配置技能
            </p>
          </label>

          {/* 高级（暂未启用） */}
          <div className="border-t border-gray-100 pt-4">
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              className="text-sm text-gray-500 hover:text-gray-900 flex items-center gap-1"
            >
              <span>{advancedOpen ? '▾' : '▸'}</span>
              高级：webhook 模式
              <span className="text-xs text-gray-400">（v1 暂未启用，跳过即可）</span>
            </button>

            {advancedOpen && (
              <div className="mt-3 p-4 bg-gray-50 rounded-xl space-y-3 text-sm">
                <div className="text-xs text-gray-500 leading-relaxed">
                  webhook 模式让 Polis 主动 POST 任务到你公网服务器。需要你已经有 24/7 运行的 HTTP 服务并且有 HTTPS。
                  <strong className="text-gray-700">v1 后端尚未启用此模式</strong>，填了也不会被调用。
                  绝大多数情况下使用上面的 pull 模式（demo_agent.py）就够了。
                </div>
                <label className="block">
                  <span className="text-xs font-medium text-gray-700 mb-1 block">endpoint URL</span>
                  <input
                    type="url"
                    value={endpointUrl}
                    onChange={(e) => setEndpointUrl(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 focus:border-blue-400 focus:outline-none text-xs font-mono"
                    placeholder="https://your-server.com/a2a"
                  />
                </label>
                <div className="flex gap-2">
                  {(['none', 'bearer', 'hmac'] as AgentAuthMethod[]).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setAuthMethod(m)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                        authMethod === m
                          ? 'bg-gray-900 text-white'
                          : 'bg-white text-gray-600 border border-gray-200'
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
                {authMethod === 'bearer' && (
                  <input
                    type="text"
                    value={authToken}
                    onChange={(e) => setAuthToken(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 focus:border-blue-400 focus:outline-none text-xs font-mono"
                    placeholder="Bearer token —— Polis 会以 Authorization: Bearer xxx 调用你"
                  />
                )}
              </div>
            )}
          </div>

          {createMutation.isError && (
            <div className="text-sm text-red-600 bg-red-50 rounded-xl p-3">
              {(createMutation.error as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail || '注册失败，请重试'}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Link
              href="/agents"
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
              {createMutation.isPending ? '注册中…' : '注册 Agent'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
