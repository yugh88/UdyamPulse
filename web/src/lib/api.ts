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

function token(): string | null {
  return localStorage.getItem("up_token");
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

async function request(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  // Every write carries a fresh idempotency key, so a network retry can never apply it twice.
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && !headers.has("Idempotency-Key")) headers.set("Idempotency-Key", crypto.randomUUID());
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check that the API is running.");
  }
  if (res.status === 401 && t && !path.startsWith("/auth/login")) {
    // Expired or invalid session: sign out everywhere and return to login.
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
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
