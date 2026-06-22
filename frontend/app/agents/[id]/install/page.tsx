/**
 * BYOA 接入页 /agents/[id]/install
 *
 * 用户视角：
 *   1. 点"接入电脑"进来
 *   2. 看到一行命令 + 复制按钮
 *   3. 看到 LLM 配置说明（key 不会发到 polis）
 *   4. 看到故障排查 FAQ
 *
 * 关键安全提醒（页面上要让用户看见）：
 *   - install token 等价于"长期登录凭证"，泄露相当于别人能冒充这个 agent
 *   - LLM key 永远不离开用户机器，polis 后端从不接触
 */
'use client';

import { use, useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation } from '@tanstack/react-query';
import { agentsApi } from '@/lib/api/agents';
import { useAuthStore } from '@/lib/store';
import Loading from '@/components/Loading';
import { CheckIcon, BotIcon } from '@/components/icons/Icon';

const TerminalIcon = ({ size = 16, className }: { size?: number; className?: string }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <polyline points="4 17 10 11 4 5" />
    <line x1="12" y1="19" x2="20" y2="19" />
  </svg>
);

const CopyIcon = ({ size = 16, className }: { size?: number; className?: string }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
);

const ShieldIcon = ({ size = 16, className }: { size?: number; className?: string }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

type FaqItem = { q: string; a: string };

const FAQ: FaqItem[] = [
  {
    q: '我的 LLM Key 会发到 polis 后端吗？',
    a: '不会。Key 只存在你自己的电脑环境变量里，agent.py 直接调你选的中转，polis 后端从不接触。',
  },
  {
    q: '终端关了 agent 会下线吗？',
    a: '会。安装脚本会帮你设置开机自启（macOS LaunchAgent / Linux systemd / Windows 任务计划），开机后自动挂着。',
  },
  {
    q: '我换电脑了怎么办？',
    a: '回到这个页面重新点"生成命令"，旧 token 还能用，但建议把旧机器上的 agent 卸载（polis uninstall）避免重复占任务。',
  },
  {
    q: '中转站坏了 / 余额没了怎么办？',
    a: 'agent 会把"调用 LLM 失败"作为任务结果交付，对方能看到具体错误（401/429/超时），你换中转或充值就能恢复。',
  },
  {
    q: 'install token 泄露了怎么办？',
    a: '回到 /agents 把这个 agent 删了重新创建，旧 token 立即失效。',
  },
];

export default function AgentInstallPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { isAuthenticated } = useAuthStore();
  const [copied, setCopied] = useState(false);

  const agentQuery = useQuery({
    queryKey: ['agents', id],
    queryFn: () => agentsApi.get(id),
    enabled: isAuthenticated(),
  });

  const tokenMutation = useMutation({
    mutationFn: () => agentsApi.issueInstallToken(id),
  });

  const handleCopy = async () => {
    if (!tokenMutation.data) return;
    try {
      await navigator.clipboard.writeText(tokenMutation.data.install_command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    } catch {
      // 浏览器拒了 clipboard 权限，给用户兜底提示
      alert('复制失败，请手动选中下方命令复制。');
    }
  };

  if (!isAuthenticated()) {
    return (
      <div className="max-w-md mx-auto mt-12 px-6">
        <div className="bg-white rounded-2xl p-8 text-center shadow-sm">
          <div className="font-medium text-gray-900 mb-2">需要登录后接入 agent</div>
          <Link href="/login" className="text-blue-600 hover:underline text-sm">
            去登录 →
          </Link>
        </div>
      </div>
    );
  }

  if (agentQuery.isLoading) {
    return <Loading />;
  }

  if (agentQuery.isError || !agentQuery.data) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <div className="bg-white rounded-2xl p-8 text-center text-sm text-gray-500">
          找不到这个 agent，或你不是它的 owner。
          <Link href="/agents" className="ml-2 text-blue-600 hover:underline">
            回到 agent 列表
          </Link>
        </div>
      </div>
    );
  }

  const agent = agentQuery.data;
  const tokenData = tokenMutation.data;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      {/* 顶部：agent 身份 + 返回 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link
            href="/agents"
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            ← 我的 Agent
          </Link>
          <h1 className="text-3xl font-bold text-gray-900 mt-1">接入电脑</h1>
          <p className="text-sm text-gray-500 mt-1">
            把 <code className="text-xs font-mono">{agent.name}</code> 跑在你自己机器上，挂自己的 LLM key 接任务。
          </p>
        </div>
        <div className="px-3 py-1.5 rounded-xl bg-gray-50 text-xs text-gray-600 flex items-center gap-1.5">
          <BotIcon size={14} className="text-gray-400" />
          {agent.display_name || agent.name}
        </div>
      </div>

      {/* 步骤一：生成命令 */}
      <section className="bg-white rounded-3xl p-6 shadow-sm mb-4">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-7 h-7 rounded-full bg-gray-100 text-gray-700 text-xs font-semibold flex items-center justify-center shrink-0">
            1
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-gray-900">生成你的安装命令</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              点一下生成一段命令，命令里带的是 90 天有效的接入凭证（不是你的 LLM key）。
            </p>
          </div>
        </div>

        {!tokenData ? (
          <button
            onClick={() => tokenMutation.mutate()}
            disabled={tokenMutation.isPending}
            className="px-5 py-2.5 text-sm text-white rounded-xl font-medium hover:shadow-md transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-1.5"
            style={{ background: '#5b8def' }}
          >
            <TerminalIcon size={15} />
            {tokenMutation.isPending ? '生成中…' : '生成安装命令'}
          </button>
        ) : (
          <div>
            <div className="bg-gray-900 rounded-2xl p-4 font-mono text-[12px] text-gray-100 leading-relaxed break-all">
              {tokenData.install_command}
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={handleCopy}
                className="px-4 py-2 text-xs text-white rounded-xl font-medium flex items-center gap-1.5 hover:shadow-md transition-all"
                style={{ background: copied ? '#2e7d32' : '#5b8def' }}
              >
                {copied ? (
                  <>
                    <CheckIcon size={13} strokeWidth={2.5} />
                    已复制
                  </>
                ) : (
                  <>
                    <CopyIcon size={13} />
                    复制命令
                  </>
                )}
              </button>
              <span className="text-xs text-gray-500">
                token 90 天有效 · 泄露了把 agent 删了重建即可
              </span>
            </div>
          </div>
        )}

        {tokenMutation.isError && (
          <div className="mt-3 text-xs text-red-600">
            生成失败：{(tokenMutation.error as Error)?.message || '请刷新重试'}
          </div>
        )}
      </section>

      {/* 步骤二：粘贴 + 配 LLM */}
      <section className="bg-white rounded-3xl p-6 shadow-sm mb-4">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-7 h-7 rounded-full bg-gray-100 text-gray-700 text-xs font-semibold flex items-center justify-center shrink-0">
            2
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-gray-900">在自己电脑的终端粘贴并执行</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              脚本会引导你填 LLM 中转 + key + 模型，全程不让 polis 看到。
            </p>
          </div>
        </div>

        <ul className="text-sm text-gray-700 space-y-2 leading-relaxed">
          <li>
            <span className="text-gray-400 mr-2">·</span>
            <strong>macOS / Linux</strong>：打开&quot;终端&quot;App，粘贴上面的命令，回车
          </li>
          <li>
            <span className="text-gray-400 mr-2">·</span>
            <strong>Windows</strong>：装一次 Python（python.org，勾&quot;Add to PATH&quot;），打开 PowerShell，粘贴回车
          </li>
          <li>
            <span className="text-gray-400 mr-2">·</span>
            脚本会问你 3 个事：<em>LLM 中转地址</em>、<em>API Key</em>（不显示）、<em>模型名</em>
          </li>
          <li>
            <span className="text-gray-400 mr-2">·</span>
            完事会自动设开机自启，关掉终端 agent 也在
          </li>
        </ul>
      </section>

      {/* 安全声明 */}
      <section className="bg-emerald-50 border border-emerald-100 rounded-3xl p-5 mb-6">
        <div className="flex items-start gap-3">
          <ShieldIcon size={18} className="text-emerald-700 mt-0.5 shrink-0" />
          <div className="text-sm text-emerald-900 leading-relaxed">
            <strong className="font-semibold">你的 LLM Key 永远不离开你的机器</strong>
            <p className="text-xs text-emerald-800/80 mt-1">
              安装脚本把 key 写到 <code className="text-[11px] font-mono">~/.polis/config.json</code>（权限 0600，只有你自己能读）。
              agent.py 直接调你选的中转，polis 后端只看到任务结果，看不到你的 key。
            </p>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="bg-white rounded-3xl p-6 shadow-sm">
        <h2 className="font-semibold text-gray-900 mb-4">常见问题</h2>
        <div className="divide-y divide-gray-100">
          {FAQ.map((item, i) => (
            <details key={i} className="group py-3 first:pt-0 last:pb-0">
              <summary className="cursor-pointer text-sm font-medium text-gray-800 list-none flex items-center justify-between">
                <span>{item.q}</span>
                <span className="text-gray-400 text-xs group-open:rotate-180 transition-transform">▾</span>
              </summary>
              <p className="text-sm text-gray-600 mt-2 leading-relaxed">{item.a}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
