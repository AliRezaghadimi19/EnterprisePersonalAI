/**
 * Unified API client — plain fetch with auth header, single-flight token refresh,
 * Persian error messages, and list-shape normalization between run_server.py
 * ({users, total}) and FastAPI (bare array) responses.
 */
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from './auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// --- single-flight refresh -------------------------------------------------
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const rt = getRefreshToken();
        if (!rt) return false;
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (!res.ok) return false;
        const data = await res.json();
        if (!data?.access_token) return false;
        setTokens(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        // allow future refreshes after current single-flight resolves
        setTimeout(() => {
          refreshPromise = null;
        }, 0);
      }
    })();
  }
  return refreshPromise;
}

// --- core fetch -------------------------------------------------------------
interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  raw?: boolean; // return the Response itself (for blob downloads)
  retryOn401?: boolean;
}

export async function apiFetch(path: string, opts: ApiFetchOptions = {}): Promise<Response> {
  const token = getAccessToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: opts.method || 'GET',
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError('ارتباط با سرور برقرار نشد.', 0);
  }

  if (res.status === 401 && opts.retryOn401 !== false && path !== '/auth/login') {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch(path, { ...opts, retryOn401: false });
    }
    clearTokens();
    if (typeof window !== 'undefined') window.location.href = '/';
    throw new ApiError('جلسه کاری منقضی شده است. لطفاً دوباره وارد شوید.', 401);
  }

  return res;
}

async function parseJsonResponse(res: Response): Promise<unknown> {
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    // run_server.py answers unknown routes with the embedded HTML SPA & status 200
    throw new ApiError('پاسخ نامعتبر از سرور دریافت شد.', res.status);
  }
  const data = await res.json();
  if (!res.ok) {
    const detail = (data as Record<string, unknown>)?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : ((detail as Record<string, unknown>)?.detail_fa as string) ||
          ((data as Record<string, unknown>)?.message as string) ||
          'خطایی در سرور رخ داده است.';
    throw new ApiError(message, res.status);
  }
  return data;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  return (await parseJsonResponse(res)) as T;
}

export async function apiSend<T>(
  path: string,
  method: 'POST' | 'PUT' | 'DELETE',
  body?: unknown
): Promise<T> {
  const res = await apiFetch(path, { method, body });
  return (await parseJsonResponse(res)) as T;
}

// --- list normalization ------------------------------------------------------
export interface PagedResult<T> {
  items: T[];
  total: number;
}

export function normalizeList<T>(data: unknown, wrapperKeys: string[] = ['users', 'items', 'groups', 'roles', 'categories', 'documents', 'models', 'providers']): PagedResult<T> {
  if (Array.isArray(data)) return { items: data as T[], total: data.length };
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    for (const key of wrapperKeys) {
      if (Array.isArray(obj[key])) {
        const total = typeof obj.total === 'number' ? obj.total : (obj[key] as T[]).length;
        return { items: obj[key] as T[], total };
      }
    }
  }
  return { items: [], total: 0 };
}

// --- file download (Authorization-protected) ---------------------------------
export async function downloadFile(path: string, filename: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw new ApiError('دانلود فایل ناموفق بود.', res.status);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// --- typed endpoint helpers ---------------------------------------------------
export const api = {
  auth: {
    me: () => apiGet<import('@/types').User>('/auth/me'),
    logout: () => apiSend('/auth/logout', 'POST').catch(() => undefined),
  },
  users: {
    list: (params?: Record<string, string | number | undefined>) => {
      const qs = buildQuery(params);
      return apiGet<unknown>(`/users${qs}`).then((d) => normalizeList<import('@/types/entities').AdminUserListItem>(d, ['users']));
    },
    get: (id: string) => apiGet<import('@/types/entities').AdminUserListItem>(`/users/${id}`),
    create: (body: Record<string, unknown>) => apiSend('/users', 'POST', body),
    update: (id: string, body: Record<string, unknown>) => apiSend(`/users/${id}`, 'PUT', body),
    remove: (id: string) => apiSend(`/users/${id}`, 'DELETE'),
  },
  groups: {
    list: () => apiGet<unknown>('/groups').then((d) => normalizeList<import('@/types/entities').AdminGroup>(d, ['groups'])),
    get: (id: string) => apiGet<import('@/types/entities').AdminGroup>(`/groups/${id}`),
    create: (body: Record<string, unknown>) => apiSend('/groups', 'POST', body),
    update: (id: string, body: Record<string, unknown>) => apiSend(`/groups/${id}`, 'PUT', body),
    remove: (id: string) => apiSend(`/groups/${id}`, 'DELETE'),
  },
  roles: {
    list: () => apiGet<unknown>('/roles').then((d) => normalizeList<import('@/types/entities').AdminRole>(d, ['roles'])),
    create: (body: Record<string, unknown>) => apiSend('/roles', 'POST', body),
    update: (id: string, body: Record<string, unknown>) => apiSend(`/roles/${id}`, 'PUT', body),
    remove: (id: string) => apiSend(`/roles/${id}`, 'DELETE'),
  },
  providers: {
    list: () => apiGet<unknown>('/ai-providers').then((d) => normalizeList<import('@/types/entities').AdminProvider>(d, ['providers'])),
    create: (body: Record<string, unknown>) => apiSend('/ai-providers', 'POST', body),
    update: (id: string, body: Record<string, unknown>) => apiSend(`/ai-providers/${id}`, 'PUT', body),
    remove: (id: string) => apiSend(`/ai-providers/${id}`, 'DELETE'),
    testConnection: (body: Record<string, unknown>) => apiSend<{ success: boolean; message?: string }>('/ai-providers/test-connection', 'POST', body),
  },
  models: {
    list: (onlyActive?: boolean) => {
      const qs = onlyActive !== undefined ? `?only_active=${onlyActive}` : '';
      return apiGet<unknown>(`/ai-models${qs}`).then((d) => normalizeList<import('@/types/entities').AdminModel>(d, ['models']));
    },
    create: (body: Record<string, unknown>) => apiSend('/ai-models', 'POST', body),
    update: (id: string, body: Record<string, unknown>) => apiSend(`/ai-models/${id}`, 'PUT', body),
    remove: (id: string) => apiSend(`/ai-models/${id}`, 'DELETE'),
    setGroupAccess: (groupId: string, allowedModelIds: string[]) =>
      apiSend('/ai-models/group-access', 'POST', { group_id: groupId, allowed_model_ids: allowedModelIds }),
  },
  knowledge: {
    categories: {
      list: () => apiGet<unknown>('/knowledge/categories').then((d) => normalizeList<import('@/types/entities').KnowledgeCategory>(d, ['categories'])),
      create: (body: Record<string, unknown>) => apiSend('/knowledge/categories', 'POST', body),
      remove: (id: string) => apiSend(`/knowledge/categories/${id}`, 'DELETE'),
    },
    documents: {
      list: (params?: Record<string, string | number | undefined>) => {
        const qs = buildQuery(params);
        return apiGet<unknown>(`/knowledge/documents${qs}`).then((d) => normalizeList<import('@/types/entities').KnowledgeDocument>(d, ['documents']));
      },
      get: (id: string) => apiGet<import('@/types/entities').KnowledgeDocument>(`/knowledge/documents/${id}`),
      create: (body: Record<string, unknown>) => apiSend('/knowledge/documents', 'POST', body),
      update: (id: string, body: Record<string, unknown>) => apiSend(`/knowledge/documents/${id}`, 'PUT', body),
      remove: (id: string) => apiSend(`/knowledge/documents/${id}`, 'DELETE'),
    },
    search: (body: Record<string, unknown>) => apiSend('/knowledge/search', 'POST', body),
  },
  settings: {
    get: () => apiGet<import('@/types').SystemSettings>('/settings'),
    update: (body: Partial<import('@/types').SystemSettings>) => apiSend('/settings', 'PUT', body),
  },
  adSettings: {
    get: () => apiGet<import('@/types').ActiveDirectoryConfig>('/ad-settings'),
    update: (body: Record<string, unknown>) => apiSend('/ad-settings', 'PUT', body),
    testConnection: (body: Record<string, unknown>) =>
      apiSend<{ success: boolean; message?: string }>('/ad-settings/test', 'POST', body),
  },
  admin: {
    stats: (days = 30) => apiGet<import('@/types/admin').DashboardStats>(`/admin/stats?days=${days}`),
    auditLogs: (params?: Record<string, string | number | undefined>) => {
      const qs = buildQuery(params);
      return apiGet<import('@/types/admin').PagedAuditLogs>(`/admin/audit-logs${qs}`);
    },
    conversations: (params?: Record<string, string | number | undefined>) => {
      const qs = buildQuery(params);
      return apiGet<import('@/types/admin').PagedConversations>(`/admin/conversations${qs}`);
    },
    conversationDetail: (id: string) => apiGet<import('@/types/admin').AdminConversationDetail>(`/admin/conversations/${id}`),
    usageReport: (params?: Record<string, string | number | undefined>) => {
      const qs = buildQuery(params);
      return apiGet<import('@/types/admin').UsageReport>(`/admin/usage-report${qs}`);
    },
  },
};

function buildQuery(params?: Record<string, string | number | undefined>): string {
  if (!params) return '';
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '' && value !== null) search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : '';
}
