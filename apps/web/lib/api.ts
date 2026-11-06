/** Same-origin API client. Sends the CSRF token on every state-changing call. */
let csrf = "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export type Me = {
  id: string; email: string; name: string; is_admin: boolean; email_verified: boolean;
  plan_id: string; credits: number; referral_code: string; mode: string; csrf: string;
};

export async function api<T = unknown>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = opts.method ?? (opts.body === undefined ? "GET" : "POST");
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["content-type"] = "application/json";
  if (method !== "GET" && csrf) headers["x-csrf-token"] = csrf;
  let r: Response;
  try {
    r = await fetch(`/api${path}`, { method, headers, body: opts.body === undefined ? undefined : JSON.stringify(opts.body), credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "You seem to be offline. Check your connection and try again.");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = (data as { detail?: unknown }).detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? "Please check the highlighted fields." : "Something went wrong.";
    throw new ApiError(r.status, msg);
  }
  return data as T;
}

export async function getMe(): Promise<Me | null> {
  try {
    const me = await api<Me>("/auth/me");
    csrf = me.csrf;
    return me;
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}

export async function login(email: string, password: string) {
  await api("/auth/login", { body: { email, password } });
  return getMe();
}

export async function signup(email: string, password: string, name: string, referral_code?: string) {
  await api("/auth/signup", { body: { email, password, name, referral_code: referral_code || null } });
  return getMe();
}

export async function logout() {
  await api("/auth/logout", { method: "POST", body: {} });
  csrf = "";
}
