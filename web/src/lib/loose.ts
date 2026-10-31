/**
 * Defensive accessors for API payloads. Until step 5 generates the full
 * interfaces in types.ts, the sidecar's shapes are `unknown` on this side;
 * these helpers let the pages render what they recognise and fall back to raw
 * JSON for the rest.
 */

export type Rec = Record<string, unknown>;

export function isRec(v: unknown): v is Rec {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

/** First string-valued key found on `v`. */
export function str(v: unknown, ...keys: string[]): string | undefined {
  if (!isRec(v)) return undefined;
  for (const k of keys) {
    const x = v[k];
    if (typeof x === "string" && x.length > 0) return x;
  }
  return undefined;
}

/** First number-valued key found on `v`. */
export function num(v: unknown, ...keys: string[]): number | undefined {
  if (!isRec(v)) return undefined;
  for (const k of keys) {
    const x = v[k];
    if (typeof x === "number") return x;
  }
  return undefined;
}

/** Text of one side of a hunk: plain string, `{text|content}`, or a list of lines. */
export function sideText(side: unknown): string | undefined {
  if (typeof side === "string") return side;
  if (Array.isArray(side) && side.every((l) => typeof l === "string")) return side.join("\n");
  if (isRec(side)) {
    const direct = str(side, "text", "content", "body");
    if (direct !== undefined) return direct;
    if (Array.isArray(side.lines)) return sideText(side.lines);
  }
  return undefined;
}

export function shortSha(sha: string | undefined, n = 10): string {
  return sha ? sha.slice(0, n) : "—";
}

export function hunkId(h: unknown, index: number): string {
  return str(h, "id", "hunk_id") ?? String(num(h, "index", "number") ?? index + 1);
}
