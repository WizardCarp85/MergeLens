# mergelens

Git-native merge conflict advisor. **Advisory only — Git stays the source of truth.**

mergelens reads your repository, explains where each side of a conflict came from
(patch-id, `cherry-pick -x`, message refs, AST similarity), how well each side was
tested (notes → trailers → origin-linked → API → ancestry → *Unknown*), and
recommends an action. It never edits your files: you resolve, then run
`mergelens commit`, which creates a standard merge commit and attaches an audit
record to `refs/notes/mergelens`.

## Hard invariants

* Only `mergelens.git.runner` may invoke a subprocess.
* Only `mergelens commit` may run `git commit`.
* No command ever writes to the user's working tree.
* The dashboard has no commit button — it can only save *pending* decisions.

## Repository layout

```
pyproject.toml            Python package (hatchling); `mergelens` console script
src/mergelens/            CLI (Typer + Rich), config, models, git/origin/evidence/scoring/decision
src/mergelens/server/     FastAPI sidecar (step 7); static/ receives the dashboard export (step 8)
web/                      Next.js dashboard, built as a static export (output: "export")
scripts/preview_server.mjs  Zero-dependency static server used only by the hosted preview
```

The repo root also carries a thin `package.json` (npm workspace → `web/`) and a
`tsconfig.json` that extends `web/tsconfig.json`. They exist so the hosted preview can run
`npm run build` / `npm run start` / `tsc --noEmit` from the root; they are not part of the
product. In the real product the Python process serves `web/out` itself.

## Development

### Python CLI

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ui]"

mergelens --version
mergelens --help
mergelens doctor            # live checks; git checks show "pending (step 4)"
mergelens status            # not implemented yet — arrives in step 6
```

### Dashboard (static export)

```bash
npm install                 # workspace root; installs web/ dependencies
npm run build               # -> web/out/ (no server routes, no database)
npm run start               # preview shim: serves web/out + /api/health
```

The dashboard talks to the FastAPI sidecar started by `mergelens ui` through
`web/src/lib/api.ts` (`/api/*`, bearer token read from the URL hash). Until the sidecar
exists (step 7) every page shows a "sidecar not running" panel.

## Configuration

Optional `.mergelens.toml` at the repo root:

```toml
[branches]
production = "origin/production"
uat        = "origin/uat"
mainline   = "origin/main"

[scoring]
prod = 45
uat_pass = 25
uat_fail = -40

[ai]
enabled = false
provider = "ollama"
model = "qwen2.5-coder"

[github]
repo = "your-org/your-repo"   # or MERGELENS_GITHUB_REPO
```

## Roadmap

| Step | Scope | Status |
|---|---|---|
| 1–3 | Repo split, Python skeleton, static-export dashboard shell | ✅ Done |
| 4 | `git/runner.py` — subprocess caller, allow-list + write guard | ✅ Done |
| 5 | Full Pydantic models + `Known`/`Unknown` wrapper, synchronized `types.ts` | ✅ Done |
| 6 | `mergelens status`: `MERGE_HEAD`, stages 1/2/3, OURS vs THEIRS, origin L1-L4, evidence waterfall, deterministic scoring | ✅ Done |
| 7 | FastAPI sidecar + `mergelens ui` with bearer token in URL hash | ✅ Done |
| 8 | `scripts/build_web.py`, `mergelens init`, decision persistence & git notes audit | ✅ Done |

## Exit codes

`0` ok · `1` user action needed (e.g. `git add`) · `2` tool / environment error
