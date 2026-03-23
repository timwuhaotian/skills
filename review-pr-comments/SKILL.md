---
name: review-pr-comments
description: Use when asked to address, triage, or respond to PR review comments (e.g. from Copilot, reviewers, bots). Covers checking which threads are unresolved, verifying each comment against actual code before acting, fixing only what is valid, replying per thread, and committing one fix per comment.
---

# Review PR Comments

Address unresolved PR review comments systematically: verify first, fix if valid, reply with evidence, commit per fix.

## When to Use

- "Address the Copilot comments on our PR"
- "Go through the review comments and fix what's needed"
- "Respond to reviewer feedback on PR #N"
- Anytime you need to triage open review threads before merging

## Workflow

```
1. Fetch all threads → filter unresolved only (GraphQL isResolved)
2. For each unresolved thread:
   a. Read the relevant code in the current branch
   b. Verify: is the comment still valid?
   c. If INVALID → reply explaining why, no code change
   d. If VALID   → fix code, commit (one commit per comment), reply with commit SHA
3. After all threads are done → ask user whether to push
```

## Step 1 – Fetch Unresolved Threads

Use the GitHub GraphQL API to get resolved status. The REST API does **not** expose `resolved`.

```bash
gh api graphql -f query='
{
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes { databaseId body }
          }
        }
      }
    }
  }
}' | python3 -c "
import json, sys
threads = json.load(sys.stdin)['data']['repository']['pullRequest']['reviewThreads']['nodes']
for t in threads:
    c = t['comments']['nodes'][0]
    if not t['isResolved']:
        print(f'id={c[\"databaseId\"]} body={c[\"body\"][:100]}')
"
```

To also get file/line context, fetch REST comments separately:

```bash
gh api "repos/OWNER/REPO/pulls/PR_NUMBER/comments?per_page=100"
```

## Step 2 – Verify Before Acting

**Read the actual current file** before deciding on a fix. Comments are written against an older diff — the code may have already been fixed.

| Finding                            | Action                                                  |
| ---------------------------------- | ------------------------------------------------------- |
| Comment is stale / already fixed   | Reply explaining what the current code does. No commit. |
| Comment points to a real issue     | Fix it, commit, reply with SHA.                         |
| Comment is a suggestion, not a bug | Use judgment; explain reasoning in reply either way.    |

**Never fix code just because a comment exists.** Verify root cause first (see `systematic-debugging` skill if needed).

## Step 3 – One Commit Per Fix

Keep fixes atomic so they're reviewable and revertable independently.

```bash
git add <file>
git commit -m "fix(scope): <what and why>\n\n<longer context if needed>"
```

Conventional commit prefix is recommended but follow the repo's existing style.

## Step 4 – Reply to Each Thread

Always reply to the original comment thread — don't just resolve it silently.

```bash
# Reply to a PR review comment thread
gh api repos/OWNER/REPO/pulls/comments/COMMENT_ID/replies \
  -X POST -f body="<your reply>"
```

**Reply templates:**

For a fix:

> Verified: valid. `<file>:<line>` was missing `<X>`. Fixed in commit `<SHA>` — `<one-sentence description of change>`.

For a non-issue:

> Verified: not applicable to current code. `<file>:<line>` already does `<X>` because `<brief explanation>`. No change needed.

## Step 5 – Ask Before Pushing

After all threads are addressed, **ask the user** whether to push the branch.

> All `N` unresolved threads have been addressed (M fixes, K non-issues). Push `<branch>` to remote?

Do not push automatically.

## Common Mistakes

| Mistake                                         | Correct approach                                       |
| ----------------------------------------------- | ------------------------------------------------------ |
| Fixing code without reading the file first      | Always read the current file; the diff may be outdated |
| Resolving threads without replying              | Always reply with evidence before resolving            |
| Bundling multiple comment fixes into one commit | One commit per comment for clean history               |
| Pushing to remote without asking                | Always confirm with user first                         |
| Using REST API to check resolved status         | Use GraphQL `reviewThreads.isResolved`                 |
| Replying to the wrong comment ID                | Confirm `in_reply_to_id` points to the thread root     |

## Quick Reference

```bash
# Check resolved status (GraphQL)
gh api graphql -f query='{ repository(owner:"O", name:"R") { pullRequest(number:N) { reviewThreads(first:100) { nodes { isResolved comments(first:1) { nodes { databaseId body } } } } } } }'

# Get comment details with file/line (REST)
gh api "repos/O/R/pulls/N/comments?per_page=100"

# Reply to a thread
gh api repos/O/R/pulls/comments/COMMENT_ID/replies -X POST -f body="MESSAGE"

# Commit a single-file fix
git add path/to/file && git commit -m "fix(scope): description"
```
