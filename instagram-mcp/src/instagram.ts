const DEFAULT_VERSION = "v23.0";

export class InstagramError extends Error {
  constructor(message: string, public status?: number, public code?: number) {
    super(message);
  }
}

export interface Config {
  token: string;
  userId: string;
  version: string;
  fetchImpl?: typeof fetch;
}

export function configFromEnv(): Config {
  return {
    token: process.env.INSTAGRAM_ACCESS_TOKEN ?? "",
    userId: process.env.INSTAGRAM_USER_ID || "me",
    version: process.env.INSTAGRAM_API_VERSION || DEFAULT_VERSION,
  };
}

export class InstagramClient {
  constructor(private cfg: Config) {}

  get userId() {
    return this.cfg.userId;
  }

  async request<T = any>(
    method: "GET" | "POST" | "DELETE",
    path: string,
    params: Record<string, string | number | boolean | undefined> = {},
  ): Promise<T> {
    if (!this.cfg.token) {
      throw new InstagramError(
        "INSTAGRAM_ACCESS_TOKEN is not set. Generate a token in Meta App Dashboard > Instagram > API setup with Instagram login, then set it in the server environment.",
      );
    }
    const url = new URL(`https://graph.instagram.com/${this.cfg.version}/${path.replace(/^\//, "")}`);
    const body = new URLSearchParams();
    const target = method === "GET" ? url.searchParams : body;
    for (const [k, v] of Object.entries(params)) if (v !== undefined) target.set(k, String(v));
    const f = this.cfg.fetchImpl ?? fetch;
    const res = await f(url, {
      method,
      headers: {
        Authorization: `Bearer ${this.cfg.token}`,
        ...(method !== "GET" ? { "Content-Type": "application/x-www-form-urlencoded" } : {}),
      },
      body: method === "GET" ? undefined : body,
    });
    const text = await res.text();
    let json: any;
    try {
      json = text ? JSON.parse(text) : {};
    } catch {
      throw new InstagramError(`Non-JSON response (HTTP ${res.status}): ${text.slice(0, 200)}`, res.status);
    }
    if (!res.ok || json.error) {
      const e = json.error ?? {};
      throw new InstagramError(explain(e.message ?? `HTTP ${res.status}`, e.code), res.status, e.code);
    }
    return json as T;
  }

  get<T = any>(path: string, params?: Record<string, any>) {
    return this.request<T>("GET", path, params);
  }
  post<T = any>(path: string, params?: Record<string, any>) {
    return this.request<T>("POST", path, params);
  }
  del<T = any>(path: string, params?: Record<string, any>) {
    return this.request<T>("DELETE", path, params);
  }
}

function explain(message: string, code?: number): string {
  const hints: Record<number, string> = {
    190: "Access token is invalid or expired. Refresh or regenerate it.",
    10: "Permission missing. Check the token has the required instagram_business_* scopes.",
    4: "Rate limit hit. Wait and retry.",
    9: "Publishing limit reached (100 API-published posts per 24h).",
    100: "Invalid parameter. Check IDs and field names.",
  };
  return `Instagram API error${code ? ` ${code}` : ""}: ${message}${code && hints[code] ? ` Hint: ${hints[code]}` : ""}`;
}
