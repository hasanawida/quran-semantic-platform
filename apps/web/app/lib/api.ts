export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const ACCESS_KEY = "qsp_access";
const REFRESH_KEY = "qsp_refresh";

export type ApiEnvelope<T> =
  | { success: true; data: T; meta: unknown }
  | { success: false; error: { code: string; message: string }; meta: unknown };

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function storeTokens(access: string, refresh: string) {
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
};

async function rawRequest<T>(
  path: string,
  { method = "GET", body, auth = false, signal }: RequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  let payload: ApiEnvelope<T> | null = null;
  try {
    payload = (await response.json()) as ApiEnvelope<T>;
  } catch {
    throw new ApiError("PARSE_ERROR", "تعذّر قراءة استجابة الخادم.", response.status);
  }

  if (!payload.success) {
    throw new ApiError(payload.error.code, payload.error.message, response.status);
  }
  return payload.data;
}

// طلب مع تجديد تلقائي للرمز عند انتهاء صلاحيته
export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  try {
    return await rawRequest<T>(path, opts);
  } catch (err) {
    if (
      err instanceof ApiError &&
      err.status === 401 &&
      err.code === "TOKEN_EXPIRED" &&
      opts.auth
    ) {
      const refreshed = await tryRefresh();
      if (refreshed) return await rawRequest<T>(path, opts);
    }
    throw err;
  }
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const data = await rawRequest<{ access_token: string; refresh_token: string }>(
      "/auth/refresh",
      { method: "POST", body: { refresh_token: refresh } }
    );
    storeTokens(data.access_token, data.refresh_token ?? refresh);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}
