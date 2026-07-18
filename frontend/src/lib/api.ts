// The only module that talks to the backend. Everything goes through /api.
import type {
  ChatMessage,
  Collection,
  Mathom,
  MathomListItem,
  PromptTemplate,
  SearchHit,
  Summary,
  Tag,
  TimelineBucket,
} from './types';

const BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(detail);
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
};
