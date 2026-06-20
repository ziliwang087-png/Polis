import React from 'react';

/**
 * Polis Icon System
 * 统一规范：
 * - 24x24 viewBox
 * - stroke=currentColor，线宽 1.75，linecap/linejoin=round
 * - 默认尺寸 size=18，无填充
 * - 通过父级 text-color 控制颜色
 */

type IconProps = {
  size?: number | string;
  className?: string;
  strokeWidth?: number;
  'aria-label'?: string;
};

const base = (size: number | string = 18) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
});

export const HomeIcon = ({ size = 18, className, strokeWidth = 1.75, ...rest }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden {...rest}>
    <path d="M3.5 11 12 4l8.5 7" />
    <path d="M5.5 9.5V19a1 1 0 0 0 1 1h4v-5h3v5h4a1 1 0 0 0 1-1V9.5" />
  </svg>
);

export const TrophyIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M7 4h10v4a5 5 0 0 1-10 0V4Z" />
    <path d="M17 5h2.5a1 1 0 0 1 1 1v1a3 3 0 0 1-3 3" />
    <path d="M7 5H4.5a1 1 0 0 0-1 1v1a3 3 0 0 0 3 3" />
    <path d="M10 13.5h4l.5 4h-5l.5-4Z" />
    <path d="M8 20h8" />
  </svg>
);

export const FeedIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" />
    <path d="M3.5 9h17" />
    <path d="M7 13h7" />
    <path d="M7 16h4" />
  </svg>
);

export const SparkleIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M12 4v4M12 16v4M4 12h4M16 12h4" />
    <path d="M6.5 6.5 9 9M15 15l2.5 2.5M6.5 17.5 9 15M15 9l2.5-2.5" />
  </svg>
);

export const FlameIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M12 3.5c1.5 3 4.5 4.5 4.5 8.5a4.5 4.5 0 1 1-9 0c0-2 1-3 1-3 .5 1 1.5 1.5 1.5 1.5C9.5 7.5 12 6 12 3.5Z" />
  </svg>
);

export const CheckIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <circle cx="12" cy="12" r="8.5" />
    <path d="m8.5 12 2.5 2.5L15.5 10" />
  </svg>
);

export const StarIcon = ({ size = 18, className, strokeWidth = 1.75, filled = false }: IconProps & { filled?: boolean }) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} fill={filled ? 'currentColor' : 'none'} aria-hidden>
    <path d="m12 4 2.5 5 5.5.8-4 3.9 1 5.5L12 16.5 7 19.2l1-5.5-4-3.9 5.5-.8L12 4Z" />
  </svg>
);

export const HeartIcon = ({ size = 18, className, strokeWidth = 1.75, filled = false }: IconProps & { filled?: boolean }) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} fill={filled ? 'currentColor' : 'none'} aria-hidden>
    <path d="M12 19.5c-3-2-7.5-5-7.5-9.2A3.8 3.8 0 0 1 8.3 6.5c1.6 0 2.9.9 3.7 2.2.8-1.3 2.1-2.2 3.7-2.2a3.8 3.8 0 0 1 3.8 3.8c0 4.2-4.5 7.2-7.5 9.2Z" />
  </svg>
);

export const MessageIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M4.5 6.5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H10l-4 3.5v-3.5h-1a2 2 0 0 1-2-2v-8Z" />
    <path d="M8 10h8M8 13h5" />
  </svg>
);

export const InboxIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M4 13.5 6.5 5h11L20 13.5" />
    <path d="M4 13.5V19a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5.5" />
    <path d="M4 13.5h4l1 2h6l1-2h4" />
  </svg>
);

export const EyeIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
    <circle cx="12" cy="12" r="2.5" />
  </svg>
);

export const UsersIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <circle cx="9" cy="9" r="3" />
    <path d="M3.5 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5" />
    <path d="M15 9.5a3 3 0 0 0 0-5" />
    <path d="M16.5 19c0-2.5 1.5-4.5 4-5" />
  </svg>
);

export const ClockIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </svg>
);

export const GemIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M5.5 9 8 4.5h8L18.5 9 12 19.5 5.5 9Z" />
    <path d="M5.5 9h13M9.5 9 12 19.5 14.5 9M9.5 9 8 4.5M14.5 9 16 4.5" />
  </svg>
);

export const BriefcaseIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <rect x="3.5" y="7.5" width="17" height="12" rx="2" />
    <path d="M9 7.5V5.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    <path d="M3.5 12.5h17" />
  </svg>
);

export const BotIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <rect x="4.5" y="7" width="15" height="12" rx="3" />
    <path d="M12 4v3" />
    <circle cx="12" cy="3.5" r="1" />
    <circle cx="9" cy="12" r=".8" fill="currentColor" />
    <circle cx="15" cy="12" r=".8" fill="currentColor" />
    <path d="M9.5 16h5" />
    <path d="M2 13v3M22 13v3" />
  </svg>
);

export const PlayIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <circle cx="12" cy="12" r="8.5" />
    <path d="m10 8.5 5 3.5-5 3.5v-7Z" />
  </svg>
);

export const RocketIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M14.5 4.5c3 .5 5 2.5 5.5 5.5L13 16.5l-5.5-5.5L14.5 4.5Z" />
    <path d="M10 13.5 6.5 17l-2-1 1-3.5L10 13.5Z" />
    <path d="M14.5 17.5l3 .5-.5 3-3-1 .5-2.5Z" />
    <circle cx="15" cy="9" r="1.2" />
  </svg>
);

export const PencilIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="m4 20 1.5-4.5L16 5l3.5 3.5L9 19l-5 1Z" />
    <path d="m14 7 3.5 3.5" />
  </svg>
);

export const PinIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M12 21v-6" />
    <path d="M8 9V4h8v5l2 4H6l2-4Z" />
  </svg>
);

export const BookmarkIcon = ({ size = 18, className, strokeWidth = 1.75, filled = false }: IconProps & { filled?: boolean }) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} fill={filled ? 'currentColor' : 'none'} aria-hidden>
    <path d="M6 4.5h12v15l-6-4-6 4v-15Z" />
  </svg>
);

export const CodeIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="m9 8-4 4 4 4M15 8l4 4-4 4M14 6l-4 12" />
  </svg>
);

export const ChartIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M4 20h16" />
    <rect x="6" y="12" width="3" height="6" rx="0.5" />
    <rect x="11" y="8" width="3" height="10" rx="0.5" />
    <rect x="16" y="4" width="3" height="14" rx="0.5" />
  </svg>
);

export const PaletteIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M12 3.5c-5 0-9 3.5-9 8 0 3 2 5 5 5 .8 0 1.5-.5 1.5-1.3 0-.8-.7-1.2-.7-2 0-1 .8-1.7 2-1.7h2.5c3 0 5-2 5-4.5 0-2-2.5-3.5-6.3-3.5Z" />
    <circle cx="7.5" cy="9.5" r=".9" fill="currentColor" />
    <circle cx="11" cy="6.5" r=".9" fill="currentColor" />
    <circle cx="15.5" cy="8" r=".9" fill="currentColor" />
    <circle cx="16.5" cy="11.5" r=".9" fill="currentColor" />
  </svg>
);

export const SearchIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m20 20-4.5-4.5" />
  </svg>
);

export const TerminalIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <path d="m7 10 3 2-3 2M12 15h5" />
  </svg>
);

export const FlaskIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M9 4h6M10 4v6L4.5 18.5A1 1 0 0 0 5.5 20h13a1 1 0 0 0 1-1.5L14 10V4" />
    <path d="M7.5 14h9" />
  </svg>
);

export const MegaphoneIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <path d="M4 9v6l13 4V5L4 9Z" />
    <path d="M4 9h-1a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h1" />
    <path d="M8 15v3a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1v-2" />
  </svg>
);

export const CoinIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <ellipse cx="12" cy="7" rx="7" ry="2.5" />
    <path d="M5 7v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V7" />
    <path d="M5 11v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-4" />
  </svg>
);

export const BeakerIcon = FlaskIcon;
export const HospitalIcon = ({ size = 18, className, strokeWidth = 1.75 }: IconProps) => (
  <svg {...base(size)} strokeWidth={strokeWidth} className={className} aria-hidden>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <path d="M12 8v8M8 12h8" />
  </svg>
);
