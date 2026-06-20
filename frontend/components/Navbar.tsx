/**
 * 顶部导航栏 - 社交风格
 */
'use client';

import Link from 'next/link';
import { useAuthStore } from '@/lib/store';
import { useRouter } from 'next/navigation';
import { HomeIcon, TrophyIcon, FeedIcon } from './icons/Icon';

export default function Navbar() {
  const { isAuthenticated, userType, logout } = useAuthStore();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  return (
    <nav className="bg-white backdrop-filter backdrop-blur-lg bg-opacity-95 mx-6 mt-6 rounded-2xl sticky top-6 z-50 shadow-sm">
      <div className="max-w-6xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* 左侧 Logo 和导航 */}
          <div className="flex items-center space-x-8">
            <Link href="/" className="text-2xl font-bold" style={{ color: '#5b8def' }}>
              Polis
            </Link>
            <div className="hidden md:flex space-x-6 text-sm font-medium">
              <Link 
                href="/" 
                className="text-gray-900 hover:text-blue-600 transition-colors flex items-center gap-1.5"
              >
                <HomeIcon size={16} />
                <span>广场</span>
              </Link>
              <Link 
                href="/leaderboard" 
                className="text-gray-600 hover:text-blue-600 transition-colors flex items-center gap-1.5"
              >
                <TrophyIcon size={16} />
                <span>排行榜</span>
              </Link>
              <Link 
                href="/feed" 
                className="text-gray-600 hover:text-blue-600 transition-colors flex items-center gap-1.5"
              >
                <FeedIcon size={16} />
                <span>动态</span>
              </Link>
            </div>
          </div>

          {/* 右侧按钮 */}
          <div className="flex items-center space-x-3">
            {isAuthenticated() ? (
              <>
                <Link 
                  href="/tasks/new"
                  className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-xl font-medium transition-colors"
                >
                  发布任务
                </Link>
                <Link 
                  href={`/profile/${userType}`}
                  className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-xl font-medium transition-colors"
                >
                  我的主页
                </Link>
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
                  style={{ background: '#5b8def' }}
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
