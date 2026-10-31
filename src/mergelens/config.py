"""Configuration: repo-level `.mergelens.toml`, overridable per user.

Only *reads* config in steps 1-3. `mergelens init` (which writes git config) is
wired up in a later step.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILENAME = ".mergelens.toml"


@dataclass(frozen=True)
class BranchConfig:
    production: str = "origin/production"
    uat: str = "origin/uat"
    mainline: str = "origin/main"


@dataclass(frozen=True)
class ScoringConfig:
    prod: int = 45
    uat_pass: int = 25
    uat_fail: int = -40
    ci_pass: int = 15
    ci_fail: int = -30
    mainline_patch: int = 10
    provenance: int = 5
    clear_winner_delta: int = 30


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    provider: str = "ollama"
    model: str = "qwen2.5-coder"
    send_code: bool = True


@dataclass(frozen=True)
class Config:
    root: Path
    branches: BranchConfig = field(default_factory=BranchConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    github_repo: str | None = None
    source_path: Path | None = None

    @property
    def state_dir(self) -> Path:
        """`.git/mergelens` — scratch area. Falls back to `.mergelens` if `.git` is read-only."""
        preferred = self.root / ".git" / "mergelens"
        try:
            preferred.mkdir(parents=True, exist_ok=True)
            return preferred
        except OSError:
            fallback = self.root / ".mergelens"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    @property
    def pending_dir(self) -> Path:
        return self.state_dir / "pending"


def _find_root(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def load(start: Path | None = None) -> Config:
    """Load config by walking up to the repo root. Missing file -> defaults."""
    root = _find_root(start) or (start or Path.cwd()).resolve()
    path = root / CONFIG_FILENAME
    if not path.is_file():
        return Config(root=root)

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    branches = BranchConfig(**data.get("branches", {}))
    scoring = ScoringConfig(**data.get("scoring", {}))
    ai = AIConfig(**{k: v for k, v in data.get("ai", {}).items() if k in AIConfig.__annotations__})
    gh = data.get("github", {}).get("repo") or os.environ.get("MERGELENS_GITHUB_REPO")

    return Config(
        root=root,
        branches=branches,
        scoring=scoring,
        ai=ai,
        github_repo=gh,
        source_path=path,
    )
