const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function clearCsrf() {}

async function fetchCsrfToken(): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/csrf`, {
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("API injoignable. Vérifiez que la console backend tourne.", 0);
  }
  if (!res.ok) {
    throw new ApiError("Impossible d'obtenir le jeton CSRF.", res.status);
  }
  const data = (await res.json()) as { csrfToken: string };
  if (!data.csrfToken) {
    throw new ApiError("Impossible d'obtenir le jeton CSRF.", res.status);
  }
  return data.csrfToken;
}

type ApiOptions = RequestInit & { _retry?: boolean };

async function parseBody(res: Response): Promise<{ text: string; data: unknown }> {
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  return { text, data };
}

function isCsrfFailure(status: number, text: string, data: unknown): boolean {
  if (status !== 403) return false;
  const detail =
    data && typeof data === "object" && "detail" in data
      ? String((data as { detail?: unknown }).detail ?? "")
      : "";
  return /csrf|x-csrftoken|interdit|jeton de sécurité/i.test(`${text} ${detail}`);
}

function buildHeaders(options: ApiOptions, csrf?: string): Headers {
  const h = new Headers(options.headers);
  h.set("Accept", h.get("Accept") || "application/json");
  if (options.body && !(options.body instanceof FormData) && !h.has("Content-Type")) {
    h.set("Content-Type", "application/json");
  }
  if (csrf) h.set("X-CSRFToken", csrf);
  return h;
}

function extractError(data: unknown): string {
  if (!data || typeof data !== "object") return "Erreur inattendue.";
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    if (/csrf|x-csrftoken|jeton de sécurité/i.test(detail)) {
      return "Session expirée. Rechargez la page, puis réessayez.";
    }
    if (detail.trimStart().startsWith("<!DOCTYPE") || detail.includes("<html")) {
      return "La requête a été refusée. Rechargez la page, puis réessayez.";
    }
    return detail;
  }
  return "Erreur inattendue.";
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { _retry, ...rest } = options;
  const method = (rest.method ?? "GET").toUpperCase();
  const needsCsrf = method !== "GET" && method !== "HEAD" && method !== "OPTIONS";
  const csrf = needsCsrf ? await fetchCsrfToken() : undefined;
  const h = buildHeaders(options, csrf);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...rest,
      credentials: "include",
      cache: "no-store",
      headers: h,
    });
  } catch {
    throw new ApiError("API injoignable. Vérifiez que la console backend tourne.", 0);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const { text, data } = await parseBody(res);

  if (!res.ok && !_retry && isCsrfFailure(res.status, text, data)) {
    return api<T>(path, { ...options, _retry: true });
  }

  if (!res.ok) {
    throw new ApiError(extractError(data), res.status);
  }
  return data as T;
}
