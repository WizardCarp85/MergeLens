"use client";

import { useCallback, useState, type FormEvent } from "react";
import { ApiPanel } from "@/components/api-panel";
import { JsonView } from "@/components/json-view";
import { getEvidence, getTimeline } from "@/lib/api";
import { arr, isRec, str } from "@/lib/loose";
import type { Status } from "@/lib/types";
import { useApi } from "@/lib/use-api";

const STATUS_STYLE: Record<Status, string> = {
  pass: "border-emerald-500/50 text-emerald-300",
  fail: "border-red-500/50 text-red-300",
  pending: "border-amber-500/50 text-amber-300",
  unknown: "border-zinc-700 text-zinc-400",
};

function isStatus(v: unknown): v is Status {
  return v === "pass" || v === "fail" || v === "pending" || v === "unknown";
}

/** Status cells for keys like prod / uat / ci — whatever the sidecar reports. */
function StatusGrid({ evidence }: { evidence: unknown }) {
  if (!isRec(evidence)) return null;
  const cells = Object.entries(evidence).flatMap(([k, v]) => {
    const status = isStatus(v) ? v : isRec(v) && isStatus(v.status) ? v.status : null;
    return status ? [{ key: k, status, source: str(v, "source", "via") }] : [];
  });
  if (cells.length === 0) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {cells.map((c) => (
        <div key={c.key} className={`rounded-lg border px-4 py-3 ${STATUS_STYLE[c.status]}`}>
          <p className="text-[11px] uppercase tracking-wide opacity-70">{c.key}</p>
          <p className="mt-1 font-mono text-sm font-semibold uppercase">{c.status}</p>
          {c.source ? <p className="mt-1 text-xs opacity-70">via {c.source}</p> : null}
        </div>
      ))}
    </div>
  );
}

function Timeline({ events }: { events: unknown }) {
  const list = arr(isRec(events) ? events.events : events);
  if (list.length === 0) return <JsonView value={events} title="raw timeline" />;
  return (
    <ol className="relative space-y-3 border-l border-zinc-800 pl-5">
      {list.map((e, i) => (
        <li key={i} className="relative">
          <span className="absolute -left-[1.4rem] top-1.5 h-2 w-2 rounded-full bg-zinc-600" />
          <p className="font-mono text-[11px] text-zinc-500">
            {str(e, "when", "date", "timestamp", "at") ?? ""}
          </p>
          <p className="text-sm text-zinc-200">
            <span className="font-medium">{str(e, "event", "kind", "type") ?? "event"}</span>
            {str(e, "detail", "message", "summary") ? (
              <span className="text-zinc-400"> — {str(e, "detail", "message", "summary")}</span>
            ) : null}
          </p>
        </li>
      ))}
    </ol>
  );
}

export default function EvidencePage() {
  const [input, setInput] = useState("");
  const [sha, setSha] = useState("");

  const loadEvidence = useCallback(() => getEvidence(sha), [sha]);
  const loadTimeline = useCallback(() => getTimeline(sha), [sha]);
  const evidence = useApi(loadEvidence, { key: sha, enabled: sha.length > 0 });
  const timeline = useApi(loadTimeline, { key: sha, enabled: sha.length > 0 });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSha(input.trim());
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Evidence</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Testing provenance for a commit: notes → trailers → origin-linked → API → ancestry →{" "}
          <em>Unknown</em>. Unknown is reported honestly, never guessed.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="commit sha or ref, e.g. 3f9c2a1 or origin/uat"
          className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 font-mono text-sm outline-none focus:border-zinc-500"
        />
        <button
          type="submit"
          className="rounded-md bg-zinc-100 px-4 py-1.5 text-sm font-medium text-zinc-900"
        >
          Look up
        </button>
      </form>

      {sha ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="space-y-3">
            <h2 className="font-mono text-sm text-zinc-300">evidence · {sha}</h2>
            <ApiPanel state={evidence}>
              {(data) => (
                <div className="space-y-3">
                  <StatusGrid evidence={data} />
                  <JsonView value={data} title="raw evidence" />
                </div>
              )}
            </ApiPanel>
          </section>
          <section className="space-y-3">
            <h2 className="font-mono text-sm text-zinc-300">timeline · {sha}</h2>
            <ApiPanel state={timeline}>{(data) => <Timeline events={data} />}</ApiPanel>
          </section>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-zinc-800 p-5 text-sm text-zinc-500">
          Enter a commit to see where it has been tested and the chain of custody behind that claim.
        </p>
      )}
    </div>
  );
}
