/**
 * Auth API —— register / login / me
 */
import { apiClient } from './client';
import type { AuthResponse, LoginPayload, RegisterPayload, User } from './types';

export const authApi = {
  register: async (payload: RegisterPayload) => {
    const { data } = await apiClient.post<AuthResponse>('/auth/register', payload);
    return data;
  },
  login: async (payload: LoginPayload) => {
    const { data } = await apiClient.post<AuthResponse>('/auth/login', payload);
    return data;
  },
  me: async () => {
    const { data } = await apiClient.get<User>('/auth/me');
    return data;
  },
  logout: async () => {
    await apiClient.post('/auth/logout');
  },
};
