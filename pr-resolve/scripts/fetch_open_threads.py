#!/usr/bin/env python3
"""
Dump everything a subagent needs to resolve one PR's outstanding feedback.

Writes to --out-dir:
  threads.json        unresolved review threads, full comment chains + diff hunks
  reviews.json        every submitted review (state, body, author)
  issue_comments.json top-level PR comments
  pr.json             PR metadata (branch, head sha, fork status)

Prints a JSON summary to stdout.

Usage:
  python3 fetch_open_threads.py --repo octocat/hello-world --pr 123 --out-dir /tmp/pr-123-resolve
  python3 fetch_open_threads.py --repo octocat/hello-world --pr 123 --out-dir /tmp/x --all-threads
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      title
      body
      url
      isDraft
      headRefName
      baseRefName
      headRefOid
      isCrossRepository
      maintainerCanModify
      reviewDecision
      author { login }
      headRepository { nameWithOwner }
      reviewThreads(first: 100) {
        totalCount
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          startLine
          diffSide
          comments(first: 50) {
            nodes {
              databaseId
              url
              createdAt
              body
              diffHunk
              path
              line
              originalLine
              author { login }
            }
          }
        }
      }
      reviews(last: 50) {
        totalCount
        nodes { state submittedAt body url author { login } }
      }
      comments(last: 100) {
        totalCount
        nodes { createdAt body url author { login } }
      }
    }
  }
}
"""


def gh_json(args: list[str]) -> dict:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return json.loads(result.stdout)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch unresolved PR review threads and feedback.")
    parser.add_argument("--repo", required=True, help="OWNER/REPO, e.g. octocat/hello-world")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    parser.add_argument("--all-threads", action="store_true",
                        help="Include resolved threads too (default: unresolved only)")
    args = parser.parse_args()

    owner, name = args.repo.split("/", 1)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = gh_json([
        "gh", "api", "graphql",
        "-f", f"query={QUERY}",
        "-F", f"owner={owner}",
        "-F", f"repo={name}",
        "-F", f"number={args.pr}",
    ])
    if "errors" in payload:
        sys.stderr.write(json.dumps(payload["errors"], indent=2) + "\n")
        raise SystemExit(1)

    pr = payload["data"]["repository"]["pullRequest"]

    # `reviews(last: 50)` fetches the 50 NEWEST reviews — the ones that decide
    # whether feedback is outstanding. Warn when the cap truncates.
    if pr["reviews"].get("totalCount", 0) > 50:
        sys.stderr.write(
            f"WARNING: PR #{args.pr} has {pr['reviews']['totalCount']} reviews — "
            "only the 50 newest were fetched; older reviews are ignored.\n"
        )

    # `reviewThreads(first: 100)` fetches the 100 oldest threads. Surface
    # truncation so unresolved threads beyond the cap are not missed silently.
    if pr["reviewThreads"].get("totalCount", 0) > 100:
        sys.stderr.write(
            f"WARNING: PR #{args.pr} has {pr['reviewThreads']['totalCount']} review threads — "
            "only the first 100 were fetched; unresolved threads beyond the cap "
            "are not included.\n"
        )

    # `comments(last: 100)` fetches the 100 NEWEST top-level comments — the
    # current feedback, not the opening chatter. Warn when the cap truncates.
    if pr["comments"].get("totalCount", 0) > 100:
        sys.stderr.write(
            f"WARNING: PR #{args.pr} has {pr['comments']['totalCount']} top-level comments — "
            "only the 100 newest were fetched; older comments are ignored.\n"
        )

    threads = []
    for t in pr["reviewThreads"]["nodes"]:
        if t["isResolved"] and not args.all_threads:
            continue
        comments = t["comments"]["nodes"]
        root = comments[0] if comments else {}
        threads.append({
            "thread_id": t["id"],
            "is_resolved": t["isResolved"],
            "is_outdated": t["isOutdated"],
            "path": t.get("path"),
            "line": t.get("line"),
            "start_line": t.get("startLine"),
            "diff_side": t.get("diffSide"),
            "root_comment_id": root.get("databaseId"),
            "diff_hunk": root.get("diffHunk"),
            "comments": [
                {
                    "id": c.get("databaseId"),
                    "author": (c.get("author") or {}).get("login", "unknown"),
                    "created_at": c.get("createdAt"),
                    "url": c.get("url"),
                    "body": c.get("body"),
                }
                for c in comments
            ],
        })

    reviews = [
        {
            "author": (r.get("author") or {}).get("login", "unknown"),
            "state": r.get("state"),
            "submitted_at": r.get("submittedAt"),
            "url": r.get("url"),
            "body": r.get("body"),
        }
        for r in pr["reviews"]["nodes"]
    ]
    issue_comments = [
        {
            "author": (c.get("author") or {}).get("login", "unknown"),
            "created_at": c.get("createdAt"),
            "url": c.get("url"),
            "body": c.get("body"),
        }
        for c in pr["comments"]["nodes"]
    ]

    meta = {
        "repo": args.repo,
        "number": pr["number"],
        "title": pr["title"],
        "body": pr.get("body"),
        "url": pr["url"],
        "author": (pr.get("author") or {}).get("login", "unknown"),
        "is_draft": pr["isDraft"],
        "head_ref": pr["headRefName"],
        "base_ref": pr["baseRefName"],
        "head_sha": pr["headRefOid"],
        "is_fork": pr["isCrossRepository"],
        "maintainer_can_modify": pr["maintainerCanModify"],
        "head_repo": (pr.get("headRepository") or {}).get("nameWithOwner"),
        "review_decision": pr.get("reviewDecision"),
    }

    write_json(out_dir / "pr.json", meta)
    write_json(out_dir / "threads.json", threads)
    write_json(out_dir / "reviews.json", reviews)
    write_json(out_dir / "issue_comments.json", issue_comments)

    changes_requested = [r for r in reviews if r["state"] == "CHANGES_REQUESTED"]
    sys.stdout.write(json.dumps({
        "repo": args.repo,
        "pr": args.pr,
        "title": meta["title"],
        "head_ref": meta["head_ref"],
        "head_sha": meta["head_sha"],
        "is_fork": meta["is_fork"],
        "open_threads": len(threads),
        "reviews": len(reviews),
        "changes_requested_reviews": len(changes_requested),
        "issue_comments": len(issue_comments),
        "output_dir": str(out_dir),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
