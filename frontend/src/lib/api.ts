import type {
  User, UserCreate, SkillProfile,
  Opportunity, OpportunityCreate, SearchRequest,
  Application, ApplicationCreate, ApplicationUpdate,
  ChatRequest, ChatResponse, SSEEvent,
} from './types';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
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

  upload: async (userId: string, file: File): Promise<SkillProfile> => {
    const fd = new FormData();
    fd.append('user_id', userId);
    fd.append('file', file);
    const res = await fetch(`${BASE}/api/profile/upload`, { method: 'POST', body: fd });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }
    return res.json() as Promise<SkillProfile>;
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
          headers: { 'Content-Type': 'application/json' },
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
