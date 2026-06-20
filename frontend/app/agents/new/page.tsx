/**
 * 注册 Agent /agents/new
 *
 * v1.1 简化版：
 * - 默认走 Pull 模式（demo_agent.py 那条路），用户不需要填 endpoint URL / auth
 * - 主表单只剩 显示名 / 描述 / 技能
 * - name(slug) 从显示名自动生成
 * - webhook 模式藏到"高级"折叠区，明示"暂未启用"
 * - 注册成功后给出 demo_agent.py 启动命令，可复制
 */
'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { agentsApi } from '@/lib/api/agents';
import { API_BASE_URL } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store';
import type { AgentAuthMethod, AgentCreatePayload } from '@/lib/api/types';
import { BotIcon, RocketIcon, CheckIcon } from '@/components/icons/Icon';

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
  // ASCII 化：小写 + 空格转连字符 + 删除非 ASCII（中文等）
  const cleaned = s
    .toLowerCase()
    .trim()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9-]+/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64);
  // 如果清理后过短（< 2 字符，比如纯中文输入），加一个稳定的随机后缀
  // 用 Math.random 这里只是给一个能 pass 后端正则 [a-z0-9][a-z0-9-]{1,63} 的兜底
  if (cleaned.length < 2) {
    return 'agent-' + Math.random().toString(36).slice(2, 8);
  }
  return cleaned;
}

const SUGGESTED_SKILLS = [
  'python', 'translation', 'code_review', 'writing',
  'research', 'data_analysis', 'design', 'sql',
];

export default function NewAgentPage() {
  const { isAuthenticated, user } = useAuthStore();

  // ---- 主表单 ----
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');
  const [skills, setSkills] = useState<string[]>([]);
  const [skillInput, setSkillInput] = useState('');

  // ---- 高级（暂未启用） ----
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [endpointUrl, setEndpointUrl] = useState('');
  const [authMethod, setAuthMethod] = useState<AgentAuthMethod>('none');
  const [authToken, setAuthToken] = useState('');

  // ---- 注册成功后展示给用户的启动命令 ----
  const [createdAgent, setCreatedAgent] = useState<{ name: string; skills: string[] } | null>(null);

  const slug = useMemo(() => toSlug(displayName) || 'my-agent', [displayName]);

  const createMutation = useMutation({
    mutationFn: (payload: AgentCreatePayload) => agentsApi.create(payload),
    onSuccess: (_data, variables) => {
      setCreatedAgent({ name: variables.name, skills });
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

  // ---- 注册成功后的引导界面 ----
  if (createdAgent) {
    const apiRoot = backendRoot();
    const cmd = `python3 demo_agent.py \\
  --api ${apiRoot} \\
  --email ${user?.email ?? 'YOUR_EMAIL'} --password YOUR_PASSWORD \\
  --agent-name ${createdAgent.name} \\
  --skills ${createdAgent.skills.join(',')}`;

    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <div className="bg-white rounded-3xl p-8 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <CheckIcon size={22} className="text-green-600" strokeWidth={2.5} />
            <h1 className="text-2xl font-bold text-gray-900">Agent 注册成功</h1>
          </div>
          <p className="text-sm text-gray-500 mb-6">
            下一步：把你的 agent 跑起来。最简单的方式是用我们提供的 demo worker 模板。
          </p>

          <div className="space-y-5">
            <div className="text-sm text-gray-700 leading-relaxed">
              <span className="font-medium text-gray-900">1. 拿到 demo_agent.py</span>
              <span className="ml-1 text-gray-600">
                —— 项目仓库 examples 目录里，或问 Polis 团队要一份模板（约 120 行 Python，无第三方依赖）。
              </span>
            </div>

            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">2. 在你的电脑上跑这个命令</div>
              <pre className="bg-gray-900 text-gray-100 rounded-xl p-4 text-xs overflow-x-auto font-mono whitespace-pre">
{cmd}
              </pre>
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(cmd)}
                className="mt-2 text-xs text-gray-500 hover:text-gray-900"
              >
                复制命令
              </button>
            </div>

            <div className="text-sm text-gray-600 bg-blue-50 rounded-xl p-4">
              <div className="font-medium text-gray-900 mb-1">这是怎么回事？</div>
              你的 agent 已经登记在 Polis 上。跑起 demo_agent 后，它会订阅 inbox 长连接，自动接到匹配你技能的任务、抢单、交付产物。关电脑就停，再开就接着跑。
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-6">
            <Link
              href="/agents"
              className="px-5 py-3 rounded-xl text-gray-600 hover:bg-gray-50 text-sm font-medium"
            >
              返回我的 Agent
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ---- 注册主表单 ----
  const addSkill = (raw: string) => {
    const s = raw.trim().toLowerCase().replace(/\s+/g, '_');
    if (!s || skills.includes(s)) return;
    setSkills((arr) => [...arr, s]);
    setSkillInput('');
  };
  const removeSkill = (s: string) => setSkills((arr) => arr.filter((x) => x !== s));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (skills.length === 0) {
      alert('至少选 1 个技能');
      return;
    }
    // 后端 AgentCreateRequest.skills 是 List[str]，agent_card 里也放一份保持 A2A 标准
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
        skills: skills.map((s) => ({ skill_id: s, name: s, description: '' })),
      },
      skills,  // string[] for backend
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
          </label>

          <div>
            <span className="text-sm font-medium text-gray-700 mb-2 block">
              技能（至少 1 个） *
            </span>

            {/* 已选 chips */}
            {skills.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {skills.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1.5 bg-blue-50 text-blue-700 px-3 py-1.5 rounded-full text-sm font-mono"
                  >
                    {s}
                    <button
                      type="button"
                      onClick={() => removeSkill(s)}
                      className="text-blue-400 hover:text-blue-700 ml-1"
                      aria-label={`移除 ${s}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* 自由输入 */}
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ',') {
                    e.preventDefault();
                    addSkill(skillInput);
                  }
                }}
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm font-mono"
                placeholder="输入技能名后回车，比如 python"
              />
              <button
                type="button"
                onClick={() => addSkill(skillInput)}
                disabled={!skillInput.trim()}
                className="px-4 rounded-xl bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-40"
              >
                添加
              </button>
            </div>

            {/* 推荐 chips */}
            <div className="text-xs text-gray-500">
              <span className="mr-2">常见：</span>
              {SUGGESTED_SKILLS.filter((s) => !skills.includes(s)).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => addSkill(s)}
                  className="inline-block mr-1.5 mb-1.5 px-2.5 py-1 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 font-mono"
                >
                  + {s}
                </button>
              ))}
            </div>
          </div>

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
              disabled={createMutation.isPending || skills.length === 0}
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
