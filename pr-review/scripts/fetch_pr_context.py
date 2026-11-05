#!/usr/bin/env python3
"""Fetch GitHub PR metadata (including the commit list), changed files, comments, and reviews.

Concurrent-safe: results are stored in a content-addressed cache
(`~/.cache/pr-review-inline/<repo>/<pr>/<head_sha>/`, or `$XDG_CACHE_HOME` /
`$PR_REVIEW_CACHE_DIR` if set) and protected by an OS-level file lock, so
multiple agents reviewing the same PR at the same head SHA share a single set
of GitHub API calls instead of duplicating them. The user-facing output
directory is populated via symlinks to the cache, so the standard
`pr.json` / `files.json` / `comments.json` / `reviews.json` files still
appear at the path you pass via `--out-dir`.

Reads are read-first: if the cache directory already has every file the
script needs, the script does not call `gh` for the bulk endpoints
(`files`, `comments`, `reviews`). Pass `--no-cache` to bypass the cache
and always refetch.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


PR_VIEW_FIELDS = ",".join(
    [
        "number",
        "title",
        "body",
        "state",
        "author",
        "baseRefName",
        "baseRefOid",
        "headRefName",
        "headRefOid",
        "mergeStateStatus",
        "commits",
    ]
)

BULK_FILES = ("files.json", "comments.json", "reviews.json")
ALL_FILES = ("pr.json",) + BULK_FILES


def run_json_command(args: list[str]) -> Any:
    try:
        result = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError:
        sys.stderr.write(
            f"Command not found: {args[0]!r}. "
            "Ensure it is installed and available on PATH.\n"
        )
        raise SystemExit(1)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return json.loads(result.stdout)


def atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON to a sibling .tmp file then atomically replace.

    The intermediate .tmp file is created in the same directory so the
    subsequent `os.replace` is guaranteed to be atomic on the same
    filesystem. Concurrent readers therefore never observe a partially
    written file.
    """
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


def read_json_if_valid(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def is_cache_complete(cache_dir: Path) -> bool:
    """Return True if cache_dir has every file the script needs."""
    if not cache_dir.is_dir():
        return False
    for name in ALL_FILES:
        path = cache_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            return False
    return True


def get_cache_dir(repo: str, pr: int, head_sha: str) -> Path:
    """Return the content-addressed cache directory for this (repo, pr, sha)."""
    safe_repo = repo.replace("/", "__")
    override = os.environ.get("PR_REVIEW_CACHE_DIR")
    if override:
        cache_root = Path(override)
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        cache_root = Path(xdg) if xdg else Path.home() / ".cache"
    return cache_root / "pr-review-inline" / safe_repo / str(pr) / head_sha


class FileLock:
    """Cross-process exclusive lock backed by flock(2).

    Used to coordinate concurrent invocations of this script for the same
    PR: only the process holding the lock is allowed to populate the cache,
    so duplicate agents never race to issue the same GitHub API calls.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fd: Optional[Any] = None
        self._locked = False

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self.path, "w")
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX)
            self._locked = True
        except OSError as exc:
            self._fd.close()
            self._fd = None
            raise SystemExit(f"failed to acquire lock {self.path}: {exc}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is None:
            return
        try:
            if self._locked:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            self._fd.close()
            self._fd = None
            self._locked = False


def fetch_bulk(repo: str, pr: int) -> dict[str, Any]:
    return {
        "files.json": run_json_command(
            ["gh", "api", f"repos/{repo}/pulls/{pr}/files", "--paginate"]
        ),
        "comments.json": run_json_command(
            ["gh", "api", f"repos/{repo}/pulls/{pr}/comments", "--paginate"]
        ),
        "reviews.json": run_json_command(
            ["gh", "api", f"repos/{repo}/pulls/{pr}/reviews", "--paginate"]
        ),
    }


def populate_cache(
    cache_dir: Path, pr_payload: Any, repo: str, pr: int
) -> dict[str, Any]:
    """Write pr.json + the three bulk files to cache_dir atomically."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(cache_dir / "pr.json", pr_payload)
    bulk = fetch_bulk(repo, pr)
    for name, payload in bulk.items():
        atomic_write_json(cache_dir / name, payload)
    return bulk


def link_or_copy(src: Path, dst: Path) -> None:
    """Symlink `dst` to `src` if possible, falling back to a copy.

    If dst already exists as a symlink pointing at src, this is a no-op
    so the script can re-run cheaply when nothing has changed.
    """
    if dst.is_symlink():
        try:
            if dst.resolve() == src.resolve():
                return
        except OSError:
            pass
    if dst.is_symlink() or dst.exists():
        try:
            dst.unlink()
        except OSError:
            pass
    try:
        dst.symlink_to(src.resolve())
    except OSError:
        shutil.copy2(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch GitHub PR metadata, changed files, comments, and reviews. "
            "Uses a content-addressed cache + file lock so concurrent "
            "invocations for the same PR share GitHub API calls."
        ),
    )
    parser.add_argument(
        "--repo", required=True, help="OWNER/REPO, e.g. octocat/hello-world"
    )
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for pr.json, files.json, comments.json, reviews.json",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip the content-addressed cache and always refetch from GitHub.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Always fetch PR metadata. Cheap, and gives us the current
    # head SHA which keys the cache. Reading pr.json from a previous run
    # would risk returning a stale SHA if the PR was force-pushed, so we
    # intentionally skip the read-first optimization for pr.json.
    pr = run_json_command(
        [
            "gh",
            "pr",
            "view",
            str(args.pr),
            "--repo",
            args.repo,
            "--json",
            PR_VIEW_FIELDS,
        ]
    )
    head_sha = pr.get("headRefOid") or ""

    bulk: dict[str, Any] = {}
    cache_state = "disabled"
    cache_dir: Optional[Path] = None

    if args.no_cache or not head_sha:
        # No cache: write directly to out_dir (original behavior, with atomic writes).
        atomic_write_json(out_dir / "pr.json", pr)
        bulk = fetch_bulk(args.repo, args.pr)
        for name, payload in bulk.items():
            atomic_write_json(out_dir / name, payload)
    else:
        cache_dir = get_cache_dir(args.repo, args.pr, head_sha)
        lock_path = cache_dir.parent / f".fetch-{args.pr}.lock"

        try:
            with FileLock(lock_path):
                # Re-check inside the lock: another process may have just
                # populated the cache while we were waiting for the lock.
                if is_cache_complete(cache_dir):
                    cache_state = "hit"
                    for name in BULK_FILES:
                        payload = read_json_if_valid(cache_dir / name)
                        if payload is None:
                            # Corrupt cache entry: refetch everything.
                            cache_state = "miss"
                            bulk = populate_cache(cache_dir, pr, args.repo, args.pr)
                            break
                        bulk[name] = payload
                else:
                    cache_state = "miss"
                    bulk = populate_cache(cache_dir, pr, args.repo, args.pr)
        except OSError as exc:
            sys.stderr.write(
                f"warning: cache unavailable ({exc}); "
                "falling back to direct fetch.\n"
            )
            cache_state = "unavailable"
            atomic_write_json(out_dir / "pr.json", pr)
            bulk = fetch_bulk(args.repo, args.pr)
            for name, payload in bulk.items():
                atomic_write_json(out_dir / name, payload)

        if cache_state in ("hit", "miss") and cache_dir is not None:
            # Mirror cache contents to out_dir via symlink (or copy on failure).
            # Multiple agents using different --out-dir paths will all point at
            # the same cached files, so the data is never duplicated on disk.
            for name in ALL_FILES:
                link_or_copy(cache_dir / name, out_dir / name)

    summary = {
        "repo": args.repo,
        "pr": args.pr,
        "title": pr.get("title"),
        "head_sha": pr.get("headRefOid"),
        "base_ref": pr.get("baseRefName"),
        "head_ref": pr.get("headRefName"),
        "changed_files": len(bulk.get("files.json", [])),
        "existing_inline_comments": len(bulk.get("comments.json", [])),
        "existing_reviews": len(bulk.get("reviews.json", [])),
        "output_dir": str(out_dir),
        "cache": cache_state,
    }
    if cache_dir is not None and cache_state != "disabled":
        summary["cache_dir"] = str(cache_dir)
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
