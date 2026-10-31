import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";
import type { ApiState } from "@/lib/use-api";

export function describeError(error: Error): { title: string; detail: string; offline: boolean } {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return {
        title: "Not authorised",
        detail:
          "The dashboard token is missing or stale. Open the URL printed by `mergelens ui` — the token travels in the URL hash.",
        offline: false,
      };
    }
    if (error.status === 404 || error.status === 502 || error.status === 503) {
      return {
        title: "Sidecar not running",
        detail:
          "This page reads from the local API that `mergelens ui` starts on 127.0.0.1. Run it and open the URL it prints.",
        offline: true,
      };
    }
    return { title: `API error ${error.status}`, detail: error.message, offline: false };
  }
  // fetch() rejects with TypeError when nothing is listening at all.
  return {
    title: "Sidecar not reachable",
    detail: `${error.message}. Start it with \`mergelens ui\`.`,
    offline: true,
  };
}

export function ErrorCard({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const d = describeError(error);
  return (
    <div
      className={
        "rounded-xl border p-5 " +
        (d.offline ? "border-zinc-700 bg-zinc-900/60" : "border-red-500/40 bg-red-500/5")
      }
    >
      <p className={"text-sm font-semibold " + (d.offline ? "text-zinc-200" : "text-red-300")}>
        {d.title}
      </p>
      <p className="mt-1 text-sm text-zinc-400">{d.detail}</p>
      {d.offline ? (
        <pre className="mt-3 rounded-md bg-black/40 px-3 py-2 font-mono text-xs text-zinc-300">
          $ mergelens ui
        </pre>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-zinc-700 px-3 py-1 text-xs text-zinc-200 hover:bg-zinc-800"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-2 rounded-xl border border-zinc-800 p-5">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="h-3 rounded bg-zinc-800" style={{ width: `${90 - i * 15}%` }} />
      ))}
    </div>
  );
}

/** Renders loading / error / data states for a `useApi` result. */
export function ApiPanel<T>({
  state,
  children,
}: {
  state: ApiState<T>;
  children: (data: T) => ReactNode;
}) {
  if (state.loading) return <Skeleton />;
  if (state.error) return <ErrorCard error={state.error} onRetry={state.reload} />;
  if (state.data === undefined) return null;
  return <>{children(state.data)}</>;
}
