import type {
  User, UserCreate, SkillProfile,
  Opportunity, OpportunityCreate, SearchRequest,
  Application, ApplicationCreate, ApplicationUpdate,
  ChatRequest, ChatResponse, SSEEvent,
  RegisterRequest, LoginRequest, TokenResponse,
  ProfileUploadResponse,
  ConversationRead, ConversationWithMessages,
} from './types';
import { getAuthHeader } from './auth';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
      ...init?.headers,
    },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  // 204 No Content (DELETE responses) — no body to parse
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/* ── Users ──────────────────────────────────────────────────────────────── */

export const users = {
  create: (data: UserCreate) =>
    request<User>('/api/users', { method: 'POST', body: JSON.stringify(data) }),

  get: (userId: string) =>
    request<User>(`/api/users/${userId}`),

  update: (userId: string, data: Partial<UserCreate>) =>
    request<User>(`/api/users/${userId}`, { method: 'PATCH', body: JSON.stringify(data) }),
};

/* ── Profile ────────────────────────────────────────────────────────────── */

export const profile = {
  get: (userId: string) =>
    request<SkillProfile>(`/api/profile/${userId}`),

  upload: async (userId: string, file: File): Promise<ProfileUploadResponse> => {
    const fd = new FormData();
    fd.append('user_id', userId);
    fd.append('file', file);
    // Note: no Content-Type header — browser sets multipart boundary. Auth header still applied.
    const res = await fetch(`${BASE}/api/profile/upload`, {
      method: 'POST',
      headers: { ...getAuthHeader() },
      body: fd,
    });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }
    return res.json() as Promise<ProfileUploadResponse>;
  },
};

/* ── Opportunities ──────────────────────────────────────────────────────── */

export const opportunities = {
  list: (skip = 0, limit = 20) =>
    request<Opportunity[]>(`/api/opportunities?skip=${skip}&limit=${limit}`),

  create: (data: OpportunityCreate) =>
    request<Opportunity>('/api/opportunities', { method: 'POST', body: JSON.stringify(data) }),

  search: (data: SearchRequest) =>
    request<Opportunity[]>('/api/opportunities/search', { method: 'POST', body: JSON.stringify(data) }),
};

/* ── Tracker ─────────────────────────────────────────────────────────────── */

export const tracker = {
  list: (userId: string) =>
    request<Application[]>(`/api/tracker/${userId}`),

  create: (data: ApplicationCreate) =>
    request<Application>('/api/tracker', { method: 'POST', body: JSON.stringify(data) }),

  update: (appId: string, data: ApplicationUpdate) =>
    request<Application>(`/api/tracker/${appId}`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (appId: string) =>
    request<void>(`/api/tracker/${appId}`, { method: 'DELETE' }),
};

/* ── Chat History ──────────────────────────────────────────────────────── */

export const history = {
  list: (userId: string) =>
    request<ConversationRead[]>(`/api/history/conversations/${userId}`),

  get: (convId: string) =>
    request<ConversationWithMessages>(`/api/history/conversations/${convId}/messages`),

  create: (userId: string, title?: string) =>
    request<ConversationRead>('/api/history/conversations', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, title: title ?? 'New chat' }),
    }),

  rename: (convId: string, title: string) =>
    request<ConversationRead>(`/api/history/conversations/${convId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  delete: (convId: string) =>
    request<void>(`/api/history/conversations/${convId}`, { method: 'DELETE' }),

  addMessage: (conversationId: string, role: 'user' | 'assistant', content: string) =>
    request<{ id: string }>('/api/history/messages', {
      method: 'POST',
      body: JSON.stringify({ conversation_id: conversationId, role, content }),
    }),
};

/* ── Auth ───────────────────────────────────────────────────────────────── */

export const auth = {
  register: (data: RegisterRequest) =>
    request<TokenResponse>('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  login: (data: LoginRequest) =>
    request<TokenResponse>('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  me: () =>
    request<User>('/api/auth/me'),
};

/* ── Chat ────────────────────────────────────────────────────────────────── */

export const chat = {
  send: (data: ChatRequest) =>
    request<ChatResponse>('/api/chat', { method: 'POST', body: JSON.stringify(data) }),

  stream: (data: ChatRequest, onEvent: (evt: SSEEvent) => void): (() => void) => {
    const controller = new AbortController();

    (async () => {
      try {
        const res = await fetch(`${BASE}/api/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
          body: JSON.stringify(data),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          onEvent({ type: 'error', message: `${res.status} ${res.statusText}` });
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const raw = line.slice(6).trim();
              if (!raw || raw === '[DONE]') continue;
              try {
                const evt = JSON.parse(raw) as SSEEvent;
                onEvent(evt);
              } catch {
                /* malformed line — skip */
              }
            }
          }
        }
        onEvent({ type: 'done' });
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          onEvent({ type: 'error', message: String(err) });
        }
      }
    })();

    return () => controller.abort();
  },
};
