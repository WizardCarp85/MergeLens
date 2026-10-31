export function JsonView({ value, title }: { value: unknown; title?: string }) {
  const text = JSON.stringify(value, null, 2) ?? String(value);
  return (
    <details className="group rounded-lg border border-zinc-800 bg-zinc-900/60" open={!title}>
      {title ? (
        <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-zinc-400 group-open:border-b group-open:border-zinc-800">
          {title}
        </summary>
      ) : null}
      <pre className="max-h-[32rem] overflow-auto p-3 font-mono text-xs leading-relaxed text-zinc-300">
        {text}
      </pre>
    </details>
  );
}
