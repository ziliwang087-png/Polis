/**
 * 全局认证状态 —— v1 不区分 owner/agent，每个用户都可以发任务和挂 agent。
 */
import { create } from 'zustand';
import type { User } from './api/types';

interface AuthState {
  user: User | null;
  hasHydrated: boolean;
  isAuthenticated: () => boolean;
  hydrateFromStorage: () => void;
  setSession: (user: User) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

const USER_KEY = 'polis_user';

function readUser(): User | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  hasHydrated: false,

  isAuthenticated: () => !!get().user,

  hydrateFromStorage: () => {
    if (typeof window === 'undefined') return;
    set({
      user: readUser(),
      hasHydrated: true,
    });
  },

  setSession: (user) => {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ user, hasHydrated: true });
  },

  setUser: (user) => {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ user });
  },

  logout: () => {
    localStorage.removeItem(USER_KEY);
    set({ user: null, hasHydrated: true });
  },
}));
