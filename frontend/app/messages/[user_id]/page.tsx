'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast, { Toaster } from 'react-hot-toast';
import { messagesApi } from '@/lib/api/messages';
import { useAuthStore } from '@/lib/store';

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN');
}

export default function MessageThreadPage() {
  const params = useParams();
  const userId = params.user_id as string;
  const queryClient = useQueryClient();
  const { user, isAuthenticated } = useAuthStore();
  const authed = isAuthenticated();
  const [draft, setDraft] = useState('');

  const threadQuery = useQuery({
    queryKey: ['messages', 'thread', userId],
    queryFn: () => messagesApi.thread(userId),
    enabled: authed && Boolean(userId),
    staleTime: 15_000,
  });

  const sendMessage = useMutation({
    mutationFn: () => messagesApi.send(userId, draft.trim()),
    onSuccess: () => {
      setDraft('');
      queryClient.invalidateQueries({ queryKey: ['messages', 'thread', userId] });
      queryClient.invalidateQueries({ queryKey: ['messages', 'conversations'] });
      queryClient.invalidateQueries({ queryKey: ['messages', 'unread'] });
      toast.success('发送成功');
    },
    onError: (error: unknown) => {
      console.error('Send message failed:', error);
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || '发送失败');
    },
  });

  useEffect(() => {
    let cancelled = false;
    const unread = (threadQuery.data ?? []).filter((message) => {
      return message.receiver_id === user?.id && !message.read;
    });
    
    Promise.all(
      unread.map((message) => 
        messagesApi.markRead(message.id).catch((error) => {
          console.error('Mark read failed:', error);
        })
      )
    ).then(() => {
      if (!cancelled) {
        queryClient.invalidateQueries({ queryKey: ['messages', 'unread'] });
        queryClient.invalidateQueries({ queryKey: ['messages', 'conversations'] });
      }
    });

    return () => {
      cancelled = true;
    };
  }, [queryClient, threadQuery.data, user?.id]);

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

  const messages = threadQuery.data ?? [];

  return (
    <main className="min-h-[100dvh] bg-[#f6f8fb] px-4 pb-16 pt-8 text-slate-950 sm:px-6 lg:px-8">
      <Toaster position="top-center" />
      <div className="mx-auto flex max-w-4xl flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
        <header className="flex items-center justify-between gap-4 border-b border-slate-100 p-5">
          <div>
            <h1 className="text-xl font-semibold">私聊</h1>
            <p className="mt-1 break-all text-xs text-slate-500">{userId}</p>
          </div>
          <Link href="/messages" className="rounded-lg bg-slate-50 px-4 py-2 text-sm font-medium text-slate-600">
            返回列表
          </Link>
        </header>

        <section className="min-h-[420px] space-y-3 p-5">
          {threadQuery.isLoading ? (
            <div className="text-center text-sm text-slate-500">加载中...</div>
          ) : messages.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500">
              还没有消息
            </div>
          ) : (
            messages.map((message) => {
              const mine = message.sender_id === user?.id;
              return (
                <article key={message.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[78%] rounded-lg px-4 py-3 ${mine ? 'bg-[#1d4ed8] text-white' : 'bg-slate-100 text-slate-800'}`}>
                    <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                    <div className={`mt-2 text-xs ${mine ? 'text-white/70' : 'text-slate-400'}`}>
                      {formatTime(message.created_at)}
                    </div>
                  </div>
                </article>
              );
            })
          )}
        </section>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.trim()) sendMessage.mutate();
          }}
          className="border-t border-slate-100 p-5"
        >
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">发送消息</span>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={4}
              className="w-full resize-none rounded-lg border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-[#1d4ed8]"
              placeholder="输入消息..."
            />
          </label>
          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              disabled={sendMessage.isPending || !draft.trim()}
              className="rounded-lg bg-[#1d4ed8] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#1e40af] disabled:opacity-60"
            >
              {sendMessage.isPending ? '发送中...' : '发送'}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
