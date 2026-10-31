"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState, type FormEvent } from "react";
import { ActionBadge } from "@/components/action-badge";
import { ApiPanel, Skeleton, describeError } from "@/components/api-panel";
import { JsonView } from "@/components/json-view";
import { getHunk, getHunks, postDecision } from "@/lib/api";
import { arr, hunkId, isRec, sideText, str } from "@/lib/loose";
import type { Keep } from "@/lib/types";
import { useApi } from "@/lib/use-api";

const KEEP_OPTIONS: { value: Keep; label: string; hint: string }[] = [
  { value: "ours", label: "Keep ours", hint: "HEAD side as-is" },
  { value: "theirs", label: "Keep theirs", hint: "MERGE_HEAD side as-is" },
  { value: "combine", label: "Combine", hint: "both changes, hand-merged" },
  { value: "custom", label: "Custom", hint: "something else — explain why" },
];

function SidePane({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "ours" | "theirs";
  value: unknown;
}) {
  const text = sideText(value);
  const sha = str(value, "sha", "commit");
  const border = tone === "ours" ? "border-ours/40" : "border-theirs/40";
  const color = tone === "ours" ? "text-ours" : "text-theirs";
  return (
    <div className={`overflow-hidden rounded-xl border ${border} bg-zinc-900/40`}>
      <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
        <span className={`font-mono text-xs font-semibold uppercase ${color}`}>{label}</span>
        <span className="font-mono text-[11px] text-zinc-500">{sha ? sha.slice(0, 10) : ""}</span>
      </div>
      {text !== undefined ? (
        <pre className="max-h-[28rem] overflow-auto p-3 font-mono text-xs leading-relaxed text-zinc-200">
          {text}
        </pre>
      ) : (
        <div className="p-3">
          <JsonView value={value ?? null} />
        </div>
      )}
    </div>
  );
}

function DecisionForm({ hunkRef, path }: { hunkRef: string; path: string | undefined }) {
  const [keep, setKeep] = useState<Keep>("ours");
  const [reason, setReason] = useState("");
  const [state, setState] = useState<{ kind: "idle" | "saving" | "saved" | "error"; msg?: string }>({
    kind: "idle",
  });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (reason.trim().length === 0) return;
    setState({ kind: "saving" });
    try {
      await postDecision({ hunk_id: hunkRef, path, keep, reason: reason.trim() });
      setState({ kind: "saved" });
    } catch (err) {
      const d = describeError(err instanceof Error ? err : new Error(String(err)));
      setState({ kind: "error", msg: `${d.title}: ${d.detail}` });
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-zinc-800 p-5">
      <div>
        <h3 className="text-sm font-medium">Record a decision</h3>
        <p className="mt-1 text-xs text-zinc-500">
          Saved as <em>pending</em> in <code className="font-mono">.git/mergelens/pending</code>. The
          dashboard cannot commit; finish with <code className="font-mono">mergelens commit</code>.
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {KEEP_OPTIONS.map((o) => (
          <label
            key={o.value}
            className={
              "flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 text-sm " +
              (keep === o.value ? "border-zinc-500 bg-zinc-900" : "border-zinc-800 hover:border-zinc-700")
            }
          >
            <input
              type="radio"
              name="keep"
              value={o.value}
              checked={keep === o.value}
              onChange={() => setKeep(o.value)}
              className="mt-1"
            />
            <span>
              <span className="block">{o.label}</span>
              <span className="block text-xs text-zinc-500">{o.hint}</span>
            </span>
          </label>
        ))}
      </div>
      <label className="block text-sm">
        <span className="text-zinc-300">Why? (required — this goes into the commit trailer)</span>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          required
          className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-900/60 p-2 font-mono text-xs text-zinc-100 outline-none focus:border-zinc-500"
          placeholder="e.g. theirs carries the UAT-passed hotfix; ours only renamed the helper"
        />
      </label>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={state.kind === "saving" || reason.trim().length === 0}
          className="rounded-md bg-zinc-100 px-4 py-1.5 text-sm font-medium text-zinc-900 disabled:opacity-40"
        >
          {state.kind === "saving" ? "Saving…" : "Save pending decision"}
        </button>
        {state.kind === "saved" ? (
          <span className="text-xs text-emerald-300">Saved. Nothing was committed.</span>
        ) : null}
        {state.kind === "error" ? <span className="text-xs text-red-300">{state.msg}</span> : null}
      </div>
    </form>
  );
}

function HunkDetail({ id }: { id: string }) {
  const load = useCallback(() => getHunk(id), [id]);
  const hunk = useApi(load, { key: id });
  return (
    <ApiPanel state={hunk}>
      {(h) => {
        const rec = isRec(h) ? h.recommendation : undefined;
        const reasons = arr(isRec(rec) ? rec.reasons : undefined);
        const path = str(h, "path", "file");
        return (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-mono text-base">{path ?? "(unknown path)"}</h2>
              <span className="font-mono text-xs text-zinc-500">hunk #{hunkId(h, 0)}</span>
              <span className="ml-auto">
                <ActionBadge action={str(rec, "action") ?? str(h, "action")} />
              </span>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <SidePane label="ours" tone="ours" value={isRec(h) ? h.ours : undefined} />
              <SidePane label="theirs" tone="theirs" value={isRec(h) ? h.theirs : undefined} />
            </div>

            {isRec(h) && h.base !== undefined ? (
              <JsonView value={sideText(h.base) ?? h.base} title="base (merge-base version)" />
            ) : null}

            {reasons.length > 0 ? (
              <div className="rounded-xl border border-zinc-800 p-5">
                <h3 className="text-sm font-medium">Why this recommendation</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-300">
                  {reasons.map((r, i) => (
                    <li key={i}>{typeof r === "string" ? r : (str(r, "text", "reason") ?? JSON.stringify(r))}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <DecisionForm hunkRef={id} path={path} />
            <JsonView value={h} title="raw hunk" />
          </div>
        );
      }}
    </ApiPanel>
  );
}

function HunkPicker() {
  const hunks = useApi(getHunks);
  return (
    <ApiPanel state={hunks}>
      {(list) =>
        list.length === 0 ? (
          <p className="rounded-xl border border-zinc-800 p-5 text-sm text-zinc-400">
            No conflict hunks to show.
          </p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {list.map((h, i) => {
              const id = hunkId(h, i);
              return (
                <li key={id}>
                  <Link
                    href={`/console/?hunk=${encodeURIComponent(id)}`}
                    className="block rounded-lg border border-zinc-800 px-4 py-3 font-mono text-sm hover:border-zinc-600"
                  >
                    <span className="text-zinc-500">#{id}</span> {str(h, "path", "file") ?? "(unknown path)"}
                  </Link>
                </li>
              );
            })}
          </ul>
        )
      }
    </ApiPanel>
  );
}

function ConsoleInner() {
  const params = useSearchParams();
  const id = params.get("hunk");
  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Console</h1>
          <p className="mt-1 text-sm text-zinc-400">
            OURS vs THEIRS for one hunk, the recommendation, and a place to record your call.
          </p>
        </div>
        {id ? (
          <Link href="/console/" className="text-xs text-zinc-400 hover:text-zinc-100">
            ← all hunks
          </Link>
        ) : null}
      </div>
      {id ? <HunkDetail id={id} /> : <HunkPicker />}
    </div>
  );
}

export default function ConsolePage() {
  // useSearchParams() needs a Suspense boundary under static export.
  return (
    <Suspense fallback={<Skeleton lines={4} />}>
      <ConsoleInner />
    </Suspense>
  );
}
