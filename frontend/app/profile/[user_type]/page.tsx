/**
 * 个人主页 /profile/[user_type]
 *  - owner: 显示我发布的任务
 *  - agent: 显示我申请过的任务
 */
'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/lib/api/auth';
import { taskApi } from '@/lib/api/tasks';
import { useAuthStore } from '@/lib/store';
import Loading from '@/components/Loading';
import { BriefcaseIcon, BotIcon, StarIcon, InboxIcon, EyeIcon, CheckIcon } from '@/components/icons/Icon';
import { CoverIllustration } from '@/components/icons/CoverIllustration';

export default function ProfilePage() {
  const params = useParams<{ user_type: string }>();
  const router = useRouter();
  const profileType = (params?.user_type as string) || 'owner';
  const { isAuthenticated, userType, userId, username } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  const isOwn = userType === profileType;

  // 拉自己的画像（auth/me）
  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => authApi.me(),
    enabled: isAuthenticated() && isOwn,
  });

  // owner: 拉公开任务列表，client 侧过滤自己 owner_id
  const { data: ownerTasks, isLoading: ownerLoading } = useQuery({
    queryKey: ['ownerTasks', userId],
    queryFn: async () => {
      const list = await taskApi.list();
      return list.filter((t) => t.owner_id === userId);
    },
    enabled: isAuthenticated() && isOwn && profileType === 'owner' && !!userId,
  });

  // agent: 拉自己的申请
  const { data: agentApps, isLoading: agentLoading } = useQuery({
    queryKey: ['myApps', userId],
    queryFn: () => taskApi.myApplications(userId as string),
    enabled: isAuthenticated() && isOwn && profileType === 'agent' && !!userId,
  });

  if (!isAuthenticated()) return null;

  if (!isOwn) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-12 text-center text-gray-500">
        当前 URL 是 /{profileType} 主页，但你的账号类型是 {userType}。
        <div className="mt-4">
          <Link
            href={`/profile/${userType}`}
            className="text-blue-600 hover:underline"
          >
            去我的主页 →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-160px)] px-6 py-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* 个人信息卡 */}
        <div className="bg-white rounded-3xl p-8 shadow-sm">
          {meLoading || !me ? (
            <Loading />
          ) : (
            <div className="flex items-center gap-5">
              <div
                className="w-20 h-20 rounded-full flex items-center justify-center text-white text-3xl font-bold"
                style={{ background: me.avatar_gradient || '#cbd5e1' }}
              >
                {(me.display_name || me.username || '?').slice(0, 1).toUpperCase()}
              </div>
              <div className="flex-1">
                <h1 className="text-2xl font-bold text-gray-900">
                  {me.display_name || me.username}
                  {me.verified && (
                    <span
                      title="已认证"
                      className="ml-2 inline-block align-middle text-blue-500"
                    >
                      <CheckIcon size={18} strokeWidth={2.2} />
                    </span>
                  )}
                </h1>
                <div className="text-sm text-gray-500 mt-1 flex flex-wrap gap-3">
                  <span>@{me.username}</span>
                  {me.organization && <span>· {me.organization}</span>}
                  <span className="inline-flex items-center gap-1">·{' '}
                    {me.user_type === 'owner' ? (
                      <BriefcaseIcon size={13} strokeWidth={2} />
                    ) : (
                      <BotIcon size={13} strokeWidth={2} />
                    )}
                    {me.user_type === 'owner' ? 'Owner' : 'Agent'}
                  </span>
                  {typeof me.rating === 'number' && (
                    <span className="inline-flex items-center gap-1 text-amber-500">
                      ·{' '}<StarIcon size={12} filled strokeWidth={2} />
                      <span className="text-gray-600">{me.rating.toFixed(1)}</span>
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* owner 任务列表 */}
        {profileType === 'owner' && (
          <div className="bg-white rounded-3xl p-6 shadow-sm">
            <h2 className="text-lg font-bold text-gray-900 mb-4">我发布的任务</h2>
            {ownerLoading ? (
              <Loading />
            ) : !ownerTasks || ownerTasks.length === 0 ? (
              <div className="text-sm text-gray-500 text-center py-8">
                还没有发布过任务，
                <Link href="/tasks/new" className="text-blue-600 hover:underline ml-1">
                  去发布一个
                </Link>
              </div>
            ) : (
              <ul className="space-y-3">
                {ownerTasks.map((t) => (
                  <li key={t.id}>
                    <Link
                      href={`/tasks/${t.id}`}
                      className="flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:bg-gray-50 transition-colors"
                    >
                      <CoverIllustration
                        category={t.category}
                        gradient={t.cover_gradient}
                        className="w-12 h-12 rounded-xl shrink-0"
                      />
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">{t.title}</div>
                        <div className="text-xs text-gray-500 mt-0.5 flex gap-2 flex-wrap items-center">
                          <span>状态 {t.status}</span>
                          <span className="inline-flex items-center gap-1">· <InboxIcon size={11} strokeWidth={1.8} /> {t.application_count ?? 0}</span>
                          <span className="inline-flex items-center gap-1">· <EyeIcon size={11} strokeWidth={1.8} /> {t.view_count ?? 0}</span>
                        </div>
                      </div>
                      <div
                        className="text-lg font-bold"
                        style={{ color: '#5b8def' }}
                      >
                        {t.reward_points}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* agent 申请列表 */}
        {profileType === 'agent' && (
          <div className="bg-white rounded-3xl p-6 shadow-sm">
            <h2 className="text-lg font-bold text-gray-900 mb-4">我申请的任务</h2>
            {agentLoading ? (
              <Loading />
            ) : !agentApps || agentApps.length === 0 ? (
              <div className="text-sm text-gray-500 text-center py-8">
                还没有申请过任务，
                <Link href="/" className="text-blue-600 hover:underline ml-1">
                  去任务广场看看
                </Link>
              </div>
            ) : (
              <ul className="space-y-3">
                {agentApps.map((a) => (
                  <li key={a.application_id}>
                    <Link
                      href={`/tasks/${a.task_id}`}
                      className="flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:bg-gray-50 transition-colors"
                    >
                      <CoverIllustration
                        category={a.category}
                        gradient={a.cover_gradient}
                        className="w-12 h-12 rounded-xl shrink-0"
                      />
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">{a.title}</div>
                        <div className="text-xs text-gray-500 mt-0.5 flex gap-2 flex-wrap">
                          <span>申请于 {new Date(a.applied_at).toLocaleString('zh-CN')}</span>
                          <span>· 申请状态 {a.application_status}</span>
                          <span>· 任务状态 {a.task_status}</span>
                          {a.assigned_agent_id === userId && (
                            <span className="text-emerald-600 font-medium">· 已被指派</span>
                          )}
                        </div>
                      </div>
                      <div
                        className="text-lg font-bold"
                        style={{ color: '#5b8def' }}
                      >
                        {a.reward_points}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
