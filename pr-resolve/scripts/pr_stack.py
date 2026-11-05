#!/usr/bin/env python3
"""
Map the PR stack a pull request belongs to, and say whether every member is
ready to merge.

A stack is a chain (or tree) of open PRs where a PR's base branch is another
open PR's head branch. Given any member, this walks DOWN to the root (the PR
whose base is the default branch, or an orphaned base) and then collects every
descendant of that root, so siblings that share a parent are included too.

Per member it reports: draft, mergeable, mergeStateStatus (retried while GitHub
is still computing it), behind_by against the CURRENT base tip, unresolved
review threads (paginated, no 100 cap), required checks from the base branch's
rules and their state on the head, failing / pending / skipped check runs, and
a readiness verdict with reasons.

"Ready" (one definition, shared with references/stacked-prs.md):
  not draft · 0 unresolved threads · not CONFLICTING · behind_by == 0 ·
  mergeStateStatus CLEAN/HAS_HOOKS · every required check passing on the head ·
  no failing check runs.
  BLOCKED where the only cause is a missing approval -> "awaiting approval".
  A member whose base is not the default branch is PROVISIONAL: its base usually
  has no rules, and after its parent merges it will need one more sync + CI run.

JSON on stdout, human summary + warnings on stderr.

Usage:
  python3 pr_stack.py --repo octocat/hello-world --pr 845
  python3 pr_stack.py --repo octocat/hello-world --pr 845 --ready   # exit code gate

Exit codes with --ready: 0 all ready · 3 ready except approvals · 1 not ready.
"""

import argparse
import json
import subprocess
import sys
import time
from urllib.parse import quote

LIST_QUERY = """
query($owner:String!, $repo:String!, $cursor:String) {
  repository(owner: $owner, name: $repo) {
    defaultBranchRef { name }
    deleteBranchOnMerge
    mergeCommitAllowed
    squashMergeAllowed
    rebaseMergeAllowed
    pullRequests(states: OPEN, first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url isDraft headRefName baseRefName isCrossRepository
        headRepository { nameWithOwner }
      }
    }
  }
}
"""

DETAIL_QUERY = """
query($owner:String!, $repo:String!, $number:Int!, $cursor:String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      isDraft mergeable mergeStateStatus reviewDecision headRefOid baseRefName
      baseRef { target { oid } }
      reviewThreads(first: 100, after: $cursor) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes { isResolved }
      }
    }
  }
}
"""

CLOSED_PARENT_QUERY = """
query($owner:String!, $repo:String!, $head:String!) {
  repository(owner: $owner, name: $repo) {
    pullRequests(headRefName: $head, states: [MERGED, CLOSED], first: 5,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes { number state isCrossRepository }
    }
  }
}
"""

PASSING = {"success", "neutral", "skipped"}
FAILING = {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"}


def run(args: list[str], allow_fail: bool = False) -> str | None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        if allow_fail:
            return None
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


def graphql(query: str, **variables) -> dict:
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is None:
            continue
        args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    payload = json.loads(run(args))
    if "errors" in payload:
        sys.stderr.write(json.dumps(payload["errors"], indent=2) + "\n")
        raise SystemExit(1)
    return payload["data"]


def rest(path: str) -> dict | list | None:
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout) if result.stdout.strip() else None
    if "404" not in result.stderr and "Not Found" not in result.stderr and "not protected" not in result.stderr:
        sys.stderr.write(
            f"WARNING: gh api {path} failed ({result.stderr.strip()[:200]}) — "
            "treating as empty; readiness may be judged on merge state alone\n"
        )
    return None


def list_open_prs(owner: str, repo: str) -> tuple[dict, list[dict]]:
    settings: dict = {}
    nodes: list[dict] = []
    cursor = None
    while True:
        data = graphql(LIST_QUERY, owner=owner, repo=repo, cursor=cursor)["repository"]
        settings = {
            "default_branch": data["defaultBranchRef"]["name"],
            "delete_branch_on_merge": data["deleteBranchOnMerge"],
            "allow_merge_commit": data["mergeCommitAllowed"],
            "allow_squash_merge": data["squashMergeAllowed"],
            "allow_rebase_merge": data["rebaseMergeAllowed"],
        }
        page = data["pullRequests"]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return settings, nodes
        cursor = page["pageInfo"]["endCursor"]


def pr_detail(owner: str, repo: str, number: int) -> dict:
    unresolved = 0
    total = 0
    cursor = None
    first: dict | None = None
    while True:
        pr = graphql(DETAIL_QUERY, owner=owner, repo=repo, number=number, cursor=cursor)["repository"][
            "pullRequest"
        ]
        if first is None:
            first = pr
        threads = pr["reviewThreads"]
        total = threads["totalCount"]
        unresolved += sum(1 for t in threads["nodes"] if not t["isResolved"])
        if not threads["pageInfo"]["hasNextPage"]:
            break
        cursor = threads["pageInfo"]["endCursor"]
    first["unresolved"] = unresolved
    first["thread_total"] = total
    return first


def behind_by(owner: str, repo: str, base_oid: str | None, head_oid: str) -> int | None:
    if not base_oid:
        return None
    cmp = rest(f"repos/{owner}/{repo}/compare/{base_oid}...{head_oid}")
    return None if cmp is None else int(cmp.get("behind_by", 0))


def base_rules(owner: str, repo: str, branch: str) -> dict:
    enc = quote(branch, safe="")
    contexts: set[str] = set()
    strict = False
    approvals = 0
    extra_unattributed = False
    for rule in rest(f"repos/{owner}/{repo}/rules/branches/{enc}") or []:
        params = rule.get("parameters") or {}
        if rule.get("type") == "required_status_checks":
            contexts.update(c["context"] for c in params.get("required_status_checks", []))
            strict = strict or bool(params.get("strict_required_status_checks_policy"))
        if rule.get("type") == "pull_request":
            approvals = max(approvals, int(params.get("required_approving_review_count") or 0))
            extra_unattributed = extra_unattributed or bool(
                params.get("require_extra_approval_for_unattributed_changes")
            )
    protection = rest(f"repos/{owner}/{repo}/branches/{enc}/protection")
    if protection and "required_status_checks" in protection:
        rsc = protection["required_status_checks"] or {}
        contexts.update(rsc.get("contexts") or [])
        contexts.update(c["context"] for c in rsc.get("checks") or [])
        strict = strict or bool(rsc.get("strict"))
    if protection and protection.get("required_pull_request_reviews"):
        approvals = max(
            approvals, int(protection["required_pull_request_reviews"].get("required_approving_review_count") or 0)
        )
    return {
        "required_contexts": sorted(contexts),
        "strict": strict,
        "required_approvals": approvals,
        "extra_approval_for_unattributed": extra_unattributed,
        "has_rules": bool(contexts) or approvals > 0 or strict,
    }


def head_checks(owner: str, repo: str, sha: str) -> dict[str, str]:
    states: dict[str, tuple[int, str]] = {}
    out = run(
        [
            "gh", "api", "--paginate", f"repos/{owner}/{repo}/commits/{sha}/check-runs?per_page=100",
            "--jq", ".check_runs[] | {id, name, status, conclusion}",
        ],
        allow_fail=True,
    ) or ""
    for line in out.splitlines():
        if not line.strip():
            continue
        cr = json.loads(line)
        if cr["status"] != "completed":
            state = "pending"
        else:
            state = (cr.get("conclusion") or "pending").lower()
        prev = states.get(cr["name"])
        if prev is None or cr["id"] > prev[0]:
            states[cr["name"]] = (cr["id"], state)
    result = {name: state for name, (_, state) in states.items()}
    combined = rest(f"repos/{owner}/{repo}/commits/{sha}/status") or {}
    for st in combined.get("statuses", []):
        mapped = {"success": "success", "pending": "pending"}.get(st["state"], "failure")
        result[st["context"]] = mapped
    return result


def assess(owner: str, repo: str, node: dict, default_branch: str) -> dict:
    # mergeStateStatus is computed lazily: UNKNOWN right after a push, and a
    # BEHIND that outlives the sync push. behind_by from the compare API is the
    # ground truth; refetch until the two agree (max ~30 s).
    for attempt in range(7):
        detail = pr_detail(owner, repo, node["number"])
        base_oid = (detail.get("baseRef") or {}).get("target", {}).get("oid")
        behind = behind_by(owner, repo, base_oid, detail["headRefOid"])
        settling = (
            "UNKNOWN" in (detail["mergeStateStatus"], detail["mergeable"])
            or (detail["mergeStateStatus"] == "BEHIND" and behind == 0)
        )
        if not settling or attempt == 6:
            break
        time.sleep(5)
    rules = base_rules(owner, repo, detail["baseRefName"])
    checks = head_checks(owner, repo, detail["headRefOid"])

    required = []
    for ctx in rules["required_contexts"]:
        state = checks.get(ctx, "missing")
        required.append({"context": ctx, "state": state})
    failing = sorted(n for n, s in checks.items() if s in FAILING)
    pending = sorted(n for n, s in checks.items() if s == "pending")
    skipped = sorted(n for n, s in checks.items() if s == "skipped")

    reasons: list[str] = []
    approval_only: list[str] = []
    if detail["isDraft"]:
        reasons.append("draft")
    if detail["unresolved"]:
        reasons.append(f"{detail['unresolved']} unresolved review thread(s)")
    if detail["mergeable"] == "CONFLICTING" or detail["mergeStateStatus"] == "DIRTY":
        reasons.append(f"conflicts with {detail['baseRefName']}")
    if behind:
        reasons.append(f"behind {detail['baseRefName']} by {behind} commit(s) — sync with its own base")
    for r in required:
        if r["state"] not in PASSING:
            reasons.append(f"required check '{r['context']}' is {r['state']}")
    if failing:
        reasons.append("failing checks: " + ", ".join(failing))
    if pending:
        reasons.append("pending checks: " + ", ".join(pending))
    state = detail["mergeStateStatus"]
    if state == "UNKNOWN":
        reasons.append("GitHub has not computed the merge state yet — rerun")
    elif state == "BEHIND" and not behind:
        reasons.append("merge state still reads BEHIND though behind_by is 0 — rerun in a minute")
    elif state == "BLOCKED" and not reasons:
        if detail["reviewDecision"] in ("REVIEW_REQUIRED", "CHANGES_REQUESTED"):
            approval_only.append(f"blocked on review ({detail['reviewDecision']})")
        elif rules["extra_approval_for_unattributed"]:
            approval_only.append("blocked on an approval for commits whose author email is not linked to GitHub")
        else:
            reasons.append("BLOCKED by a rule this script cannot see (rulesets, code owners, unattributed commits)")
    elif state == "UNSTABLE" and not failing:
        reasons.append("UNSTABLE — a non-required check is not passing")

    provisional = detail["baseRefName"] != default_branch
    verdict = "ready" if not reasons and not approval_only else ("awaiting approval" if not reasons else "not ready")
    return {
        "number": node["number"],
        "title": node["title"],
        "url": node["url"],
        "head_ref": node["headRefName"],
        "base_ref": detail["baseRefName"],
        "head_sha": detail["headRefOid"],
        "is_draft": detail["isDraft"],
        "is_fork": node["isCrossRepository"],
        "mergeable": detail["mergeable"],
        "merge_state": state,
        "behind_by": behind,
        "review_decision": detail["reviewDecision"],
        "unresolved_threads": detail["unresolved"],
        "thread_total": detail["thread_total"],
        "base_rules": rules,
        "required_checks": required,
        "failing_checks": failing,
        "pending_checks": pending,
        "skipped_checks": skipped,
        "provisional": provisional,
        "verdict": verdict,
        "reasons": reasons + approval_only,
    }


def build_stack(target: int, prs: list[dict], default_branch: str) -> tuple[list[dict], dict, str | None]:
    by_number = {p["number"]: p for p in prs}
    if target not in by_number:
        sys.stderr.write(
            f"PR #{target} is not open. If it merged as part of a stack, confirm each member's head is on "
            f"{default_branch}: gh api repos/OWNER/REPO/compare/{default_branch}...<head sha> → ahead_by 0\n"
        )
        raise SystemExit(1)
    owners = {p["headRefName"]: p for p in prs if not p["isCrossRepository"]}

    root = by_number[target]
    seen = {root["number"]}
    while root["baseRefName"] != default_branch and root["baseRefName"] in owners:
        parent = owners[root["baseRefName"]]
        if parent["number"] in seen:
            sys.stderr.write("WARNING: base chain loops — stopping the walk.\n")
            break
        seen.add(parent["number"])
        root = parent
    orphan = root["baseRefName"] if root["baseRefName"] != default_branch else None

    children: dict[int, list[int]] = {}
    order: list[dict] = []
    depth = {root["number"]: 0}
    queue = [root]
    visited = {root["number"]}
    while queue:
        pr = queue.pop(0)
        order.append(pr)
        if pr["isCrossRepository"]:
            continue
        kids = sorted(
            (p for p in prs if p["baseRefName"] == pr["headRefName"] and p["number"] not in visited),
            key=lambda p: p["number"],
        )
        children[pr["number"]] = [k["number"] for k in kids]
        for kid in kids:
            visited.add(kid["number"])
            depth[kid["number"]] = depth[pr["number"]] + 1
            queue.append(kid)
    for pr in order:
        pr["_depth"] = depth[pr["number"]]
    return order, children, orphan


def merge_plan(owner: str, repo: str, stack: list[dict], children: dict, settings: dict, orphan: str | None) -> list[str]:
    default = settings["default_branch"]
    plan: list[str] = []
    if orphan:
        plan.append(
            f"Root #{stack[0]['number']} targets '{orphan}', which no open PR owns. Retarget it first: "
            f"gh api -X PATCH repos/{owner}/{repo}/pulls/{stack[0]['number']} -f base={default}"
        )
    method = "merge commit" if settings["allow_merge_commit"] else "squash" if settings["allow_squash_merge"] else "rebase"
    for step, pr in enumerate(stack, start=1):
        into = default if pr["_depth"] == 0 and not orphan else f"{default} (after retarget)"
        line = f"{step}. Merge #{pr['number']} into {into} with a {method}."
        if method != "merge commit" and children.get(pr["number"]):
            line += " Children will show the parent's commits again until they merge the default branch in."
        plan.append(line)
        for kid in children.get(pr["number"], []):
            if settings["delete_branch_on_merge"]:
                plan.append(
                    f"   → GitHub retargets #{kid} to {default} when '{pr['head_ref']}' is deleted on merge; "
                    f"confirm: gh pr view {kid} --json baseRefName"
                )
            else:
                plan.append(
                    f"   → delete_branch_on_merge is OFF: retarget #{kid} before merging it: "
                    f"gh api -X PATCH repos/{owner}/{repo}/pulls/{kid} -f base={default}"
                )
            plan.append(
                f"   → #{kid} is then behind {default} by the merge commit: "
                f"gh api -X PUT repos/{owner}/{repo}/pulls/{kid}/update-branch -f expected_head_sha=<head sha>, "
                f"check CI once (gh pr checks {kid}), then merge it"
            )
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Map a PR stack and check every member is ready to merge.")
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--pr", required=True, type=int, help="Any PR in the stack")
    parser.add_argument("--ready", action="store_true", help="Exit non-zero unless every member is ready")
    args = parser.parse_args()
    owner, name = args.repo.split("/", 1)

    settings, prs = list_open_prs(owner, name)
    default = settings["default_branch"]
    order, children, orphan = build_stack(args.pr, prs, default)
    stack = [assess(owner, name, pr, default) | {"_depth": pr["_depth"]} for pr in order]

    warnings: list[str] = []
    if orphan:
        closed = graphql(CLOSED_PARENT_QUERY, owner=owner, repo=name, head=orphan)["repository"]["pullRequests"]["nodes"]
        owner_pr = next((c for c in closed if not c["isCrossRepository"]), None)
        hint = f" (#{owner_pr['number']} is {owner_pr['state']})" if owner_pr else ""
        warnings.append(f"root #{stack[0]['number']} targets '{orphan}', which no open PR owns{hint} — retarget it to {default}")
    for pr in stack:
        if pr["provisional"]:
            warnings.append(
                f"#{pr['number']} targets '{pr['base_ref']}', not {default}: its CLEAN is provisional — "
                f"after its parent merges it needs one more sync with {default} and a CI run"
            )
        if pr["skipped_checks"]:
            warnings.append(f"#{pr['number']} has SKIPPED jobs (full suites may not have run): " + ", ".join(pr["skipped_checks"]))
        if pr["base_rules"]["extra_approval_for_unattributed"]:
            warnings.append(f"#{pr['number']}: base rules demand an extra approval for unattributed commits")

    plan = merge_plan(owner, name, stack, children, settings, orphan)
    for pr in stack:
        pr["depth"] = pr.pop("_depth")
        pr["children"] = children.get(pr["number"], [])

    sys.stderr.write(f"Stack for #{args.pr} in {owner}/{name} (default branch {default}), root first:\n")
    for pr in stack:
        indent = "  " * pr["depth"]
        sys.stderr.write(
            f"  {indent}#{pr['number']} {pr['head_ref']} → {pr['base_ref']}  "
            f"[{pr['merge_state']}/{pr['mergeable']}, behind {pr['behind_by']}, "
            f"{pr['unresolved_threads']}/{pr['thread_total']} unresolved]  {pr['verdict'].upper()}\n"
        )
        for reason in pr["reasons"]:
            sys.stderr.write(f"  {indent}    - {reason}\n")
    sys.stderr.write(
        f"Repo: delete_branch_on_merge={settings['delete_branch_on_merge']} merge={settings['allow_merge_commit']} "
        f"squash={settings['allow_squash_merge']} rebase={settings['allow_rebase_merge']}\n"
    )
    for w in warnings:
        sys.stderr.write(f"WARNING: {w}\n")
    sys.stderr.write("Merge plan:\n" + "\n".join(f"  {p}" for p in plan) + "\n")

    json.dump(
        {
            "repo": args.repo,
            "target_pr": args.pr,
            "settings": settings,
            "orphan_base": orphan,
            "is_stack": len(stack) > 1 or orphan is not None,
            "order": [p["number"] for p in stack],
            "stack": stack,
            "merge_plan": plan,
            "warnings": warnings,
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")

    if args.ready:
        verdicts = {p["verdict"] for p in stack}
        if verdicts == {"ready"}:
            raise SystemExit(0)
        if verdicts <= {"ready", "awaiting approval"}:
            raise SystemExit(3)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
