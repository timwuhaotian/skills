# audit-pre-release

You are acting as a senior product + engineering + growth reviewer.

Your task:
Perform a full, no-blind-spot audit of the Kodda project in preparation for a public beta launch.

Context:
Kodda is a RAG-based AI platform that is being repositioned into a focused product:
"An AI support widget for product docs and FAQs."

Target users:

- Indie SaaS founders
- Developer tool founders
- Small teams with public docs / help centers
- Users without dedicated support teams

Primary use case:
Users upload or sync public docs → create an AI assistant → embed it on their website → answer support / pre-sales questions.

Constraints:

- Built by a solo developer
- Limited support bandwidth (not 24/7)
- Public beta launch (not production-grade SaaS yet)
- Goal: get first real users and first paid conversions
- Must minimize support burden and catastrophic failures

Your mission:
Audit the ENTIRE product and codebase as if this is going live to real users tomorrow.

Do NOT be polite.
Be brutally honest.
Focus on real-world failure, not theoretical perfection.

---

## Audit Scope

### 1. Product positioning & clarity

- Is the product clearly positioned as a docs support AI tool?
- Are there conflicting signals (platform vs tool)?
- Would a new user understand what this does in 10 seconds?

### 2. Onboarding & time-to-value

- Can a new user reach first "wow moment" quickly?
- Any friction points that would cause drop-off?
- Any unnecessary complexity?

### 3. Core user flow (critical)

Evaluate end-to-end:

- upload docs
- create bot
- test chat
- embed widget
- user asks questions

Find:

- breakpoints
- confusing steps
- fragile areas
- anything that might fail silently

### 4. RAG quality risks

- Where can retrieval fail badly?
- Where can hallucination happen?
- Are there missing guardrails?
- Is the system predictable enough for public-facing use?

### 5. Failure handling & resilience

What happens when:

- embedding fails
- LLM fails
- rerank fails
- no relevant context found

Are users informed properly?
Are failures silent or visible?

### 6. Data & edge cases

- Bad PDFs
- Large files
- empty documents
- multilingual content
- weird formatting
- duplicated content

### 7. Support burden risks

- What will users ask you repeatedly?
- What will break often?
- What requires manual intervention?

**Highlight:** anything that will generate high support load

### 8. Pricing & plan logic

- Are plans understandable?
- Any confusing limits?
- Any mismatch between value and pricing?
- Any logic bugs (messages, storage, quotas)?

### 9. Security & isolation risks

- Any risk of data leakage between users?
- Any unsafe assumptions?
- API key exposure?
- improper validation?

### 10. Performance & scaling risks

What breaks at:

- 10 users
- 100 users
- 1000 users

Bottlenecks: DB, vector search, LLM calls

### 11. UX & copy problems

- Confusing language?
- Too technical?
- Missing explanations?
- Misleading expectations?

### 12. Analytics & observability

Can the developer understand:

- failures
- user drop-off
- bad answers

Are logs sufficient?

### 13. Payment / entitlement risks

- Any edge cases where users get wrong access?
- Any risk of overuse without limits?
- Any broken upgrade/downgrade logic?

### 14. Legal / expectation risks

- Are you overpromising?
- Missing disclaimers?
- Risky use cases not restricted?

### 15. "This will bite you later" section

List hidden risks that are not obvious now but will cause pain later

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
- **YES WITH RISKS**
- **NO (not ready)**

Then explain why in detail.

---

## Important Mindset

Do NOT optimize for:

- code elegance
- theoretical perfection
- long-term scalability

Optimize for:

- survival after launch
- first paying users
- low support burden
- avoiding catastrophic trust loss

**Be direct. Be specific. Be practical.**

---

## How to Run This Audit

1. Load this skill
2. Explore the codebase thoroughly:
   - Read all source files
   - Test the actual user flows
   - Check error handling paths
   - Review pricing logic
   - Examine API endpoints and security
3. Run through each audit section systematically
4. Identify real failure modes, not theoretical ones
5. Output findings in the specified format
6. Give clear final judgment with reasoning
