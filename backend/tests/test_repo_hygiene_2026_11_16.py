"""Repo hygiene 2026-11-16: the worktree symlink ``frontend/node_modules`` must be ignored.

``frontend/node_modules`` is a SYMLINK into the main tree's install in every
``.wt-*`` worktree. A directory-only pattern (``node_modules/``) does not match a
symlink, so the link showed as ``??`` untracked and a ``git add -A`` would have
committed it. The root ``.gitignore`` now carries ``node_modules`` without the
trailing slash, which matches the symlink and real directories alike.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GITIGNORE = REPO_ROOT / ".gitignore"

needs_gitignore = pytest.mark.skipif(
    not GITIGNORE.is_file(), reason="repo .gitignore not present (container image)"
)
needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists() or not GITIGNORE.is_file(),
    reason="git checkout not available",
)


def _patterns(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def ignores_non_dir_named(text: str, name: str) -> bool:
    """True if a non-negated pattern matches ``name`` at any depth WITHOUT
    requiring it to be a directory (so a symlink of that name is ignored)."""
    pats = _patterns(text)
    if f"!{name}" in pats or f"!{name}/" in pats:
        return False
    return any(p in (name, f"**/{name}") for p in pats)


@needs_gitignore
def test_gitignore_ignores_node_modules_symlink_pattern():
    assert ignores_non_dir_named(GITIGNORE.read_text(), "node_modules")


def test_helper_rejects_directory_only_pattern():
    assert not ignores_non_dir_named("node_modules/\n", "node_modules")


def test_helper_rejects_commented_and_negated_patterns():
    assert not ignores_non_dir_named("# node_modules\n", "node_modules")
    assert not ignores_non_dir_named("node_modules\n!node_modules\n", "node_modules")


def test_helper_rejects_prefix_lookalike():
    assert not ignores_non_dir_named("node_modules_cache\n", "node_modules")


def _check_ignore(path: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "--no-index", "-q", path],
        capture_output=True,
        text=True,
    )
    assert res.returncode in (0, 1), res.stderr
    return res.returncode == 0


@needs_git
@pytest.mark.parametrize("path", ["frontend/node_modules", "node_modules", "backend/node_modules"])
def test_git_ignores_node_modules_as_non_directory(path):
    assert _check_ignore(path)


@needs_git
@pytest.mark.parametrize(
    "path",
    [
        "frontend/src/lib/ggwEma.ts",
        "frontend/src/hooks/useGgwLive.ts",
        "frontend/src/node_modules_helper.ts",
        "backend/tests/test_repo_hygiene_2026_11_16.py",
    ],
)
def test_git_does_not_ignore_source_files(path):
    assert not _check_ignore(path)
