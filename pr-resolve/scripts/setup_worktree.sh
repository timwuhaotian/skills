#!/usr/bin/env bash
# Create an isolated, collision-safe worktree for one PR.
#
# Prints the worktree path on stdout. Diagnostics go to stderr.
#
#   usage: setup_worktree.sh <repo_path> <pr_number> <head_ref> [head_repo]
#
# <head_repo> is the PR head repository as <owner>/<name>. Pass it for fork PRs;
# omit it (or pass the base repo) for same-repo PRs.
#
# Guarantees:
#   * Never reuses, overwrites, or --force-removes an existing directory or an
#     already-registered worktree. Another agent, another skill run, or the
#     user's own session may be inside it.
#   * Never runs `git worktree prune` (that races other agents mid-add). A
#     stale-but-registered path is simply stepped over.
#   * Checks out DETACHED, so the branch stays free for any other worktree and no
#     local branch name is claimed. Same-repo PRs detach at origin/<head_ref>;
#     fork PRs detach at refs/pull/<pr_number>/head, which the base repo always
#     serves even though origin/<head_ref> does not exist there.
#   * Retries on .git lock contention from concurrent agents.
#
# Also prints, on stderr, the push destination for this worktree:
#
#   push-target: <remote-or-url> <head_ref>
#
# For a fork PR that is an explicit https URL for the head repository, because
# `git push origin HEAD:<head_ref>` would create a stray branch on the BASE repo
# instead of updating the PR. Pushing by URL also avoids `git remote add`, which
# writes .git/config and is shared by every worktree in the clone.

set -euo pipefail

if [ $# -lt 3 ] || [ $# -gt 4 ]; then
  echo "usage: setup_worktree.sh <repo_path> <pr_number> <head_ref> [head_repo]" >&2
  exit 2
fi

REPO_PATH=$(cd "$1" && pwd)
PR_NUMBER=$2
HEAD_REF=$3
HEAD_REPO=${4:-}

REPO_NAME=$(basename "$REPO_PATH")
PARENT=$(dirname "$REPO_PATH")

git_retry() {
  # Retry a git command a few times when a concurrent agent holds a ref lock.
  local attempt=1
  until git -C "$REPO_PATH" "$@"; do
    if [ "$attempt" -ge 3 ]; then
      return 1
    fi
    echo "  git $1 failed (attempt $attempt) — retrying after lock contention" >&2
    sleep $((attempt * 3))
    attempt=$((attempt + 1))
  done
  return 0
}

# --- Work out which local ref to detach at.
#
# Same-repo PR: origin/<head_ref>, pushed back to origin.
# Fork PR:      refs/pull/<pr>/head — the branch lives in the contributor's repo, so
#               origin/<head_ref> does not exist here. The base repo always serves the
#               PR head under refs/pull/*, and the push goes to the fork by URL.
BASE_REPO=$(git -C "$REPO_PATH" config --get remote.origin.url \
  | sed -E 's#^(https://[^/]+/|git@[^:]+:)##; s#\.git$##')

IS_FORK=0
if [ -n "$HEAD_REPO" ] && [ "$HEAD_REPO" != "$BASE_REPO" ]; then
  IS_FORK=1
fi

# --- Make sure the remote tip exists locally (orchestrator normally pre-fetched).
if [ "$IS_FORK" -eq 0 ]; then
  if ! git -C "$REPO_PATH" rev-parse --verify --quiet "refs/remotes/origin/$HEAD_REF" >/dev/null; then
    echo "origin/$HEAD_REF not present — fetching just that ref" >&2
    git_retry fetch origin "$HEAD_REF" >&2 || true
  fi

  if git -C "$REPO_PATH" rev-parse --verify --quiet "refs/remotes/origin/$HEAD_REF" >/dev/null; then
    START_POINT="origin/$HEAD_REF"
    PUSH_TARGET="origin"
  else
    # No head_repo was passed but the branch is not on origin — almost certainly a
    # fork PR the caller did not flag. Fall back to refs/pull/* so we still get the
    # right tree, but refuse to guess a push destination.
    echo "origin/$HEAD_REF does not exist — falling back to refs/pull/$PR_NUMBER/head" >&2
    IS_FORK=1
  fi
fi

if [ "$IS_FORK" -eq 1 ]; then
  PULL_REF="refs/pr/$PR_NUMBER/head"
  git_retry fetch --force origin "refs/pull/$PR_NUMBER/head:$PULL_REF" >&2

  if ! git -C "$REPO_PATH" rev-parse --verify --quiet "$PULL_REF" >/dev/null; then
    echo "FATAL: neither origin/$HEAD_REF nor refs/pull/$PR_NUMBER/head could be fetched" >&2
    exit 1
  fi

  START_POINT="$PULL_REF"
  if [ -n "$HEAD_REPO" ]; then
    PUSH_TARGET="https://github.com/$HEAD_REPO.git"
  else
    PUSH_TARGET="UNKNOWN"
    echo "WARNING: fork PR with no <head_repo> argument — cannot determine a push destination." >&2
    echo "         Re-run with the 4th argument, or push by explicit fork URL yourself." >&2
    echo "         Do NOT 'git push origin HEAD:$HEAD_REF' — that creates a branch on $BASE_REPO." >&2
  fi
fi

# --- Pick a free path. Never touch an occupied one.
REGISTERED=$(git -C "$REPO_PATH" worktree list --porcelain | awk '/^worktree /{print substr($0, 10)}')

is_free() {
  local candidate=$1
  [ -e "$candidate" ] && return 1
  while IFS= read -r existing; do
    [ "$existing" = "$candidate" ] && return 1
  done <<< "$REGISTERED"
  return 0
}

BASE="$PARENT/$REPO_NAME-pr-$PR_NUMBER"
WT="$BASE"
suffix=2
while ! is_free "$WT"; do
  echo "  $WT is occupied (existing directory or registered worktree) — stepping over it" >&2
  WT="$BASE-r$suffix"
  suffix=$((suffix + 1))
  if [ "$suffix" -gt 12 ]; then
    echo "FATAL: no free worktree path near $BASE — clean up stale worktrees first" >&2
    exit 1
  fi
done

# --- Create it, detached.
if ! git_retry worktree add --detach "$WT" "$START_POINT" >&2; then
  echo "FATAL: git worktree add failed for $WT" >&2
  exit 1
fi

echo "worktree ready: $WT (detached at $START_POINT)" >&2
echo "push-target: $PUSH_TARGET $HEAD_REF" >&2
echo "$WT"
