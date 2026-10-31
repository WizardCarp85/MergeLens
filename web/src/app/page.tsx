"use client";

import Link from "next/link";
import { ActionBadge } from "@/components/action-badge";
import { ApiPanel } from "@/components/api-panel";
import { JsonView } from "@/components/json-view";
import { getContext, getHunks } from "@/lib/api";
import { arr, hunkId, isRec, num, str } from "@/lib/loose";
import { useApi } from "@/lib/use-api";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 truncate font-mono text-sm text-zinc-100" title={value}>
        {value}
      </p>
    </div>
  );
}

export default function DashboardPage() {
  const ctx = useApi(getContext);
  const hunks = useApi(getHunks);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Merge dashboard</h1>
        <p className="mt-1 text-sm text-zinc-400">
          What is in progress, where each side came from, and what mergelens recommends.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-zinc-300">Context</h2>
        <ApiPanel state={ctx}>
          {(data) => (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="operation" value={str(data, "operation") ?? "none"} />
                <Stat label="ours" value={str(data, "ours", "head", "ours_ref") ?? "—"} />
                <Stat label="theirs" value={str(data, "theirs", "merge_head", "theirs_ref") ?? "—"} />
                <Stat
                  label="conflicted files"
                  value={String(num(data, "conflicted_files", "file_count") ?? arr(isRec(data) ? data.files : []).length)}
                />
              </div>
              <JsonView value={data} title="raw context" />
            </div>
          )}
        </ApiPanel>
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-medium text-zinc-300">Conflict hunks</h2>
          <Link href="/console/" className="text-xs text-zinc-400 hover:text-zinc-100">
            open console →
          </Link>
        </div>
        <ApiPanel state={hunks}>
          {(list) =>
            list.length === 0 ? (
              <p className="rounded-xl border border-zinc-800 p-5 text-sm text-zinc-400">
                No conflicts in progress. Start a merge, or run{" "}
                <code className="font-mono text-zinc-200">mergelens status --preview &lt;branch&gt;</code>.
              </p>
            ) : (
              <ul className="divide-y divide-zinc-800 overflow-hidden rounded-xl border border-zinc-800">
                {list.map((h, i) => {
                  const id = hunkId(h, i);
                  const rec = isRec(h) ? h.recommendation : undefined;
                  const action = str(rec, "action") ?? str(h, "action");
                  return (
                    <li key={id}>
                      <Link
                        href={`/console/?hunk=${encodeURIComponent(id)}`}
                        className="flex items-center gap-4 px-4 py-3 hover:bg-zinc-900/70"
                      >
                        <span className="font-mono text-xs text-zinc-500">#{id}</span>
                        <span className="flex-1 truncate font-mono text-sm">
                          {str(h, "path", "file") ?? "(unknown path)"}
                        </span>
                        <ActionBadge action={action} />
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )
          }
        </ApiPanel>
      </section>
    </div>
  );
}
