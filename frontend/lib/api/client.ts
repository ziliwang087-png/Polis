/**
 * Axios 客户端 —— 统一鉴权头、401 处理、API base URL
 */
import axios from 'axios';

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('polis_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      const onAuthPage =
        window.location.pathname.startsWith('/login') ||
        window.location.pathname.startsWith('/register');
      if (!onAuthPage) {
        localStorage.removeItem('polis_token');
        localStorage.removeItem('polis_user');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);
