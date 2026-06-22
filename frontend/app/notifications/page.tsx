/**
 * Notifications page /notifications
 */
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Loading from '@/components/Loading';
import { CheckIcon, MessageIcon } from '@/components/icons/Icon';
import { notificationsApi } from '@/lib/api/tasks';
import { useAuthStore } from '@/lib/store';
import { relativeTime } from '@/lib/format';
import type { Notification } from '@/lib/api/types';

export default function NotificationsPage() {
  const { isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();
  const authed = isAuthenticated();

  const { data: notifications, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list(),
    enabled: authed,
    refetchInterval: 30_000, // 30 秒自动刷新
  });

  const markAsReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
    },
  });

  if (!authed) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-400">请先登录查看通知</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return <Loading />;
  }

  const unreadCount = notifications?.filter((n) => !n.read).length || 0;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <MessageIcon className="w-8 h-8 text-blue-400" />
            <div>
              <h1 className="text-3xl font-bold">通知中心</h1>
              {unreadCount > 0 && (
                <p className="text-sm text-gray-400 mt-1">
                  {unreadCount} 条未读通知
                </p>
              )}
            </div>
          </div>

          {notifications && notifications.length > 0 && (
            <button
              onClick={() => {
                markAllReadMutation.mutate();
              }}
              className="text-sm text-blue-400 hover:text-blue-300"
            >
              全部标记为已读
            </button>
          )}
        </div>

        {/* Notifications List */}
        {!notifications || notifications.length === 0 ? (
          <div className="text-center py-16">
            <MessageIcon className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400">暂无通知</p>
          </div>
        ) : (
          <div className="space-y-2">
            {notifications.map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
                onMarkAsRead={() => markAsReadMutation.mutate(notification.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function NotificationItem({
  notification,
  onMarkAsRead,
}: {
  notification: Notification;
  onMarkAsRead: () => void;
}) {
  return (
    <div
      className={`p-4 rounded-lg border transition-colors ${
        notification.read
          ? 'bg-gray-900 border-gray-800'
          : 'bg-blue-950/20 border-blue-800'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            {!notification.read && (
              <span className="w-2 h-2 bg-blue-400 rounded-full"></span>
            )}
            <h3 className="font-medium">{notification.title}</h3>
          </div>

          <p className="text-sm text-gray-400 mb-2">{notification.message}</p>

          <p className="text-xs text-gray-500">
            {relativeTime(notification.created_at)}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {!notification.read && (
            <button
              onClick={onMarkAsRead}
              className="p-2 text-gray-400 hover:text-blue-400 transition-colors"
              title="标记为已读"
            >
              <CheckIcon className="w-5 h-5" />
            </button>
          )}

        </div>
      </div>
    </div>
  );
}
