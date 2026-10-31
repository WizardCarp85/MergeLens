"use client";

import { ApiPanel } from "@/components/api-panel";
import { JsonView } from "@/components/json-view";
import { getAudit } from "@/lib/api";
import { isRec, shortSha, str } from "@/lib/loose";
import { useApi } from "@/lib/use-api";

export default function AuditPage() {
  const audit = useApi(getAudit);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Audit trail</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Decisions recorded by <code className="font-mono">mergelens commit</code> and stored as
          append-only JSON Lines in <code className="font-mono">refs/notes/mergelens</code>. Read-only
          here; share with <code className="font-mono">mergelens sync push</code>.
        </p>
      </div>

      <ApiPanel state={audit}>
        {(records) =>
          records.length === 0 ? (
            <p className="rounded-xl border border-zinc-800 p-5 text-sm text-zinc-400">
              No audit records yet. They appear after the first{" "}
              <code className="font-mono text-zinc-200">mergelens commit</code>.
            </p>
          ) : (
            <div className="overflow-hidden rounded-xl border border-zinc-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-900/60 text-[11px] uppercase tracking-wide text-zinc-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">commit</th>
                    <th className="px-4 py-2 font-medium">when</th>
                    <th className="px-4 py-2 font-medium">path</th>
                    <th className="px-4 py-2 font-medium">kept</th>
                    <th className="px-4 py-2 font-medium">reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  {records.map((r, i) => (
                    <tr key={str(r, "id") ?? i} className="align-top">
                      <td className="px-4 py-2 font-mono text-xs text-zinc-300">
                        {shortSha(str(r, "commit", "sha"))}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-zinc-500">
                        {str(r, "when", "recorded_at", "timestamp") ?? "—"}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">{str(r, "path", "file") ?? "—"}</td>
                      <td className="px-4 py-2 font-mono text-xs">
                        {str(r, "keep", "action", "choice") ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-xs text-zinc-300">
                        {str(r, "reason") ?? (isRec(r) ? <JsonView value={r} /> : String(r))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </ApiPanel>
    </div>
  );
}
