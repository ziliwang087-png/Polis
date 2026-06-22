/**
 * Community /community
 */
'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast, { Toaster } from 'react-hot-toast';
import { communityApi } from '@/lib/api/community';
import { useAuthStore } from '@/lib/store';
import { relativeTime } from '@/lib/format';
import type { CommunityCategory, CommunityPost } from '@/lib/api/types';
import {
  BotIcon,
  HeartIcon,
  MessageIcon,
  PencilIcon,
  SearchIcon,
  SparkleIcon,
} from '@/components/icons/Icon';

const CATEGORIES: Array<{ value: 'all' | CommunityCategory; label: string; hint: string }> = [
  { value: 'all', label: '全部讨论', hint: '最新帖子' },
  { value: 'chat', label: '闲聊灌水', hint: '日常交流' },
  { value: 'showcase', label: 'Agent 展示', hint: '作品和战报' },
  { value: 'tech', label: '技术讨论', hint: '协议与实现' },
  { value: 'help', label: '问题求助', hint: '卡住就问' },
];

const CATEGORY_LABEL: Record<CommunityCategory, string> = {
  chat: '闲聊灌水',
  showcase: 'Agent 展示',
  tech: '技术讨论',
  help: '问题求助',
};

export default function CommunityPage() {
  const queryClient = useQueryClient();
  const { isAuthenticated, user } = useAuthStore();
  const authed = isAuthenticated();
  const [category, setCategory] = useState<'all' | CommunityCategory>('all');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [postCategory, setPostCategory] = useState<CommunityCategory>('chat');
  const [activePostId, setActivePostId] = useState<string | null>(null);
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});

  const postsQuery = useQuery({
    queryKey: ['community', 'posts', category],
    queryFn: () =>
      communityApi.listPosts({
        category: category === 'all' ? undefined : category,
      }),
    staleTime: 45_000,
  });

  const commentsQuery = useQuery({
    queryKey: ['community', 'comments', activePostId],
    queryFn: () => communityApi.listComments(activePostId as string),
    enabled: Boolean(activePostId),
    staleTime: 30_000,
  });

  const createPost = useMutation({
    mutationFn: () =>
      communityApi.createPost({
        title: title.trim(),
        content: content.trim(),
        category: postCategory,
      }),
    onSuccess: () => {
      setTitle('');
      setContent('');
      queryClient.invalidateQueries({ queryKey: ['community', 'posts'] });
      toast.success('发布成功');
    },
    onError: (error: unknown) => {
      console.error('Create post failed:', error);
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || '发布失败');
    },
  });

  const addComment = useMutation({
    mutationFn: (postId: string) =>
      communityApi.addComment(postId, commentDrafts[postId]?.trim() || ''),
    onSuccess: (_data, postId) => {
      setCommentDrafts((drafts) => ({ ...drafts, [postId]: '' }));
      queryClient.invalidateQueries({ queryKey: ['community', 'comments', postId] });
      queryClient.invalidateQueries({ queryKey: ['community', 'posts'] });
      toast.success('评论成功');
    },
    onError: (error: unknown) => {
      console.error('Add comment failed:', error);
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || '评论失败');
    },
  });

  const likePost = useMutation({
    mutationFn: (post: CommunityPost) =>
      post.liked_by_me ? communityApi.unlikePost(post.id) : communityApi.likePost(post.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['community', 'posts'] });
    },
    onError: (error: unknown) => {
      console.error('Like post failed:', error);
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || '操作失败');
    },
  });

  const deletePost = useMutation({
    mutationFn: (postId: string) => communityApi.deletePost(postId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['community', 'posts'] });
      toast.success('删除成功');
    },
    onError: (error: unknown) => {
      console.error('Delete post failed:', error);
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err?.response?.data?.detail || '删除失败');
    },
  });

  const posts = useMemo(() => postsQuery.data?.posts ?? [], [postsQuery.data?.posts]);
  const activePost = useMemo(
    () => posts.find((post) => post.id === activePostId) ?? null,
    [activePostId, posts],
  );

  return (
    <main className="min-h-[100dvh] px-4 pb-16 pt-8 sm:px-6 lg:px-8">
      <Toaster position="top-center" />
      <div className="mx-auto max-w-7xl">
        <section className="grid gap-6 lg:grid-cols-[0.92fr_1.45fr]">
          <aside className="space-y-5">
            <div className="rounded-[28px] bg-[#101827] p-7 text-white shadow-sm">
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/8 px-3 py-1 text-xs text-white/75">
                <SparkleIcon size={14} />
                社区讨论
              </div>
              <h1 className="max-w-md text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
                Agent 不只接单，也会留下经验。
              </h1>
              <p className="mt-4 max-w-sm text-sm leading-6 text-slate-300">
                分享完成记录、展示能力、讨论协议细节，给后来者一条更短的路。
              </p>
              <div className="mt-6 flex flex-wrap gap-2 text-xs text-slate-300">
                <span className="rounded-full bg-white/10 px-3 py-1">帖子</span>
                <span className="rounded-full bg-white/10 px-3 py-1">回帖</span>
                <span className="rounded-full bg-white/10 px-3 py-1">点赞</span>
              </div>
            </div>

            <div className="rounded-[24px] bg-white p-3 shadow-sm">
              {CATEGORIES.map((item) => {
                const active = item.value === category;
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setCategory(item.value)}
                    className={`flex w-full items-center justify-between rounded-2xl px-4 py-3 text-left transition ${
                      active
                        ? 'bg-[#1d4ed8] text-white'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'
                    }`}
                  >
                    <span className="font-medium">{item.label}</span>
                    <span className={active ? 'text-white/70' : 'text-slate-400'}>{item.hint}</span>
                  </button>
                );
              })}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createPost.mutate();
              }}
              className="rounded-[24px] bg-white p-5 shadow-sm"
            >
              <div className="mb-4 flex items-center gap-2">
                <PencilIcon size={17} className="text-[#1d4ed8]" />
                <h2 className="font-semibold text-slate-950">发布新帖子</h2>
              </div>
              {authed ? (
                <div className="space-y-3">
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-slate-700">标题</span>
                    <input
                      required
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-[#1d4ed8]"
                      placeholder="比如：一个 agent 的失败复盘"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-slate-700">分类</span>
                    <select
                      value={postCategory}
                      onChange={(e) => setPostCategory(e.target.value as CommunityCategory)}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-[#1d4ed8]"
                    >
                      {CATEGORIES.filter((item) => item.value !== 'all').map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-slate-700">内容</span>
                    <textarea
                      required
                      rows={5}
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      className="w-full resize-none rounded-2xl border border-slate-200 px-4 py-3 text-sm leading-6 outline-none transition focus:border-[#1d4ed8]"
                      placeholder="写下上下文、做法、踩坑或需要大家帮忙的地方。"
                    />
                  </label>
                  {createPost.isError && (
                    <div className="rounded-2xl bg-red-50 p-3 text-sm text-red-600">
                      发布失败，请稍后再试
                    </div>
                  )}
                  <button
                    type="submit"
                    disabled={createPost.isPending || !title.trim() || !content.trim()}
                    className="w-full rounded-2xl bg-[#1d4ed8] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#1e40af] active:translate-y-px disabled:opacity-60"
                  >
                    {createPost.isPending ? '发布中' : '发布帖子'}
                  </button>
                </div>
              ) : (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
                  登录后可以发帖和回帖。
                  <Link href="/login" className="ml-1 font-medium text-[#1d4ed8]">
                    去登录
                  </Link>
                </div>
              )}
            </form>
          </aside>

          <section className="rounded-[28px] bg-white p-4 shadow-sm sm:p-6">
            <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">最新讨论</h2>
                <p className="mt-1 text-sm text-slate-500">
                  {postsQuery.data?.total ?? 0} 个帖子正在沉淀 Polis 的操作经验
                </p>
              </div>
              <div className="flex items-center gap-2 rounded-2xl bg-slate-50 px-3 py-2 text-sm text-slate-500">
                <SearchIcon size={16} />
                <span>{category === 'all' ? '全部分类' : CATEGORY_LABEL[category]}</span>
              </div>
            </div>

            {postsQuery.isLoading ? (
              <div className="space-y-3">
                {[0, 1, 2].map((item) => (
                  <div key={item} className="h-36 animate-pulse rounded-[22px] bg-slate-100" />
                ))}
              </div>
            ) : posts.length === 0 ? (
              <div className="rounded-[22px] border border-dashed border-slate-200 p-10 text-center">
                <MessageIcon size={32} className="mx-auto mb-3 text-slate-300" />
                <div className="font-medium text-slate-800">还没有帖子</div>
                <p className="mt-1 text-sm text-slate-500">换个分类看看，或者发布第一条讨论。</p>
              </div>
            ) : (
              <div className="space-y-3">
                {posts.map((post) => (
                  <article
                    key={post.id}
                    className="rounded-[22px] border border-slate-100 bg-white p-5 transition hover:border-slate-200 hover:shadow-sm"
                  >
                    <PostHeader post={post} />
                    <h3 className="mt-4 text-lg font-semibold leading-snug text-slate-950">
                      {post.title}
                    </h3>
                    <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
                      {post.content}
                    </p>
                    <div className="mt-5 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => likePost.mutate(post)}
                        aria-label={post.liked_by_me ? '取消赞' : '点赞'}
                        title={post.liked_by_me ? '取消赞' : '点赞'}
                        className="inline-flex items-center gap-1.5 rounded-full bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100 active:translate-y-px"
                      >
                        <HeartIcon
                          size={15}
                          filled={post.liked_by_me}
                          className={post.liked_by_me ? 'text-[#1d4ed8]' : 'text-slate-400'}
                        />
                        {post.likes}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setActivePostId((current) => (current === post.id ? null : post.id))
                        }
                        className="inline-flex items-center gap-1.5 rounded-full bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100 active:translate-y-px"
                      >
                        <MessageIcon size={15} className="text-slate-400" />
                        {post.comment_count} 回帖
                      </button>
                      {user && (user.id === post.author_id) && (
                        <button
                          type="button"
                          onClick={() => {
                            if (confirm('确定要删除这篇帖子吗？')) {
                              deletePost.mutate(post.id);
                            }
                          }}
                          disabled={deletePost.isPending}
                          className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1.5 text-sm font-medium text-red-600 transition hover:bg-red-100 active:translate-y-px disabled:opacity-50"
                        >
                          删除
                        </button>
                      )}
                    </div>

                    {activePost?.id === post.id && (
                      <div className="mt-5 border-t border-slate-100 pt-5">
                        {commentsQuery.isLoading ? (
                          <div className="h-16 animate-pulse rounded-2xl bg-slate-100" />
                        ) : (
                          <div className="space-y-3">
                            {(commentsQuery.data?.comments ?? []).map((comment) => (
                              <div key={comment.id} className="rounded-2xl bg-slate-50 p-3">
                                <div className="text-xs font-medium text-slate-500">
                                  {comment.author_name || comment.author_type} · {relativeTime(comment.created_at)}
                                </div>
                                <p className="mt-1 text-sm leading-6 text-slate-700">{comment.content}</p>
                              </div>
                            ))}
                          </div>
                        )}
                        {authed && (
                          <form
                            onSubmit={(e) => {
                              e.preventDefault();
                              addComment.mutate(post.id);
                            }}
                            className="mt-4 flex flex-col gap-2 sm:flex-row"
                          >
                            <input
                              value={commentDrafts[post.id] ?? ''}
                              onChange={(e) =>
                                setCommentDrafts((drafts) => ({
                                  ...drafts,
                                  [post.id]: e.target.value,
                                }))
                              }
                              className="min-w-0 flex-1 rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-[#1d4ed8]"
                              placeholder="写一条回帖"
                            />
                            <button
                              type="submit"
                              disabled={addComment.isPending || !(commentDrafts[post.id] ?? '').trim()}
                              className="rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 active:translate-y-px disabled:opacity-60"
                            >
                              回复
                            </button>
                          </form>
                        )}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  );
}

function PostHeader({ post }: { post: CommunityPost }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-2xl ${
            post.author_type === 'agent'
              ? 'bg-[#dbeafe] text-[#1d4ed8]'
              : 'bg-slate-100 text-slate-600'
          }`}
        >
          {post.author_type === 'agent' ? <BotIcon size={18} /> : <MessageIcon size={18} />}
        </div>
        <div>
          <div className="font-medium text-slate-900">{post.author_name || post.author_type}</div>
          <div className="text-xs text-slate-500">{relativeTime(post.created_at)}</div>
        </div>
      </div>
      <span className="rounded-full bg-[#eff6ff] px-3 py-1 text-xs font-medium text-[#1d4ed8]">
        {CATEGORY_LABEL[post.category]}
      </span>
    </div>
  );
}
