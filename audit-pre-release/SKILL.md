---
name: audit-pre-release
description: Perform a full pre-release audit of a project preparing for public beta launch. Acts as a senior product + engineering + growth reviewer to identify critical issues, failure modes, and support burden risks before going live.
---

# audit-pre-release

You are acting as a senior product + engineering + growth reviewer.

Your task:
Perform a full, no-blind-spot audit of the **current project** in preparation for a public beta launch.

---

## Step 0: Project Discovery (REQUIRED)

Before auditing, you MUST understand what you're auditing. Explore the codebase to answer:

1. **What is this product?** (read README, package.json, landing pages, docs)
2. **What type of application?** (SaaS, desktop app, mobile app, API, library, CLI tool, etc.)
3. **Who are the target users?** (infer from code, docs, UI)
4. **What is the core value proposition?** (what problem does it solve)
5. **What are the key user flows?** (identify primary features)
6. **What tech stack?** (framework, database, external services)
7. **Are there launch constraints?** (team size, budget, timeline - check CLAUDE.md/AGENTS.md if present)

If you cannot determine what the product is after initial exploration, ASK the user before proceeding.

**Output a brief "Project Context" section before starting the audit:**

- Product name & type
- Target users (inferred)
- Core use case
- Tech stack summary
- Launch context (if known)

---

## Audit Scope

Adapt each section below to the project type. Skip sections that don't apply (e.g., a CLI tool may not need "payment" audit).

### 1. Product positioning & clarity

- Is the product clearly positioned?
- Are there conflicting signals?
- Would a new user understand what this does in 10 seconds?
- Check: README, landing page, docs, marketing copy

### 2. Onboarding & time-to-value

- Can a new user reach first "wow moment" quickly?
- Any friction points that would cause drop-off?
- Any unnecessary complexity?
- For SaaS/apps: check signup, first-use flow
- For libraries/CLI: check installation, first command/function

### 3. Core user flow (critical)

**Identify the PRIMARY user flows first** (by exploring features, routes, commands).

Then evaluate end-to-end:

- Find breakpoints
- Identify confusing steps
- Locate fragile areas
- Anything that might fail silently

### 4. Domain-specific quality risks

Adapt to project type:

- **AI/ML apps:** retrieval accuracy, hallucination, guardrails, predictability
- **APIs/libraries:** edge case behavior, type safety, error handling
- **Desktop apps:** OS-specific bugs, permissions, crashes
- **Mobile apps:** device compatibility, network handling, battery
- **CLI tools:** argument parsing, exit codes, stdin/stdout handling
- **General:** input validation, state management, data integrity

### 5. Failure handling & resilience

What happens when:

- External services fail (APIs, databases, cloud services)
- Network is unavailable
- Invalid inputs received
- Resource limits hit (memory, disk, quotas)

Are users informed properly?
Are failures silent or visible?
Do errors have actionable messages?

### 6. Data & edge cases

Based on project type:

- Bad inputs (malformed data, invalid types)
- Large inputs (files, requests, payloads)
- Empty/null values
- Unicode/multilingual content
- Concurrent operations
- Rate limiting scenarios
- Duplicate data handling

### 7. Support burden risks

- What will users ask repeatedly?
- What will break often?
- What requires manual intervention?
- What errors are unclear?
- What documentation is missing?

**Highlight:** anything that will generate high support load

### 8. Pricing & plan logic (if applicable)

Skip if not a commercial product.

- Are plans understandable?
- Any confusing limits?
- Any mismatch between value and pricing?
- Any logic bugs (messages, storage, quotas)?
- Upgrade/downgrade edge cases?
- Trial/free tier abuse risks?

### 9. Security & isolation risks

- Any risk of data leakage between users?
- Any unsafe assumptions?
- API key/secret exposure?
- Input validation gaps?
- Authentication/authorization flaws?
- Insecure defaults?

### 10. Performance & scaling risks

What breaks at:

- 10 users
- 100 users
- 1000 users (or appropriate scale for project)

Identify bottlenecks:

- Database queries
- External API calls
- Memory usage
- File/storage limits
- Compute-heavy operations

### 11. UX & copy problems

- Confusing language?
- Too technical for target users?
- Missing explanations?
- Misleading expectations?
- Broken links or dead pages?
- Accessibility issues?

### 12. Analytics & observability

Can the developer understand:

- Failures (logs, errors)
- User drop-off (analytics, metrics)
- Performance issues
- Usage patterns

Are logs sufficient for debugging production issues?

### 13. Payment / entitlement risks (if applicable)

Skip if not a commercial product.

- Any edge cases where users get wrong access?
- Any risk of overuse without limits?
- Any broken upgrade/downgrade logic?
- Billing integration reliability?

### 14. Legal / expectation risks

- Are you overpromising in marketing?
- Missing disclaimers (beta status, limitations)?
- Risky use cases not restricted?
- Privacy/data handling disclosures needed?
- Terms of service/license clarity?

### 15. "This will bite you later" section

List hidden risks that are not obvious now but will cause pain later:

- Unmaintained dependencies
- Hard-coded values that need config
- Missing migrations/deployment scripts
- Undocumented assumptions
- Accumulating technical debt

---

## Output Format

### Severity Levels

**1. 🔴 Critical issues (must fix before launch)**
**2. 🟠 High-risk issues (should fix soon)**
**3. 🟡 Medium issues (acceptable for beta)**
**4. 🟢 Low priority**

For each issue provide:

- what is wrong
- why it matters
- how it could fail in real usage
- suggested fix (practical, not theoretical)

### Summary Sections

**16. Top 5 things most likely to break in real usage**
**17. Top 5 things that will generate user complaints**
**18. Top 5 things that will create support burden**
**19. Fastest improvements with highest ROI before launch**

---

## Final Judgment

Answer clearly:

**"Is this product ready for public beta?"**

Choose one:

- **YES (safe to launch)**
- **YES WITH RISKS** (list risks and mitigations)
- **NO (not ready)** (list blockers)

Then explain why in detail.

---

## Important Mindset

Do NOT optimize for:

- code elegance
- theoretical perfection
- long-term scalability

Optimize for:

- survival after launch
- first real users
- low support burden
- avoiding catastrophic trust loss

**Be direct. Be specific. Be practical.**

---

## How to Run This Audit

1. Load this skill
2. **Project Discovery:** Explore codebase to understand product type, users, flows
3. **Deep exploration:**
   - Read all source files (focus on core modules)
   - Trace user flows end-to-end
   - Check error handling paths
   - Review business logic (pricing, permissions if applicable)
   - Examine API endpoints and security
4. **Run through each audit section** (skip non-applicable ones)
5. **Identify real failure modes, not theoretical ones**
6. **Output findings in specified format**
7. **Give clear final judgment with reasoning**

---

## Adaptation Guidelines

| Project Type | Focus Areas                                        | Skip Sections       |
| ------------ | -------------------------------------------------- | ------------------- |
| SaaS/Web App | Onboarding, flows, pricing, security, scaling      | -                   |
| Desktop App  | OS compatibility, permissions, crash handling      | Pricing if free     |
| Mobile App   | Device testing, network, battery, store compliance | Pricing if free     |
| CLI Tool     | Args, output, errors, docs                         | Pricing, UI/UX      |
| Library/SDK  | API design, types, docs, edge cases                | Onboarding, pricing |
| API Backend  | Endpoints, auth, validation, scaling               | UI/UX               |
| Open Source  | Docs, contribution guide, licensing                | Pricing             |

---

## Context Files to Check

Look for project-specific context in:

- `README.md` / `readme.md`
- `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`
- `package.json` / `Cargo.toml` / `go.mod`
- `docs/` folder
- Landing page files (`index.html`, `pages/`, `app/` routes)
- Configuration files
