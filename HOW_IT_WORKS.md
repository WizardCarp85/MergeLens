# MergeLens — Quick Guide & How It Works

A simple, beginner-friendly guide explaining what MergeLens is, how to get started, and how to use it.

---

## 💡 What is MergeLens?

When you merge two Git branches (for example, merging a release or feature branch into `main`), you often get **merge conflicts**.

Standard Git shows you confusing conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`), but gives you zero answers to the questions that actually matter:
- **Where did this code come from?** Was it cherry-picked from another branch?
- **Has this code been tested?** Did it pass UAT?
- **Is this code running in production right now?**
- **Which version is safer to keep?**

**MergeLens answers all of these questions.** It analyzes the commit history, testing provenance, and branch ancestry, scores both sides, and gives you a clear recommendation (`KEEP_OURS`, `KEEP_THEIRS`, or `COMBINE`).

> **Golden Rule**: MergeLens is **advisory only**. It never touches or overwrites your working files without your explicit command. Git always remains the source of truth.

---

## 🚀 How to Get Started

### 1. Set Up Your Environment
Ensure you have Python 3.11+ installed. Activate your virtual environment and install MergeLens:

```bash
# Activate your environment
source .venv/bin/activate

# Or install in editable mode:
pip install -e ".[dev,ui]"
```

### 2. Verify Your Setup
Run the `doctor` command to check that everything is ready:

```bash
mergelens doctor
```
You will see green `ok` marks for Python, Git version ($\ge 2.38$), dashboard dependencies, and dashboard assets.

### 3. One-Time Repo Configuration
Configure Git to track and preserve MergeLens audit notes during rebase and commit amends:

```bash
mergelens init --yes
```

---

## 🛠️ Step-by-Step Usage During a Merge Conflict

Whenever a merge, cherry-pick, or rebase conflict happens:

### Step 1: See What Happened & Get a Recommendation
Run `mergelens status` to view a clear breakdown of the conflict:

```bash
mergelens status
```
**Example output:**
```
╭─ mergelens conflict status ──────────────────────────────────────────────╮
│ MERGE in progress                                                        │
│ OURS (HEAD): 3f1a2b4 (HEAD)                                              │
│ THEIRS (MERGE_HEAD): 7d9e2c1                                             │
│ Conflicted files: 1                                                      │
╰──────────────────────────────────────────────────────────────────────────╯
Conflict Hunks & Recommendations
┏━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Hunk ID   ┃ Path    ┃ OURS Testing ┃ THEIRS Testing              ┃     Score ┃ Recommend... ┃
┡━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ auth.py#1 │ auth.py │ ci:PASS      │ prod:PASS, uat:PASS,        │ 15 vs 100 │ KEEP_THEIRS  │
│           │         │              │ ci:PASS, origin:f16f38a1    │           │              │
└━━━━━━━━━━━┴━━━━━━━━━┴━━━━━━━━━━━━━━┴━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┴━━━━━━━━━━━┴──────────────┘
```
- It shows that **THEIRS** is already verified in production and passed UAT (+100 score).
- It recommends **`KEEP_THEIRS`**.

---

### Step 2: Understand the Differences in Plain English
Want a human-readable explanation of what each side changed? Run:

```bash
mergelens explain auth.py
```
This tells you what functions or lines were added, modified, or deleted on both sides.

---

### Step 3: Trace Where a Change Came From
If you want to know where a specific commit originated:

```bash
mergelens origin HEAD
# or trace the incoming commit:
mergelens origin MERGE_HEAD
```
MergeLens traces standard cherry-picks (`cherry-pick -x`), Django-style backports (`Backport of <hash>`), exact `git patch-id` matches, and AST similarity.

---

### Step 4: Record Your Decision
Record what you chose to keep and your reason (saved safely as pending; modifies no code):

```bash
mergelens decide auth.py --keep theirs -m "Keeping production-verified fix from upstream"
```

To see all pending decisions:
```bash
mergelens decide --show
```

---

### Step 5: Resolve and Commit
Resolve the conflict in your file (or accept the recommended code), stage the file, and commit:

```bash
# 1. Stage the resolved file
git add auth.py

# 2. Commit with MergeLens
mergelens commit
```

**What `mergelens commit` does:**
1. Creates a standard Git merge commit compatible with all Git tools.
2. Embeds audit trailers in the commit message:
   ```
   Mergelens-Provenance: verified
   Mergelens-Ours: 3f1a2b4
   Mergelens-Theirs: 7d9e2c1
   Mergelens-Decision: auth.py#1 keep=theirs reason="Keeping production-verified fix from upstream"
   ```
3. Attaches an immutable audit record to `refs/notes/mergelens`.

---

### Step 6: Share Audit Notes with Your Team
To push your conflict resolution audit trail to GitHub/remote:

```bash
mergelens sync push
```

And for your teammates to pull down the notes:
```bash
mergelens sync pull
```

---

## 🖥️ How to Use the Visual Web Dashboard

If you prefer a browser interface instead of the terminal:

```bash
mergelens ui
```
- Launches the local FastAPI server and opens your browser at `http://127.0.0.1:<port>/#token=<token>`.
- Protected by a secure one-time token in the URL hash.
- **Features**:
  - **Overview**: Live status of in-progress conflicts.
  - **Console**: Side-by-side diff view of OURS vs THEIRS.
  - **Decision Panel**: Save pending decisions with one click.
  - **Evidence**: Inspect test provenance and timeline for any commit.
  - **Audit**: View all past conflict resolutions stored in Git notes.

---

## 🔍 How It Works Behind the Scenes

```
                                      [Merge Conflict Occurs]
                                                 │
                  ┌──────────────────────────────┴──────────────────────────────┐
                  ▼                                                             ▼
     [4-Layer Origin Detection]                                   [5-Layer Evidence Waterfall]
   • L1: git patch-id (exact match)                             • Layer 1: refs/notes/mergelens
   • L2: Commit refs (cherry-pick -x, Backport of)              • Layer 2: Commit trailers (Prod:, UAT:, CI:)
   • L3: Hunk-level patch ID                                    • Layer 3: Origin-linked upstream test status
   • L4: Token & AST similarity                                 • Layer 4: Branch ancestry (origin/production)
                  │                                             • Layer 5: Honest Unknown (never hallucinated)
                  │                                                             │
                  └──────────────────────────────┬──────────────────────────────┘
                                                 ▼
                                     [Deterministic Scorer]
                           • Production: +45 pts    • UAT Pass: +25 pts
                           • CI Pass:    +15 pts    • Origin match: +15 pts
                                                 │
                                                 ▼
                                 [Clear Recommendation Emitted]
                     KEEP_OURS  |  KEEP_THEIRS  |  COMBINE  |  NO_CLEAR_WINNER
                                                 │
                                                 ▼
                                       [Developer Resolves]
                                                 │
                                                 ▼
                                       [mergelens commit]
                     • Standard Git Merge Commit created
                     • Audit trailers embedded in commit message
                     • Structured JSON note attached to refs/notes/mergelens
```

---

## ⌨️ CLI Quick Reference Cheat Sheet

| Task | Command |
| :--- | :--- |
| **Check environment** | `mergelens doctor` |
| **Configure repo** | `mergelens init` |
| **Show conflict status** | `mergelens status` |
| **Preview conflicts without merging** | `mergelens status --preview <branch>` |
| **Plain-English explanation** | `mergelens explain <file>` |
| **Trace commit origin** | `mergelens origin <sha>` |
| **Record a decision** | `mergelens decide <file> --keep <ours\|theirs\|combine\|custom> -m "<reason>"` |
| **View pending decisions** | `mergelens decide --show` |
| **Clear pending decisions** | `mergelens decide --clear` |
| **Create merge commit & notes** | `mergelens commit` |
| **Dry run commit message** | `mergelens commit --dry-run` |
| **Push audit notes to remote** | `mergelens sync push` |
| **Pull audit notes from remote** | `mergelens sync pull` |
| **Launch Web Dashboard** | `mergelens ui` |
