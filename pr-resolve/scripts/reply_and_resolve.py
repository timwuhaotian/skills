#!/usr/bin/env python3
"""
Reply to one inline review thread, then resolve it — in that order.

Replying uses the REST reply endpoint (needs the thread ROOT comment's
databaseId). Resolving uses the GraphQL resolveReviewThread mutation (needs the
thread NODE id). Both ids come from fetch_open_threads.py.

Usage:
  python3 reply_and_resolve.py --repo octocat/hello-world --pr 1234 \
      --comment-id 123456789 --thread-id PRRT_kwDO... --body "Fixed in abc1234."

  python3 reply_and_resolve.py --repo octocat/hello-world --pr 1234 \
      --comment-id 123456789 --thread-id PRRT_kwDO... --body-file /tmp/reply.md

  # Reply only, leave the thread open (use when the author must decide):
  python3 reply_and_resolve.py ... --no-resolve
"""

import argparse
import json
import subprocess
import sys

MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""


def gh(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Reply to a PR review thread, then resolve it.")
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--pr", required=True, type=int,
                        help="Pull request number the thread belongs to")
    parser.add_argument("--comment-id", required=True, type=int,
                        help="databaseId of the thread's ROOT comment")
    parser.add_argument("--thread-id", help="GraphQL node id of the thread (required unless --no-resolve)")
    parser.add_argument("--body", help="Reply text")
    parser.add_argument("--body-file", help="File containing the reply text")
    parser.add_argument("--no-resolve", action="store_true", help="Reply only, do not resolve")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen and exit")
    args = parser.parse_args()

    if bool(args.body) == bool(args.body_file):
        parser.error("provide exactly one of --body or --body-file")
    if not args.no_resolve and not args.thread_id:
        parser.error("--thread-id is required unless --no-resolve is set")

    body = args.body if args.body else open(args.body_file, encoding="utf-8").read()
    body = body.strip()
    if not body:
        parser.error("reply body is empty")

    if args.dry_run:
        sys.stdout.write(json.dumps({
            "would_reply_to": args.comment_id,
            "would_resolve": None if args.no_resolve else args.thread_id,
            "body": body,
        }, indent=2) + "\n")
        return

    reply = json.loads(gh([
        "gh", "api",
        f"repos/{args.repo}/pulls/{args.pr}/comments/{args.comment_id}/replies",
        "-X", "POST",
        "-f", f"body={body}",
    ]))

    result = {"replied": True, "reply_url": reply.get("html_url"), "resolved": False}

    if not args.no_resolve:
        payload = json.loads(gh([
            "gh", "api", "graphql",
            "-f", f"query={MUTATION}",
            "-F", f"threadId={args.thread_id}",
        ]))
        if "errors" in payload:
            sys.stderr.write(json.dumps(payload["errors"], indent=2) + "\n")
            raise SystemExit(1)
        result["resolved"] = payload["data"]["resolveReviewThread"]["thread"]["isResolved"]

    sys.stdout.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
