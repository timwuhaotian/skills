# PR Labels

Single source of truth for labelling a PR after a review, a resolve pass, or when opening one from a requirement. `pr-review`, `pr-review-resolve`, and `pr-resolve` (and any companion skills) all point here — change the rules in this file only.

Labels record the **conclusion** of the work, so a reader of the PR list sees the verdict without opening the PR. Apply them after the review is submitted / the push is done, never before.

## Vocabulary

| Label            | Apply when                                                                                                                                                                                                                                          | Remove when                                                                             |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `do not merge`   | Merging as-is can cause **immediate production harm**: downtime, data loss/corruption, an auth bypass or secret leak, a crash path on a hot path, a migration or deploy-order dependency that breaks the live system. Needs a 🔴 Critical finding at ✅ High/🔍 Medium confidence, or a stated deploy-order hazard. Also when the author's own PR body says "do not merge". | The blocking finding is fixed **and** verified in this round, or a human says so.        |
| `help wanted`    | A human is needed: a 🟠 High+ finding at ❓ Low confidence, a design decision the author must make, a conflict or red check you could not resolve, a part of the change you could not verify (no spec, no env, no access).                          | The open question is answered or the blocker is gone.                                   |
| `bug`            | At least one 🐛 Bug / 🔁 Regression / 📜 Contract finding that is real and not yet fixed. On open from a requirement: the requirement is a fix.                                                                                                              | All such findings are fixed or rebutted.                                                |
| `security`       | At least one 🔒 Security finding is real and not yet fixed.                                                                                                                                                                                         | The finding is fixed.                                                                   |
| `enhancement`    | The PR adds or changes capability, **or** the only findings are 💡 Improvement / 🧹 Clean-up suggestions (nothing blocking). On open from a requirement: the requirement is a feature.                                                                        | Never remove automatically — it describes the PR, not a blocker.                        |
| `breaking change`| The diff drops or renames a public contract: API surface, event payload, header/metadata key, env var, config schema, exported symbol — and a consumer is not updated in the same change.                                                         | The consumer is updated in the PR or the contract is restored.                          |
| `needs tests`    | A real 🧪 Test Gap finding on a risky changed behavior (or an existing test was steered around the new code).                                                                                                                                      | The tests land.                                                                         |
| `performance`    | At least one ⚡ Performance finding is real and not yet fixed.                                                                                                                                                                                      | The finding is fixed.                                                                   |

Rules of thumb:

- **Fewest labels that are true.** Most PRs get 0-2. A clean approved review adds nothing (do not add an "approved" or "lgtm" label — the review state already says that). A pure `enhancement` PR with no findings only gets `enhancement` if it adds capability.
- **`do not merge` is a hold, not an opinion.** Do not use it for style, ordinary bugs the author can fix in review, or low-confidence hunches (that is `help wanted`). Do not inflate severity to justify it. If you add it, the review body must say why in one line.
- A finding that makes you add `do not merge` should also be 🔴 Critical in the findings table; if the table and the label disagree, one of them is wrong.
- Pick labels from the **final** findings table (after Final QC removed false positives), not from first impressions.
- **Non-blocking notes never drive a label.** Notes in a review body's collapsed *Non-blocking notes* section (🔵 Low findings routed out of inline threads) add no `bug`, `needs tests`, or other label. Only the inline findings table counts.

## Repo label names

Repos name labels differently (`help wanted` is GitHub's default; some repos use "help needed"). The helper resolves each canonical name above against the repo's real labels through aliases (`help needed` / `help wanted`, `do-not-merge` / `DO NOT MERGE`, `feature` → `enhancement`, …), case- and punctuation-insensitive. Always go through the helper — never hand-roll `gh pr edit --add-label`, which fails the whole call on a label that does not exist.

```bash
python3 "$HOME/.agents/skills/pr-review/scripts/apply_pr_labels.py" \
  --repo OWNER/REPO --pr PR_NUMBER \
  --add "do not merge" --add bug \
  --remove "help wanted"
```

- Labels the repo does not have are **skipped and reported** (`missing`), not created. The one exception: pass `--create-missing` for `do not merge` — a safety hold that silently fails to apply is worse than a new label. Never create any other label.
- Output is one JSON object (`applied`, `removed`, `already`, `missing`, `errors`) on stdout. Labelling is **never fatal**: a permission error or rate limit prints a warning, exits 0, and the review/resolve outcome stands. Put what happened in the report.
- `--dry-run` prints the plan without touching GitHub.
- Idempotent: re-applying a label that is already on the PR is a no-op, so re-reviews at the same head are safe.

## Provenance line in the review body

When a review adds or changes labels, end the review body with one line so the reason travels with the PR:

```markdown
**Labels** `do not merge` — migration drops `users.email` before the reader is deployed · `bug`
```

When a later round removes a label it recorded, say so on the same line: `**Labels** removed \`bug\` — fixed in \`42796c53\``.

`pr-review-resolve` / `pr-resolve` read the most recent such line to know which labels a review added and why, so they can remove a label once its reason is fixed. A label with no provenance (applied by a human, or by an earlier tool) is **never removed automatically** — leave it and say so in the report.

## Re-evaluation after a resolve pass

After fixes are pushed, recompute the label set from what is *still true*:

- Remove `bug` / `security` / `performance` / `needs tests` / `breaking change` / `do not merge` only when the finding behind it is fixed **on the current head** (by anyone, in this round or earlier — verify it from the code, not from the thread's resolved state) or was rebutted in-thread — and, per the provenance rule above, only if a review body line records it.
- Remove `help wanted` when this round answered the open question; **add** it when this round ended with a blocked conflict, a red check you could not fix, or a thread left open for a human decision.
- Never wait for CI to decide a label. A check that is red and unfixed → `help wanted`; a pending run → nothing.
- Never remove `do not merge` on the strength of CI going green; green CI is not evidence that downtime risk is gone.
