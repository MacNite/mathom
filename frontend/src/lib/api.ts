// The only module that talks to the backend. Everything goes through /api.
import type {
  AuthentikSettings,
  AuthentikSettingsUpdate,
  AuthStatus,
  ChatMessage,
  Collection,
  Mathom,
  MathomListItem,
  PromptTemplate,
  Role,
  SearchHit,
  Summary,
  Tag,
  TimelineBucket,
  User,
} from './types';

const BASE = '/api';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // `same-origin` sends the session cookie; the frontend and API share an origin.
  const response = await fetch(`${BASE}${path}`, { credentials: 'same-origin', ...init });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export interface MathomFilters {
  favorite?: boolean;
  archived?: boolean;
  tag?: string;
}

export const api = {
  listMathoms(filters: MathomFilters = {}): Promise<MathomListItem[]> {
    const params = new URLSearchParams();
    if (filters.favorite !== undefined) params.set('favorite', String(filters.favorite));
    if (filters.archived !== undefined) params.set('archived', String(filters.archived));
    if (filters.tag) params.set('tag', filters.tag);
    const query = params.toString();
    return request(`/mathoms${query ? `?${query}` : ''}`);
  },

  getMathom(id: number): Promise<Mathom> {
    return request(`/mathoms/${id}`);
  },

  uploadMathom(file: File, title: string, templateSlug: string): Promise<Mathom> {
    const form = new FormData();
    form.append('file', file);
    form.append('title', title);
    form.append('template_slug', templateSlug);
    return request('/mathoms', { method: 'POST', body: form });
  },

  updateMathom(
    id: number,
    changes: Partial<Pick<Mathom, 'title' | 'favorite' | 'archived' | 'transcript'>>,
  ): Promise<Mathom> {
    return request(`/mathoms/${id}`, json('PATCH', changes));
  },

  deleteMathom(id: number): Promise<void> {
    return request(`/mathoms/${id}`, { method: 'DELETE' });
  },

  createSummary(id: number, templateSlug: string): Promise<Summary> {
    return request(`/mathoms/${id}/summaries`, json('POST', { template_slug: templateSlug }));
  },

  addTag(id: number, name: string): Promise<Tag[]> {
    return request(`/mathoms/${id}/tags`, json('POST', { name }));
  },

  removeTag(id: number, tagId: number): Promise<Tag[]> {
    return request(`/mathoms/${id}/tags/${tagId}`, { method: 'DELETE' });
  },

  exportUrl(id: number, format: 'md' | 'txt' | 'json'): string {
    return `${BASE}/mathoms/${id}/export?format=${format}`;
  },

  audioUrl(id: number): string {
    return `${BASE}/mathoms/${id}/audio`;
  },

  listChat(id: number): Promise<ChatMessage[]> {
    return request(`/mathoms/${id}/chat`);
  },

  sendChat(id: number, message: string): Promise<ChatMessage[]> {
    return request(`/mathoms/${id}/chat`, json('POST', { message }));
  },

  clearChat(id: number): Promise<void> {
    return request(`/mathoms/${id}/chat`, { method: 'DELETE' });
  },

  listTemplates(): Promise<PromptTemplate[]> {
    return request('/templates');
  },

  createTemplate(data: {
    slug: string;
    name: string;
    description: string;
    prompt: string;
  }): Promise<PromptTemplate> {
    return request('/templates', json('POST', data));
  },

  updateTemplate(
    id: number,
    changes: Partial<Pick<PromptTemplate, 'name' | 'description' | 'prompt'>>,
  ): Promise<PromptTemplate> {
    return request(`/templates/${id}`, json('PUT', changes));
  },

  deleteTemplate(id: number): Promise<void> {
    return request(`/templates/${id}`, { method: 'DELETE' });
  },

  listCollections(): Promise<Collection[]> {
    return request('/collections');
  },

  createCollection(name: string, description: string): Promise<Collection> {
    return request('/collections', json('POST', { name, description }));
  },

  deleteCollection(id: number): Promise<void> {
    return request(`/collections/${id}`, { method: 'DELETE' });
  },

  addToCollection(collectionId: number, mathomId: number): Promise<Collection> {
    return request(`/collections/${collectionId}/mathoms/${mathomId}`, { method: 'POST' });
  },

  removeFromCollection(collectionId: number, mathomId: number): Promise<Collection> {
    return request(`/collections/${collectionId}/mathoms/${mathomId}`, { method: 'DELETE' });
  },

  listTags(): Promise<Tag[]> {
    return request('/tags');
  },

  search(q: string): Promise<SearchHit[]> {
    return request(`/search?q=${encodeURIComponent(q)}`);
  },

  timeline(): Promise<TimelineBucket[]> {
    return request('/timeline');
  },

  // --- Auth, users, and settings -------------------------------------------

  authStatus(): Promise<AuthStatus> {
    return request('/auth/status');
  },

  logout(): Promise<void> {
    return request('/auth/logout', { method: 'POST' });
  },

  localLogin(email: string, password: string): Promise<User> {
    return request('/auth/login/local', json('POST', { email, password }));
  },
  onboarding(name: string, email: string, password: string, password_confirmation: string): Promise<User> {
    return request('/auth/onboarding', json('POST', { name, email, password, password_confirmation }));
  },
  createUser(data: {name: string; email: string; password: string; role: Role; must_change_password: boolean}): Promise<User> {
    return request('/users', json('POST', data));
  },

  listUsers(): Promise<User[]> {
    return request('/users');
  },

  updateUser(id: number, changes: { role?: Role; is_active?: boolean }): Promise<User> {
    return request(`/users/${id}`, json('PATCH', changes));
  },

  deleteUser(id: number): Promise<void> {
    return request(`/users/${id}`, { method: 'DELETE' });
  },

  getAuthentikSettings(): Promise<AuthentikSettings> {
    return request('/settings/authentik');
  },

  updateAuthentikSettings(changes: AuthentikSettingsUpdate): Promise<AuthentikSettings> {
    return request('/settings/authentik', json('PUT', changes));
  },
};
