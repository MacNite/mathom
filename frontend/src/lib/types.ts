export interface Tag {
  id: number;
  name: string;
}

export interface Summary {
  id: number;
  template_slug: string;
  template_name: string;
  content: string;
  model: string;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export type MathomStatus =
  | 'pending'
  | 'transcribing'
  | 'summarizing'
  | 'ready'
  | 'error';

export interface MathomListItem {
  id: number;
  title: string;
  status: MathomStatus;
  duration_seconds: number | null;
  language: string | null;
  favorite: boolean;
  archived: boolean;
  created_at: string;
  tags: Tag[];
}

export interface Mathom extends MathomListItem {
  original_filename: string;
  error_message: string | null;
  transcript: string | null;
  summaries: Summary[];
  chat_messages: ChatMessage[];
  collections: { id: number; name: string }[];
}

export interface PromptTemplate {
  id: number;
  slug: string;
  name: string;
  description: string;
  prompt: string;
  is_builtin: boolean;
  updated_at: string;
}

export interface Collection {
  id: number;
  name: string;
  description: string;
  created_at: string;
  mathoms: MathomListItem[];
}

export interface SearchHit {
  mathom: MathomListItem;
  snippet: string;
}

export interface TimelineBucket {
  month: string;
  count: number;
}
