const ACTION_STYLE: Record<string, string> = {
  KEEP_OURS: "border-ours/50 text-ours",
  KEEP_THEIRS: "border-theirs/50 text-theirs",
  COMBINE: "border-emerald-500/50 text-emerald-300",
  NO_CLEAR_WINNER: "border-amber-500/50 text-amber-300",
};

export function ActionBadge({ action }: { action: string | undefined }) {
  if (!action) return <span className="text-xs text-zinc-500">no recommendation</span>;
  const style = ACTION_STYLE[action] ?? "border-zinc-600 text-zinc-300";
  return (
    <span className={`rounded-full border px-2 py-0.5 font-mono text-[11px] ${style}`}>
      {action}
    </span>
  );
}
