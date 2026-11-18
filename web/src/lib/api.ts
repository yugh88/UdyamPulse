const BASE = "/api/v1";
export const UNAUTHORIZED_EVENT = "up-unauthorized";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// The access token lives in memory only (15 minutes). The refresh token is an httpOnly cookie the page
// cannot read; `refreshAccess` swaps it for a new access token and the server rotates the cookie.
let accessToken: string | null = null;
let refreshing: Promise<string | null> | null = null;
const SESSION_KEY = "up_session";

export function setAccessToken(t: string | null) {
  accessToken = t;
}

export function getAccessToken(): string | null {
  return accessToken;
}

function hasSession(): boolean {
  try {
    return localStorage.getItem(SESSION_KEY) !== null;
  } catch {
    return false;
  }
}

async function callRefresh(): Promise<Response | null> {
  try {
    return await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" });
  } catch {
    return null;
  }
}

/** One refresh at a time per tab. Returns the new access token, or null when the session is over. */
export function refreshAccess(): Promise<string | null> {
  refreshing ??= (async () => {
    let res = await callRefresh();
    if (res?.status === 401) {
      // Another tab rotated the shared cookie a moment ago: the browser now holds the newer one.
      const body = await res
        .clone()
        .json()
        .catch(() => ({}));
      if (body.code === "refresh_superseded") {
        await new Promise((r) => setTimeout(r, 200));
        res = await callRefresh();
      }
    }
    if (!res?.ok) return null;
    const body = await res.json();
    accessToken = body.access_token as string;
    return accessToken;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** A usable access token for requests made outside `api()` (the job event stream). */
export async function ensureAccessToken(): Promise<string | null> {
  return accessToken ?? (hasSession() ? refreshAccess() : null);
}

/** Reads FastAPI `{detail}` and RFC 9457 problem+json `{title, detail, code}` error bodies. */
async function toError(res: Response): Promise<ApiError> {
  let msg = res.statusText || `Request failed (${res.status})`;
  let code: string | undefined;
  try {
    const body = await res.json();
    code = typeof body.code === "string" ? body.code : undefined;
    if (typeof body.detail === "string") msg = body.detail;
    else if (Array.isArray(body.detail))
      msg =
        body.detail
          .map((d: { msg?: string }) => d.msg)
          .filter(Boolean)
          .join("; ") || msg;
    else if (typeof body.title === "string") msg = body.title;
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, msg, code);
}

async function send(path: string, init: RequestInit, headers: Headers, t: string | null): Promise<Response> {
  if (t) headers.set("Authorization", `Bearer ${t}`);
  try {
    return await fetch(`${BASE}${path}`, { ...init, headers, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check that the API is running.");
  }
}

async function request(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  // Every write carries a fresh idempotency key, so a network retry can never apply it twice.
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && !headers.has("Idempotency-Key")) headers.set("Idempotency-Key", crypto.randomUUID());
  const isAuth = path.startsWith("/auth/");
  // After a page reload the access token is gone but the refresh cookie is not: renew before the first call.
  const t = isAuth ? accessToken : await ensureAccessToken();
  let res = await send(path, init, headers, t);
  if (res.status === 401 && !isAuth && hasSession()) {
    // The access token expired mid-session: renew once and repeat the request with the same idempotency key.
    const fresh = await refreshAccess();
    if (fresh) res = await send(path, init, headers, fresh);
    if (res.status === 401) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT)); // session over: back to sign-in
  }
  if (!res.ok) throw await toError(res);
  return res;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await request(path, init);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const post = <T = any>(path: string, body?: unknown) => api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const del = <T = any>(path: string) => api<T>(path, { method: "DELETE" });

/** Fetch a protected PDF and return an object URL for an <iframe> preview. */
export async function pdfUrl(path: string): Promise<string> {
  const res = await request(path, {});
  return URL.createObjectURL(await res.blob());
}
