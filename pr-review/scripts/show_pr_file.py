#!/usr/bin/env python3

import argparse
import base64
import binascii
import subprocess
import sys
from urllib.parse import quote


def fetch_file(repo: str, ref: str, path: str) -> str:
    endpoint = f"repos/{repo}/contents/{quote(path)}?ref={quote(ref)}"
    try:
        result = subprocess.run(
            ["gh", "api", endpoint, "--jq", ".content"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        sys.stderr.write(
            "Error: GitHub CLI 'gh' was not found. "
            "Please install GitHub CLI, ensure it is on your PATH, "
            "and authenticate with 'gh auth login'.\n"
        )
        raise SystemExit(1) from exc
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)

    content = result.stdout.strip()
    if not content or content == "null":
        sys.stderr.write(
            f"error: could not fetch content for '{path}' at ref '{ref}'.\n"
            "The path may be a directory, missing, or the file may be too large "
            "(>1MB). For large files, try:\n"
            f"  gh api repos/{repo}/git/blobs/<sha> --jq .content | base64 -d\n"
        )
        raise SystemExit(1)

    try:
        decoded_bytes = base64.b64decode(content)
    except binascii.Error:
        sys.stderr.write(
            f"error: file '{path}' at ref '{ref}' returned invalid base64 content.\n"
            "The path may be a directory or the API response was unexpected.\n"
        )
        raise SystemExit(1)

    try:
        return decoded_bytes.decode("utf-8")
    except UnicodeDecodeError:
        sys.stderr.write(
            f"error: file '{path}' at ref '{ref}' in repo '{repo}' "
            "is not valid UTF-8 (possibly binary or differently encoded).\n"
        )
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show a PR-head file at an exact ref with optional line numbers.",
    )
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--ref", required=True, help="Commit SHA or ref name")
    parser.add_argument("--path", required=True, help="Repository-relative file path")
    parser.add_argument(
        "--start", type=int, default=1, help="Start line number (1-based)"
    )
    parser.add_argument("--end", type=int, help="End line number (inclusive)")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw content without line numbers",
    )
    args = parser.parse_args()

    content = fetch_file(args.repo, args.ref, args.path)
    if args.raw:
        sys.stdout.write(content)
        return

    lines = content.splitlines()
    start = max(args.start, 1)
    end = args.end if args.end is not None else len(lines)
    end = min(end, len(lines))
    width = len(str(end))

    for idx in range(start, end + 1):
        line = lines[idx - 1]
        sys.stdout.write(f"{idx:>{width}}  {line}\n")


if __name__ == "__main__":
    main()
