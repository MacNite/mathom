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

export type Role = 'admin' | 'user';

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  has_local_password?: boolean;
  has_authentik_identity?: boolean;
}

export interface AuthStatus {
  auth_enabled: boolean;
  configured: boolean;
  authenticated: boolean;
  onboarding_required?: boolean;
  local_login_available?: boolean;
  authentik_configured?: boolean;
  login_url: string;
  user: User | null;
}

export interface AuthentikSettings {
  issuer: string;
  client_id: string;
  scopes: string;
  public_base_url: string;
  auto_create_users: boolean;
  verify_ssl: boolean;
  configured: boolean;
  client_secret_set: boolean;
}

export interface AuthentikSettingsUpdate {
  issuer?: string;
  client_id?: string;
  client_secret?: string;
  scopes?: string;
  public_base_url?: string;
  auto_create_users?: boolean;
  verify_ssl?: boolean;
}
