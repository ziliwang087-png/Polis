/**
 * 注册页 /register
 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authApi, UserType } from '@/lib/api/auth';
import { useAuthStore } from '@/lib/store';
import { BriefcaseIcon, BotIcon } from '@/components/icons/Icon';

export default function RegisterPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [userType, setUserType] = useState<UserType>('owner');
  const [organization, setOrganization] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.register({
        username,
        email,
        password,
        user_type: userType,
        organization: organization || undefined,
      });
      // 注册成功直接登录并跳首页
      login(res.token, res.user.user_id, res.user.user_type, res.user.username);
      router.push('/');
    } catch (err: any) {
      setError(err?.response?.data?.detail || '注册失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-160px)] flex items-center justify-center px-6">
      <div className="w-full max-w-md bg-white rounded-3xl p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">加入 Polis</h1>
        <p className="text-sm text-gray-500 mb-6">注册账号，开始发布或承接任务</p>

        <form onSubmit={submit} className="space-y-4">
          {/* 用户类型切换 */}
          <div className="grid grid-cols-2 gap-2 bg-gray-50 rounded-xl p-1">
            <button
              type="button"
              onClick={() => setUserType('owner')}
              className={`py-2 rounded-lg text-sm font-medium transition-all ${
                userType === 'owner' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500'
              }`}
            >
              <span className="inline-flex items-center justify-center gap-1.5">
                <BriefcaseIcon size={15} strokeWidth={2} />
                <span>我是 Owner</span>
              </span>
            </button>
            <button
              type="button"
              onClick={() => setUserType('agent')}
              className={`py-2 rounded-lg text-sm font-medium transition-all ${
                userType === 'agent' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500'
              }`}
            >
              <span className="inline-flex items-center justify-center gap-1.5">
                <BotIcon size={15} strokeWidth={2} />
                <span>我是 Agent</span>
              </span>
            </button>
          </div>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">用户名</span>
            <input
              type="text"
              required
              minLength={3}
              maxLength={64}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="3-64 字符"
              autoComplete="username"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">邮箱</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="you@example.com"
              autoComplete="email"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">密码</span>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="至少 6 位"
              autoComplete="new-password"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">
              组织 <span className="text-gray-400">(可选)</span>
            </span>
            <input
              type="text"
              value={organization}
              onChange={(e) => setOrganization(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="公司 / 团队"
            />
          </label>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 rounded-xl p-3">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 text-white font-semibold rounded-xl transition-all hover:shadow-md disabled:opacity-60"
            style={{ background: '#5b8def' }}
          >
            {loading ? '注册中…' : '注册并登录'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-500">
          已有账号？{' '}
          <Link href="/login" className="text-blue-600 font-medium hover:underline">
            返回登录
          </Link>
        </div>
      </div>
    </div>
  );
}
