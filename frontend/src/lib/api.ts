// The only module that talks to the backend. Everything goes through /api.
import type {
  AuthentikSettings,
  AuthentikSettingsUpdate,
  Invitation,
  SmtpSettings,
  SmtpSettingsUpdate,
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
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // `same-origin` sends the session cookie; the frontend and API share an origin.
  const response = await fetch(`${BASE}${path}`, {
    credentials: "same-origin",
    ...init,
  });
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
  headers: { "Content-Type": "application/json" },
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
    if (filters.favorite !== undefined)
      params.set("favorite", String(filters.favorite));
    if (filters.archived !== undefined)
      params.set("archived", String(filters.archived));
    if (filters.tag) params.set("tag", filters.tag);
    const query = params.toString();
    return request(`/mathoms${query ? `?${query}` : ""}`);
  },

  getMathom(id: number): Promise<Mathom> {
    return request(`/mathoms/${id}`);
  },

  uploadMathom(
    file: File,
    title: string,
    templateSlug: string,
    templateLanguage: string,
  ): Promise<Mathom> {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("template_slug", templateSlug);
    form.append("template_language", templateLanguage);
    return request("/mathoms", { method: "POST", body: form });
  },

  updateMathom(
    id: number,
    changes: Partial<
      Pick<Mathom, "title" | "favorite" | "archived" | "transcript">
    >,
  ): Promise<Mathom> {
    return request(`/mathoms/${id}`, json("PATCH", changes));
  },

  deleteMathom(id: number): Promise<void> {
    return request(`/mathoms/${id}`, { method: "DELETE" });
  },

  createSummary(
    id: number,
    templateSlug: string,
    templateLanguage: string,
  ): Promise<Summary> {
    return request(
      `/mathoms/${id}/summaries`,
      json("POST", {
        template_slug: templateSlug,
        template_language: templateLanguage,
      }),
    );
  },

  updateSummary(
    mathomId: number,
    summaryId: number,
    content: string,
  ): Promise<Summary> {
    return request(
      `/mathoms/${mathomId}/summaries/${summaryId}`,
      json("PATCH", { content }),
    );
  },

  async streamSse(
    path: string,
    body: unknown,
    onToken: (token: string) => void,
  ): Promise<void> {
    const response = await fetch(`${BASE}${path}`, {
      ...json("POST", body),
      credentials: "same-origin",
    });
    if (!response.ok || !response.body)
      throw new ApiError(response.statusText, response.status);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const event of events) {
        const data = event
          .split("\n")
          .find((line) => line.startsWith("data: "));
        if (data && data.slice(6) !== "done")
          onToken(JSON.parse(data.slice(6)) as string);
      }
    }
  },

  streamSummary(
    id: number,
    templateSlug: string,
    templateLanguage: string,
    onToken: (token: string) => void,
    replaceSummaryId?: number,
  ): Promise<void> {
    return this.streamSse(
      `/mathoms/${id}/summaries/stream`,
      {
        template_slug: templateSlug,
        template_language: templateLanguage,
        replace_summary_id: replaceSummaryId,
      },
      onToken,
    );
  },

  streamChat(
    id: number,
    message: string,
    onToken: (token: string) => void,
  ): Promise<void> {
    return this.streamSse(`/mathoms/${id}/chat/stream`, { message }, onToken);
  },

  deleteSummary(mathomId: number, summaryId: number): Promise<void> {
    return request(`/mathoms/${mathomId}/summaries/${summaryId}`, {
      method: "DELETE",
    });
  },

  addTag(id: number, name: string): Promise<Tag[]> {
    return request(`/mathoms/${id}/tags`, json("POST", { name }));
  },

  removeTag(id: number, tagId: number): Promise<Tag[]> {
    return request(`/mathoms/${id}/tags/${tagId}`, { method: "DELETE" });
  },

  exportUrl(id: number, format: "md" | "txt" | "json" | "srt" | "vtt"): string {
    return `${BASE}/mathoms/${id}/export?format=${format}`;
  },

  audioUrl(id: number): string {
    return `${BASE}/mathoms/${id}/audio`;
  },

  listChat(id: number): Promise<ChatMessage[]> {
    return request(`/mathoms/${id}/chat`);
  },

  sendChat(id: number, message: string): Promise<ChatMessage[]> {
    return request(`/mathoms/${id}/chat`, json("POST", { message }));
  },

  clearChat(id: number): Promise<void> {
    return request(`/mathoms/${id}/chat`, { method: "DELETE" });
  },

  listTemplates(language = "en"): Promise<PromptTemplate[]> {
    return request(`/templates?language=${encodeURIComponent(language)}`);
  },

  createTemplate(data: {
    slug: string;
    name: string;
    description: string;
    prompt: string;
  }): Promise<PromptTemplate> {
    return request("/templates", json("POST", data));
  },

  updateTemplate(
    id: number,
    changes: Partial<Pick<PromptTemplate, "name" | "description" | "prompt">>,
  ): Promise<PromptTemplate> {
    return request(`/templates/${id}`, json("PUT", changes));
  },

  deleteTemplate(id: number): Promise<void> {
    return request(`/templates/${id}`, { method: "DELETE" });
  },

  listCollections(): Promise<Collection[]> {
    return request("/collections");
  },

  createCollection(name: string, description: string): Promise<Collection> {
    return request("/collections", json("POST", { name, description }));
  },

  deleteCollection(id: number): Promise<void> {
    return request(`/collections/${id}`, { method: "DELETE" });
  },

  addToCollection(collectionId: number, mathomId: number): Promise<Collection> {
    return request(`/collections/${collectionId}/mathoms/${mathomId}`, {
      method: "POST",
    });
  },

  removeFromCollection(
    collectionId: number,
    mathomId: number,
  ): Promise<Collection> {
    return request(`/collections/${collectionId}/mathoms/${mathomId}`, {
      method: "DELETE",
    });
  },

  listTags(): Promise<Tag[]> {
    return request("/tags");
  },

  search(q: string): Promise<SearchHit[]> {
    return request(`/search?q=${encodeURIComponent(q)}`);
  },

  timeline(): Promise<TimelineBucket[]> {
    return request("/timeline");
  },

  // --- Auth, users, and settings -------------------------------------------

  authStatus(): Promise<AuthStatus> {
    return request("/auth/status");
  },

  logout(): Promise<void> {
    return request("/auth/logout", { method: "POST" });
  },

  localLogin(email: string, password: string): Promise<User> {
    return request("/auth/login/local", json("POST", { email, password }));
  },
  onboarding(
    name: string,
    email: string,
    password: string,
    password_confirmation: string,
  ): Promise<User> {
    return request(
      "/auth/onboarding",
      json("POST", { name, email, password, password_confirmation }),
    );
  },
  createUser(data: {
    name: string;
    email: string;
    password: string;
    must_change_password: boolean;
  }): Promise<User> {
    return request("/users", json("POST", data));
  },

  changeMyPassword(
    currentPassword: string | null,
    password: string,
  ): Promise<User> {
    return request(
      "/users/me/password",
      json("POST", { current_password: currentPassword, password }),
    );
  },

  listUsers(): Promise<User[]> {
    return request("/users");
  },

  updateUser(
    id: number,
    changes: { role?: Role; is_active?: boolean },
  ): Promise<User> {
    return request(`/users/${id}`, json("PATCH", changes));
  },

  deleteUser(id: number): Promise<void> {
    return request(`/users/${id}`, { method: "DELETE" });
  },

  listInvitations(): Promise<Invitation[]> {
    return request("/invitations");
  },
  createInvitation(data: { name: string; email: string }): Promise<Invitation> {
    return request("/invitations", json("POST", data));
  },
  revokeInvitation(id: number): Promise<Invitation> {
    return request(`/invitations/${id}/revoke`, { method: "POST" });
  },
  deleteInvitation(id: number): Promise<void> {
    return request(`/invitations/${id}`, { method: "DELETE" });
  },
  acceptInvitation(token: string, password: string): Promise<User> {
    return request("/invitations/accept", json("POST", { token, password }));
  },
  getSmtpSettings(): Promise<SmtpSettings> {
    return request("/settings/smtp");
  },
  updateSmtpSettings(changes: SmtpSettingsUpdate): Promise<SmtpSettings> {
    return request("/settings/smtp", json("PUT", changes));
  },

  getAuthentikSettings(): Promise<AuthentikSettings> {
    return request("/settings/authentik");
  },

  updateAuthentikSettings(
    changes: AuthentikSettingsUpdate,
  ): Promise<AuthentikSettings> {
    return request("/settings/authentik", json("PUT", changes));
  },
};
