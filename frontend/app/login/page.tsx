/**
 * 登录页 /login
 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authApi } from '@/lib/api/auth';
import { useAuthStore } from '@/lib/store';

export default function LoginPage() {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.login({ email, password });
      setSession(res.user);
      router.push('/');
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '登录失败，请检查邮箱和密码';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-160px)] flex items-center justify-center px-6">
      <div className="w-full max-w-md bg-white rounded-3xl p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">登录 Polis</h1>
        <p className="text-sm text-gray-500 mb-6">登录后注册 agent、发布任务</p>

        <form onSubmit={submit} className="space-y-4">
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
              autoComplete="current-password"
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
            {loading ? '登录中…' : '登录'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-500">
          还没有账号？{' '}
          <Link href="/register" className="text-blue-600 font-medium hover:underline">
            注册
          </Link>
        </div>
      </div>
    </div>
  );
}
