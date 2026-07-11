---
name: burn
description: >-
  Use when the user wants to comprehensively audit a codebase (or part of one)
  across multiple dimensions — code quality, UI/UX bugs, performance risks,
  code design & architecture, frontend, backend API, database security,
  general security, functional analysis & optimization, dependency & supply
  chain risk, and project risk & operational readiness — and then produce a
  detailed modification plan and fix everything found, all using parallel
  agent swarms. Triggers on phrases like "audit and fix", "comprehensive
  review and optimize", "swarm audit", "burn the codebase", "find and fix
  all issues", "全面审计修复", "审计代码质量", "review and repair codebase".
  Orchestrates a multi-phase pipeline: Phase 0.5 builds a shared codebase
  intelligence brief; Phase 1 dispatches one agent per audit dimension to
  produce a scored findings report; Phase 1.5 uses a dedicated synthesis
  agent to cross-reference, deduplicate, and build a risk matrix; Phase 1.7
  produces a sequenced modification plan; Phase 2 dispatches fix-agents and
  review-agents; Phase 3 outputs the final report. Works in full-project or
  scoped (feature/page/module/directory) mode. Token-intensive by design.
user-invocable: true
argument-hint: "[scope: feature, page, component, directory, or empty for full project]"
---

# Burn

A multi-phase, parallel-agent pipeline that **understands**, **audits**,
**plans**, and **fixes** a codebase across eleven core quality dimensions —
powered by agent swarms and designed for maximum depth (token-intensive).

```
 Phase 0.5: INTELLIGENCE (2 agents)    Phase 1: AUDIT SWARM (11 agents)

 ┌──────────┐  ┌──────────┐           ┌──────────┐  ┌──────────┐
 │ Agent 0a │  │ Agent 0b │           │ Agent A  │  │ Agent B  │
 │ Arch &   │  │ Deps &   │    feed   │ Code     │  │ UI/UX    │
 │ Dataflow │  │ Techstack │──┐       │ Quality  │  │ Bugs     │
 └──────────┘  └──────────┘  │       └──────────┘  └──────────┘
       │                     │       ┌──────────┐  ┌──────────┐
       v                     │       │ Agent C  │  │ Agent D  │
 ┌─────────────┐             ├──────>│ Perform- │  │ Design & │
 │ Shared      │             │       │ ance     │  │ Arch     │
 │ Codebase    │-------------┘       └──────────┘  └──────────┘
 │ Intel Brief │                   ...9 more agents (E through K)...
 └─────────────┘

 Phase 1.5: SYNTHESIS (1 agent)       Phase 1.7: PLAN (1 agent)

 ┌──────────────────────────┐        ┌──────────────────────────┐
 │ Synthesis Agent          │        │ Planning Agent           │
 │ - Dedup & cross-ref      │───────>│ - Sequenced fix plan     │
 │ - Risk matrix (impact x  │        │ - Effort estimates       │
 │   probability)           │        │ - Regression risk per    │
 │ - Fix dependency graph   │        │   fix                    │
 │ - Root-cause grouping    │        │ - Phase/sprint grouping  │
 └──────────────────────────┘        └──────────────────────────┘

 Phase 2: FIX + REVIEW SWARM (3-11 agents each)

 ┌──────────┐  ┌──────────┐           ┌──────────┐  ┌──────────┐
 │ Fix      │  │ Fix      │           │ Review   │  │ Review   │
 │ Agent 1  │  │ Agent 2  │    then   │ Agent 1  │  │ Agent 2  │
 └──────────┘  └──────────┘  -------> └──────────┘  └──────────┘
```

---

## Phase 0 - Setup & Scoping (do this first, always)

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

## Phase 0.5 - Codebase Intelligence (parallel dispatch, 2 agents)

**Why this exists**: audit agents that start with zero context each
independently explore the codebase, producing inconsistent understanding and
shallow findings. This phase generates a **shared Codebase Intelligence
Brief** that is injected into every audit agent's prompt, dramatically
improving their depth and consistency.

Dispatch **two intelligence agents in parallel**. Both are read-only.

### Intelligence Agent 0a - Architecture & Data Flow Mapper

**Focus**: map the entire codebase's architecture, module relationships,
data flow, and business domain model.

Instructions:
- Read the project structure recursively. Identify every source directory
  and its purpose.
- Trace the **request lifecycle**: entry point → middleware → route handler →
  business logic → data layer → response. Document each hop with file paths.
- Trace the **data flow**: where data enters (user input, API, webhooks,
  cron), how it's transformed through layers, where it's persisted, where
  it's read back.
- Identify the **module dependency graph**: which modules import from which.
  Note circular dependencies, cross-layer imports, and utility modules that
  everything depends on.
- Map the **business domain**: what entities exist, what are their
  relationships, what are the core business workflows.
- Identify **critical paths**: the few code paths that, if broken, would
  take the whole product down. These get extra scrutiny in Phase 1.

Output format:
```markdown
## Codebase Intelligence — Architecture & Data Flow

### Project Structure
<directory tree with purpose annotations>

### Request Lifecycle
entry → src/index.ts → middleware (src/auth.ts) → route handler → ...

### Data Flow Map
- User input: <where it enters, how it's validated>
- API → DB: <path, transformation steps>
- DB → Response: <path, serialization steps>
- Async/jobs: <queue, worker, job types>

### Module Dependency Graph
<text-based graph or adjacency list>

### Business Domain Model
- Core entities: <list with relationships>
- Key workflows: <step-by-step for each major workflow>

### Critical Paths (highest-risk code)
1. <path description> — <why it's critical>
2. ...
```

### Intelligence Agent 0b - Dependency & Tech Stack Analyzer

**Focus**: catalog every external dependency, map the tech stack, identify
version health, and surface integration points.

Instructions:
- Read package manifest(s) (package.json, go.mod, Cargo.toml, pyproject.toml,
  requirements.txt, etc.). List every dependency with its pinned version.
- Run the project's audit command (`npm audit`, `pip-audit`, `cargo audit`)
  and record all findings.
- Identify **integration points**: external APIs called, webhooks received,
  third-party services depended on (Stripe, Twilio, SendGrid, etc.).
  Document each with: service name, purpose, auth method, failure mode if
  the service is down.
- Check **version health**: are dependencies on supported major versions?
  Are any deprecated? Are any more than 2 major versions behind current?
- Identify **dev-only vs production dependencies** and flag any production
  deps that should be dev-only (or vice versa).
- Check for **duplicate functionality** in dependencies (e.g. both lodash
  and underscore, both date-fns and moment).

Output format:
```markdown
## Codebase Intelligence — Dependencies & Tech Stack

### Tech Stack Summary
- Language: <lang + version>
- Framework: <framework + version>
- ORM: <name + version>
- Frontend: <framework + version>
- Build tool: <name>
- Deploy target: <docker / serverless / VM / etc.>

### Dependency Inventory
| Package | Version | Latest | Status | Notes |
|---------|---------|--------|--------|-------|
| ...     | ...     | ...    | ok / outdated / deprecated / vulnerable | ... |

### Integration Points
| Service | Purpose | Auth | Failure Mode |
|---------|---------|------|-------------|
| ...     | ...     | ...  | ...          |

### Dependency Health Flags
- Outdated (>2 major behind): <list>
- Deprecated: <list>
- Known CVEs: <list>
- Duplicate functionality: <list>
```

### Assemble the Codebase Intelligence Brief

After both agents return, **merge their outputs** into a single document
called the **Codebase Intelligence Brief**. This brief is injected into
**every Phase 1 audit agent's prompt** as shared context. Each agent now
starts with deep codebase understanding instead of zero context.

The brief should be concise enough to fit in an agent prompt (trim verbose
sections, keep file paths and structural facts). If it's too long, summarize
sections and keep the full detail only for critical paths.

---

## Phase 1 - Audit Swarm (parallel dispatch, 11 agents)

Dispatch **one agent per dimension**, all in parallel. Each agent is
read-only — it reviews, finds issues, and reports back. It does NOT modify
code.

Every audit agent receives in its prompt:
1. The project root path.
2. The scope (which files/directories to focus on).
3. The project's tech stack and conventions.
4. The **Codebase Intelligence Brief** from Phase 0.5 (shared context).
5. How to run lint / tests / type-check / build (so it can verify issues).
6. Its specific dimension's checklist (below).
7. The **required output format** (below).

### Audit Agent A - Code Quality

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

### Audit Agent B - UI/UX Bugs

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

### Audit Agent C - Performance Risks

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

### Audit Agent D - Code Design & Architecture

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

### Audit Agent E - Security (General)

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

### Audit Agent F - Frontend

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

### Audit Agent G - Backend API

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

### Audit Agent H - Database Security

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

### Audit Agent I - Functional Analysis & Optimization

**Focus**: business logic correctness, feature completeness, workflow
soundness, functional edge cases, data flow integrity, requirement coverage,
workflow optimization, dead-end paths, and functional test gaps.

Checklist:
- **Business logic correctness**: conditions that use the wrong operator
  (`<` vs `<=`, `&&` vs `||`), off-by-one in business rules (quantity
  thresholds, tier boundaries), inverted boolean checks that do the opposite
  of what the feature requires
- **Feature completeness**: half-implemented features (API endpoint exists
  but no UI to call it, or UI button exists but no handler), TODO/FIXME
  markers in shipped code paths, feature flags permanently stuck off
- **Workflow soundness**: multi-step flows that can be entered out of order
  (e.g. checkout without cart), missing state-transition guards (canceling
  an already-completed order), steps that silently no-op instead of blocking
- **Functional edge cases**: zero-quantity / empty-cart / single-item edge
  cases, negative or zero amounts in calculations, concurrent actions on
  the same resource (double-submit, race between read and update), timezone
  or locale affecting business logic (cutoff times, business-day logic)
- **Data flow integrity**: data transformed or lost between layers (API
  returns `snake_case`, frontend expects `camelCase` and silently gets
  `undefined`), required fields dropped during mapping, enums whose values
  don't match between frontend and backend
- **Requirement coverage**: read the project's docs/RFC/README and trace each
  stated requirement to code — find requirements with no implementation,
  or implemented features that contradict the documented spec
- **Dead-end paths**: user flows that lead nowhere (form submit with no
  success page, error with no recovery path, "coming soon" placeholders in
  production routes), API responses the frontend never consumes
- **Workflow optimization**: unnecessarily complex multi-step processes that
  could be simplified, redundant validation layers (same check repeated in
  UI + API + DB trigger with no added value), manual steps that could be
  automated, unnecessary intermediate data transformations
- **Functional test gaps**: critical business logic with no test coverage,
  edge cases (zero, negative, boundary values) untested, integration tests
  missing for multi-step workflows, no test for error/rollback paths
- **Consistency across layers**: the same business rule implemented
  differently in frontend vs backend vs DB (e.g. max item count = 10 in UI
  but 50 in API), validation rules that drift between create and update
- **Idempotency & retry**: actions that produce side effects on retry
  (duplicate charges, duplicate sends), missing de-dup keys, retry logic
  that re-executes non-idempotent operations
- **State synchronization**: local state that can go stale vs server state
  (optimistic updates without reconciliation), cached data not invalidated
  after mutations, multiple clients editing the same resource without
  conflict detection

### Audit Agent J - Dependency & Supply Chain Risk

**Focus**: third-party dependency health, version pinning, license
compliance, transitive dependency risk, supply chain attack surface,
integration point failure modes.

Checklist:
- **Version pinning**: dependencies using `^` or `~` when exact pinning is
  safer (especially for prod-critical packages), missing lockfile, lockfile
  out of sync with manifest
- **Outdated dependencies**: packages more than 2 major versions behind
  current stable, packages with no release in > 12 months (potential
  abandonment), packages that have been renamed or superseded
- **Known vulnerabilities**: run `npm audit` / `pip-audit` / `cargo audit`
  and enumerate every CVE with severity, exploitability, and fix path
- **License compliance**: GPL/AGPL packages in a project that ships
  proprietary code, missing license files, incompatible license combos
- **Transitive dependencies**: deep dependency trees that are hard to audit
  (check `npm ls --all` or equivalent), transitive deps with known issues
  that the direct dep doesn't fix
- **Supply chain attack surface**: dependencies from unverified publishers,
  packages with very low download counts (potential typosquatting), packages
  added to the manifest but never imported in code (potential injection)
- **Integration point failure modes**: for each external service the app
  depends on (identified in the Codebase Intelligence Brief), check: what
  happens if it's down? Is there a fallback? A timeout? A circuit breaker?
  Is the failure mode silent (data loss) or loud (error)?
- **Duplicate functionality**: multiple packages providing the same utility
  (e.g. both `lodash` and `underscore`, both `axios` and `fetch` wrapper),
  increasing bundle size and attack surface for no benefit
- **Dev/prod boundary**: dev-only dependencies (test runners, linters)
  accidentally listed as production dependencies, or vice versa
- **Self-hosted vs managed**: dependencies that could be replaced by managed
  services or platform features (e.g. self-hosted Redis client when the
  platform provides a cache), reducing operational burden

### Audit Agent K - Project Risk & Operational Readiness

**Focus**: bus factor, CI/CD pipeline gaps, deployment risk, monitoring &
observability, disaster recovery, documentation gaps, technical debt
assessment, scalability ceilings.

Checklist:
- **Bus factor**: how many people understand each critical module? Any
  module understood by only one person (or only AI-generated with no human
  review)? Key files with no comments, no docs, and complex logic
- **CI/CD pipeline**: is there a CI pipeline? Does it run tests, lint,
  type-check, build on every PR? Are there pre-commit hooks? Is deployment
  automated or manual? Are there staging environments? Is there a rollback
  mechanism?
- **Deployment risk**: can a bad deploy take down the service with no
  automatic recovery? Are migrations run before or after code deploy (can
  cause mismatches)? Is there blue-green or canary deployment? Health checks
  after deploy?
- **Monitoring & observability**: is there structured logging? Error tracking
  (Sentry, etc.)? Metrics dashboards? Alerting on critical errors? Is there
  any way to know if the service is degraded but not down?
- **Disaster recovery**: if the database is corrupted, how long to recover?
  Is there a documented runbook for common incidents? When was the last
  backup restore test? Is there a single point of failure (one DB, one
  server, one region)?
- **Documentation gaps**: is there an architecture doc? An onboarding guide?
  Are API endpoints documented (OpenAPI/Swagger)? Are environment variables
  documented? Are there runbooks for operations tasks?
- **Technical debt**: TODO/FIXME/HACK comments in code (count and severity),
  workarounds that were "temporary" but became permanent, deprecated APIs
  still in use, code that should be refactored but keeps getting deferred
- **Scalability ceilings**: what breaks first at 10x current load? (DB
  connections? API rate limits? Memory? File handles?) Are there hardcoded
  limits (max users, max items, max connections) that would block growth?
- **Environment configuration**: are all environment variables documented?
  Are there separate configs for dev/staging/prod? Can the app start without
  all required env vars (fail-fast vs silent misconfiguration)?
- **Onboarding friction**: how long would it take a new developer to get the
  project running locally? Are there missing setup steps? Undocumented
  prerequisites? Manual database seeding required?

### Required Output Format (every audit agent)

Each agent must return findings in this exact structure:

```markdown
## [Dimension Name] - Audit Results

**Score**: X/4  (0 = critical issues everywhere, 4 = excellent)
**Files reviewed**: N
**Issues found**: M

### P0 - Critical (must fix before merge / blocks production)
- **[file:line]** Short description of the issue.
  Impact: what breaks / risk level.
  Suggested fix: one-sentence direction.
- ...

### P1 - High (should fix this sprint)
- **[file:line]** ...
  Impact: ...
  Suggested fix: ...

### P2 - Medium (should fix soon)
- **[file:line]** ...

### P3 - Low / Nits (nice to have)
- **[file:line]** ...
```

If an agent finds zero issues in its dimension, it should say so explicitly:
`No issues found in [Dimension]. Score: 4/4.`

---

## Phase 1.5 - Synthesis & Risk Matrix (1 dedicated agent)

After all 11 audit agents return, dispatch a **dedicated Synthesis Agent**
that takes all findings as input and produces a unified, cross-referenced,
prioritized report with a risk matrix and fix dependency graph.

**Why a dedicated agent instead of manual synthesis**: the orchestrator's
context is limited and manual synthesis tends to be shallow — just collecting
and counting. A dedicated agent can deeply cross-reference findings across
dimensions, identify root causes that span multiple files, and produce a
genuinely actionable risk matrix.

### Synthesis Agent Instructions

Input: all 11 audit agent reports + the Codebase Intelligence Brief.

Tasks:
1. **Deduplicate**: the same issue may appear in multiple dimensions (e.g. a
   missing error boundary is both a UI/UX bug and an architecture + frontend
   issue). Merge duplicates, keeping the most detailed description and the
   highest severity.
2. **Cross-reference**: some issues are symptoms of a deeper root cause. If
   three files have the same anti-pattern, group them as one fix task.
   Trace symptom → root cause using the Codebase Intelligence Brief's
   architecture map.
3. **Build risk matrix**: for every unique issue, assign:
   - **Impact** (1-5): how bad is it if this issue manifests?
   - **Probability** (1-5): how likely is it to manifest in production?
   - **Risk score** = Impact × Probability (1-25)
   - Sort all issues by risk score descending.
4. **Build fix dependency graph**: identify which fixes depend on others:
   - "Fix A must be done before Fix B" (e.g. fix the DB schema before fixing
     the query that depends on it)
   - "Fix A and Fix B are independent" (can be done in parallel)
   - "Fix A conflicts with Fix B" (both touch the same code, must be sequenced)
5. **Re-prioritize**: after merging and cross-referencing, P-levels may need
   adjustment. Use the risk matrix as the source of truth, not the original
   P-levels from individual agents.

### Synthesis Output Format

```markdown
## Consolidated Audit Report

### Summary Table
| Dimension               | Score | P0 | P1 | P2 | P3 | Total |
|-------------------------|-------|----|----|----|----|----|
| Code Quality            | 2/4   | 3  | 5  | 8  | 4  | 20   |
| UI/UX Bugs              | 1/4   | 2  | 6  | 4  | 2  | 14   |
| Performance             | 3/4   | 1  | 3  | 5  | 1  | 10   |
| Design/Arch             | 2/4   | 2  | 4  | 3  | 3  | 12   |
| Security                | 3/4   | 1  | 2  | 1  | 0  | 4    |
| Frontend                | 2/4   | 2  | 3  | 4  | 2  | 11   |
| Backend API             | 2/4   | 3  | 4  | 3  | 1  | 11   |
| Database Security       | 3/4   | 1  | 2  | 2  | 0  | 5    |
| Functional & Opt        | 2/4   | 2  | 3  | 4  | 2  | 11   |
| Dependency & Supply     | 2/4   | 1  | 3  | 2  | 1  | 7    |
| Project Risk & Ops      | 1/4   | 2  | 4  | 3  | 2  | 11   |
| **TOTAL**               |       | 20 | 39 | 39 | 18 | 116  |

### Risk Matrix (top 20 by risk score)
| # | Issue | Dimension(s) | Impact | Prob | Risk | P-level |
|---|-------|-------------|--------|------|------|---------|
| 1 | ...   | Security+DB | 5      | 4    | 20   | P0     |
| 2 | ...   | Backend     | 5      | 3    | 15   | P0     |
| ...                     |             |        |      |      |        |

### Root-Cause Groups
1. **[Root cause description]** — manifests as: issue #3, #7, #12
   Files: `src/a.ts`, `src/b.ts`
   Fix: <unified approach>

### Fix Dependency Graph
```
[Issue #1] ──blocks──> [Issue #5] ──blocks──> [Issue #8]
[Issue #2] (independent)
[Issue #3] ──conflicts──> [Issue #4] (sequence these)
```
```

### User Confirmation

After presenting the consolidated report, **wait for user confirmation**
before proceeding to Phase 1.7. The user may want to:
- Fix everything (default).
- Fix only P0 + P1.
- Fix only risk score >= 15.
- Skip certain dimensions.
- Adjust priorities.

This checkpoint is **non-negotiable** — never auto-proceed to planning or
fixes. The user must see the audit results and explicitly approve the scope.

---

## Phase 1.7 - Modification Plan (1 dedicated agent)

After user approval, dispatch a **dedicated Planning Agent** that transforms
the approved findings into a **detailed, sequenced modification plan**.

**Why a dedicated phase**: jumping straight from audit to fixes produces
uncoordinated patches. A plan ensures fixes are sequenced correctly
(dependencies respected), effort is estimated, regression risks are flagged,
and the user has a final checkpoint before code changes begin.

### Planning Agent Instructions

Input: approved findings from Phase 1.5 + Codebase Intelligence Brief +
fix dependency graph.

Tasks:
1. **Sequencing**: order all approved fixes respecting the dependency graph.
   Independent fixes can be batched into parallel groups. Dependent fixes
   must be sequenced.
2. **Effort estimation**: for each fix, estimate:
   - **Complexity**: S (< 30 min) / M (30 min - 2h) / L (2h - 1d) / XL (> 1d)
   - **Files affected**: list of files that will be modified
   - **Risk of regression**: Low / Medium / High (based on how central the
     code is, per the Codebase Intelligence Brief's critical paths)
3. **Phase grouping**: group the sequenced fixes into 2-5 phases:
   - Phase A: critical fixes (P0, high risk score) — must be done first
   - Phase B: high-priority fixes (P1) — next sprint
   - Phase C: medium-priority (P2) — backlog
   - Phase D: nice-to-have (P3) — when time permits
4. **Verification plan**: for each fix, specify how to verify it worked:
   - Which test to run (existing or needs new test)
   - Which manual check to perform
   - Which lint/type-check rule validates the fix
5. **Rollback plan**: for high-risk fixes, specify how to roll back if they
   cause regressions.

### Plan Output Format

```markdown
## Modification Plan

### Phase A — Critical Fixes (must do first)
| # | Issue | Fix Description | Files | Complexity | Regression Risk | Prerequisites | Verify |
|---|-------|----------------|-------|------------|----------------|---------------|--------|
| 1 | #5    | Add input validation schema | src/routes/api.ts | M | Low | none | `npx tsc`; POST with bad input returns 400 |
| 2 | #1    | Fix SQL injection in search | src/db/search.ts | S | Medium | none | `npm test`; query with `' OR 1=1` returns empty |
| ...                                                                                            |

### Phase B — High-Priority Fixes
| # | Issue | ... |
|---|-------|-----|

### Phase C — Medium-Priority
...

### Phase D — Nice-to-Have
...

### Parallelization Map
- **Wave 1** (parallel): Issue #1, #2, #3 (independent files)
- **Wave 2** (after #1): Issue #5, #6 (depend on #1's schema change)
- **Wave 3** (after #2): Issue #8

### Total Effort Estimate
- Phase A: ~Xh (S×n + M×n + L×n)
- Phase B: ~Xh
- Phase C: ~Xh
- Phase D: ~Xh
- **Total: ~Xh**

### Rollback Plan (for High-risk fixes)
- Issue #3: revert `src/auth.ts` to previous commit, re-run `npm test`
- Issue #7: the migration is reversible — `pnpm db:rollback`
```

### Plan Confirmation

Present the modification plan to the user. They may:
- Approve as-is (proceed to Phase 2).
- Adjust scope (remove items, add items).
- Reorder phases.
- Ask for more detail on specific items.

**Do not proceed to Phase 2 until the user explicitly approves the plan.**

---

## Phase 2 - Fix & Review Swarm (parallel dispatch)

After plan approval, execute the modification plan in **waves** defined by
the parallelization map. Each wave dispatches fix-agents in parallel; after
all fix-agents in a wave complete, dispatch review-agents to verify.

### 2.1 Grouping rules

Create bundles that are **independent** — two agents should never edit the
same files simultaneously. Group by:

1. **File locality**: issues in the same file or tightly-coupled files go in
   one bundle (one agent fixes all issues in `UserForm.tsx` + its tests).
2. **Root cause**: issues sharing a root cause go together (five files with
   the same N+1 query pattern = one agent, one systematic fix).
3. **Dimension cross-cutting**: if the same file has both a P0 security issue
   and a P1 performance issue, one agent fixes both — don't split.
4. **Wave respect**: only group fixes within the same wave. Cross-wave fixes
   are sequenced, not parallelized.

Target: 3–11 fix-agents per wave. Fewer = each agent has too much context.
More = coordination overhead.

**Anti-pattern**: one agent per dimension. Dimensions are for *finding*
issues; fixing is organized by *code locality*, not by audit dimension.

### 2.2 Fix agent prompt template

Every fix agent receives:

```
## Context
- Project root: <path>
- Tech stack: <framework, language, conventions>
- Scope: the files this agent owns — <list of files>
- Codebase Intelligence Brief: <included>

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
- Tests: <before> -> <after>
```

### 2.3 Dispatch & monitor

Dispatch all fix-agents in a wave in parallel. As they return:

1. **Collect results** — which issues were fixed, skipped, or partial.
2. **Detect conflicts** — did two agents accidentally touch the same file?
   (Shouldn't happen if grouping was correct, but verify.)
3. **Re-run the full baseline** — tests, lint, type-check, build. Everything
   must be at least as green as Phase 0's baseline.
4. **Handle failures**: if a fix broke something, either fix it yourself (if
   small) or dispatch a targeted follow-up agent.
5. **Proceed to next wave** only after the current wave is fully verified.

### 2.4 Post-Fix Review Agents (NEW)

After each wave's fixes are applied and baseline passes, dispatch **review
agents** (different agents from the fix agents) to independently verify fix
quality.

**Why**: tests passing doesn't mean the fix is correct — tests may not cover
the fixed code path, or the fix may introduce subtle behavioral changes that
tests don't catch. An independent review agent reads the diff and checks:

- Did the fix actually address the root cause, or just the symptom?
- Did the fix introduce new issues (edge cases, performance regressions)?
- Is the fix consistent with the codebase's patterns and conventions?
- Are there missing test cases that should be added for the fixed behavior?
- Did the fix accidentally remove or alter unrelated code?

Review agent prompt template:
```
## Context
- Project root: <path>
- Codebase Intelligence Brief: <included>

## Review Scope
Review the following fix for correctness, completeness, and regressions:

### Fix #N
- Issue: <description from audit>
- Fix applied: <description from fix agent>
- Files changed: <list>
- Diff: <included>

## Check
1. Does the fix address the root cause?
2. Does it introduce new edge cases or bugs?
3. Is it consistent with codebase patterns?
4. Are there missing tests that should be added?
5. Did it accidentally modify unrelated code?

## Output
- Fix #N: **approved** | **needs revision: <reason>** | **rejected: <reason>**
- Notes: <details>
- Suggested follow-up: <if any>
```

If a review agent flags a fix as "needs revision" or "rejected", dispatch a
targeted follow-up fix agent to address the review feedback before proceeding
to the next wave.

### 2.5 Verification gate

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

## Phase 3 - Final Report

Produce a final summary for the user:

```markdown
## Burn — Audit, Plan & Fix Complete

### Audit Summary
- Dimensions audited: 11
- Intelligence brief: generated (architecture map + dependency inventory)
- Total issues found: N
- Unique issues after dedup: M
- Root-cause groups identified: K

### Risk Matrix Summary
| Risk Level | Count | Fixed | Remaining |
|------------|-------|-------|-----------|
| Critical (20-25) | N | X | Y |
| High (15-19)     | N | X | Y |
| Medium (10-14)   | N | X | Y |
| Low (1-9)        | N | X | Y |

### Score Before vs After (estimated)
| Dimension               | Before | After |
|-------------------------|--------|-------|
| Code Quality            | 2/4    | 3/4   |
| ...                     | ...    | ...   |

### Fixes Applied
- P0 fixed: X/Y
- P1 fixed: X/Y
- P2 fixed: X/Y
- P3 fixed: X/Y
- Skipped: Z (with reasons)
- Review-approved: A/B
- Review-rejected and re-done: C

### Files Modified
- `path/to/file.ts` — <what changed>
- ...

### Modification Plan Status
- Phase A (Critical): complete / partial / not started
- Phase B (High): complete / partial / not started
- Phase C (Medium): complete / partial / not started
- Phase D (Low): not started (deferred)

### Verification
- Lint: pass (was: N warnings, now: M warnings)
- Type-check: pass
- Tests: pass (N tests, 0 failing)
- Build: pass
- Review agents: A approved, B needs follow-up

### Remaining Issues (deferred or skipped)
| # | Issue | Risk Score | Reason for Deferral |
|---|-------|------------|---------------------|
| 1 | ...   | 12         | Requires schema migration, deferred to next sprint |
| ...                                                                       |

### Recommendations (next steps)
1. <strategic recommendation based on findings>
2. <process improvement (e.g. add CI step for X)>
3. <technical debt to pay down in next quarter>
```

---

## Quick Start (for the agent reading this)

When this skill is invoked, follow these steps in order:

```
1. Read this SKILL.md fully. ✓
2. Phase 0: Determine scope, gather context, establish baseline.
3. Phase 0.5: Dispatch 2 intelligence agents (0a arch+dataflow, 0b deps+techstack)
   in parallel. Merge into Codebase Intelligence Brief.
4. Phase 1: Dispatch 11 audit agents (A-K) in parallel, each with the Brief.
5. Phase 1.5: Dispatch 1 synthesis agent — dedup, risk matrix, fix dependency graph.
6. WAIT for user to confirm fix scope.
7. Phase 1.7: Dispatch 1 planning agent — sequenced modification plan, effort,
   regression risk, waves.
8. WAIT for user to approve the modification plan.
9. Phase 2: Execute fix waves. After each wave: fix agents → baseline check →
   review agents → handle review feedback → next wave.
10. Phase 2.5: Run full verification suite.
11. Phase 3: Present final report with risk matrix, plan status, recommendations.
```

**Never skip the two user confirmation checkpoints** (Phase 1.5 and Phase 1.7).
The user must see both the audit results and the modification plan before any
fixes are applied.

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

The core pipeline (understand → audit → synthesize → plan → fix → review →
report) is the same regardless of harness. Only the dispatch mechanism changes.

---

## Anti-Patterns to Avoid

1. **❌ One mega-agent that audits everything** — context bloat, shallow analysis.
   **✅ One agent per dimension**, each focused and deep.

2. **❌ Skipping Phase 0.5 (Codebase Intelligence)** — every audit agent starts
   with zero context and independently explores, producing inconsistent
   understanding and shallow findings.
   **✅ Always run Phase 0.5 first.** The intelligence brief makes every
   subsequent agent dramatically more effective.

3. **❌ Fixing during audit** — audit agents should be read-only. Fixes need
   coordination and grouping, not reactive patching.
   **✅ Audit first, synthesize, plan, then fix.**

4. **❌ Skipping the modification plan (Phase 1.7)** — jumping straight from
   audit to fixes produces uncoordinated patches that may conflict or miss
   dependencies.
   **✅ Always produce a sequenced plan and get user approval before fixing.**

5. **❌ Auto-proceeding to fixes without user review** — the user may disagree
   with priorities or want to skip certain dimensions.
   **✅ Always present the report and plan, wait for approval at both checkpoints.**

6. **❌ Grouping fixes by dimension** — a file with both a security P0 and a
   performance P1 needs one agent, not two (they'd conflict on the same file).
   **✅ Group fixes by file locality and root cause.**

7. **❌ Skipping post-fix review** — "tests pass" is not proof the fix is
   correct. Tests may not cover the fixed path, or the fix may introduce
   subtle behavioral changes.
   **✅ Always dispatch independent review agents after fixes.**

8. **❌ Skipping verification** — "the agent said it's fixed" is not proof.
   **✅ Run the actual test/lint/type-check/build suite.**

9. **❌ Fixing unrelated code you noticed along the way** — scope creep breaks
   reviewability and introduces regressions.
   **✅ Only fix what the audit flagged. File new issues for the rest.**

10. **❌ Treating any dimension as "not applicable" without checking** — a
    project may have a minimal backend or a thin database layer, but the agent
    must still scan for issues. Only skip a dimension if the project genuinely
    has no code in that domain (e.g. a pure CLI tool with no DB). State the
    skip reason in the report.
    **✅ Run all 11 agents; let each report "no issues / N/A" if applicable.**

11. **❌ Manual synthesis instead of a dedicated agent** — the orchestrator's
    context is limited. Manual synthesis tends to be a shallow count-and-collect
    instead of deep cross-referencing and root-cause analysis.
    **✅ Dispatch a dedicated synthesis agent with all findings as input.**
