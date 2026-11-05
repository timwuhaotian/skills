---
name: pr-review-resolve
description: End-to-end GitHub PR workflow combining review and resolution — first perform a deep inline PR review (old-vs-new behavior comparison, regression and contract-drift detection, structured inline review comments), then immediately triage and resolve ALL unresolved inline review threads (including the ones just posted, existing reviewer/bot comments, one commit per fix, reply-then-resolve, sync with the base and resolve any conflicts, update the PR title/body to match this round's changes, push, fixing checks already red on the untouched head, and even when there are no threads at all), and stop once every member is pushed — the CI run a push triggers is never waited on or watched, merge readiness is never gated, and nothing is ever merged. Labels the PR with its conclusion after the review (`do not merge`, `help wanted`, `bug`, `enhancement`, …) and re-evaluates the labels after the push. Handles stacked PRs / PR stacks (a PR whose base is another PR's branch) — reviews each member against its own base, syncs the whole stack bottom-up, and pushes every member. Use when asked to "review and fix the PR", "review then address the comments", "do a full PR pass", "review and fix this stack", or any request wanting review + resolution in one continuous flow. For review-only use pr-review; for resolve-only use pr-resolve. The local main checkout is never modified — it is only used to add and remove worktrees.
---

# Review and Resolve Inline PR

One continuous workflow: **review the PR inline first, then resolve every unresolved inline review thread** (yours included).

This skill orchestrates two existing skills. It does NOT duplicate their procedures — it sequences them. When a step says "follow skill X", load and execute that skill's SKILL.md exactly.

- Review phase → `~/.agents/skills/pr-review/SKILL.md`
- Resolve phase → `~/.agents/skills/pr-resolve/SKILL.md`

Use the individual skills instead when only one phase is wanted:

- `pr-review` — review a PR and post inline comments, no fixing
- `pr-resolve` — triage/fix/resolve existing review threads, no fresh review

## The main checkout is a launcher, not a workspace

The clone the user is sitting in belongs to them. It is used for exactly two things: `git worktree add` and `git worktree remove`. It must come out of this run byte-identical — same branch, same HEAD, same working tree.

- **Never** in the main checkout: `git commit`, `git merge`, `git rebase`, `git pull`, `git checkout` / `git switch`, `git reset`, `git cherry-pick`, `git revert`, `git stash`, `git clean`, `git branch -m` / `-d`, or any file edit.
- **Only** in the main checkout: `git status`, `git log`, `git rev-parse`, `git worktree list`, `git remote get-url`, `git fetch` (updates remote-tracking refs only — it does not move HEAD or touch the working tree), and `gh` commands.
- If the main checkout is already dirty, that is the user's work: leave it exactly as it is. Never stash, clean, or reset it to "help".
- Every write command — commit, merge, rebase, push, branch rename — runs inside the worktree, with the worktree as the current directory (or `git -C <worktree>`).

## Output style — `ultracave`

If a `ultracave` skill exists (`~/.agents/skills/ultracave/SKILL.md`, `.claude/skills/ultracave/SKILL.md`, or a vendored `.agents/skills/ultracave/`), load it once at the start and apply its register to **chat output only** — progress notes across both phases, the final report below, and anything said to the user. If it is absent, proceed normally without mentioning it.

Everything persisted stays in normal language, in both phases: inline review comments, the review body, thread replies, commit messages, code, and docs. Terse register is for the conversation, not for the PR.

## When to Use

- "Review this PR and fix whatever comes up"
- "Do a full review pass and address all the comments"
- "Review PR #N, then resolve the review feedback"
- Pre-merge hygiene: fresh deep review + clean thread list before merging

## Workflow

```text
Phase A — Review (pr-review)
 1. Fetch PR context (fetch_pr_context.py) — pr.json, files.json, comments.json, reviews.json
 2. Triage files, reconstruct old-vs-new behavior, trace changed branches to producers
 3. Write qualifying findings -> submit one structured GitHub review with inline comments
 3b. Label the PR with the review's conclusion (pr-review step 9; `**Labels**` line in the body)

Phase B — Resolve (pr-resolve)
 4. Detect the stack (pr_stack.py); on a stack, steps 5-13 run per member, root first
 5. Create isolated git worktree on the PR branch (setup_worktree.sh)
 6. Sync worktree with the PR's OWN base (default branch; parent branch for a stacked child),
    resolve any conflicts
 7. Sweep ALL outstanding feedback — existing threads from other reviewers/bots,
    review bodies, top-level comments, AND the ones just posted in Phase A
 8. Per item: verify against current code -> fix (one commit per comment) or explain why invalid
    -> reply with evidence -> resolve thread
 9. Fix checks ALREADY failing on the head (snapshotted in Phase A) — read the
    log, fix in this worktree, re-run the local gates. One attempt per failing check
10. Sync the PR title and body with this round's changes (pr-resolve Step 7b —
    `gh pr edit`, full body, only what is stale)
11. Push the branch once (explicit refspec HEAD:<branch>, fork PRs push to the fork URL).
    Do NOT wait for or watch the CI run the push triggers
12. Remove the worktree
12b. Re-evaluate labels from what is still true (pr-resolve Step 8c)
13. Report what was pushed (and any known CI failure fixed or left blocked), per
    member, mark the task done, and STOP. Never merge, never watch CI.
```

## Phase A — Review

Follow `~/.agents/skills/pr-review/SKILL.md` end to end (steps 1-8), with one adjustment:

- **Always submit as `COMMENT`, never `APPROVE`.** This workflow continues into fixing; approval is the PR author's call after the fixes land.
- Use the machine-level skill dir: `SKILL_DIR="$HOME/.agents/skills/pr-review"`.
- If the review produces zero qualifying findings, or reports SKIPPED under pr-review's re-review silence rule, still proceed to Phase B — there may be pre-existing unresolved threads from other reviewers or bots.
- While fetching PR context, also snapshot the untouched head's health: `gh pr checks PR_NUMBER --repo OWNER/REPO` and `mergeable` / `mergeStateStatus`. Failing checks, a `DIRTY` conflict, or a `BEHIND` base noted here are Phase B work items even if the review is clean and no thread ever mentions them.

Keep the review's findings list at hand — it seeds Phase B triage (you already know which of your own comments are real bugs vs. judgment calls).

**Label the PR as part of Phase A** (pr-review step 9; vocabulary in `~/.agents/skills/pr-review/references/pr-labels.md`): `do not merge` for immediate-harm risk (downtime, data loss, auth/secret hole, deploy-order break — a believed 🔴 Critical finding), `help wanted` when a human is needed, `bug` / `security` / `performance` / `needs tests` / `breaking change` for real unfixed findings, `enhancement` for capability or improvement-only findings. End the review body with a `**Labels**` line giving one-line reasons, so Phase B can remove a label once its reason is fixed.

**Stacked PR:** a child's diff is against its parent branch, not `main` — review only what the child adds, and do not re-flag the parent's changes there. If you were asked to review the stack, review each member against its own base. Run `pr_stack.py` (Phase B, step 4) before reviewing if you are unsure whether the PR is stacked.

## Phase B — Resolve

Follow `~/.agents/skills/pr-resolve/SKILL.md` end to end (steps 1-10, including 7b PR-title/body sync and 8b fix-known-CI-failures; Step 10 is report-and-stop — the session ends once every member is pushed, without waiting on CI). Stacked PRs follow `~/.agents/skills/pr-resolve/references/stacked-prs.md`. Points that matter specifically in this combined flow:

1. **Refetch, and fetch everything.** Phase A just posted new comments — any thread list from the review phase is stale. Re-run the Step 3 fetch *after* the review is submitted, and take all of it: unresolved threads from other reviewers and bots, `CHANGES_REQUESTED` review bodies, and unanswered top-level comments. Do not narrow the sweep to your own findings.
2. **Own comments are threads too.** The findings you posted in Phase A are now unresolved threads. Verify each against the worktree code like any other comment, using the same rubric (`~/.agents/skills/pr-review/references/finding-verification.md`). Phase A already ran its refute pass, so in Phase B look for what changed since, and do not just restate Phase A's verdict. Then fix the valid ones (one commit per comment), and reply referencing the commit SHA. Do not silently resolve your own findings.
3. **Read whole threads.** Phase A's own threads have no replies yet, but pre-existing ones usually do. A follow-up reply ("actually fine as-is", "fixed in #123") changes the verdict — triage the chain, not the root comment.
4. **A clean review is not a clean resolve.** Zero findings in Phase A says nothing about feedback other people left earlier. Phase B still runs the full sweep and reports its counts.
5. **Worktree isolation still applies.** Even though you just reviewed this PR, all fixes happen in the worktree from `setup_worktree.sh`, never the main checkout. Review-phase reads were against GitHub/local files; fix-phase reads must be inside `$WT`. The main checkout is only a launcher for `git worktree add` / `git worktree remove` — no write command ever runs there.
6. **Sync before fixing.** Merge/rebase `origin/<target>` into the worktree before touching code — the branch may have drifted while you were reviewing. `<target>` is the PR's own base; on a stack, merge (never rebase) and go root first.
7. **Push once at the end** (once per member on a stack). Fix any already-failing check (Step 8b) *before* that push and *before* removing the worktree, so the fix is made in the tree you already have. Never wait for the run the push triggers.
8. **Expand to the stack.** A stack member with no review findings and no threads may still be the blocker (behind its base). Every member is synced and pushed, not just the PR you reviewed. A child's sync waits for its parent's push, not for the parent's CI.
9. **Stop when everything is pushed.** Not when CI turns green. Fix the checks that were already red — one attempt each — then report honestly: no failing checks at start, fixed `<check>` (new run not watched), or red on `<check>` blocked with job URLs. Never poll, `--watch`, or park a shell/subagent on a run. Never gate on merge readiness and never merge.
10. **Your Phase A findings are not CI.** A check that was already red and the review never mentioned still has to be fixed. Judge it on the log like any other failure, even if it lands on a line you just reviewed.
11. **No threads + clean review ≠ done.** If Phase A found nothing and no pre-existing threads exist, Phase B is still the sync/conflict + known-failure pass: merge the base in, resolve any conflicts (verify: `git ls-files -u` empty, no conflict markers, gates pass on the merged tree), fix checks that were already red, and push if that changed anything. If nothing needs pushing, you are done — do not wait for pending checks.
12. **Sync the PR title and body before the push.** This round's review fixes, pre-existing-thread fixes, conflict resolutions, and CI fixes all moved the branch — the description must match it (pr-resolve Step 7b). Check the title and body against everything this round changed, including your own Phase A findings' fixes, and `gh pr edit` only what is stale (always the full body; REST PATCH when `gh pr edit` fails on classic Projects). Every run — not only when a reviewer flagged it. On a stack, per member: a child's body describes its delta against its parent.

13. **Re-evaluate labels after the push** (pr-resolve Step 8c). The fixes just pushed may have cleared the reason for a Phase A label: remove `bug` / `security` / `performance` / `needs tests` / `breaking change` / `do not merge` only when its finding was fixed or rebutted this round and your Phase A `**Labels**` line (or an earlier one) records it — never because CI is green, never a label with no record. Add `help wanted` for a blocked conflict, a red check you could not fix, or a thread left open for a human decision.
14. **File hygiene (500-line rule).** Phase B fixes follow the pr-resolve file rule: when creating new code or modifying existing code, work with a refactor-and-cleanup mindset — keep every touched file under 500 lines. If a fix would push a file over ~500 lines, or the file is already over, split it instead of growing it (extract a module/helper, add a new file to carry the structure). A file that cannot stay under 500 lines signals weak structure, not a reason for a bigger file. Keep the split scoped to what the fix needs; unrelated cleanups stay out.

## Ordering Guarantees

- Review before resolve: Phase B needs a thread list fetched after Phase A posted, and reviewing stale-but-about-to-be-fixed code wastes findings.
- Reply before resolve on every thread.
- All commits in the worktree, one push, then cleanup. No waiting on the CI run the push triggers.

## Acceptance Checks

- [ ] Phase A review submitted (structured body + inline comments, or a clean COMMENT review)
- [ ] Full feedback refetched AFTER the review was posted — threads, review bodies, top-level comments
- [ ] Every unresolved thread has a reply AND is resolved
- [ ] Non-threaded feedback (CHANGES_REQUESTED bodies, top-level comments) answered in one post
- [ ] PR title/body checked against this round's changes and updated where stale before the push (full body via `gh pr edit` / REST PATCH) — or reported already in sync
- [ ] Every valid fix is its own commit
- [ ] Fetch truncation warnings surfaced in the report, if any
- [ ] Branch pushed (fast-forward, no force-push)
- [ ] Checks already failing on each head fixed (one attempt each) or reported red with job URLs and log tails; the post-push run was NOT waited on or watched, and CI is never reported green for a run not observed
- [ ] Conflicts handled end to end: base synced per member, any conflict resolved with no markers left (`git ls-files -u` empty, `git diff --check` clean, gates pass on the merged tree)
- [ ] CI/conflict-only case covered: a clean review with zero threads still got the sync + known-failure pass, not an early exit
- [ ] Worktree removed after known CI failures were fixed, not before
- [ ] Stack detected; if stacked, every member (including quiet ones) synced root first against its own base, each child after its parent's push
- [ ] Session ended once everything was pushed — no CI watching, no readiness gate, nothing merged
- [ ] Main checkout unchanged — same branch, same HEAD, same `git status` as before the run
- [ ] Labels applied after the review from the final findings table (`**Labels**` line in the body) and re-evaluated after the push — stale ones removed only with provenance, `help wanted` for anything left blocked, labelling failures reported not retried

## Common Mistakes

| Mistake | Correct approach |
| --- | --- |
| Running a write command in the main checkout (`merge`, `rebase`, `checkout`, `stash`) | Only `git worktree add` / `remove` and read-only commands belong there — every write runs in the worktree |
| "Tidying up" the dirty main checkout before starting | Leave the user's uncommitted work alone — the checkout must come out byte-identical |
| Ignoring checks already red on the head | Step 8b: read the log and fix what is yours before the push |
| Waiting for or watching CI after the push | Do not. No watcher shell, no subagent, no `--watch` — pushed means done |
| Rerunning a red check instead of reading the job log | `gh run rerun <id> --failed` is for flakiness only, once, fire-and-forget |
| Reporting CI green for a run you did not observe | Say "no failing checks at start" or "pending, not waited on" |
| Merging because CI went green | Merging is a separate, explicit human request |
| Using `do not merge` for ordinary bugs or style | It is a hold for immediate-harm risk; otherwise `bug` / `help wanted` |
| Removing `do not merge` (or any label) because CI went green, or one with no `**Labels**` record | Remove only when the recorded finding was fixed or rebutted this round |
| Leaving the PR title/body stale after this round's fixes | pr-resolve Step 7b: check against this round's changes and `gh pr edit` (full body) before the push |

## Final Report Format

```text
Review: N findings posted (X critical/high, Y medium/low) — or "clean review, no findings"
Labels: per member — added <…> after review; after push removed <…> / added <…> / kept-without-provenance <…> / missing-in-repo <…> — or "none"
Resolve: M threads addressed (F fixes in F commits, K non-issues/stale)
         — P of them your own Phase A findings, Q pre-existing from others
Non-threaded: R items (review bodies / top-level comments) addressed
Stack: #A → #B … (root first) — or "single PR"
Pushed: <branch> to <remote> (per member, with SHAs)
PR desc: per member — updated (<what changed>) | already in sync
Conflicts: per member — none | resolved <files> @ <sha> | blocked on <files>
CI: per member — no failing checks at start | fixed <check> @ <sha> | red on <check> (blocked)
    | pending (not waited on); job URLs when red; post-push run NOT watched
Not run locally: e2e / Playwright / DB suites — GitHub CI runs them on the pushed head (coverage gate runs locally)
Worktree: removed
Main checkout: unchanged (byte-identical)
Session: ended once everything was pushed — CI not watched, nothing merged
```
