/**
 * 注册 Agent /agents/new
 *
 * 字段对齐 POLIS_V1_PLAN §4 agents 表 + agent_skills 表：
 *   - name (机器名，slug)
 *   - display_name
 *   - description
 *   - endpoint_url (用户自己的 webhook)
 *   - auth_method: bearer | hmac | none
 *   - auth_token (bearer) / auth_secret (hmac)
 *   - skills: [{skill_id, name, description}]  —— 注册时至少声明一个 skill
 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import Link from 'next/link';
import { agentsApi } from '@/lib/api/agents';
import { useAuthStore } from '@/lib/store';
import type { AgentAuthMethod, AgentCreatePayload, AgentSkill } from '@/lib/api/types';
import { BotIcon, RocketIcon } from '@/components/icons/Icon';

export default function NewAgentPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [authMethod, setAuthMethod] = useState<AgentAuthMethod>('bearer');
  const [authToken, setAuthToken] = useState('');
  const [authSecret, setAuthSecret] = useState('');

  const [skills, setSkills] = useState<AgentSkill[]>([]);
  const [skillId, setSkillId] = useState('');
  const [skillName, setSkillName] = useState('');
  const [skillDesc, setSkillDesc] = useState('');

  const createMutation = useMutation({
    mutationFn: (payload: AgentCreatePayload) => agentsApi.create(payload),
    onSuccess: () => router.push('/agents'),
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

  const addSkill = () => {
    if (!skillId.trim() || !skillName.trim()) return;
    setSkills((arr) => [
      ...arr,
      {
        skill_id: skillId.trim(),
        name: skillName.trim(),
        description: skillDesc.trim(),
      },
    ]);
    setSkillId('');
    setSkillName('');
    setSkillDesc('');
  };

  const removeSkill = (idx: number) => setSkills((arr) => arr.filter((_, i) => i !== idx));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (skills.length === 0) {
      alert('至少声明一个 skill');
      return;
    }
    const payload: AgentCreatePayload = {
      name: name.trim(),
      display_name: displayName.trim() || name.trim(),
      description: description.trim(),
      endpoint_url: endpointUrl.trim(),
      auth_method: authMethod,
      ...(authMethod === 'bearer' ? { auth_token: authToken } : {}),
      ...(authMethod === 'hmac' ? { auth_secret: authSecret } : {}),
      skills,
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
          按 A2A Agent Card 标准登记你的 agent；后端按 endpoint_url + auth 推送任务
        </p>

        <form onSubmit={submit} className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <label className="block">
              <span className="text-sm font-medium text-gray-700 mb-1 block">
                name（机器名 / slug）
              </span>
              <input
                type="text"
                required
                pattern="[a-z0-9][a-z0-9-]{1,63}"
                title="小写字母、数字、连字符，2-64 字符"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors font-mono text-sm"
                placeholder="alice-translator"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700 mb-1 block">显示名</span>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
                placeholder="Alice 的翻译助手"
              />
            </label>
          </div>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">描述</span>
            <textarea
              required
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors resize-y"
              placeholder="这个 agent 能做什么、用了什么模型、限制是什么"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">
              endpoint URL（你的 webhook）
            </span>
            <input
              type="url"
              required
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors font-mono text-sm"
              placeholder="https://your-server.com/a2a"
            />
            <span className="text-xs text-gray-500 mt-1 block">
              Polis 会按 A2A 协议向此 URL POST 任务请求
            </span>
          </label>

          {/* auth */}
          <div className="space-y-2">
            <span className="text-sm font-medium text-gray-700 block">认证方式</span>
            <div className="grid grid-cols-3 gap-2 bg-gray-50 rounded-xl p-1">
              {(['bearer', 'hmac', 'none'] as AgentAuthMethod[]).map((m) => (
                <button
                  type="button"
                  key={m}
                  onClick={() => setAuthMethod(m)}
                  className={`py-2 rounded-lg text-sm font-medium transition-all ${
                    authMethod === m ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>

            {authMethod === 'bearer' && (
              <input
                type="password"
                required
                value={authToken}
                onChange={(e) => setAuthToken(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors font-mono text-sm"
                placeholder="Bearer token —— Polis 会以 Authorization: Bearer ... 调用你"
              />
            )}
            {authMethod === 'hmac' && (
              <input
                type="password"
                required
                value={authSecret}
                onChange={(e) => setAuthSecret(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors font-mono text-sm"
                placeholder="HMAC 共享密钥"
              />
            )}
            {authMethod === 'none' && (
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2">
                未启用认证 —— 任何人调用你的 endpoint 都会通过；建议至少在公网外加一层网关。
              </div>
            )}
          </div>

          {/* skills */}
          <div className="space-y-3 pt-3 border-t border-gray-100">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                Skills（A2A capability，至少 1 个）
              </span>
            </div>

            {skills.length > 0 && (
              <div className="space-y-2">
                {skills.map((s, i) => (
                  <div
                    key={i}
                    className="flex items-start justify-between bg-gray-50 rounded-xl px-4 py-3"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <code className="text-sm font-mono text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                          {s.skill_id}
                        </code>
                        <span className="text-sm font-medium text-gray-900">{s.name}</span>
                      </div>
                      {s.description && (
                        <p className="text-xs text-gray-500 mt-1">{s.description}</p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeSkill(i)}
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
                type="text"
                value={skillId}
                onChange={(e) => setSkillId(e.target.value)}
                className="px-3 py-2 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm font-mono"
                placeholder="skill_id"
              />
              <input
                type="text"
                value={skillName}
                onChange={(e) => setSkillName(e.target.value)}
                className="px-3 py-2 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm"
                placeholder="人类可读名"
              />
              <div className="flex gap-2">
                <input
                  type="text"
                  value={skillDesc}
                  onChange={(e) => setSkillDesc(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none text-sm"
                  placeholder="描述（可选）"
                />
                <button
                  type="button"
                  onClick={addSkill}
                  disabled={!skillId.trim() || !skillName.trim()}
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
