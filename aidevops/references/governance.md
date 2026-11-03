# Governance and PRINCE-lite Control

Use this reference when the user wants PRINCE-style project control without turning a small MVP into a heavy program.

## Principles

- Govern by exception: continue while work stays within agreed tolerances; escalate when it crosses them.
- Keep the business case visible: the MVP exists to prove value, not to complete a backlog.
- Manage by stages: discovery, design, delivery, acceptance.
- Define roles before decisions are needed.
- Keep risk, issue, change, and quality evidence in the phase files.

## Roles

Minimum roles for a small project:

- **Executive / sponsor**: owns business case and release risk.
- **Product owner**: owns scope, PRD, priority, and acceptance.
- **Delivery owner**: owns plan, implementation, verification, and deployment.
- **Design owner**: owns product/service/UX/system design decisions.
- **Reviewer / QA**: owns independent review evidence.

One person can hold multiple roles, but every decision needs an owner.

## Tolerances

Set tolerances in `00-discovery.yaml`:

- Scope: what can change without approval?
- Schedule: timebox or milestone slip allowed?
- Effort/cost: budget or agent/runtime limit?
- Quality: minimum tests, accessibility, security, or performance bar?
- Risk: which risks require escalation?
- Privacy/security: what data or credential exposure is never acceptable?

If a tolerance is breached, record an exception and stop expanding scope until the owner decides.

## Logs

Keep logs concise:

- **Decision log**: decision, owner, date, rationale, affected IDs.
- **Risk log**: risk, probability, impact, mitigation, owner, status.
- **Issue log**: current problem, impact, owner, next action.
- **Change log**: requested change, reason, affected scope, decision.
- **Quality log**: checks planned, checks run, evidence, result.

For the minimal workflow, put:

- Business case, roles, tolerances, and early decisions in `00-discovery.yaml`.
- Design and architecture quality criteria in `01-design.yaml`.
- Active risk/issue/change logs plus deployment controls in `02-delivery.yaml`.
- Final quality evidence, release decision, accepted risks, and retrospective in `03-acceptance.yaml`.

## Stage Gates

Discovery gate:

- Business case is still valid.
- MVP scope and success signal are explicit.
- Open questions are accepted or resolved.
- Tolerances and owners are named.

Design gate:

- Product, service, UX, IA, visual direction, and architecture are coherent.
- Prototype requests visualize approved decisions.
- Security/privacy and data boundaries are explicit.

Delivery gate:

- P1 story is independently testable.
- Tasks have owners, dependencies, verification, and acceptance refs.
- Deployment, env, migration, rollback, and git plan are present.
- Active risks and issues have owners.

Acceptance gate:

- Evidence maps to PRD/story IDs.
- Release blockers are resolved or explicitly accepted.
- Rollback/manual fallback is possible or intentionally deferred.
- Lessons and next sprint candidates are captured.

## Exception Handling

Create an exception when:

- A requirement cannot be met within the MVP tolerance.
- A security/privacy or credential risk appears.
- A prototype or implementation changes product scope.
- A dependency or API behavior invalidates the plan.
- Verification cannot be run and no equivalent manual evidence exists.

An exception record needs: trigger, impact, options, recommended action, owner, and decision.
