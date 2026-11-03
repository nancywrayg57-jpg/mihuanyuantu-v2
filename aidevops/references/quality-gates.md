# Quality Gates, Review, Git, and Agent Delegation

Use this reference when creating sprint checks, reviewing implementation, planning release, or delegating work to coding agents.

## Gate 1: PRD Readiness

Pass when:

- MVP in/out scope is explicit.
- Business case, owner, and governance tolerances are visible.
- Source requirements or rough PRD are stored or referenced from `input/`.
- Roles and journeys that affect behavior are documented.
- Every FR has testable acceptance criteria.
- Success metrics and counter-metrics are named when meaningful.
- `[NEEDS CLARIFICATION]` markers are resolved or accepted as assumptions.
- Non-goals prevent likely scope creep.
- `progress.yaml` points to the discovery evidence and next capability.
- `00-discovery.yaml.knowledge_assets` and `wiki.md` capture source lessons, terminology, assumptions, and reusable discovery rules.

Fail when:

- The PRD is mostly feature names without user value.
- Requirements use adjectives instead of measurable behavior.
- Hidden assumptions decide architecture or data handling.

## Gate 2: Design Readiness

Pass when:

- Product, service/system, interaction, IA, and visual system decisions are separated.
- `DESIGN.md` and `EXPERIENCE.md` exist or are explicitly deferred with an owner and reason when visual/UX work is part of the request.
- Screen inventory covers the MVP journey.
- Empty, loading, error, and permission states are considered.
- UX spec names visual direction and anti-references.
- Prototype prompts do not invent unapproved features.
- Prototype images, if generated, have validation reports when generated through an API relay and are reviewed at the active validation level.
- If `prototype_image_request.required` is `true`, real PNG files exist and are listed in `generated_assets`; HTML boards, visual-system screenshots, contact sheets, or SVG mockups do not satisfy this gate.
- Validation reports prove the route used `responses-image-tool` with `gpt-image-2`; prompt/report evidence includes target size and quality.
- `prototype_image_request.design_system_lock` exists and was used in the image prompts.
- Draft PNG mode (`validation_mode: simple_return`) has the minimum evidence: returned PNG files are preserved unchanged, validation reports exist, prompts include target size and quality, the refreshed `prototypes/visual-system-desktop.png` is referenced when available, and notes say the images are draft references rather than approved UI.
- Strict PNG mode is required only when the user asks for approved UI, production-ready design, or exact visual matching. In strict mode, required PNGs pass visual consistency review against `DESIGN.md`, `EXPERIENCE.md`, and `visual-system.html`; rejected PNGs are not listed as generated assets; `prototype_image_request.visual_consistency_review.status` is `pass`.
- `system_flow_diagram` exists with `prototypes/system-flow.html` and a valid `prototypes/system-flow.png` when the MVP has app/backend/data/AI/review/export boundaries.
- Accessibility expectations are explicit.
- `progress.yaml` records the design gate result and prototype evidence pointers when images are generated.
- `01-design.yaml.knowledge_assets` and `wiki.md` capture design decisions, prototype prompts, visual rules, architecture tradeoffs, and review notes.

## Gate 3: Architecture Readiness

Pass when:

- Data ownership, migrations, and retention are clear.
- API/contracts map to FRs and stories.
- Security, privacy, permissions, and secret handling are explicit.
- Observability and rollback paths are documented.
- Simpler alternatives were considered before adding new services or abstractions.

## Gate 4: Sprint Readiness

Pass when:

- P1 story is independently buildable, testable, and demoable.
- Setup/foundation tasks are minimal and justified.
- Tasks include exact paths or artifact targets.
- Code directory and format rules are defined in `02-delivery.yaml.code_structure` or inherited from the target repo.
- Each story has verification commands or manual checks.
- Parallel tasks are marked only when they touch independent files or systems.
- Deployment, env, migration, rollback, and git controls are in `02-delivery.yaml`.
- Risk, issue, change, and quality logs have owners when non-empty.
- `02-delivery.yaml.knowledge_assets` and `wiki.md` capture commands, task patterns, env/deploy/rollback notes, and implementation lessons.

## Gate 4.5: Pre-Code Release

Before writing production-intended code, produce a go/hold decision.

Pass when:

- Identity/auth source is decided or isolated behind a deliberate adapter.
- Deployment target, storage, migration, and rollback assumptions are explicit.
- Data classification, retention, logging, and secret handling are acceptable.
- AI/model calls, if any, have approved data boundaries and a non-AI fallback.
- P1 stories form one independently demoable user-value loop.
- Acceptance scenarios exist for the first slice.
- Open questions are non-blocking or accepted as risks by an owner.

Hold when:

- The PRD has feature lists but no acceptance criteria.
- A core integration, identity source, data policy, or deployment target is unknown.
- The technical stack is guessed instead of confirmed. Recommend local-first Go, Python, Node.js, or plain HTML prototypes with SQLite for local MVPs, but require user confirmation.
- The coding agent has no agreed directory, naming, formatting, migration, env, or test conventions.
- AI output quality is essential but no quality threshold, sample set, or human correction path exists.
- The MVP scope cannot be completed as one testable vertical slice.

Record the decision in `03-acceptance.yaml.release_decision` and link blockers from `progress.yaml.next_action`.

## Gate 4.6: Vibe Coding Loop

Pass when fast-lane mode is active and:

- `progress.yaml.vibe_coding.current_loop.goal` names one slice, not a bundle of unrelated features.
- The slice has a visible output: local URL, screenshot, prototype board, generated asset, or command output.
- If the loop goal explicitly says PNG prototype images, the visible output must include real generated PNG files, not only a prototype board or screenshot.
- Verification is recorded: compile/test/lint, browser check, API smoke test, or manual acceptance mapped to a story.
- The user can understand the next action from one short Chinese explanation.
- `wiki.md` records the loop result and next safest step.

Hold when:

- The agent is about to code without knowing whether this is throwaway prototype or production-intended work.
- There is no way for the user to run or inspect the output.
- A generated UI has not been visually checked.
- The loop expands into multiple unverified features.

## Gate 5: Code Review

Review findings first, ordered by severity:

- Bugs or requirement mismatches.
- Security/privacy issues.
- Data integrity and migration risks.
- Error handling and observability gaps.
- UX/accessibility regressions.
- Missing or weak tests.
- Maintainability issues that will affect the next sprint.

For each finding include:

```markdown
- **Severity**: <critical|high|medium|low>
  **Location**: <file:line or artifact section>
  **Issue**: <specific problem>
  **Impact**: <why it matters>
  **Fix**: <concrete remediation>
```

## Verification Matrix

Use this table in `03-acceptance.yaml` or a stakeholder-facing acceptance report:

| Layer | Evidence Examples |
| --- | --- |
| Requirements | PRD IDs mapped to stories and checks |
| Static quality | typecheck, lint, format, compile |
| Unit | domain logic, validators, utility functions |
| Contract | API schema, event schema, SDK/public surface |
| Integration | DB, auth, external provider, key workflow |
| E2E/manual | user journey screenshots, screen recordings, smoke tests |
| Security | permission boundaries, secret scan, injection/abuse checks |
| Release | migration dry run, rollback notes, env/config check |

## Hub Progress Gate

Pass when:

- `progress.yaml.current_phase` matches the latest active phase.
- Every completed capability has an evidence pointer.
- Every phase gate is `pass`, `accepted_risk`, or has a named blocker.
- No capability status says `complete` while the referenced phase file is still blank.
- `wiki.md` exists and every completed phase has contributed outcomes, lessons, or evidence through `knowledge_assets`.
- If `vibe_coding.enabled` is true, every completed loop has visible output and verification evidence.
- The next action has an owner or is explicitly marked complete.

## Git Workflow

Before production-intended code, guide the user to install and use Git:

1. Run `git --version`.
2. If missing, provide install guidance:
   - Windows: install Git for Windows, then reopen the terminal.
   - macOS: `xcode-select --install` or `brew install git`.
   - Ubuntu/Debian: `sudo apt update && sudo apt install git`.
   - CentOS/RHEL/Fedora: `sudo yum install git` or `sudo dnf install git`.
3. Run `git rev-parse --is-inside-work-tree`.
4. If not a repo, ask before `git init`.
5. Inspect current branch and dirty state before edits.
6. Create a branch such as `feature/<slug>` or follow local convention.
7. Keep commits small and coherent if commits are requested.
8. Do not commit secrets, `.env`, raw generated credentials, or noisy local artifacts.
9. Before handoff run:
   - focused tests for touched code,
   - broader project checks when feasible,
   - `git diff --check` when git exists.
10. Write PR descriptions with:
   - Summary,
   - Requirement/story IDs,
   - Verification commands and results,
   - Risks/deferred scope,
   - Screenshots/prototype links when relevant.

## Delegating to Coding Agents

Delegate only when the task is clear enough to verify independently:

- Good: repetitive refactors, isolated story implementation, test generation, static audit.
- Risky: product tradeoffs, vague UX changes, security-sensitive design, broad architecture.

Delegation brief:

```markdown
# Agent Task Brief

## Goal
<single outcome>

## Scope
In:
Out:

## Required Context
- PRD/story IDs:
- Architecture decisions:
- Existing patterns/files:

## Rules
- Reuse existing helpers:
- Do not change:
- Stop if:

## Verification
- Commands:
- Manual checks:

## Expected Output
- Files changed:
- Report format:
```

After delegated work:

1. Independently inspect the diff.
2. Run the verification commands yourself when possible.
3. Check for silent feature loss, overbroad refactors, and invented architecture.
4. Update acceptance evidence only after verification, not from the agent's claim.

## Retrospective

Record:

- What shipped.
- What changed from the plan.
- Defects found and how they were caught.
- Missed checks to add next time.
- Reusable project rules or templates to update.
- Next sprint candidates.
- Which wiki entries should guide the next agent or next similar project.
