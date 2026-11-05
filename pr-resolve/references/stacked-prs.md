# Stacked PRs — resolve, sync, and push the whole stack

A **stacked PR** targets another open PR's branch instead of the default branch:

```text
main  ←  #837 feat/run-cost-stats  ←  #845 feat/expected-bands  ←  (#850 …)
root (base = main)                 child (base = #837's head)
```

The PR you were asked about is rarely the only one that needs work. Treat the
**stack** as the unit: every member is synced, verified, and pushed, and any check
already failing on its head is fixed. The job is done once every member is pushed —
never wait for or watch the CI run a push triggers.

Shared by `pr-resolve` and `pr-review-resolve`. Helper: `scripts/pr_stack.py` (in this skill).

## 1. Detect the stack — always, before any sync

```bash
SKILL_DIR="$HOME/.agents/skills/pr-resolve"
python3 "$SKILL_DIR/scripts/pr_stack.py" --repo OWNER/REPO --pr N > /tmp/pr-N-stack.json
```

- Walks DOWN from N to the root, then collects every descendant of the root, so
  siblings sharing a parent are included. JSON on stdout (`order` = root first),
  human summary + warnings + merge plan on stderr.
- `is_stack: false` and one member → a normal PR; the rest of this doc does not
  apply.
- `orphan_base` set → the root targets a branch no open PR owns (its parent was
  merged or closed). Retarget it to the default branch first (see §6).

## 2. Diagnose with merge state, not check colours

"Fix the CI errors" / "the stack has rebase conflicts" on a stack very often
means **every check is green and the PRs are `BEHIND`** under a strict
"branches must be up to date" rule. `statusCheckRollup` alone hides that.

Read, per member: `mergeStateStatus`, `mergeable`, and `behind_by` (compare API
against the base's current tip — `pr_stack.py` reports all three).

| `mergeStateStatus` | Meaning | Action |
|---|---|---|
| `BEHIND` | Base moved; strict rule demands an update | Sync with its own base (§3) |
| `DIRTY` / `mergeable: CONFLICTING` | Real conflict with its base | Sync and resolve conflicts (§3) |
| `BLOCKED` | Required check, review, or ruleset unmet | Read the reasons; approvals are a human's |
| `UNSTABLE` | A non-required check failing | Fix it — "ready" means no red checks |
| `UNKNOWN` | GitHub has not computed it yet | Wait and rerun — never report it |
| `CLEAN` | Mergeable now | On a child, only **provisional** (§5) |

`mergeStateStatus` is computed lazily: it reads `UNKNOWN` right after a push,
and a `BEHIND` can outlive the sync push by a minute. `behind_by == 0` is the
ground truth; rerun before reporting a stale value.

A child whose base is a feature branch usually has **no rules on that base**, so
it reads `CLEAN` even when it is behind its parent. Check `behind_by`, not the
merge state, for children.

## 3. Sync bottom-up, each PR against its OWN base

Order: root first, then each child after its parent is pushed (not after the parent's CI finishes).

1. **Root** — worktree on the root's branch, `git fetch origin <default>`,
   `git merge origin/<default>`, resolve, verify (§4), fix known red checks (§4b), push.
2. **Each child** — only after its parent's push has landed:
   `git fetch origin <parent-branch>` (re-fetch: the local ref is stale the
   moment the parent was pushed), `git merge origin/<parent-branch>`, verify, fix known red checks, push.
3. Repeat up the tree. Siblings can be synced in any order once their shared
   parent is pushed.

Rules:

- **Never merge the default branch into a child.** Its PR diff is computed
  against the parent branch; pulling `main` in makes the child's diff show every
  unrelated `main` commit the parent has not yet absorbed. A child gets `main`
  only through its parent.
- **Merge, don't rebase.** Rebasing a pushed stack member requires a force-push
  and re-parents every child above it. A sync merge commit is harmless and keeps
  every push fast-forward.
- **Prove a conflict resolution before pushing it:** `git ls-files -u` prints
  nothing, no `<<<<<<<` / `>>>>>>>` markers remain in the resolved files,
  `git diff --check` is clean, and the §4 gates pass on the merged tree. A
  marker left behind is a CI failure you shipped.
- **A member with zero feedback still gets synced.** The root that blocks the
  stack often has every thread resolved. Feedback-based discovery misses it —
  expand to the whole stack (§1) and sync every member.
- One worktree per member, created with `setup_worktree.sh`, removed after that
  member's push. Process members **sequentially** — a child's sync depends on
  its parent's push.
- Check `git ls-remote origin refs/heads/<branch>` right before each push; if
  someone else moved the branch, fetch that one ref and merge it, never
  force-push.

## 4. Verify where it counts

- **Per member:** static gates (lint, format check, typecheck), the unit suite, and the coverage / fast gate (e.g. `pnpm coverage`, `pnpm test:fast`) on that member's merged tree. Local verification stops there.
- **Not run locally:** e2e / Playwright and DB-backed suites. GitHub CI runs them on the pushed heads.
- **CI may not run everything before approval.** Some repos run selective or
  partial suites until a PR is approved; the umbrella required job goes green
  while the full suites read `SKIPPED`. `pr_stack.py` lists skipped jobs by name
  — say in the report which full gates have NOT run on the current heads, and
  what you ran locally instead.

## 4b. Fix known CI failures — per member, root first, never wait

Do **not** wait for, poll, or watch the CI run a push triggers — no `wait_for_ci.sh`,
no `--watch`, no background shell or watcher subagent. Once a member is pushed, it is done.

Only checks **already failing** on the member's head are in scope (one non-blocking
`gh pr checks N`). Pending checks are ignored. For each: `gh run view <run-id> --log-failed`,
classify the failure, fix it in the member's worktree, commit, re-run the §4 gates, and
push (ideally in the same push as the rest of the member's work). One honest attempt per
failing check; if the log does not yield a fix, report it blocked with the job URL and log
tail. If nothing else was pushed for a member but its head is red, fix and push that.

Two things make this different on a stack:

- **A child inherits the parent's commits, so it inherits their failures.** Fix the root's
  known failure first, then sync the child — otherwise the same failure comes back once
  per member and you fix it N times for the same bug.
- **A child's CI can be green and still not mergeable.** Its base is a feature branch with
  no rules (§2), so "green" says nothing about what happens after the parent lands.

There is no post-push CI re-check and no post-CI merge-state re-check. See §5 for what
done does *not* mean.

## 5. Readiness — on demand only, never part of the default flow

The resolve skills end at **the push**, never at CI or merge readiness. A push says
nothing about whether checks pass, nor about approvals, base rules, or whether the
branch is mergeable today. Readiness is a one-shot check, run only when the
user explicitly asks ("did CI pass?", "is it ready to merge?"):

```bash
python3 "$SKILL_DIR/scripts/pr_stack.py" --repo OWNER/REPO --pr N
```

That prints one snapshot per member: draft, unresolved threads, `behind_by`,
`mergeStateStatus`, required-check states, skipped jobs, and the merge plan.
Report the snapshot as-is. Never loop on it, never rerun "until ready", never
block the session on pending checks.

A member is **ready** when, on its current head:

- not a draft
- 0 unresolved review threads (paginated — no 100-thread cap)
- not `CONFLICTING`, and `behind_by == 0` against its base
- `mergeStateStatus` `CLEAN` / `HAS_HOOKS`
- every required check from the base branch's rules passing; no failing check runs

`BLOCKED` with only a missing approval → **awaiting approval**; a human must
grant it. Also read the base rules the script prints:
`required_approving_review_count`, `strict`, and
`require_extra_approval_for_unattributed_changes` (commits whose author email is
not linked to a GitHub account need an extra approval).

A child targeting a feature branch is **provisional** even when ready: after its
parent merges it needs one more sync with the default branch and a CI run (§6).
Say so in the report.

If the user asks for readiness and a member is not ready, fix only what they
name (a specific missing approval, a new conflict) as a fresh request. A check
that was already red is in scope for the default run (§4b) — it is "not ready"
and "not built" at the same time, and only the second one is the agent's to fix.

## 6. Merge plan — report it, do not execute it unasked

The resolve skills leave the stack **pushed**; they do not merge. Print the plan
`pr_stack.py` produced. Merge only on an explicit instruction, and then:

1. Merge the **root** into the default branch. Prefer a merge commit.
2. The child is retargeted to the default branch **only when the parent branch is
   deleted** (`delete_branch_on_merge`, or deleting it by hand after the merge).
   Confirm: `gh pr view <child> --json baseRefName`. If it was not retargeted,
   do it before merging the child — never merge a child into a dead parent branch:
   `gh api -X PATCH repos/OWNER/REPO/pulls/<child> -f base=<default>`
   (REST; `gh pr edit --base` fails on repos with classic Projects).
3. Under a strict rule the child is now `BEHIND` by the parent's merge commit.
   Update it server-side — GitHub merges the base into the branch, no force-push:
   `gh api -X PUT repos/OWNER/REPO/pulls/<child>/update-branch -f expected_head_sha=<child head sha>`.
   A 422 means a conflict: sync it locally in a worktree instead.
4. Check the child's CI once (`gh pr checks <child>`), then merge it. Repeat up
   the stack.

Variants:

- **Parent squash- or rebase-merged:** the child still carries the parent's
  original commits and its diff shows them again. Merge the default branch into
  the child (step 3) — the duplicate commits drop out of the diff because their
  content is already on the default branch. Do not rebase-and-force-push.
- **Collapsed merge:** if the top PR's head lands on the default branch in one
  merge commit, every lower member's head lands with it, and GitHub marks each
  lower PR merged by that same commit. Example:
  `main` got one commit (parents: old `main`, #845's head) and both #837 and #845
  read MERGED with it. Afterwards, confirm with
  `gh api repos/OWNER/REPO/compare/<default>...<each head sha>` → `ahead_by: 0`
  for every member, before reporting the stack landed.

## 7. Hazards

- **Never close a parent PR and delete its branch while a child is open** —
  GitHub closes the child along with it. Retarget the child first.
- **Sequence-numbered artifacts collide across sibling stacks** — DB migration
  numbers, changelog entries. Two stacks off the same `main` can each claim the
  next number; whichever lands second renumbers. Mention it when you see one.
- **Two agents on one stack** fight over the same branches. One agent owns a
  whole stack (bulk runs group by stack before fan-out).
- **Stale local refs:** after any push in the stack, re-fetch the single ref you
  are about to merge from. `merge-base` against a stale ref silently omits the
  parent's newest commits.

## 8. Report shape

```text
Stack (root first): #837 feat/run-cost-stats → main · #845 feat/expected-bands → feat/run-cost-stats
Was:   #837 BEHIND main by 27 (CI-only commits) · #845 BEHIND parent by 3 — all checks green, 0 open threads
Did:   #837 merged origin/main → ac64a754 · #845 merged updated parent → ece9406c
Verified: per-PR lint/fmt/typecheck/unit; top-of-stack full DB suite (126 files) — locally, since CI skips it pre-approval
Pushed: #837 → origin @ ac64a754 · #845 → origin @ ece9406c
CI:     #837 no failing checks at start · #845 fixed `unit` (b1f20c9, null deref in band lookup) — post-push runs not watched
Not run on current heads: full unit / DB / coverage jobs (SKIPPED pre-approval)
```
