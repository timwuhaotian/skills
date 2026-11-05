#!/usr/bin/env python3
"""Add/remove canonical PR labels, resolving them against the repo's real labels.

Never fatal for label problems: missing labels, permission errors, and rate
limits are reported in the JSON result and the script still exits 0.
See references/pr-labels.md for the vocabulary and rules.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import quote

CANONICAL_ALIASES: dict[str, list[str]] = {
    "do not merge": ["do not merge", "dnm", "hold", "status do not merge"],
    "help wanted": ["help wanted", "help needed", "needs help", "status help wanted"],
    "bug": ["bug", "defect", "type bug"],
    "security": ["security", "type security"],
    "enhancement": ["enhancement", "feature", "improvement", "type enhancement", "type feature"],
    "breaking change": ["breaking change", "breaking", "type breaking change"],
    "needs tests": ["needs tests", "needs test", "test gap", "missing tests"],
    "performance": ["performance", "perf", "type performance"],
}

CREATE_SPEC: dict[str, tuple[str, str]] = {
    "do not merge": ("B60205", "Merging as-is can cause immediate production harm"),
}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def gh(args: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["gh", *args], input=stdin, capture_output=True, text=True, check=False
    )
    return proc.returncode, proc.stdout, proc.stderr.strip()


def list_repo_labels(repo: str) -> dict[str, str] | None:
    rc, out, err = gh(
        ["api", "--paginate", f"repos/{repo}/labels?per_page=100", "--jq", ".[].name"]
    )
    if rc != 0:
        print(f"warning: could not list labels for {repo}: {err}", file=sys.stderr)
        return None
    return {norm(n): n for n in out.splitlines() if n.strip()}


def resolve(canonical: str, repo_labels: dict[str, str]) -> str | None:
    key = norm(canonical)
    aliases = CANONICAL_ALIASES.get(key, [key])
    for alias in aliases:
        hit = repo_labels.get(norm(alias))
        if hit:
            return hit
    return None


def canonicalize(name: str) -> str:
    key = norm(name)
    for canon, aliases in CANONICAL_ALIASES.items():
        if key == canon or key in (norm(a) for a in aliases):
            return canon
    return key


def current_pr_labels(repo: str, pr: int) -> set[str] | None:
    rc, out, err = gh(
        ["api", f"repos/{repo}/issues/{pr}", "--jq", "[.labels[].name]"]
    )
    if rc != 0:
        print(f"warning: could not read PR #{pr} labels: {err}", file=sys.stderr)
        return None
    return set(json.loads(out or "[]"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, help="OWNER/REPO")
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--add", action="append", default=[], metavar="LABEL")
    ap.add_argument("--remove", action="append", default=[], metavar="LABEL")
    ap.add_argument(
        "--create-missing",
        action="store_true",
        help="create a missing label — only honoured for 'do not merge'",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    result: dict[str, list] = {
        "applied": [], "removed": [], "already": [], "missing": [], "errors": [],
    }

    if not args.add and not args.remove:
        print(json.dumps(result))
        return 0

    repo_labels = list_repo_labels(args.repo)
    if repo_labels is None:
        result["errors"].append("could not list repo labels; nothing changed")
        print(json.dumps(result))
        return 0

    on_pr = current_pr_labels(args.repo, args.pr) or set()
    on_pr_norm = {norm(n): n for n in on_pr}

    for want in args.add:
        canon = canonicalize(want)
        real = resolve(canon, repo_labels)
        if real is None and args.create_missing and canon in CREATE_SPEC:
            color, desc = CREATE_SPEC[canon]
            if args.dry_run:
                result["applied"].append(f"{canon} (would create)")
                continue
            rc, _, err = gh(
                ["api", "-X", "POST", f"repos/{args.repo}/labels",
                 "-f", f"name={canon}", "-f", f"color={color}", "-f", f"description={desc}"]
            )
            if rc != 0:
                result["errors"].append(f"create {canon}: {err}")
                continue
            real = canon
        if real is None:
            result["missing"].append(want)
            continue
        if norm(real) in on_pr_norm:
            result["already"].append(real)
            continue
        if args.dry_run:
            result["applied"].append(f"{real} (dry-run)")
            continue
        rc, _, err = gh(
            ["api", "-X", "POST", f"repos/{args.repo}/issues/{args.pr}/labels",
             "-f", f"labels[]={real}"]
        )
        (result["applied"] if rc == 0 else result["errors"]).append(
            real if rc == 0 else f"add {real}: {err}"
        )

    for drop in args.remove:
        real = resolve(canonicalize(drop), repo_labels) or drop
        present = on_pr_norm.get(norm(real))
        if present is None:
            result["already"].append(f"{drop} (not on PR)")
            continue
        if args.dry_run:
            result["removed"].append(f"{present} (dry-run)")
            continue
        encoded = quote(present, safe="")
        rc, _, err = gh(
            ["api", "-X", "DELETE", f"repos/{args.repo}/issues/{args.pr}/labels/{encoded}"]
        )
        (result["removed"] if rc == 0 else result["errors"]).append(
            present if rc == 0 else f"remove {present}: {err}"
        )

    for msg in result["errors"]:
        print(f"warning: {msg}", file=sys.stderr)
    for name in result["missing"]:
        print(f"warning: repo has no label for '{name}' — skipped", file=sys.stderr)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
