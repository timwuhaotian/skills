---
name: burn
description: >-
  Use when the user wants to comprehensively audit a codebase (or part of one)
  across multiple dimensions — code quality, UI/UX bugs, performance risks,
  code design & architecture, frontend, backend API, database security, and
  general security — and then fix everything found, all using parallel agent
  swarms. Triggers on phrases like "audit and fix", "comprehensive review and
  optimize", "swarm audit", "burn the codebase", "find and fix all issues",
  "全面审计修复", "审计代码质量", "review and repair codebase". Orchestrates
  a two-phase pipeline: Phase 1 dispatches one agent per audit dimension to
  produce a scored findings report; Phase 2 dispatches fix-agents grouped by
  independence to resolve every issue. Works in full-project or scoped
  (feature/page/module/directory) mode.
user-invocable: true
argument-hint: "[scope: feature, page, component, directory, or empty for full project]"
---

# Burn

A two-phase, parallel-agent pipeline that **audits** a codebase across eight
core quality dimensions and then **fixes** every issue found — both phases
powered by agent swarms.

```
 Phase 1: AUDIT SWARM (8 agents)                Phase 2: FIX SWARM (3-8 agents)

 ┌──────────┐  ┌──────────┐                     ┌──────────┐  ┌──────────┐
 │ Agent A  │  │ Agent B  │   ┌──────────┐      │ Agent 1  │  │ Agent 2  │
 │ Code     │  │ UI/UX    │   │ Synth &  │      │ Fix P0   │  │ Fix P1   │
 │ Quality  │  │ Bugs     │───│ Dedup &  │─────>│ bundle   │  │ bundle   │
 └──────────┘  └──────────┘   │ Priorit- │      └──────────┘  └──────────┘
 ┌──────────┐  ┌──────────┐   │ ize      │      ┌──────────┐  ┌──────────┐
 │ Agent C  │  │ Agent D  │   │          │      │ Agent 3  │  │ Agent 4  │
 │ Perform- │  │ Design & │   └──────────┘      │ Fix arch │  │ Fix DB   │
 │ ance     │  │ Arch     │                      └──────────┘  └──────────┘
 ┌──────────┐  ┌──────────┐                                    ...
 │ Agent E  │  │ Agent F  │
 │ Security │  │ Frontend │
 └──────────┘  └──────────┘
 ┌──────────┐  ┌──────────┐
 │ Agent G  │  │ Agent H  │
 │ Backend  │  │ Database │
 │ API      │  │ Security │
 └──────────┘  └──────────┘
```

---

## Phase 0 — Setup & Scoping (do this first, always)

### 0.1 Determine scope

If the user provided an argument (a feature name, page route, component, file,
or directory), treat that as the audit scope. If no argument was given:

1. Explore the project structure to understand the layout.
2. Identify the main source directories (`src/`, `app/`, `pages/`, `lib/`,
   `components/`, etc.).
3. Estimate file count and total LoC.
4. If the project is very large (> 300 source files or > 30k LoC), **ask the
   user to narrow the scope** to a specific feature/page/module. Auditing
   10k+ files in one pass produces shallow, unreliable results.

### 0.2 Gather project context

Read or skim these before dispatching agents (so you can pass real context
into each agent prompt — agents start with zero context):

- README, AGENTS.md, CLAUDE.md, package.json / go.mod / Cargo.toml
- Build & test commands (from package.json scripts, Makefile, etc.)
- Linting / type-check setup (eslint, tsc, biome, ruff, etc.)
- Testing framework & how to run tests
- Key architectural decisions / patterns
- Database setup (ORM, schema files, migration scripts, seed data)
- API structure (REST/GraphQL/RPC conventions, route handlers, middleware)
- Frontend stack (framework, component library, state management, CSS approach)

Record:
- **Project type**: language(s), framework(s), frontend/backend/fullstack
- **Test command**: exact command to run tests (e.g. `npm test`, `pytest`)
- **Lint command**: exact command (e.g. `npm run lint`)
- **Type-check command**: exact command (e.g. `npx tsc --noEmit`)
- **Build command**: exact command (e.g. `npm run build`)
- **Database**: type (Postgres/MongoDB/MySQL/SQLite), ORM, schema location
- **API style**: REST / GraphQL / tRPC / RPC, route directory layout

### 0.3 Establish baseline

Run the test / lint / type-check / build commands **before** dispatching
agents. Record the current state (pass/fail, warning counts). This baseline
is the acceptance criterion for Phase 2 — after fixes, everything should be
at least as green as before, ideally greener.

---

## Phase 1 — Audit Swarm (parallel dispatch)

Dispatch **one agent per dimension**, all in parallel. Each agent is
read-only — it reviews, finds issues, and reports back. It does NOT modify
code.

Every audit agent receives in its prompt:
1. The project root path.
2. The scope (which files/directories to focus on).
3. The project's tech stack and conventions.
4. How to run lint / tests / type-check / build (so it can verify issues).
5. Its specific dimension's checklist (below).
6. The **required output format** (below).

### Audit Agent A — Code Quality

**Focus**: correctness, type safety, error handling, dead code, naming,
consistency, lint violations, anti-patterns.

Checklist:
- Type errors, unsafe casts, `any`/`unknown` abuse, missing null checks
- Unhandled promise rejections, swallowed errors, missing try/catch
- Dead code: unused imports, unreachable branches, commented-out blocks
- Naming: inconsistent casing, misleading names, non-descriptive identifiers
- Magic numbers / hard-coded strings that should be constants or config
- Duplicate code blocks (copy-paste that should be extracted)
- Lint rule violations (run the project's linter, review output)
- Inconsistent coding style vs. project conventions (e.g. semicolons, quotes)
- Race conditions in async code, missing cleanup (event listeners, timers)
- Off-by-one, incorrect comparison operators, wrong boolean logic

### Audit Agent B — UI/UX Bugs

**Focus**: accessibility, responsiveness, interaction edge cases, error
states, loading states, empty states, i18n, keyboard navigation.

Checklist:
- ARIA: missing labels, roles, states on interactive elements
- Keyboard: focus traps, illogical tab order, non-keyboard-accessible actions
- Contrast ratios below WCAG AA (4.5:1 text, 3:1 large text / UI components)
- Semantic HTML: `<div onClick>` instead of `<button>`, broken heading
  hierarchy, missing `<nav>`/`<main>`/`<footer>` landmarks
- Responsive: fixed widths that break on mobile, overflow, horizontal scroll
- Forms: missing labels, no validation feedback, no required indicators
- Loading states: missing skeletons/spinners, flash of empty content
- Empty states: no "no data" message, no actionable guidance
- Error states: no error boundary, no retry option, raw error messages shown
- i18n: hard-coded user-facing strings, missing translations
- Interaction bugs: double-click, no disabled state during loading, optimistic
  update rollback failures

### Audit Agent C — Performance Risks

**Focus**: render performance, bundle size, query efficiency, memory leaks,
network waterfall, unnecessary re-renders, missing optimization.

Checklist:
- React/View layer: unnecessary re-renders, missing `memo`/`useMemo`/`useCallback`
  where profiling shows churn, missing `key` in lists
- Expensive operations in render path: sort/filter/map on large arrays per render
- Animations on layout properties (`width`/`height`/`top`/`left`) instead of
  `transform`/`opacity`
- Missing lazy loading: images, routes, heavy components loaded eagerly
- Bundle: importing entire libraries when tree-shakeable alternatives exist
  (`import _ from 'lodash'` vs `import debounce from 'lodash/debounce'`)
- N+1 queries, missing DB indexes (check slow query patterns), missing pagination
- Missing caching for repeated expensive computations or API calls
- Memory leaks: event listeners not removed, intervals not cleared, growing maps
- Network: waterfall requests that could be parallelized, missing prefetch
- Large assets unoptimized (uncompressed images, unminified JS, missing srcset)

### Audit Agent D — Code Design & Architecture

**Focus**: coupling, cohesion, separation of concerns, SOLID, modularity,
dependency direction, abstraction level, dead abstractions, circular deps.

Checklist:
- Circular dependencies between modules / packages
- God objects/components: files doing too much (> 300 LoC, multiple
  responsibilities)
- Leaky abstractions: internal implementation details exposed through public API
- Wrong abstraction level: business logic in UI components, UI concerns in
  data layer
- Tight coupling: modules that depend on concrete implementations instead of
  interfaces, making unit testing painful
- Shotgun surgery: a single conceptual change requires editing many files
- Dead abstractions: interfaces with one implementation, wrappers that add
  no value
- Missing error boundaries / circuit breakers at architecture level
- Configuration scattered across files instead of centralized
- Inconsistent patterns: two modules solving the same problem differently
- Dependency direction violations (UI importing from data layer the wrong way,
  utilities importing from domain layer, etc.)

### Audit Agent E — Security (General)

**Focus**: injection, authentication/authorization bypass, data exposure,
secrets, dependency vulnerabilities, unsafe deserialization.

Checklist:
- SQL/NoSQL injection: raw query construction with user input
- XSS: `dangerouslySetInnerHTML`, unescaped user input in templates
- Auth: missing route guards, IDOR (insecure direct object reference),
  privilege escalation paths
- Secrets: hard-coded API keys / passwords / tokens in source
- Sensitive data exposure: PII in logs, passwords in error messages, missing
  HTTPS enforcement
- Insecure deserialization: `JSON.parse` on untrusted input without validation
- CORS misconfiguration: overly permissive origins
- Dependency vulnerabilities: outdated packages with known CVEs (run
  `npm audit` / `pip-audit` / `cargo audit`)
- Missing rate limiting on sensitive endpoints
- Insecure defaults: debug mode in production config, default credentials

### Audit Agent F — Frontend

**Focus**: component architecture, state management, routing, build/bundle
config, design system adherence, hydration/SSR correctness, client-side data
fetching patterns.

Checklist:
- **Component boundaries**: components that mix data-fetching, business logic,
  and presentation in one file; missing separation between container and
  presentational components
- **State management**: prop drilling beyond 2 levels, global state used for
  local concerns, missing context where appropriate, state duplication
  (same data in multiple stores)
- **Routing**: missing loading/error boundaries per route, unprotected routes
  that should require auth, missing redirects, catch-all 404 handling
- **SSR / hydration**: hydration mismatches, client-only code running on
  server (`window` / `document` access without guard), missing `"use client"`
  or equivalent directive where needed
- **Data fetching**: missing suspense/streaming, fetch-on-render waterfalls
  (can be parallelized), no stale-while-revalidate, missing error retry on
  fetch failure, uncancelled requests on unmount
- **Bundle**: client-side imports of server-only code (e.g. importing Mongoose
  models into a client component), missing code-splitting on heavy routes
- **Design system**: components bypassing the design system (hard-coded styles
  instead of tokens), inconsistent spacing/typography vs. design tokens
- **Forms**: uncontrolled/controlled mixing without reason, missing form
  validation schema, no optimistic UI on submit
- **Events**: global event listeners not cleaned up, missing `useEffect`
  cleanup functions

### Audit Agent G — Backend API

**Focus**: route handler design, input validation, response consistency,
error handling, middleware, auth enforcement, API versioning, idempotency,
rate limiting, file upload handling.

Checklist:
- **Input validation**: route handlers trusting client input without
  validation (missing schema checks, no type coercion, accepting arbitrary
  JSON keys)
- **Response format**: inconsistent response shapes across endpoints (some
  return `{data}`, others return raw arrays, others return `{result}`)
- **Error handling**: leaking stack traces / internal errors to clients,
  missing try/catch in handlers, generic 500 for what should be 400/404/409
- **HTTP semantics**: wrong status codes (200 for creates instead of 201,
  200 for not-found instead of 404), missing proper headers
- **Auth & authorization**: route handlers missing auth middleware, no
  per-resource ownership checks (user A can read user B's data), missing
  role checks on admin endpoints
- **Idempotency**: POST/PUT endpoints that create duplicates on retry,
  missing idempotency keys on payment/order endpoints
- **Rate limiting**: sensitive endpoints (login, register, password reset)
  missing rate limits; bulk endpoints missing throttling
- **File uploads**: no file type validation, no size limits, storing user
  filenames directly (path traversal risk), missing virus/malware scanning
  on user uploads
- **API versioning**: no version prefix (`/api/v1/`), breaking changes mixed
  into existing routes
- **N+1 in handlers**: route handler that loops and queries DB per item
  instead of batching
- **Pagination**: list endpoints missing pagination, unbounded queries
  (`find()` with no limit), missing total count for pagination metadata
- **CORS / headers**: missing security headers (CSP, HSTS, X-Frame-Options)

### Audit Agent H — Database Security

**Focus**: schema design, indexing strategy, query safety, connection
management, migration safety, data encryption, access control at the data
layer, backup/restore posture.

Checklist:
- **Injection**: raw query construction with string concatenation,
  `$where` with user input in MongoDB, `eval` in DB scripts
- **Indexing**: queries on fields without indexes (check for
  `COLLSCAN` / collection scans), missing compound indexes for common query
  patterns, unused indexes slowing writes
- **Schema design**: unbounded arrays in documents (MongoDB), missing `createdAt`/
  `updatedAt` timestamps, fields that should be required but are optional,
  storing what should be separate collections as embedded sub-docs
- **Connection management**: creating a new DB connection per request instead
  of pooling, missing connection retry/backoff, connection leak (not closing
  cursors/sessions)
- **Migration safety**: non-atomic migrations that can leave DB in partial
  state, missing rollback script, destructive migrations without backup,
  migrations that lock large tables in production
- **Data encryption**: sensitive fields (PII, financial data) stored in
  plaintext, missing field-level encryption, passwords not hashed (or hashed
  with weak algorithm like MD5/SHA1 without salt)
- **Access control**: DB user with `root` / superuser privileges used by the
  app instead of least-privilege role, missing row-level security where
  multi-tenant
- **Data exposure in logs**: full documents written to logs (may contain PII),
  query logging that includes parameters with sensitive values
- **Backup**: no backup strategy, backups not tested for restore, backups
  stored in same region/availability zone as primary
- **Connection string security**: DB credentials in connection string in
  source code, missing TLS on DB connection, default ports unchanged

### Required Output Format (every audit agent)

Each agent must return findings in this exact structure:

```markdown
## [Dimension Name] — Audit Results

**Score**: X/4  (0 = critical issues everywhere, 4 = excellent)
**Files reviewed**: N
**Issues found**: M

### P0 — Critical (must fix before merge / blocks production)
- **[file:line]** Short description of the issue.
  Impact: what breaks / risk level.
  Suggested fix: one-sentence direction.
- ...

### P1 — High (should fix this sprint)
- **[file:line]** ...
  Impact: ...
  Suggested fix: ...

### P2 — Medium (should fix soon)
- **[file:line]** ...

### P3 — Low / Nits (nice to have)
- **[file:line]** ...
```

If an agent finds zero issues in its dimension, it should say so explicitly:
`No issues found in [Dimension]. Score: 4/4.`

---

## Phase 1.5 — Synthesis & Deduplication

After all audit agents return, **you** (the orchestrator) must:

1. **Collect** all findings into a single list.
2. **Deduplicate**: the same issue may appear in multiple dimensions (e.g. a
   missing error boundary is both a UI/UX bug and an architecture + frontend
   issue). Merge duplicates, keeping the most detailed description and the
   highest severity.
3. **Cross-reference**: some issues are symptoms of a deeper root cause. If
   three files have the same anti-pattern, group them as one fix task.
4. **Re-prioritize**: after merging, the P-levels may need adjustment.
5. **Present the consolidated report** to the user with a summary table:

```
| Dimension         | Score | P0 | P1 | P2 | P3 | Total |
|-------------------|-------|----|----|----|----|----|
| Code Quality      | 2/4   | 3  | 5  | 8  | 4  | 20   |
| UI/UX Bugs        | 1/4   | 2  | 6  | 4  | 2  | 14   |
| Performance       | 3/4   | 1  | 3  | 5  | 1  | 10   |
| Design/Arch       | 2/4   | 2  | 4  | 3  | 3  | 12   |
| Security          | 3/4   | 1  | 2  | 1  | 0  | 4    |
| Frontend          | 2/4   | 2  | 3  | 4  | 2  | 11   |
| Backend API       | 2/4   | 3  | 4  | 3  | 1  | 11   |
| Database Security | 3/4   | 1  | 2  | 2  | 0  | 5    |
| **TOTAL**         |       | 15 | 29 | 30 | 13 | 87   |
```

6. **Wait for user confirmation** before proceeding to Phase 2. The user may
   want to:
   - Fix everything (default).
   - Fix only P0 + P1.
   - Skip certain dimensions.
   - Adjust priorities.

This checkpoint is **non-negotiable** — never auto-proceed to fixes. The user
must see the audit results and explicitly approve the fix scope.

---

## Phase 2 — Fix Swarm (parallel dispatch)

After user approval, group the approved issues into **independent fix
bundles** and dispatch one fix-agent per bundle in parallel.

### 2.1 Grouping rules

Create bundles that are **independent** — two agents should never edit the
same files simultaneously. Group by:

1. **File locality**: issues in the same file or tightly-coupled files go in
   one bundle (one agent fixes all issues in `UserForm.tsx` + its tests).
2. **Root cause**: issues sharing a root cause go together (five files with
   the same N+1 query pattern = one agent, one systematic fix).
3. **Dimension cross-cutting**: if the same file has both a P0 security issue
   and a P1 performance issue, one agent fixes both — don't split.

Target: 3–8 fix-agents. Fewer = each agent has too much context. More =
coordination overhead. If you have 50 issues across 3 files, that's 3 agents.
If you have 15 issues across 15 independent files, that's ~8 agents (batch
some together).

**Anti-pattern**: one agent per dimension. Dimensions are for *finding*
issues; fixing is organized by *code locality*, not by audit dimension.

### 2.2 Fix agent prompt template

Every fix agent receives:

```
## Context
- Project root: <path>
- Tech stack: <framework, language, conventions>
- Scope: the files this agent owns — <list of files>

## Baseline (must remain green after changes)
- Tests: <command> — currently <pass/fail: N failing>
- Lint: <command> — currently <pass/fail: N warnings>
- Type-check: <command> — currently <pass/fail>
- Build: <command> — currently <pass/fail>

## Issues to fix (in priority order)

### P0
1. **[file:line]** <description>
   Suggested fix: <direction from audit>
2. ...

### P1
3. **[file:line]** <description>
   ...

## Rules
- ONLY modify the files listed in your scope above.
- Do NOT refactor unrelated code you happen to see.
- After each fix, run the relevant check (lint / type-check / test) to
  verify your change works.
- If a suggested fix turns out to be wrong or risky, DO NOT force it —
  report it back as "skipped: <reason>" and leave the code as-is.
- Follow the existing code style of the project.
- If you add a new pattern, make it consistent with existing patterns.

## Output format
Return for each issue:
- Issue #N: **fixed** | **skipped: <reason>** | **partially fixed: <details>**
- Files changed: <list>
- Tests: <before> → <after>
```

### 2.3 Dispatch & monitor

Dispatch all fix-agents in parallel. As they return:

1. **Collect results** — which issues were fixed, skipped, or partial.
2. **Detect conflicts** — did two agents accidentally touch the same file?
   (Shouldn't happen if grouping was correct, but verify.)
3. **Re-run the full baseline** — tests, lint, type-check, build. Everything
   must be at least as green as Phase 0's baseline.
4. **Handle failures**: if a fix broke something, either fix it yourself (if
   small) or dispatch a targeted follow-up agent.

### 2.4 Verification gate

Before declaring done, run the **complete** verification suite:

```bash
# Replace with actual project commands
<lint-command>
<type-check-command>
<test-command>
<build-command>
```

All must pass (or match the baseline's status + new improvements). If
anything regressed, it's not done.

---

## Phase 3 — Report

Produce a final summary for the user:

```markdown
## Burn — Audit & Fix Complete

### Audit Summary
- Dimensions audited: 8
- Total issues found: N
- Score before: <dimension scores>
- Score after (estimated): <dimension scores>

### Fixes Applied
- P0 fixed: X/Y
- P1 fixed: X/Y
- P2 fixed: X/Y
- P3 fixed: X/Y
- Skipped: Z (with reasons)

### Files Modified
- `path/to/file.ts` — <what changed>
- ...

### Verification
- Lint: pass (was: N warnings)
- Type-check: pass
- Tests: pass (N tests, 0 failing)
- Build: pass

### Remaining Issues
- <list of skipped or deferred issues with reasons>
```

---

## Quick Start (for the agent reading this)

When this skill is invoked, follow these steps in order:

```
1. Read this SKILL.md fully. ✓
2. Phase 0: Determine scope, gather context, establish baseline.
3. Phase 1: Dispatch 8 audit agents (A-H) in parallel.
4. Phase 1.5: Collect, deduplicate, re-prioritize, present report.
5. WAIT for user to confirm fix scope.
6. Phase 2: Group into fix bundles, dispatch fix agents in parallel.
7. Phase 2.4: Run full verification suite.
8. Phase 3: Present final report.
```

**Never skip Phase 1.5's user confirmation checkpoint.** The user must see
the audit results and approve before any fixes are applied.

---

## Scope Modes

| Mode | When | How |
|------|------|-----|
| **Full project** | No argument given, project is small (< 300 files) | Audit all source dirs |
| **Feature / page** | Argument is a route or feature name | Trace all files involved in that feature (page + components + API routes + models + tests) |
| **Directory** | Argument is a path like `src/components/` | Audit everything under that path |
| **Single file** | Argument is one file path | Audit that file + its direct imports deeply |

---

## Adaptation Notes for Different Harnesses

This skill is written to be harness-agnostic. When implementing:

- **Claude Code**: use the `Task` tool to dispatch sub-agents. Each `Task` call
  is one agent. Multiple `Task` calls in one response run in parallel.
- **Kimi Code**: use `AgentSwarm` for batch dispatch with a prompt template,
  or multiple `Agent` calls for diverse prompts.
- **Cursor / Windsurf**: use the agent/composer parallel-task feature.
- **Plain LLM (no sub-agent tool)**: run each dimension as a separate
  conversation, then paste results back for synthesis. Slower but functional.

The core pipeline (audit → synthesize → fix → verify) is the same regardless
of harness. Only the dispatch mechanism changes.

---

## Anti-Patterns to Avoid

1. **❌ One mega-agent that audits everything** — context bloat, shallow analysis.
   **✅ One agent per dimension**, each focused and deep.

2. **❌ Fixing during audit** — audit agents should be read-only. Fixes need
   coordination and grouping, not reactive patching.
   **✅ Audit first, synthesize, then fix.**

3. **❌ Auto-proceeding to fixes without user review** — the user may disagree
   with priorities or want to skip certain dimensions.
   **✅ Always present the report and wait for approval.**

4. **❌ Grouping fixes by dimension** — a file with both a security P0 and a
   performance P1 needs one agent, not two (they'd conflict on the same file).
   **✅ Group fixes by file locality and root cause.**

5. **❌ Skipping verification** — "the agent said it's fixed" is not proof.
   **✅ Run the actual test/lint/type-check/build suite.**

6. **❌ Fixing unrelated code you noticed along the way** — scope creep breaks
   reviewability and introduces regressions.
   **✅ Only fix what the audit flagged. File new issues for the rest.**

7. **❌ Treating backend/database/frontend as "not applicable" without
   checking** — a project may have a minimal backend or a thin database layer,
   but the agent must still scan for issues. Only skip a dimension if the
   project genuinely has no code in that domain (e.g. a pure CLI tool with no
   DB). State the skip reason in the report.
   **✅ Run all 8 agents; let each report "no issues / N/A" if applicable.**
