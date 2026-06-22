/**
 * 注册 Agent /agents/new
 *
 * v1.2 现代化风格（对齐 /agents/[id]/install 页面设计）：
 * - 注册成功后分步骤展示（1. 拿模板 / 2. 跑命令）
 * - 用卡片 + 编号圆圈 + 安全说明的设计语言
 * - 默认走 Pull 模式（demo_agent.py）
 * - webhook 模式藏到"高级"折叠区
 */
'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { agentsApi } from '@/lib/api/agents';
import { API_BASE_URL } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store';
import type { AgentAuthMethod, AgentCreatePayload } from '@/lib/api/types';
import { BotIcon, RocketIcon, CheckIcon, CopyIcon, ShieldIcon } from '@/components/icons/Icon';

/** API_BASE_URL 形如 https://api.example.com/api/v1 —— 砍掉 /api/v1 得 backend root */
function backendRoot(): string {
  try {
    const u = new URL(API_BASE_URL);
    return `${u.protocol}//${u.host}`;
  } catch {
    return 'http://localhost:8000';
  }
}

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
  const { isAuthenticated, user } = useAuthStore();

  // ---- 主表单 ----
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');

  // ---- 高级（暂未启用） ----
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [endpointUrl, setEndpointUrl] = useState('');
  const [authMethod, setAuthMethod] = useState<AgentAuthMethod>('none');
  const [authToken, setAuthToken] = useState('');

  // ---- 注册成功后展示 ----
  const [createdAgent, setCreatedAgent] = useState<{ name: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const slug = useMemo(() => toSlug(displayName) || 'my-agent', [displayName]);

  const createMutation = useMutation({
    mutationFn: (payload: AgentCreatePayload) => agentsApi.create(payload),
    onSuccess: (_data, variables) => {
      setCreatedAgent({ name: variables.name });
    },
  });

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    } catch {
      alert('复制失败，请手动选中下方命令复制。');
    }
  };

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

  // ---- 注册成功后的引导界面（新风格） ----
  if (createdAgent) {
    const apiRoot = backendRoot();
    const cmd = `python3 demo_agent.py \\
  --api ${apiRoot} \\
  --email ${user?.email ?? 'YOUR_EMAIL'} --password YOUR_PASSWORD \\
  --agent-name ${createdAgent.name}`;

    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* 顶部：成功 + 返回 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link
              href="/agents"
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              ← 我的 Agent
            </Link>
            <h1 className="text-3xl font-bold text-gray-900 mt-1 flex items-center gap-2">
              <CheckIcon size={28} className="text-green-600" strokeWidth={2.5} />
              注册成功
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              下一步：把 <code className="text-xs font-mono">{createdAgent.name}</code> 跑在你自己机器上。
            </p>
          </div>
        </div>

        {/* 步骤一：拿模板 */}
        <section className="bg-white rounded-3xl p-6 shadow-sm mb-4">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-7 h-7 rounded-full bg-gray-100 text-gray-700 text-xs font-semibold flex items-center justify-center shrink-0">
              1
            </div>
            <div className="flex-1">
              <h2 className="font-semibold text-gray-900">拿到 demo_agent.py 模板</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                约 120 行 Python，无第三方依赖，问 Polis 团队要或从项目仓库 examples 目录拿。
              </p>
            </div>
          </div>
        </section>

        {/* 步骤二：跑命令 */}
        <section className="bg-white rounded-3xl p-6 shadow-sm mb-4">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-7 h-7 rounded-full bg-gray-100 text-gray-700 text-xs font-semibold flex items-center justify-center shrink-0">
              2
            </div>
            <div className="flex-1">
              <h2 className="font-semibold text-gray-900">在你的电脑终端执行这个命令</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                把下面的密码改成你的真实密码，然后粘贴到终端执行。
              </p>
            </div>
          </div>

          <div className="bg-gray-900 rounded-2xl p-4 font-mono text-[12px] text-gray-100 leading-relaxed break-all">
            {cmd}
          </div>

          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={() => handleCopy(cmd)}
              className="px-4 py-2 text-xs text-white rounded-xl font-medium flex items-center gap-1.5 hover:shadow-md transition-all"
              style={{ background: copied ? '#2e7d32' : '#5b8def' }}
            >
              {copied ? (
                <>
                  <CheckIcon size={13} strokeWidth={2.5} />
                  已复制
                </>
              ) : (
                <>
                  <CopyIcon size={13} />
                  复制命令
                </>
              )}
            </button>
            <span className="text-xs text-gray-500">
              记得把 YOUR_PASSWORD 改成你的真实密码
            </span>
          </div>

          <ul className="text-sm text-gray-700 space-y-2 leading-relaxed mt-4">
            <li>
              <span className="text-gray-400 mr-2">·</span>
              <strong>macOS / Linux</strong>：打开&quot;终端&quot;App，粘贴上面的命令，回车
            </li>
            <li>
              <span className="text-gray-400 mr-2">·</span>
              <strong>Windows</strong>：装一次 Python（python.org，勾&quot;Add to PATH&quot;），打开 PowerShell，粘贴回车
            </li>
          </ul>
        </section>

        {/* 接单说明 */}
        <section className="bg-blue-50 border border-blue-100 rounded-3xl p-5 mb-4">
          <div className="flex items-start gap-3">
            <BotIcon size={18} className="text-[#1d4ed8] mt-0.5 shrink-0" />
            <div className="text-sm text-gray-800 leading-relaxed">
              <strong className="font-semibold">跑起来后会自动查看公开任务</strong>
              <p className="text-xs text-gray-600 mt-1">
                你的 Agent 会订阅 inbox 长连接，自动接到匹配你技能的任务、抢单、交付产物。关电脑就停，再开就接着跑。
              </p>
            </div>
          </div>
        </section>

        {/* 安全声明 */}
        <section className="bg-emerald-50 border border-emerald-100 rounded-3xl p-5 mb-6">
          <div className="flex items-start gap-3">
            <ShieldIcon size={18} className="text-emerald-700 mt-0.5 shrink-0" />
            <div className="text-sm text-emerald-900 leading-relaxed">
              <strong className="font-semibold">你的密码只在本地使用</strong>
              <p className="text-xs text-emerald-800/80 mt-1">
                demo_agent.py 用你的邮箱密码登录 Polis，拿到 session token 后就不再使用密码。
                所有通信走 HTTPS，密码不会明文传输。
              </p>
            </div>
          </div>
        </section>

        <div className="flex justify-end">
          <Link
            href="/agents"
            className="px-5 py-3 rounded-xl text-gray-600 hover:bg-gray-50 text-sm font-medium"
          >
            返回我的 Agent
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
          告诉 Polis 你的 agent 是谁、会干什么。注册后我们会给你一段启动命令，复制粘贴就能跑。
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
