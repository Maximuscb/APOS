function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("apos_token");
}

export function setAuthToken(token: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem("apos_token", token);
}

export function clearAuthToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("apos_token");
}

export function getAuthToken(): string | null {
  return getStoredToken();
}

function buildHeaders(hasBody: boolean) {
  const headers: Record<string, string> = {};
  if (hasBody) {
    headers["Content-Type"] = "application/json";
  }
  const token = getStoredToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function apiGet<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { headers: buildHeaders(false) });
  } catch {
    throw new Error("Network error: unable to reach API.");
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.error) msg = data.error;
    } catch {}
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: buildHeaders(true),
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Network error: unable to reach API.");
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.error) msg = data.error;
    } catch {}
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

export async function apiDelete(path: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(path, { method: "DELETE", headers: buildHeaders(false) });
  } catch {
    throw new Error("Network error: unable to reach API.");
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.error) msg = data.error;
    } catch {}
    throw new Error(msg);
  }
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "PUT",
      headers: buildHeaders(true),
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Network error: unable to reach API.");
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.error) msg = data.error;
    } catch {}
    throw new Error(msg);
  }
  return (await res.json()) as T;
}
