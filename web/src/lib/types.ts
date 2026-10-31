// Mirrors src/mergelens/models.py. Keep the string unions and interfaces in sync.

export type Side = "ours" | "theirs" | "base";
export type Operation = "merge" | "cherry-pick" | "rebase" | "none";
export type Status = "pass" | "fail" | "pending" | "unknown";
export type MatchType =
  | "patch_id"
  | "cherry_pick_x"
  | "message_ref"
  | "hunk_patch_id"
  | "ast_similar";
export type Relation =
  | "equivalent"
  | "superset_ours"
  | "superset_theirs"
  | "complementary"
  | "contradictory"
  | "unknown";
export type Action = "KEEP_OURS" | "KEEP_THEIRS" | "COMBINE" | "NO_CLEAR_WINNER";

/** What `mergelens decide --keep` accepts. */
export type Keep = "ours" | "theirs" | "combine" | "custom";

export interface OriginMatch {
  match_type: MatchType;
  source_sha: string;
  target_sha: string;
  confidence: number;
  reason: string;
  details?: Record<string, unknown>;
}

export interface EvidenceItem {
  status: Status;
  source: string;
  detail?: string | null;
}

export interface EvidenceReport {
  sha: string;
  prod: EvidenceItem;
  uat: EvidenceItem;
  ci: EvidenceItem;
  ancestry: string[];
  notes_present: boolean;
  trailers: Record<string, string>;
}

export interface SideInfo {
  side: Side;
  sha?: string | null;
  text: string;
  lines: string[];
  origin?: OriginMatch | null;
  evidence?: EvidenceReport | null;
}

export interface Recommendation {
  action: Action;
  confidence: number;
  score_ours: number;
  score_theirs: number;
  reasons: string[];
}

export interface ConflictHunk {
  hunk_id: string;
  path: string;
  start_line: number;
  ours: SideInfo;
  theirs: SideInfo;
  base?: SideInfo | null;
  recommendation: Recommendation;
  relation: Relation;
}

export interface MergeContext {
  operation: Operation;
  ours: string;
  theirs: string;
  head: string;
  merge_head: string;
  conflicted_files: string[];
  is_preview?: boolean;
}

export interface Decision {
  hunk_id: string;
  path: string;
  keep: Keep;
  reason: string;
  decided_at?: string;
}

export interface AuditRecord {
  id: string;
  commit: string;
  when: string;
  path: string;
  hunk_id?: string | null;
  keep: string;
  reason: string;
  author?: string | null;
  details?: Record<string, unknown>;
}
