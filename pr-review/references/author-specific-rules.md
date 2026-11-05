# Author-specific review rules

Load from `pr-review` step 2 when the PR author is a bot. Everything in `SKILL.md` still applies; these add to it.

## Claude-authored PRs (when author is claude[bot])

- Claude-generated PRs should be reviewed with the same rigor as human-authored PRs — do not assume the code is correct just because it compiles or CI is green.
- Pay extra attention to hallucinated APIs, non-existent function signatures, or imports from packages that aren't actually dependencies.
- Check that the PR doesn't introduce patterns that violate project conventions (e.g. raw framework primitives instead of the repo's wrappers, console.log instead of the structured logger).
- Verify that any tests added by Claude actually test meaningful behavior, not just trivially-true assertions or mocked-out logic.
- Look for over-engineered solutions — Claude often adds unnecessary abstraction, speculative config, or extra error handling that isn't needed.
- If the PR modifies CI/workflow files, apply the same SHA-pinning rules as for Dependabot workflow bumps.

## Dependabot PRs (when author is dependabot[bot])

- If the PR bumps a GitHub Action (`.github/workflows/*.yml`), verify the action is pinned to a full-length commit SHA with a `# vX.Y.Z` version comment - never a mutable tag. An unpinned tag can trip security alerts, and Dependabot cannot re-bump a SHA pin without the version comment.
- If the repo generates workflow copies from a source of truth, flag edits to generated copies instead of the source.
- For npm dependency bumps, check for major version jumps that introduce breaking changes. Look at the dependency's CHANGELOG or release notes for API removals, peer dependency changes, or Node engine requirement shifts.
- Check that `package-lock.json` / `pnpm-lock.yaml` changes are consistent with the `package.json` version bump - a partial lockfile update will break CI.
- For runtime-critical deps (SDKs, runtime packages), verify the new version is compatible with the deployed runtime version.
- Dependabot PRs that only touch lockfiles or bump patch versions are usually safe to approve if CI is green, but still verify no transitive dependency introduces a security or contract issue.
