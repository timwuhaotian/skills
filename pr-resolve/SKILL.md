---
name: pr-resolve
description: Use when asked to address, triage, or respond to inline PR review comments from reviewers or bots, or to get a PR (or a stacked PR / PR stack) fixed and pushed. Covers checking which threads are unresolved, verifying each comment against current code before acting, fixing only what's valid, replying per thread, resolving the thread after replying, and syncing the PR title and body with the changes made this round so the description always reflects the branch's latest state. By default works in an isolated git worktree on the PR's branch, syncs with the target branch (default main) and resolves any conflicts, pushes changes, then removes the worktree when done. Detects stacked PRs (a PR whose base is another PR's branch, "rebase stack conflicts", "stack is behind"), syncs the whole stack bottom-up against each PR's own base, pushes every member, and fixes any check already failing on a head — reading the failed job log, patching the cause in the same worktree, re-running the local gates. After the push it updates the PR's labels to match the new state (`help wanted` for anything blocked, stale `bug` / `do not merge` removed once their finding is fixed). It never waits for or watches the CI run a push triggers (no polling shell, no watcher subagent) — once everything is pushed, the task is done. Merge readiness is never gated and nothing is ever merged. This applies even when a PR has no unresolved threads at all — a red check or a conflict on its own is a full run (sync, fix, push), not a skip. The local main checkout is never modified — it is only used to add and remove worktrees.
---

# Resolve Inline PR Comment

Address unresolved inline PR review comments systematically: isolate in a worktree on the PR branch, sync with the target branch and resolve any conflicts, verify first, fix if valid, reply with evidence, resolve, push, clean up the worktree, and stop. Fix checks that are already failing, but **never wait for the CI run your push triggers** — once everything is pushed, mark the task done. Never merge, and never gate on merge readiness: green CI is not permission to merge.

**Stacked PRs.** If the PR's base is another open PR's branch (or another PR targets this one), the unit of work is the whole stack, not the PR you were handed. Step 1 detects it; every later step then runs per member, root first. The full procedure, with the reasons behind each rule, is in `$HOME/.agents/skills/pr-resolve/references/stacked-prs.md` — read it whenever the stack has more than one member.

**Install scope:** these skills ship both user-scoped (here, `~/.agents/skills/`) and project-scoped in repos that vendor them (e.g. `<repo>/.agents/skills/`). Inside such a repo the project copy takes precedence automatically — prefer its repo-root-relative `.agents/skills/…` paths there. The `$HOME/.agents/skills/…` paths in this document are the fallback for repos without a vendored copy.

## The main checkout is a launcher, not a workspace

The clone the user is sitting in belongs to them. It is used for exactly two things: `git worktree add` and `git worktree remove`. It must come out of this run byte-identical — same branch, same HEAD, same working tree.

- **Never** in the main checkout: `git commit`, `git merge`, `git rebase`, `git pull`, `git checkout` / `git switch`, `git reset`, `git cherry-pick`, `git revert`, `git stash`, `git clean`, `git branch -m` / `-d`, or any file edit.
- **Only** in the main checkout: `git status`, `git log`, `git rev-parse`, `git worktree list`, `git remote get-url`, `git fetch` (updates remote-tracking refs only — it does not move HEAD or touch the working tree), and `gh` commands.
- If the main checkout is already dirty, that is the user's work: leave it exactly as it is. Never stash, clean, or reset it to "help".
- Every write command — commit, merge, rebase, push, branch rename — runs inside the worktree, with the worktree as the current directory (or `git -C <worktree>`).

## Output style — `ultracave`

If a `ultracave` skill exists (`~/.agents/skills/ultracave/SKILL.md`, `.claude/skills/ultracave/SKILL.md`, or a vendored `.agents/skills/ultracave/`), load it and apply its register to **chat output only** — progress notes, the pushed-per-member report, the final summary to the user. If it is absent, proceed normally without mentioning it.

Everything persisted stays in normal language: thread replies, commit messages, code, and docs. A terse reply that a reviewer cannot follow has defeated the resolve — terseness is for the conversation, not for the PR.

## When to Use

- "Address the Copilot comments on our PR"
- "Go through the review comments and fix what's needed"
- "Respond to reviewer feedback on PR #N"
- Anytime you need to triage open inline review threads before merging
- "Fix the CI errors as well" — the default run already does this: checks already failing on the head are diagnosed and fixed (Step 8b); the new run after the push is never waited on
- "Fix the CI on PR #N" / "PR #N has conflicts" with no review comments at all — still this skill: sync + resolve conflicts, diagnose the current head's failing checks, fix, push
- "This PR is stacked on #N" / "we have rebase stack conflicts with #N, fix both"

## Workflow

```text
 1. Fetch PR metadata -> head branch, base branch, owner, repo
    + detect the stack (pr_stack.py) -> ordered members, root first; scope = every member
    For EACH member, root first (a child starts only after its parent is pushed):
 2. Create a git worktree on the member's branch for isolation
 3. Sync the worktree with the member's OWN base (root: default branch; child: parent branch)
    and resolve any conflicts
 4. Fetch every outstanding feedback item -> unresolved threads (full comment chains),
    CHANGES_REQUESTED review bodies, unanswered top-level comments
 5. For each unresolved thread:
    a. Read the relevant code inside the worktree
    b. Verify: is the comment still valid?
    c. If INVALID -> reply explaining why, no code change, then resolve thread
    d. If VALID   -> fix code, commit (one commit per comment), reply with commit SHA, then resolve thread
 6. Verify, then push the member's branch
 6b. Fix checks already failing on the head (log -> fix -> local gates, same push).
    Do NOT wait for or watch the CI run the push triggers
 6c. Sync the PR title and body with this round's changes (Step 7b) — every member, every run, before its push
 7. Remove the member's worktree
 7b. Update the member's labels from what is still true (Step 8c) — after the push, never waiting on CI
    Then, for the whole stack:
 8. Report what was pushed (and any CI failure fixed or left blocked), per member,
    mark the task done, and STOP. No CI watching, no readiness gate, no merge.
```

## Step 1 - Fetch PR Metadata and Create Worktree

First, get the PR's head branch, target branch, owner, and repo so you can check out the right branch in an isolated worktree and sync it with the target.

```bash
gh pr view PR_NUMBER --json headRefName,baseRefName,headRepositoryOwner,headRepository,isCrossRepository,mergeable,mergeStateStatus
```

(`gh pr view` has no `baseRepository` field — asking for it fails the whole call.)

From the JSON, extract:

- `headRefName` - the branch name (e.g. `feature/foo`)
- `baseRefName` - the target branch to sync with (e.g. `main`, `develop`, or another PR's branch). If the PR metadata is unavailable or `baseRefName` is missing, assume `main`.
- The repo owner/name - the repo the PR lives in (from the URL you were given, or `gh repo view --json nameWithOwner`); `isCrossRepository: true` means a fork PR
- `headRepository.nameWithOwner` - the head repo as `<owner>/<name>`. Pass it to the worktree script; for a fork it is both where the branch lives and where the push must land.
- `mergeStateStatus` / `mergeable` - the merge blocker, if any. `BEHIND` with every check green is the usual cause of "CI errors" / "rebase conflicts" complaints on a stack: the branch is just out of date under a strict up-to-date rule. Check this before reading check colours.
- The **current head's CI state, before you change anything**: `gh pr checks PR_NUMBER --repo OWNER/REPO` (or the `statusCheckRollup` in the same snapshot). Note which checks are already failing on the untouched head — those failures are in scope from the start, not a surprise to discover after your push. If none are failing and there are no threads, the sync (Step 2) may still be the whole job.

### Detect a stack

```bash
SKILL_DIR="$HOME/.agents/skills/pr-resolve"
python3 "$SKILL_DIR/scripts/pr_stack.py" --repo OWNER/REPO --pr PR_NUMBER > /tmp/pr-PR_NUMBER-stack.json
```

stderr prints the stack root first, each member's merge state, `behind_by`, unresolved-thread count, readiness reasons, and a merge plan. If `is_stack` is false, carry on with this PR alone. If it is true:

- **Scope is every member** in `order`, including members with zero feedback — a quiet root that is behind its base blocks the whole stack.
- **Work members sequentially, root first.** Run Steps 1-9 for one member (its own worktree, its own sync, its own push, its own cleanup), then move up. A child's sync needs its parent's push.
- `orphan_base` set means the root targets a branch no open PR owns (its parent merged or closed): retarget it to the default branch first — `gh api -X PATCH repos/OWNER/REPO/pulls/<root> -f base=<default>` (REST; `gh pr edit` fails on repos with classic Projects).
- Read `references/stacked-prs.md` (path above) before syncing.

### Create the worktree

All code changes happen inside a worktree, never in the main checkout. Use the
collision-safe setup script vendored in this skill's `scripts/` directory — it checks
out detached at the PR head (so the branch stays free for other worktrees),
steps over occupied paths instead of clobbering them, handles fork PRs, and
retries on ref-lock contention from concurrent agents.

```bash
# From the repo root, get the clone path, and snapshot it — the main checkout
# must come out of this run byte-identical
REPO_PATH=$(git rev-parse --show-toplevel)
MAIN_HEAD=$(git -C "$REPO_PATH" rev-parse HEAD)
MAIN_BRANCH=$(git -C "$REPO_PATH" rev-parse --abbrev-ref HEAD)
MAIN_STATUS=$(git -C "$REPO_PATH" status --porcelain)

# Create the worktree — prints the path on stdout, diagnostics on stderr
SKILL_DIR="$HOME/.agents/skills/pr-resolve"
WT=$(bash "$SKILL_DIR/scripts/setup_worktree.sh" "$REPO_PATH" <PR_NUMBER> <branch-name> <head-repo>)

# cd into it — EVERY file read, edit, commit, and push from here on is inside $WT
cd "$WT"
```

The script guarantees:

- **Detached at the PR head.** A branch checked out in one worktree cannot be checked out in another — `git worktree add <branch>` fails when another agent or session holds it. Detached HEAD sidesteps that, and you push with an explicit refspec (`HEAD:<branch>`) at the end. Same-repo PRs detach at `origin/<branch>`; fork PRs detach at `refs/pull/<PR_NUMBER>/head`, since the branch lives in the contributor's repo and `origin/<branch>` does not exist locally.
- **Tells you where to push.** Its last stderr line is `push-target: <remote-or-url> <branch>` — `origin` for a same-repo PR, an `https://github.com/<head-repo>.git` URL for a fork. Use it verbatim in Step 8.
- **Never reuses or force-removes an occupied path.** The conventional path `<repo>-pr-<N>` may already hold a live worktree with someone's uncommitted work. The script steps over it to `<repo>-pr-<N>-r2` instead of touching it.
- **Never runs `git worktree prune`** (that races another agent mid-add) and retries on `.git` ref-lock contention.

**Important isolation rules while inside the worktree:**

- Never run bare `git stash` / `git stash pop` — the stash stack is shared across every worktree in the clone.
- Never write repo-level git config (`git config <key> <value>`) — it is shared by all worktrees. Use `git -c <key>=<value>` per command.
- Never run a write command in the main checkout — it is only a launcher for `git worktree add` / `git worktree remove`. If you are in `<main-repo-path>`, `cd "$WT"` before doing anything.

If the user explicitly says "don't use a worktree" or "work in place", skip this step and work in the current checkout. That waives the read-only rule above for this run. But the default is always worktree isolation.

## Step 2 - Sync with the Target Branch and Resolve Conflicts

Before verifying any comments, bring the worktree up to date with the target branch. Review comments sit on the PR's diff; code on the branch may have drifted from `main`/`develop` while the PR was open. Fixing conflicts first ensures every file you read is current, every fix lands cleanly on the real tree, and the final push stays fast-forwardable.

### 2a. Fetch the target branch

Fetch only the target ref — never a full `git fetch --all`, which contends on ref locks in a shared clone:

```bash
# TARGET is this PR's own baseRefName from Step 1 — main, develop, or (for a stacked child) the parent PR's branch.
TARGET=<baseRefName>

git fetch origin "$TARGET"
```

**Stacked child: the target is the parent branch, never the default branch.** The child's diff is computed against its parent; merging `main` into it makes the child show every `main` commit the parent has not absorbed yet. The child gets `main` only through its parent. And fetch the parent ref **after** the parent's push in this run — a ref fetched before that push is stale.

### 2b. Merge the target into the worktree

```bash
git merge origin/"$TARGET"
```

If it succeeds, the worktree is up to date — proceed to Step 3. A merge commit on the PR branch is normal and harmless; PRs commonly include sync merges. Do not squash or rewrite it.

If a merge commit is not desired (e.g. the repo's history is strictly linear), `git rebase origin/"$TARGET"` instead — then the push in Step 8 is a plain fast-forward. Pick one strategy and stay consistent within this run. **On a stack, always merge:** rebasing a pushed member needs a force-push and re-parents every child above it.

### 2c. Resolve conflicts

If the merge reports conflicts, resolve them file by file. For each conflicted path:

1. Read the file (conflict markers `<<<<<<<` / `=======` / `>>>>>>>` mark the two sides).
2. Decide what the combined result should be — consider what the PR changed, what the target changed, and what the review comments expect.
3. Edit the file to the correct final state and remove the markers.

Then prove the resolution is real before staging — a leftover marker or a tree the
merge broke is a CI failure you shipped:

```bash
git ls-files -u                       # must print nothing (no unmerged paths left)
grep -rn '<<<<<<<\|>>>>>>>' <resolved-files>   # must find no conflict markers
git diff --check                      # no whitespace/marker errors
```

Then stage and commit the resolution:

```bash
git add <resolved-files>
git commit -m "merge: resolve conflicts with origin/<target>"
```

The gates in Step 8 (lint / typecheck / unit tests) run on this merged tree before
any push — a conflict resolution that compiles on neither side's terms fails there,
not on CI.

Notes:

- **Never force-push** to work around a conflict — see Step 8.
- If a conflict is genuinely hard to resolve and needs a human decision, stop, report the PR as blocked with the conflicting files and paths, and leave the worktree in place. Do not guess.
- If the worktree ends up with no net changes (merge or rebase applied cleanly, no fixes were needed), there is nothing to push at the end.

## Step 3 - Fetch Every Outstanding Feedback Item

Review feedback lands on a PR in three shapes. All three are outstanding work, so triage all of them — not just inline threads.

| Shape                    | Where it lives                                    | How you close it                     |
| ------------------------ | ------------------------------------------------- | ------------------------------------ |
| Inline review thread     | `reviewThreads.isResolved == false`               | Reply in the thread, then resolve it |
| Review body, no inline   | `reviews[].state == CHANGES_REQUESTED`, body only | Reply on the review + summary comment |
| Top-level PR comment     | `comments[]` (issue comments, no thread)          | Reply to the comment                 |

Use the fetch script in this skill's `scripts/` directory — one call dumps all three, with file/line, `is_outdated`, and each thread's full comment chain:

```bash
SKILL_DIR="$HOME/.agents/skills/pr-resolve"
FEEDBACK_DIR=$(mktemp -d)
python3 "$SKILL_DIR/scripts/fetch_open_threads.py" \
  --repo OWNER/REPO --pr PR_NUMBER --out-dir "$FEEDBACK_DIR"
```

It writes `pr.json`, `threads.json`, `reviews.json`, and `issue_comments.json` into `$FEEDBACK_DIR`. Warnings on stderr mean a cap truncated the data (only the first 100 threads, 50 newest reviews, 100 newest comments) — surface those in the final report instead of reporting a clean sweep.

Work each thread from `threads.json`: `thread_id` (GraphQL node id — required to resolve), `root_comment_id` (databaseId — required to reply), `path`, `line`, `is_outdated`, `diff_hunk`, and the `comments` chain.

**Read the whole `comments` chain, not just the root.** A thread opening with "rename this" can carry a later reply of "actually fine as-is" — the root alone is not the thread. Same for a bot that posted a finding someone already dismissed in-thread.

**`is_outdated: true` is a hint, not a verdict** — confirm staleness from the file in the worktree.

### Non-threaded feedback

`reviews.json` and `issue_comments.json` have no thread to resolve. When either carries unanswered feedback — a `CHANGES_REQUESTED` review whose findings live only in the body, or a top-level comment asking for a change — verify each point against the code, fix what is valid, then post **one consolidated top-level comment**:

```bash
gh pr comment PR_NUMBER --repo OWNER/REPO --body "$(cat <<'EOF'
<what you addressed, with commit SHAs>
EOF
)"
```

Bot status comments (check runs, licence headers, coverage reports) carry no action item — ignore them unless they report a real failure.

## Step 4 - Verify Before Acting

Read the actual current file **inside the worktree** before deciding on a fix. Comments are written against an older diff, so the code may already be fixed.

Judge every comment with the shared rubric in `$HOME/.agents/skills/pr-review/references/finding-verification.md`. The `pr-review` skill uses the same file to decide what to post, so the finder and the fixer apply one standard.

1. **Refute first (§1).** Before writing code, try to disprove the comment through the three lenses — reachability, impact, defenses — each cited `file:line`. Test Gap and Improvement/Clean-up comments get their category check instead. Our own review's findings get the same treatment: this pass is the only independent check they get.
2. **Check precedents (§3).** A finding this PR or this repo already rebutted needs new evidence, not a second fix attempt.
3. **Give exactly one verdict (§4):** `needs-fix`, `already-fixed`, `stale`, `refuted`, `needs-decision`, or `suggestion`. The table there also gives each verdict's action and reply opening.

Common comment authors and how to treat them:

- `copilot[bot]`, `github-advanced-security[bot]` — automated findings; often valid, sometimes stale after refactors
- The PR author's own self-notes — annotations acknowledging findings; treat as resolved notes, not action items
- Other humans — code review feedback requiring an actual fix, still verified through the lenses before you change code
- **Non-blocking notes** in a `pr-review` body — the author's call; leave them unless the user asks

Never fix code just because a comment exists. Verify root cause first.

## Step 5 - One Commit Per Fix

Keep fixes atomic so they stay reviewable and revertable independently. Run these commands **inside the worktree**.

**Test coverage for behavior changes.** A fix that adds or changes behavior ships with tests in the same push:

- Fixing a 🧪 Test Gap comment or a `needs tests` label means adding the missing test(s) — unit for logic, e2e / Playwright for user-facing paths — not just replying. The label comes off only when the tests land (see Step 8c).
- Any other fix that changes runtime behavior (new branch, guard, default, payload shape) extends the suite the same way: a regression test that fails before the fix and passes after.
- Pure refutes / stale / already-fixed verdicts, conflict resolutions with no behavior delta, and comment-only replies need no new tests — say so in the reply.
- Write e2e / Playwright and DB-backed specs even though they are not run locally (Step 8) — CI runs them on the pushed head.

```bash
git add <file>
git commit -m "fix(scope): <what and why>

<longer context if needed>"
```

Conventional commit prefix is recommended, but follow the repo's existing style.

## Step 6 - Reply to Each Thread

Always reply to the original comment thread. Do not resolve it silently.

```bash
gh api repos/OWNER/REPO/pulls/PR_NUMBER/comments/COMMENT_ID/replies \
  -X POST -f body="<your reply>"
```

Open each reply with its verdict's opening from the table in `$HOME/.agents/skills/pr-review/references/finding-verification.md` §4. `Pushing back:` is only for a finding that is wrong, never for one the code has since moved past; later reviews read those openings as precedents.

Whether or not a comment flags it, the PR title and body must match this round's changes before the push — that is Step 7b, run once per member after all of that member's commits are in.

## Step 7 - Resolve Each Thread

After replying, resolve the thread using the GraphQL `resolveReviewThread` mutation. You need the thread's node ID, not the comment's database ID.

```bash
gh api graphql -f query='
mutation {
  resolveReviewThread(input: { threadId: "THREAD_NODE_ID" }) {
    thread { isResolved }
  }
}'
```

Order matters: reply first, then resolve.

## Step 7b - Sync the PR Title and Body With This Round's Changes

The PR description is part of the change, not decoration. Every round of fixes moves the branch; the title and body must describe the branch as it is **now** — not as it was when the PR was opened, and not as it was at the start of this run. Do this every run, whether or not any reviewer flagged the description.

Run it once per member, after all of that member's commits are in (thread fixes, conflict resolution, and Step 8b CI fixes alike) and **before the Step 8 push**, so reviewers open an accurate description alongside the new commits.

Re-read the current title and body (`pr.json` from the Step 3 fetch, or `gh pr view PR_NUMBER --json title,body`) and check them against everything this round changed:

- A fix that added, removed, or renamed behavior the body describes — a "Changes" bullet that no longer exists, a feature the fixes dropped, a limitation that no longer applies
- Checkboxes / todo items for work this round completed — tick them (add the fix SHA if the body references SHAs)
- A conflict resolution or sync that changed the shape of the change
- A CI fix that added a guard, test, or config worth a line
- Scope drift — the title no longer matches what the branch does

Edit only what is stale. Never rewrite an accurate description for the sake of activity, keep the body's structure (headings, tables, ticket links) intact, and never delete context a reviewer or the merge process needs. If the title and body already match the branch, edit nothing and report "PR description already in sync".

```bash
gh pr edit PR_NUMBER --repo OWNER/REPO --title "<updated title>" --body "$(cat <<'EOF'
<full updated body>
EOF
)"
```

Pass only the flags you are changing. The edit replaces the body **wholesale** — always send the complete updated body, never a delta. On repos with classic Projects where `gh pr edit` fails, PATCH the REST endpoint instead (same wholesale semantics):

```bash
gh api -X PATCH repos/OWNER/REPO/pulls/PR_NUMBER \
  -f title="<updated title>" -f body="$(cat <<'EOF'
<full updated body>
EOF
)"
```

On a stack, every member's own PR gets its own check — a child's description describes its delta against its parent, not the whole stack.

## Step 8 - Push Changes

Before pushing, verify the merged tree with the repo's own gates (lint, format check, typecheck, unit tests — whatever its AGENTS.md / CLAUDE.md names). Run gates bare and read the exit code; never pipe them through `head`. Local verification = lint, format check, typecheck, unit tests, and the repo's coverage / fast gate where one exists (e.g. `pnpm coverage`, `pnpm test:fast`). New/updated unit tests from Step 5 must run locally and pass. Do NOT run DB-backed suites or e2e / browser tests locally — GitHub CI runs those on the pushed head, but they are still written and pushed in this round when the change calls for them. On a stack, also run the gates on the **top** member: it is the only tree containing every member plus the synced base, and a child's earlier green run predates the parent changes it just absorbed.

After all threads are addressed, push the branch automatically - no confirmation needed. Run this **inside the worktree**. Since the worktree is on a detached HEAD, use an explicit refspec, aimed at the `push-target` the setup script printed in Step 1. Check `git ls-remote <push-target> refs/heads/<branch-name>` first — if the remote moved, someone else pushed; merge that ref in rather than overwriting it:

```bash
git push <push-target> HEAD:<branch-name>
```

`<push-target>` is `origin` for a same-repo PR. For a fork PR it is the fork's URL (`https://github.com/<head-repo>.git`) — pushing to `origin` there would create a stray branch on the base repo instead of updating the PR. If the script reported `push-target: UNKNOWN`, stop and report the PR as blocked rather than guessing.

If the push is rejected as non-fast-forward, the branch moved while you worked. Fetch that one ref, rebase, and retry:

```bash
git fetch <push-target> <branch-name>
git rebase FETCH_HEAD
git push <push-target> HEAD:<branch-name>
```

If the rebase conflicts, do NOT force-push. Abort the rebase, leave the commits in place, and report the PR as blocked with the conflicting files. (If your local commits include a sync merge — always the case on a stack — use `git merge FETCH_HEAD` instead of rebasing; a rebase flattens the sync merge.)

Note what shipped for the final report (Step 10):

> All `N` unresolved threads addressed (`M` fixes, `K` non-issues), plus `P` non-threaded items (review bodies / top-level comments). Pushed `<branch>` to remote. Add any fetch-truncation warnings here.

**If there is nothing to push** (no thread fixes, sync already up to date) but the head already has failing checks, Step 8b still applies: fix them in this worktree, commit, and push. If the head has no failing checks, there is nothing to do — do not wait for pending ones.

On a stack, go back to Step 1's member loop for the next member (Step 8b, then Step 9 cleanup) before Step 10.

## Step 8b - Fix Known CI Failures (Never Wait on CI)

Goal: do not leave behind a failure you can already see. **Do not wait for, poll, or watch the CI run that your push triggers** — no `wait_for_ci.sh`, no `gh pr checks --watch`, no `while` loop, no background shell, no subagent parked on a run. CI is remote and slow; once the work is pushed, the task is done.

**In scope:** checks that were already failing on the head in Step 1's snapshot (`gh pr checks PR_NUMBER --repo OWNER/REPO`, one call, non-blocking). Pending / in-progress checks are not work — ignore them. Do this before the Step 8 push so the fixes ride along in one push; if you only spot a failure after pushing, push a follow-up commit. Run it per member while `$WT` is alive. If the member had nothing else to push but its head has red checks, fix them and push.

### Diagnose a failure

Get the log of the failing job, then read the code:

```bash
gh pr checks PR_NUMBER --repo OWNER/REPO                    # failing check names + links
gh run view <run-id> --repo OWNER/REPO --log-failed         # the run id is in the check URL
```

For a job link (`.../actions/runs/<id>/job/<job-id>`), `gh run view <id> --job <job-id> --log-failed` narrows it to that job.

### Classify before fixing

Not every red check is yours to fix. Triage first, then act:

| Failure | Owner | Action |
| ------- | ----- | ------ |
| Caused by this branch's diff | yours | fix it here |
| Caused by an earlier stack member you just synced in | yours | fix it here — the child's tree includes the parent's commits |
| Same check red on the base branch, at the base's current tip | pre-existing | do not chase it; note it in the report |
| Flaky (timing, ports, ordering, network, an unrelated date) | nobody's | optionally fire one `gh run rerun <run-id> --failed` and move on without waiting; note it in the report |
| Infra (runner lost, action could not be downloaded, billing) | nobody's | report it; do not patch the repo around a GitHub outage |
| Cancelled with no failure in the log (superseded run, manual cancel, timeout kill) | nobody's | same as flaky: optional fire-and-forget rerun, note it, move on |
| Needs a product decision, an upstream fix, or a new secret | a human | leave it, reply in a PR comment with what is needed, report the PR as blocked |

**Rerunning is not fixing.** A rerun of a genuinely broken job just buys a second red run — only rerun when the log shows real flakiness, and never wait for the result.

### Fix

Read the failing file inside `$WT`, make the smallest correct change, commit, re-run the same local gates as Step 8, and push. Then move on — do not wait to see whether the new run is green:

```bash
# ... edit inside $WT ...
git add <file>
git commit -m "fix(ci): <what the check caught>"
git push <push-target> HEAD:<branch-name>
```

A CI fix is a normal commit: reply to the thread that asked for it if one exists, and never bundle unrelated cleanups into it.

### Stop conditions

One honest attempt per failing check. If you cannot find or fix the cause from the log, stop and report it as blocked with the job URL and the last ~20 log lines, so a human does not have to go looking. Leaving a check red and reporting it is a legitimate outcome; looping on it is not.

There is no post-push CI re-check and no post-CI merge-state re-check. A non-fast-forward rejection is handled in Step 8; if the base moves after you push, that is a new request, not part of this run.

Then continue: update labels (Step 8c), remove the worktree (Step 9), and move to the next member.

## Step 8c - Update Labels From What Is Still True

Labels record the PR's conclusion, so they go stale the moment a round of fixes lands. After the member's push (and its Step 8b fixes), recompute them. Vocabulary, thresholds, and the provenance rule are in `$HOME/.agents/skills/pr-review/references/pr-labels.md` — read it first.

1. Read the current labels (`gh pr view PR_NUMBER --json labels`) and the most recent `**Labels**` provenance line in the PR's review bodies (`reviews.json` from Step 3).
2. **Remove** a label only when this round fixed (pushed) or rebutted in-thread the finding behind it, **and** a `**Labels**` line records it. `bug`, `security`, `performance`, `needs tests`, `breaking change` and `do not merge` all follow this rule. A label with no provenance (a human's, or an earlier tool's) stays; say so in the report. Never remove `do not merge` because CI is green.
3. **Add** `help wanted` when this round ends with a conflict you could not resolve, a check you could not fix (Step 8b stop condition), or a thread left open for a human decision. Remove `help wanted` when this round answered the question behind it.
4. Do not add new `bug` labels here — those come from a review. If a fix you made reveals a new immediate-harm risk, say so in a PR comment and add `do not merge` with the reason.

```bash
SKILL_DIR="$HOME/.agents/skills/pr-review"
python3 "$SKILL_DIR/scripts/apply_pr_labels.py" --repo OWNER/REPO --pr PR_NUMBER \
  --add "help wanted" --remove bug --remove "do not merge"
```

Labelling is non-fatal: a permission error or missing label goes in the report, not in a retry loop. Never wait for CI to decide a label — red-and-unfixed means `help wanted`, pending means nothing.

## Step 9 - Clean Up the Worktree

After pushing, remove the worktree and prune. Run this from the **main repo directory** (not the worktree), and remove only `$WT` — the path the setup script gave you. Never remove a path you merely assume is yours:

```bash
# Return to the main repo
cd <main-repo-path>

# Remove the worktree
git worktree remove "$WT"
```

Everything is committed and pushed, and Step 8b has handled any known CI failures, so a plain `remove` should succeed. If it refuses because of leftover build artifacts you created (`dist/`, `node_modules/`), `git worktree remove --force` is fine. If it refuses because of **uncommitted source changes**, stop — do not force. Report the worktree path as left behind so a human can inspect it.

Do not run `git worktree prune` — another session may be mid-worktree-creation.

If the user asked to keep the worktree, skip the removal above. But the default is to clean up.

Then check the main checkout is exactly as we found it:

```bash
# The main checkout must be exactly as we found it
git -C "$REPO_PATH" rev-parse HEAD               # must equal $MAIN_HEAD
git -C "$REPO_PATH" rev-parse --abbrev-ref HEAD  # must equal $MAIN_BRANCH
git -C "$REPO_PATH" status --porcelain           # must equal $MAIN_STATUS
```

If any of the three differs, this run dirtied the main checkout — undo what you can and say so in the final report.

## Step 10 - Report and Stop

The workflow ends here. Once every member has been pushed and its worktree removed, write the report, mark the task done, and stop. Do not wait for the CI run the push started.

**Never gate on merge readiness** — no `pr_stack.py --ready` loop, no "rerun until ready", no merge, and no waiting for CI to finish. Pushing is the finish line of this skill.

Done means:

- every unresolved thread has a reply and is resolved (or left open with a reply laying out the decision a human must make)
- non-threaded feedback (review bodies, top-level comments) answered
- the PR title and body were checked against this round's changes and updated where stale (Step 7b) — the description matches the branch as pushed
- each member synced with its own base and pushed — fast-forward, never force-pushed
- checks that were already failing on each head diagnosed and fixed (or reported as blocked with the failing job URLs and log tails); the CI run the push triggered was not waited on
- local gates run (lint / format / typecheck / unit tests / coverage). Heavier suites (e2e / Playwright / DB-backed) were **not** run locally — GitHub CI runs those on the pushed head
- worktrees removed
- labels re-evaluated per member (Step 8c): stale ones removed only with provenance, `help wanted` added for anything left blocked
- the main checkout is byte-identical to how you found it — same branch, same HEAD, same `git status`

Report CI honestly per member, and never claim a result you did not observe. "No failing checks at start", "fixed `unit` (see `<SHA>`), new run not watched", "red: `e2e-auth` could not be fixed, log tail in the PR comment", and "checks pending, not waited on" are different outcomes and must never be collapsed into one "CI is fine".

If the user later asks about **merge readiness** ("is it ready to merge?"), that is a new request: take one snapshot then (`pr_stack.py --repo OWNER/REPO --pr PR_NUMBER`, no loop) and report it as-is — approvals, base rules, `behind_by`. Never merge as part of this skill. If the user explicitly asks you to merge the stack, follow §6 of `references/stacked-prs.md`.

Final report:

> Stack (root first): `#A <head> → <base>` · `#B …` (or "single PR")
> Was: per member, merge state + behind_by + open threads before you started
> Did: threads (`M` fixes, `K` non-issues) and sync merges, per member, with pushed SHAs
> Verified: gates per member (including coverage); heavy suites (e2e / Playwright / DB) not run locally — CI runs them on the pushed head
> Pushed: per member, `<branch>` → `<remote>` with SHAs; worktrees removed
> PR desc: per member — updated (<what changed>) or already in sync
> Labels: per member — added / removed / kept-without-provenance / missing-in-repo, or unchanged
> CI: per member, no failing checks at start / fixed `<check>` (`<SHA>`, new run not watched) / red on `<check>` (blocked, job URL) / pending (not waited on)
> Left for a human: threads left open for a decision, red checks you could not fix, fetch-truncation warnings, anything blocked

## Common Mistakes

| Mistake                                                        | Correct approach                                                                                                 |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Working in the main checkout instead of a worktree             | Always create a worktree on the PR branch by default                                                             |
| Skipping the sync with the target branch                       | Fetch and merge/rebase `origin/<target>` (default main) first — comments and fixes must land on the current tree |
| Merging in the target branch and force-pushing later           | Never force-push — the sync merge (Step 2) keeps the push fast-forwardable                                       |
| `git fetch --all` in a shared clone                            | Fetch only the target ref — a full fetch contends on ref locks with other worktrees                              |
| `git worktree add <branch>`                                    | Use `setup_worktree.sh` — it detaches, because the branch may be checked out elsewhere (and may not exist on `origin` at all, for a fork) |
| Hand-rolling the worktree path                                 | Use the path `setup_worktree.sh` printed — it may have stepped over a collision (`-r2`, `-r3`, …)                |
| Bare `git push` on detached HEAD                               | Use `git push <push-target> HEAD:<branch-name>` — the worktree has no upstream                                   |
| `git push origin HEAD:<branch>` on a fork PR                   | Push to the fork URL from the `push-target` line — `origin` is the base repo and would create a stray branch      |
| Bare `git stash` / `git stash pop` in a worktree               | The stash stack is shared across all worktrees — never use it                                                    |
| Forgetting to `cd` into the worktree before reading/committing | All file operations and git commits happen inside the worktree                                                   |
| Fixing code without reading the file first                     | Always read the current file; the diff may be outdated                                                           |
| Resolving threads without replying first                       | Reply with evidence, then resolve                                                                                |
| Replying but forgetting to resolve                             | Always resolve after replying                                                                                    |
| Bundling multiple comment fixes into one commit                | One commit per comment                                                                                           |
| Triaging only inline threads                                    | `CHANGES_REQUESTED` review bodies and top-level comments are feedback too — Step 3 covers all three shapes       |
| Reading only the root comment of a thread                       | Read the full `comments` chain — a later reply often retracts or narrows the original finding                    |
| Updating the PR body only when a reviewer flags it as stale | Step 7b every run: check title/body against this round's changes, `gh pr edit` what is stale before the push |
| Sending `gh pr edit` a body delta or partial body | It replaces the body wholesale — always send the full updated body |
| Swallowing a fetch truncation warning                           | A capped fetch silently misses threads/reviews/comments — say so in the final report instead of claiming a sweep  |
| Using REST API to check resolved status                        | Use GraphQL `reviewThreads.isResolved`                                                                           |
| Using comment databaseId to resolve threads                    | Resolving requires the thread node ID                                                                            |
| Replying to the wrong comment ID                               | Confirm `in_reply_to_id` points to the thread root                                                               |
| Force-pushing after a rebase conflict                          | Abort, report as blocked, let a human decide                                                                     |
| Leaving the worktree behind after finishing                    | Remove the worktree after pushing                                                                                |
| Running `git worktree prune` inside an agent                   | It races another agent's `worktree add`                                                                          |
| Trying to remove the worktree from inside it                   | `cd` back to the main repo first, then `git worktree remove "$WT"`                                               |
| Reading only check colours when told "CI is failing"           | Read `mergeStateStatus` + `behind_by` first — on stacks the blocker is usually `BEHIND` with every check green    |
| Merging `main` into a stacked child                            | Sync each PR with its OWN base: root ↔ default branch, child ↔ parent branch (re-fetched after the parent's push) |
| Touching only the PRs that have open threads                   | Expand to the whole stack with `pr_stack.py` — a quiet, behind root blocks every child                            |
| Syncing a child before its parent is pushed                    | Root first, strictly sequential; one worktree per member                                                          |
| Rebasing a stack member                                        | Merge — a rebase needs a force-push and re-parents every child above it                                           |
| Calling a child "ready" because it reads `CLEAN`               | Its base has no rules; check `behind_by` and flag it provisional until its parent merges                          |
| Ignoring checks that are already red on the head | Step 8b: read the failed log and fix what is yours before the push — but never wait for the new run |
| Skipping Step 8b because nothing was pushed | The head may already be red — fix known failures and push; if none, you are done |
| Waiting for CI to turn green after the push | Do not. No watcher shell, no subagent, no `--watch` — pushed means done |
| Committing a conflict resolution with markers left in   | `git ls-files -u` empty, no `<<<<<<<`/`>>>>>>>` markers, `git diff --check` clean, gates pass on the merged tree |
| Removing the worktree before fixing known red checks | Fix them first — a fix after cleanup needs a whole new worktree and sync |
| Reporting CI green without having seen it | Say "pending, not waited on" or "no failing checks at start" — never "green" for a run you did not observe |
| Rerunning a red check instead of reading its log | `gh run rerun <id> --failed` is for flakiness only, once, fire-and-forget |
| Fixing a check that is red on the base branch too        | Confirm against the base's current tip first; pre-existing breakage is reported, not patched               |
| Polling checks in a hand-rolled `while true` loop or `--watch` | Never poll CI — read the checks once, fix what is red, push, stop |
| Looping CI fixes forever | One honest attempt per failing check, then report with job URLs and log tails |
| Merging because CI turned green | This skill never merges — merging is a separate, explicit request |
| Leaving `bug` / `do not merge` on after the fix is pushed | Step 8c: remove it when a `**Labels**` line records it and the finding is fixed; leave unrecorded labels alone |
| Removing `do not merge` because CI went green | Green CI is not evidence the downtime risk is gone — only the fix is |
| Ending with a blocked conflict / red check and no label | Step 8c: add `help wanted` so a human sees it in the PR list |
| Merging the stack because it is ready                          | Report the merge plan; merge only on an explicit instruction                                                      |
| Running a write command in the main checkout (`merge`, `rebase`, `checkout`, `stash`) | Only `git worktree add` / `remove` and read-only commands belong there — every write runs in the worktree         |
| "Tidying up" the dirty main checkout before starting                                  | Leave the user's uncommitted work alone — the checkout must come out byte-identical                               |

## Quick Reference

```bash
# Get PR branch, target branch and merge blocker
gh pr view PR_NUMBER --json headRefName,baseRefName,mergeStateStatus,mergeable

# Map the stack (root first) and each member's state — one snapshot, no watching
SKILL_DIR="$HOME/.agents/skills/pr-resolve"
python3 "$SKILL_DIR/scripts/pr_stack.py" --repo OWNER/REPO --pr PR_NUMBER

# Create an isolated worktree on the PR branch (collision-safe, detached)
REPO_PATH=$(git rev-parse --show-toplevel)
# Snapshot the main checkout — it must come out of this run byte-identical
MAIN_HEAD=$(git -C "$REPO_PATH" rev-parse HEAD)
MAIN_BRANCH=$(git -C "$REPO_PATH" rev-parse --abbrev-ref HEAD)
MAIN_STATUS=$(git -C "$REPO_PATH" status --porcelain)
WT=$(bash "$SKILL_DIR/scripts/setup_worktree.sh" "$REPO_PATH" PR_NUMBER <branch-name> <head-repo>)
cd "$WT"

# Sync with THIS PR's own base (stacked child: the parent branch, never main)
TARGET=<baseRefName>
git fetch origin "$TARGET"
git merge origin/"$TARGET"
# On conflict: edit files, remove markers, then:
# git add <resolved-files> && git commit -m "merge: resolve conflicts with origin/<target>"

# Fetch every outstanding feedback item: unresolved threads (with full comment
# chains, path/line, is_outdated), all reviews, all top-level comments, PR metadata
# -> pr.json threads.json reviews.json issue_comments.json; stderr warns on truncation
FEEDBACK_DIR=$(mktemp -d)
python3 "$SKILL_DIR/scripts/fetch_open_threads.py" --repo OWNER/REPO --pr PR_NUMBER --out-dir "$FEEDBACK_DIR"

# Reply to a thread
gh api repos/O/R/pulls/N/comments/COMMENT_ID/replies -X POST -f body="MESSAGE"

# Resolve a thread
gh api graphql -f query='mutation { resolveReviewThread(input: { threadId: "THREAD_NODE_ID" }) { thread { isResolved } } }'

# Or reply + resolve in one call (correct order, correct id per API)
python3 "$SKILL_DIR/scripts/reply_and_resolve.py" --repo OWNER/REPO --pr N \
  --comment-id ROOT_COMMENT_ID --thread-id THREAD_NODE_ID --body "MESSAGE"

# Answer non-threaded feedback (review bodies / top-level comments) in one post
gh pr comment N --repo OWNER/REPO --body "MESSAGE"

# Keep the PR description in sync with this round's changes (Step 7b — edit only if stale; FULL body)
gh pr edit N --repo OWNER/REPO --title "..." --body "$(cat <<'EOF'
<full updated body>
EOF
)"
# gh pr edit fails on classic-Projects repos → REST fallback:
gh api -X PATCH repos/OWNER/REPO/pulls/N -f title="..." -f body="..."

# Commit a single-file fix (inside worktree)
git add path/to/file
git commit -m "fix(scope): description"

# Push (inside worktree — detached HEAD needs explicit refspec; fork PRs push to the fork URL)
git push <push-target> HEAD:<branch-name>

# Fix checks ALREADY failing on the head (one call, no waiting/watching):
# gh pr checks N --repo O/R, then gh run view <run-id> --log-failed,
# fix inside $WT, commit, run local gates, push. Never wait for the new run.

# Update labels after the push (Step 8c) — missing labels are skipped, never fatal
python3 "$HOME/.agents/skills/pr-review/scripts/apply_pr_labels.py" --repo OWNER/REPO --pr N --add "help wanted" --remove bug

# Clean up worktree (from main repo — remove only $WT)
cd <main-repo-path>
git worktree remove "$WT"
# The main checkout must be exactly as we found it
git -C "$REPO_PATH" rev-parse HEAD               # must equal $MAIN_HEAD
git -C "$REPO_PATH" rev-parse --abbrev-ref HEAD  # must equal $MAIN_BRANCH
git -C "$REPO_PATH" status --porcelain           # must equal $MAIN_STATUS

# Done: everything pushed, worktrees removed. Nothing merged, CI not watched.
# Merge READINESS is a separate one-shot question, only when the user asks (no loop):
python3 "$SKILL_DIR/scripts/pr_stack.py" --repo OWNER/REPO --pr PR_NUMBER
```
