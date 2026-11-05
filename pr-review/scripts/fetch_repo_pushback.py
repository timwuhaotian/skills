#!/usr/bin/env python3
"""List recent pr-review findings in a repo that were rebutted or retracted.

These are the repo's "don't repeat this" precedents. A finding posted by the
pr-review skill (its first line carries `**Severity: ...**`) counts as
pushed back when any reply in its thread says it does not hold: "pushing
back", "not applicable", "retracting", "false positive", "by design",
"already handled", and similar. Replies that open by accepting the finding
("Verified: valid", "Fixed in", "Addressed in") are ignored.

Output: a JSON array on stdout, newest first. Each item has pr, url, path,
category, severity, claim (the finding's first sentence), and rebuttal (the
rebutting reply, trimmed). Progress goes to stderr.

Cached per repo for --ttl-hours (default 24) under
`~/.cache/pr-review-inline/<owner>__<repo>/_pushback.json`, or under
`$PR_REVIEW_CACHE_DIR` / `$XDG_CACHE_HOME` if set. The file is replaced
atomically, so concurrent readers never see a partial write. This script only
reads from GitHub; it never writes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

QUERY = """
query($o:String!,$r:String!,$n:Int!,$after:String){
  repository(owner:$o,name:$r){
    pullRequests(first:$n, after:$after, orderBy:{field:UPDATED_AT,direction:DESC}){
      pageInfo{hasNextPage endCursor}
      nodes{
        number url
        reviewThreads(first:100){
          nodes{
            path
            comments(first:20){nodes{body url createdAt}}
          }
        }
      }
    }
  }
}
"""

PUSHBACK = re.compile(
    r"pushing back|push back|not applicable|retract|false positive|"
    r"not a (real )?(bug|issue|regression|problem)|does not apply|doesn't apply|"
    r"by design|intentional(ly)?\b|won'?t fix|not valid|invalid finding|"
    r"already (handled|covered|exists|guarded)\b",
    re.I,
)
ACCEPT_PREFIX = re.compile(
    r"^\W*(verified:\s*(valid|partly)|valid\b|partly\b|confirmed\b|agreed?\b|good catch|"
    r"you('| a)re right|right\b|fixed\b|addressed\b|added\b|applied\b|done\b|both (added|fixed)|"
    r"still open|same (as|finding)|duplicate|stale\b|already fixed)",
    re.I,
)
OPENING = 240  # judge a reply by how it opens; later text often quotes the finding
SEVERITY = re.compile(r"\*\*Severity:\s*(\w+)")
CATEGORY = re.compile(r"^\W*\*\*([\w -]+)\*\*")


def cache_root() -> Path:
    if os.environ.get("PR_REVIEW_CACHE_DIR"):
        return Path(os.environ["PR_REVIEW_CACHE_DIR"])
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "pr-review-inline"


def gh_graphql(owner: str, repo: str, n: int, after: str | None) -> dict[str, Any]:
    args = ["gh", "api", "graphql", "-f", f"query={QUERY}",
            "-F", f"o={owner}", "-F", f"r={repo}", "-F", f"n={n}"]
    if after:
        args += ["-f", f"after={after}"]
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(f"gh api graphql failed: {res.stderr.strip()}\n")
        raise SystemExit(1)
    return json.loads(res.stdout)["data"]["repository"]["pullRequests"]


def claim_of(body: str) -> str:
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    text = next((l for l in lines[1:] if not l.startswith("**🛠️")), "")
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    return (m.group(1) if m else text)[:300]


def collect(owner: str, repo: str, max_prs: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    after, seen = None, 0
    while seen < max_prs:
        page = gh_graphql(owner, repo, min(10, max_prs - seen), after)
        for pr in page["nodes"]:
            seen += 1
            for t in pr["reviewThreads"]["nodes"]:
                cs = t["comments"]["nodes"]
                if not cs or not SEVERITY.search(cs[0]["body"]):
                    continue
                rebut = next((c for c in cs[1:]
                              if PUSHBACK.search(c["body"][:OPENING]) and not ACCEPT_PREFIX.match(c["body"])), None)
                if not rebut:
                    continue
                root = cs[0]["body"]
                cat = CATEGORY.match(root)
                out.append({
                    "pr": pr["number"],
                    "url": cs[0]["url"],
                    "path": t["path"],
                    "category": cat.group(1).strip() if cat else None,
                    "severity": SEVERITY.search(root).group(1),
                    "claim": claim_of(root),
                    "rebuttal": " ".join(rebut["body"].split())[:400],
                    "posted_at": cs[0]["createdAt"],
                })
        sys.stderr.write(f"scanned {seen} PRs, {len(out)} pushed-back findings so far\n")
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    out.sort(key=lambda x: x["posted_at"], reverse=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True, help="OWNER/REPO")
    ap.add_argument("--max-prs", type=int, default=100, help="most recently updated PRs to scan (default 100)")
    ap.add_argument("--exclude-pr", type=int, help="drop this PR's own threads (step 4 handles those)")
    ap.add_argument("--ttl-hours", type=float, default=24)
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    owner, repo = a.repo.split("/", 1)

    cache = cache_root() / f"{owner}__{repo}" / "_pushback.json"
    data = None
    if not a.no_cache and cache.exists() and time.time() - cache.stat().st_mtime < a.ttl_hours * 3600:
        try:
            cached = json.loads(cache.read_text())
            if cached.get("max_prs", 0) >= a.max_prs:
                data = cached["items"]
                sys.stderr.write(f"cache hit: {cache}\n")
        except (ValueError, KeyError):
            data = None
    if data is None:
        data = collect(owner, repo, a.max_prs)
        cache.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=cache.parent, prefix="._pushback.")
        with os.fdopen(fd, "w") as f:
            json.dump({"max_prs": a.max_prs, "items": data}, f)
        os.replace(tmp, cache)

    if a.exclude_pr:
        data = [d for d in data if d["pr"] != a.exclude_pr]
    json.dump(data, sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
