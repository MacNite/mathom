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
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export type MathomStatus =
  | "pending"
  | "transcribing"
  | "summarizing"
  | "ready"
  | "error";

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

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  speaker: string | null;
}

export interface Mathom extends MathomListItem {
  original_filename: string;
  error_message: string | null;
  transcript: string | null;
  segments: TranscriptSegment[];
  summaries: Summary[];
  chat_messages: ChatMessage[];
  collections: { id: number; name: string }[];
  queue_position: number | null;
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

export type Role = "admin" | "user";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  must_change_password?: boolean;
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

export interface Invitation {
  id: number;
  email: string;
  name: string;
  created_at: string;
  expires_at: string;
  sent_at: string | null;
  accepted_at: string | null;
  revoked_at: string | null;
}
export interface SmtpSettings {
  host: string;
  port: number;
  username: string;
  from_email: string;
  from_name: string;
  public_base_url: string;
  use_tls: boolean;
  invite_expiry_hours: number;
  configured: boolean;
  password_set: boolean;
}
export interface SmtpSettingsUpdate {
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  from_email?: string;
  from_name?: string;
  public_base_url?: string;
  use_tls?: boolean;
  invite_expiry_hours?: number;
}
