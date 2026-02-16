import { normalizeApiError } from "./errors";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class ApiError extends Error {
  status: number;
  payload?: any;
  constructor(status: number, message: string, payload?: any) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

type RequestOptions = {
  method?: HttpMethod;
  path: string;
  token?: string | null;
  headers?: Record<string, string>;
  body?: any;
  rawBody?: BodyInit;
};

export async function apiRequest<T>(opts: RequestOptions): Promise<T> {
  const url = `${API_URL}${opts.path}`;
  const headers: Record<string, string> = { ...(opts.headers ?? {}) };

  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;

  let body: BodyInit | undefined;
  if (opts.rawBody !== undefined) {
    body = opts.rawBody;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(url, { method: opts.method ?? "GET", headers, body });

  const contentType = res.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await res.json().catch(() => null) : await res.text().catch(() => null);

  if (!res.ok) {
    const message = isJson ? normalizeApiError(payload) : (payload ? String(payload) : res.statusText);
    throw new ApiError(res.status, message, payload);
  }

  return payload as T;
}

export { API_URL };
