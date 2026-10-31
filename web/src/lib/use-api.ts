"use client";

import { useCallback, useEffect, useState } from "react";

type Settled<T> = { status: "ok"; data: T } | { status: "error"; error: Error };

export type ApiState<T> = {
  loading: boolean;
  data: T | undefined;
  error: Error | undefined;
  reload: () => void;
};

type Options = {
  /** Changes to `key` restart the request (e.g. a hunk id or SHA). */
  key?: string;
  /** When false, nothing is fetched and the state is idle. */
  enabled?: boolean;
};

function toError(err: unknown): Error {
  return err instanceof Error ? err : new Error(String(err));
}

/**
 * Minimal fetch-state hook for the sidecar API. `load` should be referentially
 * stable (a module-level function or a `useCallback`).
 */
export function useApi<T>(load: () => Promise<T>, options: Options = {}): ApiState<T> {
  const { key = "", enabled = true } = options;
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<{
    key: string;
    nonce: number;
    settled: Settled<T>;
  } | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    load().then(
      (data) => {
        if (!cancelled) setResult({ key, nonce, settled: { status: "ok", data } });
      },
      (err: unknown) => {
        if (!cancelled) setResult({ key, nonce, settled: { status: "error", error: toError(err) } });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [load, key, nonce, enabled]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  const current = result !== null && result.key === key && result.nonce === nonce ? result : null;
  return {
    loading: enabled && current === null,
    data: current?.settled.status === "ok" ? current.settled.data : undefined,
    error: current?.settled.status === "error" ? current.settled.error : undefined,
    reload,
  };
}
