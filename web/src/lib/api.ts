/**
 * Browser-side client for the FastAPI sidecar started by `mergelens ui`.
 *
 * `mergelens ui` opens the dashboard at:  http://127.0.0.1:<port>/#token=<token>
 * The token is read from the URL hash and sent as a bearer header.
 */

const TOKEN_KEY = "mergelens.token";

function token(): string {
  if (typeof window === "undefined") return "";
  const hash = new URLSearchParams(window.location.hash.slice(1));
  const fromHash = hash.get("token");
  if (fromHash) {
    sessionStorage.setItem(TOKEN_KEY, fromHash);
    history.replaceState(null, "", window.location.pathname + window.location.search);
    return fromHash;
  }
  return sessionStorage.getItem(TOKEN_KEY) ?? "";
}

/** Whether a dashboard token is available (diagnostics only; never exposes it). */
export function hasToken(): boolean {
  return token().length > 0;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token()}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(await res.text().catch(() => res.statusText), res.status);
  }
  return (await res.json()) as T;
}

// Endpoint shims — shapes land in web/src/lib/types.ts alongside models.py (step 5).
export const getContext = () => api<unknown>("/context");
export const getHunks = () => api<unknown[]>("/hunks");
export const getHunk = (id: string) => api<unknown>(`/hunks/${encodeURIComponent(id)}`);
export const getEvidence = (sha: string) => api<unknown>(`/evidence/${encodeURIComponent(sha)}`);
export const getTimeline = (sha: string) => api<unknown>(`/timeline/${encodeURIComponent(sha)}`);
export const getAudit = () => api<unknown[]>("/audit");

/** The dashboard can only save *pending* decisions. There is no commit endpoint. */
export const postDecision = (body: unknown) =>
  api<unknown>("/decisions", { method: "POST", body: JSON.stringify(body) });
