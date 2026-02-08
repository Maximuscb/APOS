const BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiError extends Error {
  status: number;
  detail: string;
  constructor(title: string, detail: string, status: number) {
    super(title);
    this.detail = detail;
    this.status = status;
  }
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('apos_token', token);
    } else {
      localStorage.removeItem('apos_token');
    }
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('apos_token');
    }
    return this.token;
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let res: Response;
    try {
      res = await fetch(`${BASE_URL}${path}`, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw new ApiError('Network Error', 'Network error: unable to reach API.', 0);
    }

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        if (err?.error) detail = err.error;
        else if (err?.detail) detail = err.detail;
        else if (err?.message) detail = err.message;
      } catch {
        // ignore parse error
      }

      if (res.status === 403) {
        if (!detail.toLowerCase().includes('permission') && !detail.toLowerCase().includes('forbidden')) {
          detail = `Forbidden: ${detail}. You may not have permission for this action.`;
        }
      } else if (res.status === 401) {
        if (!detail.toLowerCase().includes('auth') && !detail.toLowerCase().includes('token')) {
          detail = `Unauthorized: ${detail}. Please sign in again.`;
        }
      }

      throw new ApiError(res.statusText, detail, res.status);
    }

    return res.json();
  }

  get<T>(path: string) { return this.request<T>('GET', path); }
  post<T>(path: string, body?: unknown) { return this.request<T>('POST', path, body); }
  put<T>(path: string, body?: unknown) { return this.request<T>('PUT', path, body); }
  patch<T>(path: string, body?: unknown) { return this.request<T>('PATCH', path, body); }
  delete<T>(path: string) { return this.request<T>('DELETE', path); }
}

export const api = new ApiClient();
export { ApiError };
