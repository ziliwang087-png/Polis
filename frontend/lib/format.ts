/**
 * 共用格式化工具：相对时间 / 任务状态展示。
 */

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const now = Date.now();
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const diff = now - t;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return sec <= 1 ? '刚刚' : `${sec} 秒前`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前`;
  const day = Math.floor(hour / 24);
  if (day < 30) return `${day} 天前`;
  const month = Math.floor(day / 30);
  if (month < 12) return `${month} 个月前`;
  return `${Math.floor(month / 12)} 年前`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

import type { JobStatus } from './api/types';

export const JOB_STATUS_META: Record<
  JobStatus,
  { label: string; bg: string; color: string }
> = {
  submitted: { label: '待抢单', bg: '#e8f5e9', color: '#2e7d32' },
  claimed: { label: '已抢单', bg: '#e3f2fd', color: '#1565c0' },
  working: { label: '执行中', bg: '#fff3e0', color: '#e65100' },
  completed: { label: '已完成', bg: '#f3e5f5', color: '#6a1b9a' },
  failed: { label: '失败', bg: '#ffebee', color: '#c62828' },
  canceled: { label: '已取消', bg: '#eceff1', color: '#546e7a' },
};
