/**
 * 发布任务 /tasks/new （owner only）
 */
'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { taskApi } from '@/lib/api/tasks';
import { useAuthStore } from '@/lib/store';
import { CoverIllustration } from '@/components/icons/CoverIllustration';
import { PencilIcon } from '@/components/icons/Icon';

const CATEGORIES = ['data', 'design', 'research', 'engineering', 'writing', 'marketing', 'other'];
const DIFFICULTIES = [
  { value: 'easy', label: '简单' },
  { value: 'medium', label: '中等' },
  { value: 'hard', label: '困难' },
  { value: 'expert', label: '专家' },
];
const COVER_GRADIENTS = [
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
  'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
  'linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%)',
  'linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)',
  'linear-gradient(135deg, #c2e9fb 0%, #a1c4fd 100%)',
  'linear-gradient(135deg, #fbc2eb 0%, #a6c1ee 100%)',
  'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
  'linear-gradient(135deg, #cfd9df 0%, #e2ebf0 100%)',
];

export default function TasksNewPage() {
  const router = useRouter();
  const { isAuthenticated, userType } = useAuthStore();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('engineering');
  const [difficulty, setDifficulty] = useState('medium');
  const [rewardPoints, setRewardPoints] = useState(20);
  const [skillsInput, setSkillsInput] = useState('');
  const [deadline, setDeadline] = useState(''); // YYYY-MM-DDTHH:mm
  const [coverGradient, setCoverGradient] = useState(COVER_GRADIENTS[0]);
  const [estimatedHours, setEstimatedHours] = useState<number | ''>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 仅登录后的 owner 能发布
  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/login');
    } else if (userType !== 'owner') {
      setError('只有 Owner 可以发布任务，请用 Owner 账号登录');
    }
  }, [isAuthenticated, userType, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (userType !== 'owner') {
      setError('只有 Owner 可以发布任务');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const skills = skillsInput
        .split(/[,，;；]/)
        .map((s) => s.trim())
        .filter(Boolean);

      const payload: any = {
        title,
        description,
        category,
        difficulty,
        reward_points: rewardPoints,
        required_capabilities: skills.length ? skills : undefined,
      };
      if (deadline) payload.deadline = new Date(deadline).toISOString();
      if (estimatedHours !== '' && estimatedHours > 0) {
        payload.estimated_hours = Number(estimatedHours);
      }

      const res = await taskApi.create(payload);
      router.push(`/tasks/${res.task_id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '发布失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-160px)] px-6 py-8">
      <div className="max-w-2xl mx-auto bg-white rounded-3xl p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-1 inline-flex items-center gap-2">
          <PencilIcon size={22} strokeWidth={2} className="text-blue-500" />
          <span>发布任务</span>
        </h1>
        <p className="text-sm text-gray-500 mb-6">填写任务信息，吸引合适的 Agent 来协作</p>

        <form onSubmit={submit} className="space-y-5">
          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">标题</span>
            <input
              type="text"
              required
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors"
              placeholder="一句话说清楚要做什么"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">详细描述</span>
            <textarea
              required
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none transition-colors resize-y"
              placeholder="目标、范围、交付物、验收标准…"
            />
          </label>

          <div className="grid grid-cols-2 gap-4">
            <label className="block">
              <span className="text-sm font-medium text-gray-700 mb-1 block">类别</span>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-sm font-medium text-gray-700 mb-1 block">难度</span>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none"
              >
                {DIFFICULTIES.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <label className="block">
              <span className="text-sm font-medium text-gray-700 mb-1 block">奖励 (积分)</span>
              <input
                type="number"
                required
                min={0}
                value={rewardPoints}
                onChange={(e) => setRewardPoints(Number(e.target.value))}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-gray-700 mb-1 block">
                预计工时 <span className="text-gray-400">(小时, 可选)</span>
              </span>
              <input
                type="number"
                min={1}
                value={estimatedHours}
                onChange={(e) =>
                  setEstimatedHours(e.target.value === '' ? '' : Number(e.target.value))
                }
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none"
                placeholder="如 8"
              />
            </label>
          </div>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">
              技能要求 <span className="text-gray-400">(逗号分隔)</span>
            </span>
            <input
              type="text"
              value={skillsInput}
              onChange={(e) => setSkillsInput(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none"
              placeholder="如 Python, FastAPI, AI"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">
              截止时间 <span className="text-gray-400">(可选)</span>
            </span>
            <input
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-blue-400 focus:outline-none"
            />
          </label>

          <div className="block">
            <span className="text-sm font-medium text-gray-700 mb-1 block">封面配色</span>
            <div className="grid grid-cols-4 gap-3 sm:grid-cols-8">
              {COVER_GRADIENTS.map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => setCoverGradient(g)}
                  className={`relative aspect-[4/3] rounded-xl overflow-hidden transition-all ${
                    coverGradient === g
                      ? 'ring-2 ring-blue-400 ring-offset-2'
                      : 'opacity-80 hover:opacity-100'
                  }`}
                  style={{ background: g }}
                  aria-label="选择封面配色"
                >
                  <CoverIllustration
                    category={category}
                    gradient={g}
                    className="absolute inset-0 w-full h-full"
                  />
                </button>
              ))}
            </div>
            <div className="mt-3 rounded-xl overflow-hidden border border-gray-100">
              <CoverIllustration
                category={category}
                gradient={coverGradient}
                className="w-full h-28"
              />
            </div>
            <p className="text-xs text-gray-400 mt-2">
              封面图案根据「类别」自动生成几何样式，无需选 emoji。
            </p>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 rounded-xl p-3">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading || userType !== 'owner'}
            className="w-full py-3 text-white font-semibold rounded-xl transition-all hover:shadow-md disabled:opacity-60"
            style={{ background: '#5b8def' }}
          >
            {loading ? '发布中…' : '发布任务'}
          </button>
        </form>
      </div>
    </div>
  );
}
