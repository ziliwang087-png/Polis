'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '@/lib/api/tasks';
import type { Notification } from '@/lib/api/types';

export default function NotificationBell() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showDropdown, setShowDropdown] = useState(false);

  const unreadCountQuery = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: notificationsApi.unreadCount,
    refetchInterval: 30000,
    retry: 1,
  });

  const notificationsQuery = useQuery({
    queryKey: ['notifications', 'list'],
    queryFn: () => notificationsApi.list(),
    enabled: showDropdown,
    retry: 1,
  });

  const unreadCount = unreadCountQuery.data?.count ?? 0;
  const notifications = notificationsQuery.data ?? [];
  const loading = notificationsQuery.isLoading;

  const handleBellClick = () => {
    setShowDropdown(!showDropdown);
  };

  const handleNotificationClick = async (notification: Notification) => {
    // 标记为已读
    if (!notification.read) {
      try {
        await notificationsApi.markRead(notification.id);
        queryClient.setQueryData<{ count: number }>(
          ['notifications', 'unread-count'],
          (current) => ({ count: Math.max(0, (current?.count ?? unreadCount) - 1) }),
        );
        queryClient.setQueryData<Notification[]>(
          ['notifications', 'list'],
          (current) =>
            current?.map((n) => (n.id === notification.id ? { ...n, read: true } : n)) ??
            current,
        );
      } catch (error) {
        console.error('标记已读失败:', error);
      }
    }

    // 跳转链接
    if (notification.link) {
      router.push(notification.link);
      setShowDropdown(false);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      queryClient.setQueryData<{ count: number }>(
        ['notifications', 'unread-count'],
        { count: 0 },
      );
      queryClient.setQueryData<Notification[]>(
        ['notifications', 'list'],
        (current) => current?.map((n) => ({ ...n, read: true })) ?? current,
      );
    } catch (error) {
      console.error('标记全部已读失败:', error);
    }
  };

  const notificationIcons: Record<Notification['type'], string> = {
    task_accepted: '✅',
    task_completed: '🎉',
    task_failed: '❌',
    task_rated: '⭐',
    level_up: '🆙',
    badge_earned: '🏆',
  };

  return (
    <div className="relative">
      {/* Bell Button */}
      <button
        onClick={handleBellClick}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* Unread Badge */}
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white bg-red-600 rounded-full">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {showDropdown && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowDropdown(false)}
          />

          {/* Dropdown Content */}
          <div className="absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-xl z-20 border border-gray-200">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">通知</h3>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  全部标为已读
                </button>
              )}
            </div>

            {/* Notification List */}
            <div className="max-h-96 overflow-y-auto">
              {loading ? (
                <div className="p-8 text-center text-gray-500">加载中...</div>
              ) : notifications.length === 0 ? (
                <div className="p-8 text-center text-gray-500">暂无通知</div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {notifications.map((notification) => (
                    <button
                      key={notification.id}
                      onClick={() => handleNotificationClick(notification)}
                      className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                        !notification.read ? 'bg-blue-50' : ''
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-2xl flex-shrink-0">
                          {notificationIcons[notification.type]}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <h4 className="font-semibold text-gray-900 text-sm">
                              {notification.title}
                            </h4>
                            {!notification.read && (
                              <span className="w-2 h-2 bg-blue-600 rounded-full flex-shrink-0 mt-1" />
                            )}
                          </div>
                          <p className="text-sm text-gray-600 mt-1">
                            {notification.message}
                          </p>
                          <p className="text-xs text-gray-400 mt-1">
                            {new Date(notification.created_at).toLocaleString('zh-CN')}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            {notifications.length > 0 && (
              <div className="p-3 border-t border-gray-200 text-center">
                <button
                  onClick={() => {
                    router.push('/notifications');
                    setShowDropdown(false);
                  }}
                  className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  查看全部通知
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
