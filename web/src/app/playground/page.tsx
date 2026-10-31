"use client";

import { useState, useSyncExternalStore, type FormEvent } from "react";
import { describeError } from "@/components/api-panel";
import { JsonView } from "@/components/json-view";
import { api, hasToken } from "@/lib/api";

type Method = "GET" | "POST";

const PRESETS: { method: Method; path: string; body?: string; note: string }[] = [
  { method: "GET", path: "/context", note: "operation, HEAD, MERGE_HEAD" },
  { method: "GET", path: "/hunks", note: "all conflict hunks" },
  { method: "GET", path: "/hunks/1", note: "one hunk with OURS/THEIRS/BASE" },
  { method: "GET", path: "/evidence/HEAD", note: "testing provenance" },
  { method: "GET", path: "/timeline/HEAD", note: "chain of custody" },
  { method: "GET", path: "/audit", note: "refs/notes/mergelens records" },
  {
    method: "POST",
    path: "/decisions",
    body: JSON.stringify({ hunk_id: "1", keep: "theirs", reason: "example" }, null, 2),
    note: "save a pending decision (never commits)",
  },
];

type Result =
  | { kind: "idle" }
  | { kind: "busy" }
  | { kind: "ok"; ms: number; data: unknown }
  | { kind: "error"; ms: number; title: string; detail: string };

const noop = () => () => {};

export default function PlaygroundPage() {
  const tokenPresent = useSyncExternalStore(noop, hasToken, () => false);
  const [method, setMethod] = useState<Method>("GET");
  const [path, setPath] = useState("/context");
  const [body, setBody] = useState("");
  const [result, setResult] = useState<Result>({ kind: "idle" });

  async function send(e?: FormEvent) {
    e?.preventDefault();
    setResult({ kind: "busy" });
    const started = performance.now();
    try {
      const data = await api<unknown>(path, method === "POST" ? { method, body } : undefined);
      setResult({ kind: "ok", ms: Math.round(performance.now() - started), data });
    } catch (err) {
      const d = describeError(err instanceof Error ? err : new Error(String(err)));
      setResult({
        kind: "error",
        ms: Math.round(performance.now() - started),
        title: d.title,
        detail: d.detail,
      });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Playground</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Drive the local sidecar API directly. Every call goes through the same client the
          dashboard uses (<code className="font-mono">web/src/lib/api.ts</code>). There is no commit
          endpoint to call.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span
          className={
            "rounded-full border px-2.5 py-0.5 font-mono " +
            (tokenPresent
              ? "border-emerald-500/50 text-emerald-300"
              : "border-amber-500/50 text-amber-300")
          }
        >
          token {tokenPresent ? "present" : "missing"}
        </span>
        <span className="text-zinc-500">
          {tokenPresent
            ? "sent as Authorization: Bearer on every request"
            : "open the URL printed by `mergelens ui` to load one"}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.method + p.path}
            type="button"
            title={p.note}
            onClick={() => {
              setMethod(p.method);
              setPath(p.path);
              setBody(p.body ?? "");
            }}
            className="rounded-md border border-zinc-800 px-2.5 py-1 font-mono text-xs text-zinc-300 hover:border-zinc-600"
          >
            <span className={p.method === "POST" ? "text-theirs" : "text-ours"}>{p.method}</span>{" "}
            {p.path}
          </button>
        ))}
      </div>

      <form onSubmit={send} className="space-y-3 rounded-xl border border-zinc-800 p-5">
        <div className="flex gap-2">
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value as Method)}
            className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-2 py-2 font-mono text-sm"
          >
            <option>GET</option>
            <option>POST</option>
          </select>
          <div className="flex flex-1 items-center rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 font-mono text-sm">
            <span className="text-zinc-500">/api</span>
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              className="flex-1 bg-transparent py-2 outline-none"
              spellCheck={false}
            />
          </div>
          <button
            type="submit"
            disabled={result.kind === "busy"}
            className="rounded-md bg-zinc-100 px-4 py-1.5 text-sm font-medium text-zinc-900 disabled:opacity-40"
          >
            {result.kind === "busy" ? "Sending…" : "Send"}
          </button>
        </div>
        {method === "POST" ? (
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
            spellCheck={false}
            placeholder='{"hunk_id": "1", "keep": "theirs", "reason": "…"}'
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 p-2 font-mono text-xs outline-none focus:border-zinc-500"
          />
        ) : null}
      </form>

      {result.kind === "ok" ? (
        <section className="space-y-2">
          <p className="font-mono text-xs text-emerald-300">200 · {result.ms} ms</p>
          <JsonView value={result.data} />
        </section>
      ) : null}
      {result.kind === "error" ? (
        <section className="rounded-xl border border-zinc-800 p-5">
          <p className="font-mono text-xs text-red-300">
            {result.title} · {result.ms} ms
          </p>
          <p className="mt-1 text-sm text-zinc-400">{result.detail}</p>
        </section>
      ) : null}
    </div>
  );
}
