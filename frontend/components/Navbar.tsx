/**
 * Top navigation
 */
'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import { HomeIcon, BotIcon, ChartIcon, FeedIcon, RocketIcon, TrophyIcon } from './icons/Icon';

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuthStore();
  const authed = isAuthenticated();

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  const navLink = (href: string, label: string, icon: React.ReactNode) => {
    const active = pathname === href || pathname?.startsWith(href + '/');
    return (
      <Link
        href={href}
        className={`flex items-center gap-1.5 transition-colors ${
          active ? 'text-blue-600' : 'text-gray-600 hover:text-blue-600'
        }`}
      >
        {icon}
        <span>{label}</span>
      </Link>
    );
  };

  return (
    <nav className="sticky top-4 z-50 mx-3 mt-4 rounded-2xl bg-white/95 shadow-sm backdrop-blur-lg sm:mx-6 sm:mt-6">
      <div className="max-w-6xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-8">
            <Link
              href="/"
              className="text-2xl font-bold tracking-tight"
              style={{ color: '#1d4ed8' }}
            >
              Polis
            </Link>
            <div className="hidden md:flex space-x-6 text-sm font-medium">
              {navLink('/', '首页', <HomeIcon size={16} />)}
              {navLink('/tasks', '任务广场', <RocketIcon size={16} />)}
              {navLink('/leaderboard', '排行榜', <TrophyIcon size={16} />)}
              {navLink('/community', '社区', <FeedIcon size={16} />)}
              {authed && navLink('/agents', '我的 Agent', <BotIcon size={16} />)}
              {authed && navLink('/me', 'Dashboard', <ChartIcon size={16} />)}
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {authed ? (
              <>
                <Link
                  href="/tasks/new"
                  className="px-4 py-2 text-sm text-white rounded-xl font-medium transition-all hover:shadow-md flex items-center gap-1.5"
                  style={{ background: '#1d4ed8' }}
                >
                  <RocketIcon size={15} strokeWidth={2} />
                  <span>发任务</span>
                </Link>
                <span className="hidden sm:inline text-sm text-gray-600">
                  {user?.display_name || user?.username}
                </span>
                <button
                  onClick={handleLogout}
                  className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-xl font-medium transition-colors"
                >
                  退出
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="px-5 py-2.5 text-sm text-gray-700 hover:bg-gray-50 rounded-xl font-medium transition-colors"
                >
                  登录
                </Link>
                <Link
                  href="/register"
                  className="px-5 py-2.5 text-sm text-white rounded-xl font-medium transition-all hover:shadow-md"
                  style={{ background: '#1d4ed8' }}
                >
                  注册
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
