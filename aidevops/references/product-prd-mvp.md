# Product, PRD, and MVP

Use this reference when turning an idea into requirements, stories, and a minimal usable release.

## Input Folder

Before optimizing a new idea or PRD, guide the user to place source material under:

```text
docs/<feature-slug>/input/
```

Accepted inputs:

- Rough PRD or requirement notes.
- Current manual workflow samples.
- Screenshots or sample reports.
- Meeting notes or stakeholder feedback.
- Sanitized data samples.

If the user gives a file elsewhere, reference or copy it into `input/` and record the source in `progress.yaml.source_prd` or `evidence_pointers.source_inputs`.

## Idea Forge

Before writing a PRD, pressure-test the idea:

- **Assumptions**: what must be true for the product to work?
- **Cracks**: where can the workflow, market, data, integration, or trust model fail?
- **Locks**: decisions already fixed by user, business, repo, platform, or deadline.
- **Kill criteria**: facts that would make the MVP not worth building.
- **Fast evidence**: smallest research, prototype, spike, or manual test that reduces the highest risk.

Ask one focused round of questions when a missing answer changes scope, architecture, or release risk.

## PRD Spine

Use stable IDs so later work can trace back:

- `UJ-N`: user journey.
- `FR-N`: functional requirement.
- `NFR-N`: non-functional requirement.
- `SM-N`: success metric.
- `US-N`: user story.
- `AC-N`: acceptance criterion.

Minimum PRD contents:

- Product promise and target user.
- Business case and constraints.
- Glossary of product terms.
- MVP user journeys with entry, path, value moment, resolution, and recovery.
- Functional requirements with observable acceptance criteria.
- Non-functional requirements for security, privacy, performance, accessibility, reliability, and observability when relevant.
- In-scope, out-of-scope, and deferred scope.
- Success metrics and counter-metrics.
- Assumptions and open questions.

## Story Rules

A good user story:

- Names the actor, capability, and user value.
- Can be built and verified without completing later stories.
- Has acceptance scenarios, including at least one edge or failure state when meaningful.
- Names dependencies explicitly.
- Avoids vague verbs such as "manage", "handle", or "support" unless the acceptance criteria make them concrete.

## MVP Slicing

Prefer one vertical journey over many shallow features. A normal first MVP has:

- One primary role.
- One primary journey.
- One core data object or workflow.
- One happy path.
- Enough empty/error/recovery behavior to avoid a broken demo.
- One release path with rollback or manual fallback.

Default slicing order:

1. Manual or mocked workflow that proves value.
2. Single-user or single-tenant workflow.
3. Real persistence and validation.
4. Integration or automation.
5. Scale, permissions, analytics, and advanced states.

Do not add advanced roles, dashboards, settings, notifications, or admin controls unless they are required to complete the first value journey safely.

## PRD Quality Gate

Pass only when:

- MVP in/out scope is explicit.
- Every P1 requirement has an acceptance criterion.
- Major assumptions are named and either validated or accepted.
- The smallest release is demoable and useful without deferred stories.
- Governance tolerances say when to stop, escalate, or release with risk.
