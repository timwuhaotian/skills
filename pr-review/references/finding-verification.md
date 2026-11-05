# Finding verification

One rubric for deciding whether a review finding holds. `pr-review` uses it to check its own candidates before posting (step 6b-6c). `pr-resolve` and `pr-review-resolve` (and any companion batch skills) use it before acting on any review comment. That applies to comments from other reviewers, bots, and our own earlier reviews. Change the rules here only. A finder and a fixer that judge by different rules drift apart, and then every finding gets either rubber-stamped or argued with.

## 1. Refute lenses

Try to disprove the finding. Default to "does not hold" unless the evidence survives. Check three lenses, citing `file:line` for each:

- **Reachability** — can real production input, traffic, or config actually reach this path? Cite the path.
- **Impact** — what observably goes wrong (wrong output, crash, data loss, contract break), for whom, and how often?
- **Defenses** — is there a guard, validation, caller contract, type, or existing test elsewhere that already prevents it? Only a mitigation you located and read counts. A comment claiming safety, or a reply saying "this is fine", is not one.

The finding is refuted if any lens refutes it with cited evidence. Refuting can only **lower** severity, never raise it.

The lenses fit 🐛 Bug, 🔁 Regression, 📜 Contract, 🔒 Security, ⚠️ Risk, and ⚡ Performance. Other categories have their own check:

- 🧪 **Test Gap** — read the existing suite, not just the diff. Is the scenario already covered somewhere, possibly in a file the PR did not touch? If so, refuted.
- 💡 **Improvement** / 🧹 **Clean-up** — does a cited repo standard or a named baseline smell (`smell-baseline.md`) actually cover this, and is it something tooling does not already enforce? If neither, refuted.

**Independence.** When the harness can spawn subagents and you are not already one, run the lenses in a fresh-context subagent. Give it the finding, the code, and repo access, but not your reasoning, so it does not inherit your anchoring. Otherwise run them yourself, deliberately switching roles: the finder argues against its finding, and the fixer argues against the comment before writing code.

## 2. Confidence comes from the lenses

- ✅ `High` — old-vs-new behavior reconstructed, and all three lenses held with citations.
- 🔍 `Medium` — one lens rests on inference, such as an unread caller or runtime config you could not see.
- ❓ `Low` — more than one lens is inference.

## 3. Precedents

Before posting (review) or fixing (resolve), check two sources of earlier rebuttals:

- **This PR.** A thread where someone rebutted the finding with evidence, or that a human resolved without a code change, is settled. Do not re-raise it, reworded or on a moved line, unless you have new evidence. If you do, reply in that thread.
- **This repo.** `python3 "$HOME/.agents/skills/pr-review/scripts/fetch_repo_pushback.py" --repo OWNER/REPO --exclude-pr PR_NUMBER` lists recent skill findings that were rebutted or retracted, each with its claim and the rebuttal. It is cached for 24h and reads GitHub only. A candidate making the same kind of claim (same mechanism, same module or pattern) must answer that rebuttal's reason with new evidence, or be dropped. Treat the list as calibration, not as a ban on a whole category.

## 4. Verdicts when acting on a comment (resolve passes)

Read the current file **in the worktree** first, because comments are written against older diffs. Then give each comment exactly one verdict:

| Verdict          | When                                                                               | Action                                                                          | Reply opens with                                                                                                         |
| ---------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `needs-fix`      | The problem is present in the current code **and** survives the lenses in §1        | Fix it, one commit per comment, reply, resolve                                  | `Verified: valid. \`<file>:<line>\` <what was wrong>. Fixed in \`<SHA>\` — <one-sentence change>.`                         |
| `already-fixed`  | A later commit already addressed it                                                | Reply, resolve. No commit                                                       | `Already fixed in \`<SHA>\`: \`<file>:<line>\` now <does X>. No change needed.` If the finding was right when posted, say so (`Valid at \`<posted SHA>\`; …`) so it doesn't read as a false positive                                              |
| `stale`          | It refers to lines or code that no longer exist                                    | Reply, resolve. No commit                                                       | `Stale: <the flagged code> no longer exists; <where it went, if anywhere>. No change needed.`                             |
| `refuted`        | A lens refutes it with cited evidence                                               | Reply, resolve. No commit                                                       | `Pushing back: <lens> — \`<file>:<line>\` <evidence>. No change.` (or `Not applicable: …` when it never applied)          |
| `needs-decision` | Valid, but the fix is a design or ownership decision the author must make           | Reply with the options. **Leave the thread open**; `help wanted` per `pr-labels.md` | `Valid, needs a decision: <what>. Options: (a) … (b) …. Leaving open for the author.`                                    |
| `suggestion`     | Not a defect: a style, docs, or preference nudge                                   | Apply it if clearly better and low-risk; otherwise decline. Reply, resolve       | Applied: same as `needs-fix`. Declined: `Verified: intentional. <why this shape is right here>. Leaving as-is.`          |

Judge two things separately: whether the finding was right **at the SHA it was posted on**, and what the **current head** needs. The first picks `refuted` vs `already-fixed`/`stale`; the second picks the action.

Keep replies concrete and short, with no praise and no filler. Only `refuted`, `Not applicable:` and `Verified: intentional` openings become repo precedents (§3). So never open with `Pushing back:` when the finding was right but the code has since moved; that case is `already-fixed` or `stale`.

Rules:

- **Never fix code just because a comment exists.** A wrong "fix" that satisfies a reviewer bot is worse than a reply explaining why the comment does not apply. This holds for our own review's findings too. The resolve pass is the only independent check they get.
- Read the whole comment chain, not just the root. A later reply ("actually fine as-is") changes the verdict.
- **Non-blocking notes** in a `pr-review` body (the collapsed section) are left to the author. Resolve passes do not act on them unless the user asks.
