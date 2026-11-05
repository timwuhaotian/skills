#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def load_comments(comments_path: Path) -> list[dict]:
    try:
        raw = comments_path.read_text()
    except FileNotFoundError:
        raise SystemExit(f"comments file not found: {comments_path}")
    except OSError as exc:
        raise SystemExit(
            f"failed to read comments file {comments_path}: {exc}"
        ) from exc
    try:
        comments = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"failed to parse comments JSON file {comments_path}: {exc}"
        ) from exc
    if not isinstance(comments, list):
        raise SystemExit("comments file must contain a JSON array")

    validated: list[dict] = []
    for idx, comment in enumerate(comments):
        if not isinstance(comment, dict):
            raise SystemExit(f"comment {idx} must be a JSON object")
        for key in ("path", "line", "body"):
            if key not in comment:
                raise SystemExit(f"comment {idx} is missing required key: {key}")

        path = comment["path"]
        body = comment["body"]
        line = comment["line"]
        side = comment.get("side", "RIGHT")

        if not isinstance(path, str):
            raise SystemExit(
                f"comment {idx} field 'path' must be a string (got {type(path).__name__})"
            )

        if not isinstance(body, str):
            raise SystemExit(
                f"comment {idx} field 'body' must be a string (got {type(body).__name__})"
            )

        if isinstance(line, int):
            line_int = line
        elif isinstance(line, str):
            if line.isdigit():
                line_int = int(line)
            else:
                raise SystemExit(
                    f"comment {idx} field 'line' must be an integer or numeric string "
                    f"(got non-numeric string: {line!r})"
                )
        else:
            raise SystemExit(
                f"comment {idx} field 'line' must be an integer or numeric string "
                f"(got {type(line).__name__})"
            )

        if line_int <= 0:
            raise SystemExit(
                f"comment {idx} field 'line' must be a positive integer (got {line_int})"
            )

        if not isinstance(side, str):
            raise SystemExit(
                f"comment {idx} field 'side' must be a string (got {type(side).__name__})"
            )

        side_normalized = side.upper()
        if side_normalized not in {"LEFT", "RIGHT"}:
            raise SystemExit(
                f"comment {idx} field 'side' must be 'LEFT' or 'RIGHT' (got {side!r})"
            )

        # NOTE: `category`, `severity`, and `confidence` labels are embedded in
        # the comment `body` text (see the Comment Format spec in
        # pr-review/SKILL.md), not separate JSON keys. `entry` carries
        # only the GitHub review-comment envelope fields here; any other keys
        # in the source dict are dropped, since GitHub's review-comment
        # endpoint rejects unknown fields with HTTP 422.
        entry: dict = {
            "path": path,
            "line": line_int,
            "side": side_normalized,
            "body": body,
        }

        start_line = comment.get("start_line")
        if start_line is not None:
            if isinstance(start_line, str) and start_line.isdigit():
                start_line = int(start_line)
            if not isinstance(start_line, int) or start_line <= 0:
                raise SystemExit(
                    f"comment {idx} field 'start_line' must be a positive integer"
                )
            if start_line >= line_int:
                raise SystemExit(
                    f"comment {idx} field 'start_line' ({start_line}) must be "
                    f"less than 'line' ({line_int})"
                )
            entry["start_line"] = start_line
            start_side = comment.get("start_side", side_normalized)
            if not isinstance(start_side, str) or start_side.upper() not in {
                "LEFT",
                "RIGHT",
            }:
                raise SystemExit(
                    f"comment {idx} field 'start_side' must be 'LEFT' or 'RIGHT'"
                )
            entry["start_side"] = start_side.upper()

        validated.append(entry)
    return validated


def load_body(body: str | None, body_file: str | None) -> str:
    if body is not None and body_file is not None:
        raise SystemExit("use either --body or --body-file, not both")

    if body_file is None:
        return body or "PR review from pr-review."

    body_path = Path(body_file)
    try:
        return body_path.read_text()
    except FileNotFoundError:
        raise SystemExit(f"body file not found: {body_path}")
    except OSError as exc:
        raise SystemExit(f"failed to read body file {body_path}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit a GitHub pull request review with optional inline comments.",
    )
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument("--commit", required=True, help="PR head commit SHA")
    parser.add_argument(
        "--event",
        default="COMMENT",
        choices=("COMMENT", "APPROVE", "REQUEST_CHANGES"),
        help="GitHub review event to submit",
    )
    parser.add_argument(
        "--body",
        help="Review summary body. Use --body-file for multi-line Markdown.",
    )
    parser.add_argument(
        "--body-file",
        help="Path to a Markdown file to use as the review summary body",
    )
    parser.add_argument(
        "--comments-file",
        help="Path to JSON array of inline review comments",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payload instead of posting the review",
    )
    args = parser.parse_args()

    comments = load_comments(Path(args.comments_file)) if args.comments_file else []
    body = load_body(args.body, args.body_file)

    if args.event == "APPROVE" and comments:
        raise SystemExit("APPROVE reviews cannot include inline comments")

    if args.event in {"COMMENT", "REQUEST_CHANGES"} and not body.strip():
        raise SystemExit(f"{args.event} reviews require a non-empty body")

    payload = {
        "commit_id": args.commit,
        "event": args.event,
        "body": body,
    }
    if comments:
        payload["comments"] = comments

    if args.dry_run:
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return

    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{args.repo}/pulls/{args.pr}/reviews",
                "--input",
                "-",
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        sys.stderr.write(
            "error: GitHub CLI 'gh' is not installed or not found on PATH.\n"
            "Please install the GitHub CLI and ensure it is available on PATH,\n"
            "then authenticate with 'gh auth login'.\n"
        )
        raise SystemExit(1) from exc
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(
            "error: GitHub API returned non-JSON response.\n"
            f"Raw response:\n{result.stdout}\n"
        )
        raise SystemExit(1)
    if "html_url" in response:
        sys.stdout.write(response["html_url"] + "\n")
    else:
        sys.stdout.write(json.dumps(response, indent=2) + "\n")


if __name__ == "__main__":
    main()
