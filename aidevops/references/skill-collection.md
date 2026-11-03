# AidevOps Skill Collection

AidevOps is a local skill collection and orchestrator. Child skills live under `aidevops/skills/` as upstream snapshots; `references/` contains AidevOps-specific routing and phase-file notes. Do not rewrite upstream child skills unless there is a concrete conflict. The parent AidevOps workflow maps their outputs into one progress ledger and four phase files.

Every complete flow also maintains `docs/<feature>/wiki.md`. Each phase writes process assets to `knowledge_assets` first, then durable lessons, outcomes, prompts, commands, risks, and decisions are summarized into the wiki.

For beginner or vibe-coding requests, AidevOps also maintains `progress.yaml.vibe_coding`: one visible slice per loop, a clear next user action, and evidence that the output ran or was inspected.

## Language Policy

For domestic Chinese beginner users:

- Use Chinese for guidance, questions, PRD/design/delivery/acceptance notes, UI copy, and review findings.
- Keep filenames, code identifiers, environment variables, API routes, model names, HTTP fields, and external issue names in English.
- Use bilingual prompts for image generation when helpful: English layout/style instructions plus exact Chinese labels and sample data.
- Explain framework names in Chinese once when first used.

## Capability Spine

| AidevOps Capability | Upstream Child Skills | Inspired By | What to Keep | Output Location |
| --- | --- | --- | --- | --- |
| `intake` | `bmad-prd`, `bmad-spec` | BMAD PRD brain dump, Spec Kit input discipline | Put rough requirements and source material in `docs/<feature>/input/`; extract facts, assumptions, and cracks before authoring. | `progress.yaml`, `00-discovery.yaml` |
| `idea-forge` | `bmad-forge-idea` | BMAD Forge / elicitation | Pressure-test value, scope, risks, and kill criteria. Ask one high-impact question at a time when blocked. | `00-discovery.yaml` |
| `prd` | `bmad-prd`, `bmad-spec` | BMAD PRD, BMAD Spec, Spec Kit spec | Stable requirement IDs, journeys, acceptance scenarios, open-question markers, source reconciliation. | `00-discovery.yaml` |
| `mvp-slicing` | `bmad-prd`, `bmad-spec`, `team-lifecycle-v4` | Spec Kit independently testable stories, Maestro lifecycle | P1 story must be independently demoable, testable, and deployable. Avoid broad backlog dumps. | `00-discovery.yaml`, `02-delivery.yaml` |
| `governance` | `team-lifecycle-v4`, `bmad-check-implementation-readiness` | PRINCE-lite, BMAD readiness, Maestro checkpoints | Business case, roles, tolerances, risk/issue/change/quality logs, go/hold decisions. | All phase files |
| `designer` | `bmad-ux`, `ux-coach`, `frontend-design`, `team-uidesign`, `team-ui-polish`, `team-ux-improve`, `team-visual-a11y`, `ui-ux-pro-max` | Anthropic frontend-design, BMAD UX, UI/UX Pro Max, Maestro UI skills | Produce `DESIGN.md` and `EXPERIENCE.md` before visual mockups; score visual quality before images/code. | `01-design.yaml`, `prototypes/` |
| `prototype-image-request` | `imagegen`, `openai-docs`, `frontend-design`, `bmad-ux`, UI QA specs | OpenAI image generation, relay compatibility findings, design prompt handoff | Generate only decision-critical screens; validate model route, PNG dimensions, metadata, image tool usage, and visual consistency against the design spine. Relay implementations are compatibility notes, not child skills. | `01-design.yaml`, `prototypes/` |
| `architect` | `bmad-agent-architect`, `maestro-plan`, `bmad-check-implementation-readiness` | BMAD Architect, Spec Kit plan, Maestro plan | Prefer boring/local-first architecture; confirm stack before production-intended code. | `01-design.yaml` |
| `delivery-planner` | `maestro-plan`, `team-lifecycle-v4`, `code-review-testing` | Spec Kit tasks, Maestro plan/TDD, Codex testing review | Setup, foundation, user-story slices, Git readiness, verification commands, deployment/rollback in one delivery file. | `02-delivery.yaml` |
| `reviewer` | `quality-review`, `bmad-code-review`, `code-review`, `code-review-testing` | Codex code-review, BMAD code review, Maestro quality-review | Findings first, traceability, security/privacy, acceptance matrix, release decision. | `03-acceptance.yaml` |
| `retro-knowledge` | `team-lifecycle-v4`, `quality-review` | Maestro knowledge backflow | Capture reusable rules, changed assumptions, missed checks, next sprint candidates. | `03-acceptance.yaml` |

Fast-lane mode is not a separate child skill. It is an AidevOps operating mode that uses the same capabilities in smaller loops.

## Aggregation Order

Run capabilities in this order unless the user asks for a narrow artifact:

1. Intake and source placement.
2. PRD and MVP slicing.
3. Governance setup.
4. Designer spine: `DESIGN.md` and `EXPERIENCE.md`.
5. Prototype prompt pack and image generation when useful.
6. Architecture and contracts.
7. Sprint delivery plan.
8. Pre-code go/hold gate.
9. Implementation loop only after blockers are resolved.
10. Acceptance, release, rollback, and retrospective.

After every capability, update the relevant phase file, `phase_confirmation` when needed, `knowledge_assets`, `wiki.md`, and then `progress.yaml`.

In vibe-coding mode, also update `progress.yaml.vibe_coding.current_loop` after each visible slice.

## When to Ask the User

Ask instead of guessing when the answer changes architecture, security, cost, or release risk:

- Target stack, runtime, UI framework, and whether code is throwaway prototype or production-intended.
- Auth and organization identity source.
- Deployment target, storage, backup, migration, and rollback.
- Data classification, retention, logging, and AI/model externalization.
- Visual direction when the user has a brand or strong preference.
- Release acceptance threshold and owner.
- Whether this is a throwaway prototype or production-intended code.

When the user has no stack preference, recommend local-first Go, Python, Node.js, or plain HTML for prototypes, and SQLite for the first local MVP database. Treat the recommendation as pending confirmation.

## Designer Capability Rules

The designer capability must produce real design artifacts, not only narrative:

- `DESIGN.md`: visual identity, tokens, typography, color, spacing, components, do/don't rules. Follow upstream `bmad-ux` / `ux-coach`.
- `EXPERIENCE.md`: IA, flows, component behavior, state patterns, accessibility floor, key journeys. Follow upstream `bmad-ux` / `ux-coach`.
- `visual-system.html`: polished visual board or prototype board showing tokens, components, states, and screen thumbnails.
- PNG mockups: only for decision-critical screens/states, normally 3 for a new MVP.

Use the upstream designer skills named in `skills/registry.yaml` before producing these artifacts.

For operational/internal SaaS products, the default visual direction is dense, calm, scannable, and work-focused. Avoid marketing heroes, decorative illustration-heavy layouts, generic monochrome wireframes, and text that overflows UI containers.

Before PNG mockups, freeze a design-system lock and render `visual-system.html` to `prototypes/visual-system-desktop.png` for reference-image guidance when supported. Draft mode keeps returned PNGs as discussion assets and records drift notes. Apply strict `references/visual-prototype-quality.md` rejection only when the user asks for approved UI, production-ready design, or exact matching.

## Quality Gates

Do not mark a phase complete until the evidence exists:

- PRD gate: source input exists, requirements have IDs, P1 journey is testable, blockers are named.
- Design gate: DESIGN/EXPERIENCE decisions exist, screen inventory maps to journeys, visual assets are reviewed or explicitly deferred.
- Prototype gate: prompts use synthetic data, generated files exist, reports validate size/metadata/usage where available. Draft mode only requires returned PNGs, reports, preserved original bytes, and rough flow match; strict visual review requires `visual_consistency_review.status: pass` only when the user asks for approved UI or exact visual matching.
- Architecture gate: stack and deployment assumptions are confirmed or marked as blockers.
- Pre-code gate: auth, data, deployment, AI boundaries, and P1 acceptance are ready for code or explicitly held.

## External Framework Use

Use local cloned research as reference material when available, but keep AidevOps compact:

- From BMAD, keep role perspectives, PRD/UX validation, readiness gates, and design spines.
- From Spec Kit, keep independent user stories, stable requirements, technical context, and task grouping by story.
- From Maestro, keep wave/checkpoint thinking and the analyst/writer/planner/executor/tester/reviewer/supervisor lenses, without requiring a heavyweight CSV workflow.
- From OpenAI relay research, keep explicit Responses image-tool requests, relay smoke tests, and usage/metadata validation.
- From beginner vibe-coding workflows, keep small prompts, visible outputs, local run evidence, and a stop/go loop instead of large one-shot generation.
