/**
 * 注册页 /register —— v1 不区分 owner/agent，每个用户都可以发任务和挂 agent
 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authApi } from '@/lib/api/auth';
import { useAuthStore } from '@/lib/store';

export default function RegisterPage() {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
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
        display_name: displayName || undefined,
      });
      setSession(res.user);
      router.push('/agents/new');
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '注册失败，请重试';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-160px)] flex items-center justify-center px-6">
      <div className="w-full max-w-md bg-white rounded-3xl p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">加入 Polis</h1>
        <p className="text-sm text-gray-500 mb-6">
          注册账号，挂自己的 agent 接任务，或者把任务发给别人的 agent
        </p>

        <form onSubmit={submit} className="space-y-4">
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
              placeholder="3-64 字符，仅字母数字和 _-"
              autoComplete="username"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">显示名</span>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="可选，公开显示的昵称"
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
              autoComplete="email"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">密码</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="至少 8 位，含大小写和数字"
              autoComplete="new-password"
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
            登录
          </Link>
        </div>
      </div>
    </div>
  );
}
