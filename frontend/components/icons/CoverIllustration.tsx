import React from 'react';

/**
 * CoverIllustration —— 任务封面几何图案
 * 替代之前的 cover_emoji（🛡️ 🧬 🤖 …）。
 * 按 category 给出原创的低密度抽象几何图，统一线条 + 半透明色块风格。
 *
 * 用法：<CoverIllustration category="web3" gradient={task.cover_gradient} />
 * 自适应父级宽度，aspect-ratio 16/9。
 */

type Props = {
  category?: string | null;
  gradient?: string | null;
  className?: string;
  /** 仅取背景色不显图案（用于 avatar/小封面） */
  symbolOnly?: boolean;
};

const FALLBACK_GRADIENT = 'linear-gradient(135deg, #fef3f2 0%, #fce7f3 100%)';

/* 不同 category 的抽象 symbol —— 全部使用 currentColor + 透明叠层。*/
const SYMBOLS: Record<string, React.ReactNode> = {
  web3: (
    // 立体棱形（区块 / 链）
    <g stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinejoin="round">
      <path d="M50 18 78 36 78 64 50 82 22 64 22 36 Z" opacity="0.35" />
      <path d="M50 18 50 50 22 36" opacity="0.55" />
      <path d="M50 50 78 36 M50 50 50 82" opacity="0.55" />
      <circle cx="50" cy="50" r="3" fill="currentColor" opacity="0.7" />
    </g>
  ),
  research: (
    // 节点网络
    <g stroke="currentColor" strokeWidth="1.5" fill="none">
      <circle cx="30" cy="35" r="4" opacity="0.6" />
      <circle cx="70" cy="30" r="6" opacity="0.45" />
      <circle cx="50" cy="60" r="5" opacity="0.5" />
      <circle cx="78" cy="62" r="3.5" opacity="0.6" />
      <circle cx="22" cy="68" r="3" opacity="0.6" />
      <path d="M30 35 70 30 50 60 22 68 30 35 50 60 78 62 70 30" opacity="0.35" />
    </g>
  ),
  ai: (
    // 神经网络层
    <g stroke="currentColor" strokeWidth="1.4" fill="none" opacity="0.55">
      {[26, 50, 74].map((y, i) =>
        [25, 50, 75].map((x, j) => <circle key={`${i}-${j}`} cx={x} cy={y} r="2.6" />)
      )}
      {[25, 50, 75].map((x1) =>
        [25, 50, 75].map((x2) => (
          <path key={`l-${x1}-${x2}`} d={`M${x1} 28 L${x2} 48`} opacity="0.4" />
        ))
      )}
      {[25, 50, 75].map((x1) =>
        [25, 50, 75].map((x2) => (
          <path key={`l2-${x1}-${x2}`} d={`M${x1} 52 L${x2} 72`} opacity="0.4" />
        ))
      )}
    </g>
  ),
  development: (
    // 代码括号
    <g stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M28 30 14 50 28 70" opacity="0.65" />
      <path d="M72 30 86 50 72 70" opacity="0.65" />
      <path d="M58 26 42 74" opacity="0.55" />
    </g>
  ),
  design: (
    // 三圆叠加调色板
    <g stroke="currentColor" strokeWidth="1.5" fill="currentColor">
      <circle cx="38" cy="40" r="14" fillOpacity="0.18" strokeOpacity="0.5" />
      <circle cx="58" cy="40" r="14" fillOpacity="0.22" strokeOpacity="0.5" />
      <circle cx="48" cy="58" r="14" fillOpacity="0.18" strokeOpacity="0.5" />
    </g>
  ),
  data: (
    // 柱状图
    <g stroke="currentColor" strokeWidth="1.5" fill="currentColor" strokeLinecap="round">
      <rect x="22" y="56" width="9" height="22" rx="1.5" fillOpacity="0.25" />
      <rect x="36" y="44" width="9" height="34" rx="1.5" fillOpacity="0.35" />
      <rect x="50" y="32" width="9" height="46" rx="1.5" fillOpacity="0.5" />
      <rect x="64" y="50" width="9" height="28" rx="1.5" fillOpacity="0.3" />
      <path d="M14 78 86 78" strokeOpacity="0.5" />
    </g>
  ),
  marketing: (
    // 喇叭脉冲
    <g stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 42 22 58 50 66 50 34 22 42 Z" opacity="0.5" />
      <path d="M50 36 64 30 64 70 50 64" opacity="0.55" />
      <path d="M70 42q5 0 5 8t-5 8" opacity="0.45" />
      <path d="M76 36q9 0 9 14t-9 14" opacity="0.35" />
    </g>
  ),
  health: (
    // DNA 螺旋
    <g stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round">
      <path d="M30 20 Q60 35 30 50 Q60 65 30 80" opacity="0.55" />
      <path d="M70 20 Q40 35 70 50 Q40 65 70 80" opacity="0.55" />
      {[25, 35, 50, 65, 75].map((y) => (
        <path key={y} d={`M30 ${y} L70 ${y}`} opacity="0.35" />
      ))}
    </g>
  ),
  writing: (
    // 文档+笔
    <g stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M28 18 28 80 60 80 60 28 50 18 28 18Z" opacity="0.5" />
      <path d="M50 18 50 28 60 28" opacity="0.5" />
      <path d="M36 38 52 38 M36 46 52 46 M36 54 48 54 M36 62 50 62" opacity="0.45" />
      <path d="m62 50 18-18 4 4-18 18-6 2 2-6Z" opacity="0.65" />
    </g>
  ),
  default: (
    // 抽象几何
    <g stroke="currentColor" strokeWidth="1.5" fill="none">
      <circle cx="50" cy="50" r="22" opacity="0.4" />
      <rect x="34" y="34" width="32" height="32" rx="4" opacity="0.5" transform="rotate(15 50 50)" />
      <path d="M50 30 50 70 M30 50 70 50" opacity="0.35" />
    </g>
  ),
};

/**
 * 把任意 category 字符串归一到 SYMBOLS key
 */
function normalizeCategory(c?: string | null): keyof typeof SYMBOLS {
  if (!c) return 'default';
  const lower = c.toLowerCase();
  if (/web3|crypto|defi|dao|blockchain|nft|smart-contract/.test(lower)) return 'web3';
  if (/research|paper|literature|study/.test(lower)) return 'research';
  if (/ai|ml|llm|model|agent/.test(lower)) return 'ai';
  if (/dev|code|backend|frontend|software|engineering|micro/.test(lower)) return 'development';
  if (/design|ui|ux|visual|brand/.test(lower)) return 'design';
  if (/data|analytic|metric|dashboard|bi/.test(lower)) return 'data';
  if (/market|growth|content|social|seo|community/.test(lower)) return 'marketing';
  if (/health|medical|bio|pharma|clinical/.test(lower)) return 'health';
  if (/writ|copy|article|blog|edit/.test(lower)) return 'writing';
  return 'default';
}

export function CoverIllustration({ category, gradient, className = '', symbolOnly = false }: Props) {
  const key = normalizeCategory(category);
  const symbol = SYMBOLS[key];
  const bg = gradient || FALLBACK_GRADIENT;

  if (symbolOnly) {
    return (
      <div
        className={`relative overflow-hidden ${className}`}
        style={{ background: bg }}
      >
        <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full text-white/80" preserveAspectRatio="xMidYMid meet">
          {symbol}
        </svg>
      </div>
    );
  }

  return (
    <div
      className={`relative overflow-hidden ${className}`}
      style={{ background: bg }}
    >
      {/* 噪点/纹理叠层（可选） */}
      <div className="absolute inset-0 opacity-30" style={{
        backgroundImage: 'radial-gradient(circle at 20% 30%, rgba(255,255,255,0.4) 0%, transparent 40%)',
      }} />
      {/* 主图案 */}
      <svg
        viewBox="0 0 100 100"
        className="absolute inset-0 w-full h-full text-white"
        preserveAspectRatio="xMidYMid meet"
      >
        {symbol}
      </svg>
    </div>
  );
}

export { normalizeCategory };
