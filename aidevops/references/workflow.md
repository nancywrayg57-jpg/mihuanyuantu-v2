# AidevOps Workflow

This reference is the full operating loop for a small software project. Use it when the user asks for a complete AI-assisted development process, a project plan, or help moving from idea to MVP delivery.

## Principles

- **MVP first**: Build the smallest independently useful vertical slice before broadening scope.
- **Spec before code**: Requirements, flows, contracts, and acceptance criteria drive implementation.
- **Evidence over confidence**: Every phase exits with artifacts and checks, not just narrative approval.
- **Language agnostic**: Prefer the target repo's actual stack and conventions; do not force a framework.
- **Human-in-loop**: Ask for decisions at product tradeoffs, risk acceptance, visual direction, and release readiness.
- **Learning loop**: Retrospectives update docs, prompts, checks, and future task patterns.

## Document-First Operation

AidevOps does not require Python. The authoritative workflow is the document set under `docs/<feature-slug>/`: `progress.yaml`, `wiki.md`, `00-discovery.yaml`, `01-design.yaml`, `02-delivery.yaml`, `03-acceptance.yaml`, `input/`, and `prototypes/`.

Use scripts only as optional accelerators for initialization, validation, or API smoke tests. When scripts are not used, create the phase files from `references/templates.md` and update them directly.

Each phase file must carry its own `phase_confirmation` block. This keeps final decisions distributed where they belong:

- Discovery confirms final requirements, MVP scope, user stories, assumptions, and open questions.
- Design confirms UX, visual system, prototype plan, architecture, contracts, and technical risks.
- Delivery confirms sprint scope, tasks, Git readiness, environment, deployment, migration, and rollback.
- Acceptance confirms verification evidence, release verdict, accepted risks, retrospective, and next sprint.

`progress.yaml` only points to the latest evidence and next action. It must not become the only place where requirements or phase decisions are recorded.

Each phase file must also carry `knowledge_assets`. This block records phase outcomes, lessons, reusable rules, prompts/commands, and evidence links. Update `wiki.md` from those assets at the end of each phase so the feature has a local LLM Wiki for future agents and reviewers.

## Clarification Modes

Default to `ask-user` for real delivery. Ask no more than 5 high-impact questions per round and stop before decisions that change architecture, security, cost, data policy, or release risk.

Use `auto-assume` only when the user explicitly says the run is a test, evaluation, demo, dry run, or should be automatically completed. In that mode, continue by filling missing non-sensitive details with minimal assumptions, mark each one as `[AUTO-FILLED FOR TEST: reason]`, and keep protected decisions unconfirmed until the user approves them. Protected decisions are technical stack, auth/identity, deployment target, data policy, and AI/model boundary.

Record the active mode in `progress.yaml.clarification_policy` and keep the question/assumption trail in `00-discovery.yaml.clarification` plus the active phase's `phase_confirmation`.

## Beginner Vibe Coding Fast Lane

Use this fast lane when the user wants rapid MVP work, is new to coding, or explicitly says "vibe coding". Read `references/vibe-coding.md`.

This mode still uses the same phase files, but the working unit is one visible slice:

1. Capture a one-sentence intent: product, target user, painful job, visible success.
2. Ask at most 5 questions; in explicit test mode, auto-fill non-sensitive gaps and label them.
3. Write the thinnest useful PRD/story/acceptance slice.
4. Create design artifacts before coding UI.
5. Build or plan one independently demoable story.
6. Run the app or prototype locally, provide the URL when a dev server is needed, and record verification.
7. Update `knowledge_assets`, `wiki.md`, and `progress.yaml.vibe_coding`.

Before coding, classify the work as `throwaway prototype` or `production-intended code`. Throwaway prototypes may use lighter assumptions, but production-intended code still requires Git, confirmed stack, auth/identity, deployment, data policy, and AI/model boundary decisions.

Beginner guidance rules:

- Use Chinese for next-step explanations and review notes.
- Prefer one decision or one command at a time.
- Recommend a default when useful, but keep protected decisions unconfirmed until the user approves.
- Do not hide blockers behind generated code.
- Keep the user oriented with current phase, current slice, local URL or command, and next action.

## Phase 0: Repo and Context Scan

For brownfield projects:

1. Inspect `README`, `AGENTS.md`, package manifests, lockfiles, docs, tests, CI, and source layout.
2. Identify the framework, routing, data, auth, deployment, test commands, lint/format conventions, and existing UI system.
3. Find where requirements and architecture docs already live.
4. Record constraints that affect the new feature.

For greenfield projects:

1. Ask the user for target platform, preferred language, deployment target, non-negotiable integrations, budget/timebox, and team skill level.
2. Recommend the simplest common stack that can ship the MVP.
3. Avoid future-proofing beyond confirmed constraints.
4. In explicit test/evaluation mode, auto-fill missing answers with minimal local-first defaults and mark them as test assumptions.

Reference scan for vibe coding and fast MVPs:

1. Search GitHub and, for domestic Chinese users when useful, Gitee for similar apps, templates, admin dashboards, or workflow examples.
2. If the user provides a reference framework/base repo, scan it before proposing code directories.
3. Extract reusable functions, IA, data models, component patterns, directory conventions, tests, env/deploy patterns, and anti-patterns.
4. Record findings in `00-discovery.yaml.reference_scan`, `02-delivery.yaml.code_structure`, and `wiki.md`.
5. Do not copy code or assets unless license and user intent are explicit.

Input handling:

1. Create or identify `docs/<feature-slug>/input/`.
2. Ask the user to place current requirements, rough PRDs, samples, screenshots, or notes there.
3. If a source PRD already exists elsewhere in the repo, copy or reference it from the input folder and record the source path in `progress.yaml`.
4. Never put secrets, real credentials, or sensitive customer data into this folder unless the repo is approved for that data.

Language handling:

1. For domestic Chinese beginner users, write explanations, PRD fields, phase notes, UI copy, and review findings in Chinese by default.
2. Keep code identifiers, filenames, environment variables, HTTP routes, API/model names, stack names, and external issue titles in English.
3. For image-generation prompts, use bilingual structure when it improves model output: English layout/style instructions plus exact Chinese UI copy and sample data.
4. For stakeholder artifacts, avoid unexplained English process jargon; if an English method name is useful, include a short Chinese meaning once.

Exit artifact: update `00-discovery.yaml.phase_confirmation`, update `00-discovery.yaml.knowledge_assets`, update `wiki.md`, and set `progress.yaml.current_phase` to `discovery`.

## Phase 1: Discovery and PRD

Run discovery in short rounds. Ask no more than 5 questions per round, grouped by decision impact:

- User and buyer: who uses it, who approves it, who is excluded for v1?
- Problem and value: what painful moment does the product improve?
- Current workflow: how is the job done today?
- Primary journey: what is the first value-delivering path?
- Constraints: platform, integrations, data sensitivity, compliance, budget, deadline.
- Scope: what is explicitly not in MVP?
- Success: what measurable or observable result proves the MVP works?

Write requirements as stable IDs:

- `UJ-N`: User journey.
- `FR-N`: Functional requirement.
- `NFR-N`: Non-functional requirement.
- `SM-N`: Success metric.
- `US-N`: User story.
- `AC-N`: Acceptance criterion.

Exit gate:

- Blocking `[NEEDS CLARIFICATION]` markers are either answered or explicitly accepted as assumptions.
- Test-mode `[AUTO-FILLED FOR TEST]` assumptions are visible and not treated as user-confirmed production decisions.
- MVP in-scope and out-of-scope lists are clear.
- Every FR has at least one testable consequence or acceptance criterion.
- `00-discovery.yaml.phase_confirmation` lists confirmed requirement decisions and remaining open questions.
- `00-discovery.yaml.knowledge_assets` and `wiki.md` preserve source lessons, product terminology, rejected scope, and reusable discovery rules.
- `progress.yaml.vibe_coding.current_loop` names the visible output and verification signal when fast-lane mode is active.

## Phase 2: Role Flows and Design Spine

Create a design spine before drawing screens:

1. Role/persona inventory: only roles that change permissions, behavior, or content.
2. Product model: user job, value moment, feature boundaries, terminology.
3. Service/system map: actors, handoffs, integrations, manual/back-office steps, recovery paths.
4. Journey map: entry state, trigger, path, value moment, completion, recovery.
5. Interaction model: primary actions, controls, feedback, validation, empty/loading/error/permission states.
6. Navigation and IA: top-level surfaces, nested flows, critical transitions.
7. Content/data states: realistic sample data, permissions, validation errors.
8. Visual direction: product category, tone, visual references, anti-references, accessibility level, design tokens.
9. Visual prototype quality: before PNG generation, freeze a design-system lock from `DESIGN.md`, `EXPERIENCE.md`, and `visual-system.html`. Use draft PNG mode by default; read `references/visual-prototype-quality.md` for strict consistency review only when the user asks for approved UI, production-ready design, or exact matching.

Exit gate:

- A developer can name all MVP screens and states.
- Service/system handoffs and recovery states are visible.
- Prototype prompts can be generated without inventing major screens.
- Visual style serves the domain, not a generic landing page.
- `01-design.yaml.phase_confirmation` lists confirmed design and architecture decisions or blockers.
- `01-design.yaml.knowledge_assets` and `wiki.md` preserve design decisions, tokens, prototype prompts, architecture tradeoffs, and quality checks.
- Beginner-facing design work has a visible board, screenshot, or local URL; text-only design is acceptable only when explicitly deferred.
- Required PNG prototypes, when requested, are real generated PNGs; screenshots of the board do not count. Draft mode requires `validation_mode: simple_return`, preserved returned bytes, validation reports, target size/quality in prompts, and rough flow match. Strict mode additionally requires visual consistency review against the visual board.

Exit artifact: update `01-design.yaml.phase_confirmation`, update `01-design.yaml.knowledge_assets`, update `wiki.md`, and update `progress.yaml.capabilities`.

## Phase 3: Architecture and Contracts

Translate the PRD into build decisions:

- System context: apps, services, external systems, users.
- Data model: entities, relationships, ownership, retention, migration needs.
- APIs/contracts: endpoints, events, request/response shapes, error codes, permissions.
- Security/privacy: auth, authorization, secret handling, data boundaries.
- Observability: logs, metrics, audit trail, debugging entry points.
- Deployment: environments, config, migrations, rollback.
- Tradeoffs: decisions made, alternatives rejected, risks.

Exit gate:

- Every major technical decision ties to an FR, NFR, constraint, or repo convention.
- No unowned integration, credential, data migration, or deployment assumption remains hidden.
- The plan names what will be verified automatically and what needs manual acceptance.
- Uncertain stack choices are either confirmed by the user or marked as blockers. When no preference exists, recommend local-first Go, Python, Node.js, or plain HTML prototypes with SQLite for the first local MVP database, then wait for confirmation before production-intended code.
- Architecture decisions are confirmed in `01-design.yaml.phase_confirmation` before production-intended code.
- Architecture lessons and reusable constraints are written to `01-design.yaml.knowledge_assets` and `wiki.md`.

Exit artifact: update `01-design.yaml.phase_confirmation`, update `01-design.yaml.knowledge_assets`, update `wiki.md`, and update the design/architecture gate in `progress.yaml`.

## Phase 4: Sprint and Task Breakdown

Create the MVP sprint from independently testable stories:

1. Sort user stories by value and dependency.
2. Mark `US-1` or the P1 story as MVP unless another slice better proves the product.
3. Split tasks into setup, foundation, per-story implementation, and polish.
4. Give each task a path or artifact target when possible.
5. Attach verification evidence to each story.

Task format:

```markdown
- [ ] T001 [US-1] Implement <capability> in <path>. Depends: T000. Verify: <command/check>. AC: <criterion id>.
```

Put deployment, env, migration, release, rollback, and git notes in `02-delivery.yaml`. Do not create a separate deploy file for the MVP unless the target repo already has a required deployment document.

Before production-intended code, define `02-delivery.yaml.code_structure`:

- Target repo or app root.
- Framework/runtime and package manager.
- Directory map for source, UI/routes, domain/services, data/models, tests, migrations, config, static assets, docs.
- Naming conventions for files, classes/functions, routes, database tables, env vars.
- Formatting/lint/typecheck/test commands.
- Migration and seed-data rules.
- Asset rules for generated PNGs, screenshots, icons, and prototype files.
- Files/directories the coding agent must not touch.

For brownfield projects, inherit existing conventions from `README`, `AGENTS.md`, package manifests, lockfiles, source tree, tests, and config. For greenfield projects, propose a minimal local-first structure and mark it pending user confirmation.

Before production-intended code, run the delivery-git child skill. Check `git --version`, guide the user to install Git if missing, confirm or initialize repository version control with user approval, inspect branch/dirty state, and record the result in `02-delivery.yaml.git`.

Exit gate:

- The first story can be built, tested, and demoed without completing later stories.
- Shared foundation work is minimal and blocks only what it must.
- Tasks do not contain vague verbs such as "handle", "improve", or "make better" without measurable output.
- `02-delivery.yaml.phase_confirmation` records sprint, Git, env, deployment, rollback, and pre-code go/hold status.
- `02-delivery.yaml.knowledge_assets` and `wiki.md` preserve commands, task patterns, env/deploy/rollback notes, and implementation lessons.
- For vibe coding, each implementation loop lists one visible output, one local run command or URL, and one verification result.

Exit artifact: update `02-delivery.yaml.phase_confirmation`, update `02-delivery.yaml.knowledge_assets`, update `wiki.md`, and set the next action in `progress.yaml`.

## Phase 5: Build Loop

For each story:

1. Confirm Git is installed, the project is under version control, and current branch/worktree state is understood.
2. Write/adjust contracts and tests if practical.
3. Implement the smallest vertical slice.
4. Run focused validation.
5. Update `02-delivery.yaml` task status.
6. Review diff for unrelated churn, secrets, generated noise, and requirement drift.
7. Update task and evidence pointers in `progress.yaml`.
8. Commit only coherent work when commits are requested or expected.

Stop after a story when:

- Acceptance criteria pass.
- A design or requirement conflict appears.
- The next step would expand scope beyond the sprint.

## Phase 6: Review, Acceptance, and Release

Review order:

1. Correctness and requirements mapping.
2. Security and data integrity.
3. Error handling and observability.
4. UX and accessibility.
5. Performance and maintainability.
6. Tests and deployability.

Acceptance report shape:

```markdown
# Acceptance Report: <feature>

## Summary
- Status: pass | concerns | fail
- Build/slice reviewed:
- Remaining release blockers:

## Requirement Evidence
| ID | Evidence | Result | Notes |
| --- | --- | --- | --- |
| FR-1 | <test/command/manual path> | pass | |

## Defects and Follow-ups
- [severity] <issue> -> owner/next action
```

For the minimal workflow, write this evidence into `03-acceptance.yaml` instead of creating a separate report, then set `progress.yaml.current_phase` to `acceptance`.

## Phase 7: Retrospective and Knowledge Backflow

Capture:

- What changed from the PRD and why.
- Which assumptions were wrong.
- Which checks caught real issues.
- Which reusable rule should be added to project docs, AGENTS, templates, or this workflow.
- Next sprint candidates ordered by value.

Do not preserve private customer details in reusable public workflow assets.

Exit artifact: update `03-acceptance.yaml.phase_confirmation`, update `03-acceptance.yaml.knowledge_assets`, and update `wiki.md`.
