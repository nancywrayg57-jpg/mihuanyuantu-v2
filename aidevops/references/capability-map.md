# AidevOps Capability Map

Use this reference to choose which sub-skill to run and which phase file to update. Keep the MVP default to one config file per phase plus `progress.yaml`; create extra docs only when a stakeholder or existing repo convention requires them.

## Capability Routes

| Capability | Child Skill | Use When | Primary Output | Phase File |
| --- | --- | --- | --- | --- |
| `intake` | `bmad-prd`, `bmad-spec` | Need source placement or rough requirement ingestion. | Input ledger, source paths, assumptions, cracks. | `progress.yaml`, `00-discovery.yaml` |
| `idea-forge` | `bmad-forge-idea` | Idea is vague, risky, or over-scoped. | Assumptions, cracks, locks, kill criteria. | `00-discovery.yaml` |
| `prd` | `bmad-prd`, `bmad-spec` | Need product requirements or acceptance criteria. | PRD spine with UJ/FR/NFR/SM IDs. | `00-discovery.yaml` |
| `mvp-slicing` | `bmad-prd`, `bmad-spec`, `team-lifecycle-v4` | Need the smallest usable slice. | In/out scope, story priority, deferred scope. | `00-discovery.yaml`, `02-delivery.yaml` |
| `governance` | `team-lifecycle-v4`, `bmad-check-implementation-readiness` | Need project control without heavy ceremony. | Business case, roles, tolerances, logs, gates. | All four, mostly `00` and `02` |
| `designer` | `bmad-ux`, `ux-coach`, `frontend-design`, `team-uidesign`, `team-ui-polish`, `team-ux-improve`, `team-visual-a11y`, `ui-ux-pro-max` | Need product/service/system/UX direction or visual assets. | `DESIGN.md`, `EXPERIENCE.md`, visual board, IA, flows, tokens, states, review notes. | `01-design.yaml`, `prototypes/` |
| `prototype-image-request` | `imagegen`, `openai-docs`, designer QA references | Need high-fidelity mockup prompts, image API testing, draft PNGs, or strict visual consistency review. Relay implementations are compatibility notes, not child skills. | Prompt pack, image count, design-system lock, API request, validation report, generated PNGs, draft/strict review notes. | `01-design.yaml` |
| `architect` | `bmad-agent-architect`, `maestro-plan`, `bmad-check-implementation-readiness` | Need implementation structure and contracts. | System context, data/API/security/observability decisions. | `01-design.yaml` |
| `delivery-planner` | `maestro-plan`, `team-lifecycle-v4`, `code-review-testing` | Need build tasks, Git readiness, deployment, env, rollback, or repo changes. | Stories, tasks, verification, git, deploy, rollback. | `02-delivery.yaml` |
| `reviewer` | `quality-review`, `bmad-code-review`, `code-review`, `code-review-testing` | Need QA, code review, release readiness, or pre-code go/hold. | Findings, evidence matrix, release decision. | `03-acceptance.yaml` |
| `retro-knowledge` | `team-lifecycle-v4`, `quality-review` | Need learning loop after delivery. | Lessons, changed assumptions, next sprint candidates. | `03-acceptance.yaml` |

## Hub Progress Ledger

`progress.yaml` is the orchestration file for using AidevOps as a skill hub. It records:

- Current phase and active capability.
- Capability queue and status.
- Gate result for each phase.
- Evidence pointers to the four phase files, prototype assets, reports, test logs, PRs, or commits.
- Next action and owner.

It should not duplicate the PRD, design, delivery plan, or acceptance report. Put detailed content in the four phase files and link to it from the progress ledger.

Each phase file must maintain its own `phase_confirmation` block. Use it to record user questions, test-mode auto-filled assumptions, confirmed decisions, accepted risks, blockers, and change history for that phase. `progress.yaml` only records the latest pointer and gate state.

Each phase file must also maintain `knowledge_assets`, then summarize durable items into `wiki.md`. This makes the local feature workspace work like a compact LLM Wiki: future agents can recover lessons, decisions, prompts, commands, risks, and outcomes without replaying the full conversation.

When the user is new to coding or asks for fast "vibe coding", `progress.yaml.vibe_coding` records the active loop. Keep one visible output, one verification method, and one next user action per loop.

## Integrating Other Skills

AidevOps can coordinate other skills or specialist procedures, but it remains responsible for traceability and completion evidence.

| Phase | Specialist Capability to Invoke | Return Evidence |
| --- | --- | --- |
| Discovery | idea forge, PRD writer, research, elicitation | assumptions, PRD IDs, MVP decision |
| Design | designer/UX coach, product design, architecture, image prompt builder | design spines, screen inventory, design decisions, contracts |
| Delivery | delivery-git, coding agent, test writer, deployment helper | Git readiness, changed files, commands, task status |
| Acceptance | reviewer, QA, security audit, release checklist | findings, evidence matrix, release verdict |

When a specialist capability finishes, update `progress.yaml`, the relevant phase file, that phase's `knowledge_assets`, and `wiki.md` before moving on.

## Selection Rules

- If the user asks for a complete process, run all capabilities in order but keep artifacts compact.
- If the user asks for vibe coding or fast MVP work, use the same capabilities in one-slice loops and read `references/vibe-coding.md`.
- If the user asks for an artifact, generate that artifact and update the minimum upstream/downstream traceability needed.
- If implementation starts from a repo, inspect the repo before locking architecture or task paths.
- If visual design matters, run `designer` before `prototype-image-request`; generated images should visualize decisions, not invent them. Draft PNG mode requires real returned PNGs, reports, preserved bytes, and rough flow match. Strict visual consistency review from `references/visual-prototype-quality.md` is required only when the user asks for approved UI, production-ready design, or exact matching.
- If a risk crosses a tolerance, use `governance` to record an exception and ask for a decision before expanding scope.
- Before production-intended code, run `quality-review` as a pre-code go/hold gate; do not treat an existing PRD as implementation-ready by default.

## MVP Closed Loop

A usable MVP loop must answer:

1. Who gets value, and what one journey proves it?
2. What is the smallest story set that completes that journey?
3. What design and architecture choices are needed for that story set only?
4. What tasks build it with verification evidence?
5. What gate decides release, rollback, or another iteration?

If any answer is missing, the product is not yet closed-loop usable.
