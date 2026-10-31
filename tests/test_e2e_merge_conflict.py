"""End-to-end integration test simulating a realistic backport merge conflict."""

import os
import shutil
import tempfile
from pathlib import Path

from mergelens.cli.status import build_status_hunks
from mergelens.config import BranchConfig, Config, ScoringConfig
from mergelens.decision.manager import (
    clear_pending_decisions,
    compose_commit_message,
    load_audit_records,
    load_pending_decisions,
    record_audit_notes,
    save_decision,
)
from mergelens.git.runner import run_git
from mergelens.models import Action, Decision


def test_full_backport_conflict_lifecycle():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # 1. Initialize git repo
        run_git(["init", "-b", "main"], cwd=temp_dir, allow_write=True, allow_fixture=True)
        run_git(["config", "user.name", "Test Developer"], cwd=temp_dir, allow_write=True)
        run_git(["config", "user.email", "dev@example.com"], cwd=temp_dir, allow_write=True)

        # Base commit
        file_a = temp_dir / "calculator.py"
        file_a.write_text("def calculate(x):\n    return x * 2\n")
        run_git(["add", "calculator.py"], cwd=temp_dir, allow_write=True)
        run_git(["commit", "-m", "Initial calculator"], cwd=temp_dir, allow_commit=True)

        # Create production branch at initial commit
        run_git(["branch", "production"], cwd=temp_dir, allow_write=True)

        # 2. Add fix to main and advance production
        file_a.write_text("def calculate(x):\n    # Optimized by main\n    return x * 10\n")
        run_git(["add", "calculator.py"], cwd=temp_dir, allow_write=True)
        run_git(
            ["commit", "-m", "Optimization on main\n\nProd: verified\nUAT: pass"],
            cwd=temp_dir,
            allow_commit=True,
        )
        main_fix_sha = run_git(["rev-parse", "HEAD"], cwd=temp_dir).stdout.strip()

        # Update production branch to include this fix
        run_git(["branch", "-f", "production", "HEAD"], cwd=temp_dir, allow_write=True)

        # 3. Create release/v1 branch from base and cherry-pick with -x
        run_git(["checkout", "-b", "release/v1", "HEAD~1"], cwd=temp_dir, allow_fixture=True)
        file_a.write_text("def calculate(x):\n    # Backported fix\n    return x * 10\n")
        run_git(["add", "calculator.py"], cwd=temp_dir, allow_write=True)
        backport_msg = f"Backport fix to v1\n\n(cherry picked from commit {main_fix_sha})"
        run_git(["commit", "-m", backport_msg], cwd=temp_dir, allow_commit=True)
        theirs_sha = run_git(["rev-parse", "HEAD"], cwd=temp_dir).stdout.strip()

        # 4. On main, introduce a diverging local change to cause a conflict
        run_git(["checkout", "main"], cwd=temp_dir, allow_fixture=True)
        file_a.write_text("def calculate(x):\n    # Diverged quick patch\n    return x * 5\n")
        run_git(["add", "calculator.py"], cwd=temp_dir, allow_write=True)
        run_git(["commit", "-m", "Unverified divergent patch"], cwd=temp_dir, allow_commit=True)
        ours_sha = run_git(["rev-parse", "HEAD"], cwd=temp_dir).stdout.strip()

        # 5. Start merge to trigger conflict
        merge_res = run_git(["merge", "release/v1"], cwd=temp_dir, check=False, allow_fixture=True)
        assert merge_res.returncode != 0
        assert (temp_dir / ".git" / "MERGE_HEAD").is_file()

        # 6. Run MergeLens status analysis
        cfg = Config(
            root=temp_dir,
            branches=BranchConfig(production="production", mainline="main"),
            scoring=ScoringConfig(),
        )

        ctx, hunks = build_status_hunks(cfg)
        assert len(hunks) >= 1
        hunk = hunks[0]

        # Verify origin and provenance were detected
        assert hunk.theirs.origin is not None
        assert hunk.theirs.origin.source_sha == main_fix_sha
        assert hunk.theirs.evidence is not None
        assert hunk.theirs.evidence.prod.status.value == "pass"

        # Verify recommendation chose THEIRS because it is verified in production!
        assert hunk.recommendation.action == Action.KEEP_THEIRS
        assert hunk.recommendation.score_theirs > hunk.recommendation.score_ours

        # 7. Record decision
        dec = Decision(
            hunk_id=hunk.hunk_id,
            path="calculator.py",
            keep="theirs",
            reason="Cherry-pick of main commit verified in production",
        )
        save_decision(temp_dir, theirs_sha, dec)
        pending = load_pending_decisions(temp_dir, theirs_sha)
        assert len(pending) == 1
        assert pending[0].keep == "theirs"

        # 8. Resolve working tree and commit
        file_a.write_text("def calculate(x):\n    # Backported fix\n    return x * 10\n")
        run_git(["add", "calculator.py"], cwd=temp_dir, allow_write=True)

        commit_msg = compose_commit_message(
            subject="Merge branch 'release/v1' into main",
            body="Resolved conflicts with MergeLens",
            decisions=pending,
            ours_sha=ours_sha,
            theirs_sha=theirs_sha,
        )
        run_git(["commit", "-m", commit_msg], cwd=temp_dir, allow_commit=True)
        new_commit = run_git(["rev-parse", "HEAD"], cwd=temp_dir).stdout.strip()

        # Record audit notes and clear pending
        record_audit_notes(temp_dir, new_commit, pending)
        clear_pending_decisions(temp_dir, theirs_sha)

        # 9. Verify notes and commit trailers
        audit_records = load_audit_records(temp_dir)
        assert len(audit_records) >= 1
        assert audit_records[0].keep == "theirs"
        assert audit_records[0].path == "calculator.py"

        # Verify commit message has trailers
        log_msg = run_git(["log", "-1", "--format=%B"], cwd=temp_dir).stdout
        assert "Mergelens-Provenance: verified" in log_msg
        assert "Mergelens-Decision: calculator.py" in log_msg
        assert "keep=theirs" in log_msg

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
