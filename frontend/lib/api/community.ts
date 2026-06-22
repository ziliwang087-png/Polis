/**
 * Community API —— posts / comments / likes
 */
import { apiClient } from './client';
import type {
  CommunityCategory,
  CommunityComment,
  CommunityCommentListResponse,
  CommunityLikeResponse,
  CommunityPost,
  CommunityPostCreatePayload,
  CommunityPostCreateResponse,
  CommunityPostListResponse,
} from './types';

export const communityApi = {
  listPosts: async (params: { category?: CommunityCategory } = {}) => {
    const { data } = await apiClient.get<CommunityPostListResponse>('/community/posts', {
      params,
    });
    return data;
  },
  getPost: async (id: string) => {
    const { data } = await apiClient.get<CommunityPost>(`/community/posts/${id}`);
    return data;
  },
  createPost: async (payload: CommunityPostCreatePayload) => {
    const { data } = await apiClient.post<CommunityPostCreateResponse>('/community/posts', payload);
    return data;
  },
  listComments: async (postId: string) => {
    const { data } = await apiClient.get<CommunityCommentListResponse>(
      `/community/posts/${postId}/comments`,
    );
    return data;
  },
  addComment: async (postId: string, content: string) => {
    const { data } = await apiClient.post<CommunityComment>(
      `/community/posts/${postId}/comments`,
      { content },
    );
    return data;
  },
  likePost: async (postId: string) => {
    const { data } = await apiClient.post<CommunityLikeResponse>(
      `/community/posts/${postId}/like`,
    );
    return data;
  },
};
