'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { messagesApi } from '@/lib/api/messages';
import { useAuthStore } from '@/lib/store';
import { MessageIcon } from '@/components/icons/Icon';

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN');
}

export default function MessagesPage() {
  const { isAuthenticated } = useAuthStore();
  const authed = isAuthenticated();

  const conversationsQuery = useQuery({
    queryKey: ['messages', 'conversations'],
    queryFn: () => messagesApi.list(),
    enabled: authed,
    staleTime: 30_000,
  });

  if (!authed) {
    return (
      <main className="mx-auto max-w-md px-6 py-12">
        <div className="rounded-lg bg-white p-8 text-center shadow-sm">
          <div className="font-medium text-slate-900">登录后查看私聊</div>
          <Link href="/login" className="mt-3 inline-flex text-sm font-semibold text-[#1d4ed8]">
            去登录
          </Link>
        </div>
      </main>
    );
  }

  const conversations = conversationsQuery.data ?? [];

  return (
    <main className="min-h-[100dvh] bg-[#f6f8fb] px-4 pb-16 pt-8 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl">
        <header className="mb-6">
          <h1 className="text-3xl font-semibold tracking-tight">最近聊天</h1>
          <p className="mt-2 text-sm text-slate-500">消息不会实时推送，刷新页面即可查看新内容。</p>
        </header>

        {conversationsQuery.isLoading ? (
          <div className="rounded-lg bg-white p-8 text-center text-slate-500 shadow-sm">加载中...</div>
        ) : conversations.length === 0 ? (
          <div className="rounded-lg bg-white p-10 text-center shadow-sm">
            <MessageIcon size={34} className="mx-auto mb-3 text-slate-300" />
            <div className="font-medium text-slate-800">还没有私聊</div>
            <p className="mt-1 text-sm text-slate-500">从用户或任务相关入口开始一次对话。</p>
          </div>
        ) : (
          <div className="space-y-3">
            {conversations.map((item) => (
              <Link
                key={item.conversation_user_id}
                href={`/messages/${item.conversation_user_id}`}
                className="block rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:border-[#bfdbfe] hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="truncate font-semibold text-slate-950">
                        {item.conversation_user_name || item.conversation_user_id}
                      </h2>
                      {item.unread_count > 0 && (
                        <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-600">
                          {item.unread_count}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 line-clamp-1 text-sm text-slate-600">{item.last_message}</p>
                  </div>
                  <span className="shrink-0 text-xs text-slate-400">{formatTime(item.last_message_at)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
