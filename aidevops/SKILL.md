---
name: aidevops
description: AI-assisted development skill hub for shipping small software MVPs. Use when Codex needs to turn an idea, PRD, story, architecture note, sprint, design brief, prototype request, or beginner vibe-coding request into a governed MVP loop with PRD, user stories, PRINCE-lite controls, product/service/UX/system design, gpt-image-2 prototype request guidance, architecture, sprint delivery, review, acceptance, deployment, rollback, and retrospective. Also use when the workspace has AidevOps activation markers such as `.aidevops-active.yaml`, project instructions that point to `aidevops/SKILL.md`, or existing `docs/*/progress.yaml` AidevOps phase files, even if the user does not repeat the skill name.
---

# AidevOps

Use this skill as a compact development hub for small software products. The job is not to create documents for their own sake; it is to move from idea to a usable MVP loop: clarify, design, govern, build, verify, release, learn.

## Operating Mode

Classify the request first, then read `skills/registry.yaml` and the original upstream child skills listed there. Child skills under `skills/` are upstream snapshots and should not be edited unless there is a concrete conflict. AidevOps-specific routing and output normalization live in this file, `skills/registry.yaml`, optional scripts, and `references/`.

- **Intake / PRD / MVP**: Read `skills/bmad-prd/SKILL.md`, `skills/bmad-spec/SKILL.md`, and `skills/bmad-forge-idea/SKILL.md` as needed.
- **Governance / Readiness**: Read `skills/team-lifecycle-v4/SKILL.md` and `skills/bmad-check-implementation-readiness/SKILL.md`.
- **Designer**: Read `skills/bmad-ux/SKILL.md`, `skills/ux-coach/SKILL.md`, `skills/frontend-design/SKILL.md`, and `skills/team-uidesign/SKILL.md`; use `skills/team-ui-polish/SKILL.md`, `skills/team-ux-improve/SKILL.md`, `skills/team-visual-a11y/SKILL.md`, and `skills/ui-ux-pro-max/SKILL.md` for design QA.
- **Prototype Image Request**: Read `skills/imagegen/SKILL.md` and `skills/openai-docs/SKILL.md`; use `references/prototyping.md` and `references/visual-prototype-quality.md` for AidevOps image-generation route checks, relay/account notes, visual consistency gates, and phase-file conventions.
- **Architect / Delivery**: Read `skills/bmad-agent-architect/SKILL.md`, `skills/maestro-plan/SKILL.md`, and `skills/team-lifecycle-v4/SKILL.md`.
- **Coding / Implementation**: Codex implements code directly; no separate child coding skill is required. Before production-intended code, read `references/workflow.md` Phase 5, `references/quality-gates.md` Git Workflow / Gate 4.5 / Gate 5, and target-repo instructions such as `AGENTS.md`, `README`, package manifests, tests, and existing conventions.
- **Reviewer / Acceptance**: Read `skills/quality-review/SKILL.md`, `skills/bmad-code-review/SKILL.md`, `skills/code-review/SKILL.md`, and `skills/code-review-testing/SKILL.md`.
- **Beginner Vibe Coding / Fast MVP**: Read `references/vibe-coding.md` plus the relevant phase references; use one visible slice per loop and keep protected decisions explicit.
- **Skill Authoring**: Read `skills/skill-creator/SKILL.md` when changing this skill collection.
- **Framework Research**: Read `references/research-synthesis.md` and browse current primary sources when facts may have changed.

If the user asks for a complete flow, run the phases below in order. If they ask for one artifact, produce that artifact while preserving traceability to upstream requirements and downstream verification.

## Workspace Activation

A skill cannot force true permanent residency by itself; the host tool decides whether `SKILL.md` is loaded on each turn. Make AidevOps sticky at the workspace level instead:

- When AidevOps is first used in a target repo and the user expects continued use in Codex, WorkBuddy, Zcode, or another coding agent, create or update project-level instructions that point future agents back to `aidevops/SKILL.md`.
- Use `python3 aidevops/scripts/activate_workspace.py --workspace . --skill-path aidevops/SKILL.md` when Python is available. If not, create the same files manually from `references/persistent-activation.md`.
- The activation writes `.aidevops-active.yaml` and an `AGENTS.md` block. If WorkBuddy or Zcode does not read `AGENTS.md`, copy the same block into that tool's project memory, rules, or custom instructions.
- Treat activation as a router, not as loaded context. On future relevant turns, read `aidevops/SKILL.md` again, then continue from `docs/<feature>/progress.yaml` and the phase files.
- Do not activate AidevOps globally for unrelated coding questions. Apply it to PRD, design, prototype, architecture, sprint, MVP, vibe-coding, review, deployment, or acceptance work.

## Clarification Policy

Default mode is `ask-user`: ask targeted questions before decisions that affect architecture, security, cost, data handling, or release risk. Ask no more than 5 questions per round and write unresolved blockers as `[NEEDS CLARIFICATION: question]`.

Use `auto-assume` only when the user explicitly says the run is a test, evaluation, demo, dry run, or should be automatically completed. In `auto-assume` mode:

- Continue without waiting for the user.
- Fill missing non-sensitive details with minimal local-first assumptions.
- Mark every synthesized answer as `[AUTO-FILLED FOR TEST: reason]`.
- Prefer Go, Python, Node.js, or plain HTML for local prototypes and SQLite for the first MVP database when no stack is specified.
- Do not mark auto-filled decisions as user-confirmed.
- Do not proceed to production-intended code until protected decisions are confirmed: technical stack, auth/identity, deployment target, data policy, and AI/model boundary.
- Record the policy and assumptions in `progress.yaml.clarification_policy` and `00-discovery.yaml.clarification`.

## Document-First Phase Control

Python scripts are optional helpers, not the workflow source of truth. If Python is unavailable or the user prefers document guidance, create and update the files manually from `references/templates.md`.

Each phase file owns its own confirmation state. At the end of every phase, update that phase file with:

- `phase_confirmation.status`: `draft`, `needs_user`, `auto_filled_for_test`, `confirmed`, `accepted_risk`, or `blocked`.
- `phase_confirmation.user_questions`: questions still waiting for the user.
- `phase_confirmation.auto_filled_for_test`: assumptions synthesized only for a test/evaluation run.
- `phase_confirmation.confirmed_decisions`: final decisions for that phase.
- `phase_confirmation.change_log`: what changed since the previous pass and why.

Each phase also owns its process assets through `knowledge_assets`: lessons, reusable rules, decisions worth preserving, evidence links, and wiki update items.

Use `progress.yaml` only as the hub ledger: current phase, capability queue, gate status, evidence pointers, and next action. Do not put final requirements only in `progress.yaml`; final PRD decisions belong in `00-discovery.yaml`, design/architecture decisions in `01-design.yaml`, sprint/deployment/git decisions in `02-delivery.yaml`, and acceptance/release decisions in `03-acceptance.yaml`.

Maintain `wiki.md` in the feature workspace as the local LLM Wiki. It is mandatory for complete flows. Keep it concise and update it after each phase with reusable knowledge, decisions, prompts, commands, quality checks, risks, and handoff notes. Do not put secrets or private customer data in the wiki.

## Beginner Vibe Coding Mode

When the user wants fast development, is a beginner, or asks to "vibe code", use `references/vibe-coding.md` as the fast lane inside the same phase files. This mode optimizes for one visible, runnable MVP slice per loop:

- Start from one-sentence intent, source files in `input/`, and at most 5 high-impact questions.
- Before locking features or code structure, scan GitHub/Gitee for similar apps and scan any user-provided reference framework/base code; record findings locally and do not copy code blindly.
- In explicit test mode, auto-fill non-sensitive gaps and label them; in real delivery, ask before protected decisions.
- Explain only the next concrete action in Chinese, while keeping commands, filenames, APIs, env vars, and code identifiers in English.
- Distinguish `throwaway prototype` from `production-intended code` before coding.
- For UI work, create design artifacts and verify visually before calling the slice done.
- Start the local dev server when needed, provide the URL, and verify compile/test/manual workflow evidence.
- After each loop, update `knowledge_assets`, `wiki.md`, and `progress.yaml.vibe_coding`.

## Required Workflow

1. **Context Intake**
   - Inspect the current repo before prescribing implementation details.
   - Ask the user to place the current requirement, rough PRD, notes, screenshots, samples, or interview material under `docs/<feature-slug>/input/`. If the user already has a file elsewhere, copy or reference it from that folder before optimizing.
   - Identify greenfield vs brownfield, target users, platform, business goal, technical constraints, deployment target, budget/timebox, and existing conventions.
   - For uncertain requirements, follow the active clarification policy. In normal delivery, ask targeted questions instead of silently deciding. In explicit test/evaluation mode, auto-fill non-sensitive gaps and label them as test assumptions.
   - Technical stack, auth, deployment, data policy, and AI/model boundaries require explicit user confirmation before production-intended code, even if they were auto-filled for a test run.
   - When the user has no stack preference, recommend local-first options in this order: Go, Python, Node.js, plain HTML for static prototypes; prefer SQLite for the first local MVP database. Treat this as a recommendation, not an implicit decision.
   - For domestic Chinese beginner users, use Chinese for conversation, phase files, product copy, and review notes by default. Keep code identifiers, API names, model names, config keys, and external issue references in English. Use bilingual or English prompts only when needed for image/API quality or external tool compatibility.
   - If current external facts matter, browse primary sources and cite them.

2. **Idea, PRD, and MVP Discovery**
   - Ask at most 5 high-value questions per round.
   - Separate confirmed facts, assumptions, cracks, open questions, and out-of-scope items.
   - Mark unresolved build-blocking gaps as `[NEEDS CLARIFICATION: question]`; do not silently invent requirements.
   - Produce a PRD spine, user stories, success metrics, and an MVP slice small enough to verify end to end.
   - Update `00-discovery.yaml.phase_confirmation` with final requirement decisions, open user questions, and test-mode assumptions.
   - Update `00-discovery.yaml.knowledge_assets` and `wiki.md` with product terminology, requirement lessons, source inputs, and reusable discovery rules.

3. **Governance Setup**
   - Define the lightweight business case, decision owner, delivery owner, review owner, and release approver.
   - Set tolerances for scope, schedule, quality, cost/effort, risk, and privacy/security.
   - Start decision, risk, issue, change, and quality logs only at the level needed for the MVP.

4. **User Roles and Flows**
   - Define personas/roles only when they drive product or permission decisions.
   - Write user journeys with entry state, path, value moment, resolution, and edge cases.
   - Convert journeys into independently testable user stories ordered by MVP value.

5. **Design and Architecture**
   - Create a design spine before generating screens: product model, service/system boundaries, UX flows, IA, content/data states, visual direction, accessibility, and design tokens.
   - For UI/UX work, produce real design artifacts before or alongside mockups: `DESIGN.md`, `EXPERIENCE.md`, and a visual system/prototype board under `prototypes/` when design quality matters.
   - For UI/UX work, apply the bundled designer and QA child skills as quality inputs. Use `frontend-design` to avoid templated defaults; use `team-uidesign` specs for tokens, anti-patterns, scoring, and UX writing; use `ui-ux-pro-max` for accessibility, interaction, layout, typography, and color checks.
   - Treat `visual-system.html` as the visual source of truth for generated screen PNGs. If the board itself is weak, generic, or inconsistent with `DESIGN.md` / `EXPERIENCE.md`, improve the board before generating images.
   - For products with backend, data, AI/model, approval, or export boundaries, create a runtime flow diagram under `prototypes/system-flow.html` and `prototypes/system-flow.png`. Treat it as an architecture support artifact, not a `gpt-image-2` generated prototype.
   - Choose the simplest architecture that satisfies the PRD and constraints.
   - Document data model, interfaces/contracts, security/privacy boundaries, observability, deployment assumptions, and risks.
   - Update `01-design.yaml.phase_confirmation` with confirmed design and architecture decisions.
   - Update `01-design.yaml.knowledge_assets` and `wiki.md` with design tokens, screen decisions, prototype prompts, architecture decisions, and quality review notes.
   - For brownfield work, prefer existing framework, style, helpers, and tests over new abstractions.

6. **Prototype**
   - Generate or request images only for decision-critical screens/states.
   - For bitmap prototype generation with OpenAI, read `references/prototyping.md`.
   - If the user asked for PNG prototype images, or `01-design.yaml.prototype_image_request.required` is `true`, produce real PNG files and validation reports. A `visual-system.html` board or Chromium screenshot is supporting evidence, not a substitute.
   - Default to one real PNG per decision-critical screen/state. A contact sheet can be used only for early exploration; it must not replace the generated prototype PNG set or its reports.
   - Default PNG work to draft prototype mode unless the user asks for formal design approval. In draft mode, refresh `visual-system.html` to `prototypes/visual-system-desktop.png`, pass that screenshot as a reference image when the route supports it, generate PNGs, preserve returned bytes, and record reports beside the prototype files. Do not run a heavyweight design acceptance gate.
   - Before generating PNGs, freeze `01-design.yaml.prototype_image_request.design_system_lock` from `DESIGN.md`, `EXPERIENCE.md`, and `visual-system.html`: palette, app shell, layout density, typography, component rules, exact UI copy, and anti-references.
   - In draft mode, do only a lightweight sanity check: image file exists, report exists, prompt includes target size/quality, returned PNG is preserved unchanged, and the rough screen matches the intended flow enough for discussion.
   - Keep runtime flow diagrams out of `prototype_image_request.generated_assets`; list them in `system_flow_diagram` instead.
   - Use strict visual consistency review only when the user asks for approved UI, production-ready design, or exact visual matching. In strict mode, compare every accepted image against the visual board; reject images that drift in palette, density, shell, components, business workflow, UI copy, or overall polish.
   - If PNG generation cannot run, record the failed command, error summary, and blocker in `01-design.yaml`, `03-acceptance.yaml`, and `wiki.md`; do not mark `prototype-image-request` complete.
   - Default to polished, domain-specific product mockups; do not default to generic monochrome wireframes unless explicitly requested.

7. **MVP and Sprint Planning**
   - Pick the smallest user story set that demonstrates real value end to end.
   - Break work into setup, foundation, story slices, and polish.
   - Every task must include exact artifact/file targets when a repo exists, dependencies, verification command or manual check, and acceptance criteria.
   - Before production-intended code, define or inherit code structure rules: directories, naming, formatting, tests, env/config, migrations, generated assets, and files that must not be touched.
   - Update `02-delivery.yaml.phase_confirmation` with sprint, git, deployment, rollback, and pre-code confirmation status.
   - Update `02-delivery.yaml.knowledge_assets` and `wiki.md` with commands, task patterns, environment notes, Git rules, deployment notes, rollback notes, and implementation lessons.
   - Before production-intended implementation, guide the user to install Git if missing and confirm that the project is under version control.

8. **Implementation Loop**
   - Treat implementation as Codex's native coding work, governed by the phase files and repo conventions, not as a separate child skill.
   - Before coding, read `references/workflow.md` Phase 5 and `references/quality-gates.md` Gate 4.5 / Git Workflow. For UI implementation, also read the active design references; for test planning, use `skills/code-review-testing/SKILL.md` when needed.
   - Run `git --version` and `git rev-parse --is-inside-work-tree` before code changes. If Git is missing, provide OS-specific install guidance and stop production-intended coding until Git is available.
   - If the project is not a Git repository, ask before running `git init`; if it is a repository, inspect branch and dirty state.
   - Inspect target-repo instructions and conventions before editing: `AGENTS.md`, `README`, package manifests, lockfiles, source layout, tests, CI, format/lint config, migrations, env/config patterns, and existing UI system.
   - Use a feature branch such as `feature/<feature-slug>` or the repo's existing convention.
   - Implement one vertical slice at a time: contract/test if practical, backend/core logic, frontend/UI, migration/config, docs.
   - Run focused checks after each slice and broader checks before handoff.
   - Keep secrets out of logs, docs, commits, generated images, and screenshots.

9. **Review, Acceptance, Release, Retrospective**
   - Review for bugs, security, data integrity, UX regressions, missing tests, and requirement drift.
   - Produce an acceptance report mapping PRD requirements and user stories to evidence.
   - Keep deploy, env, migration, release, rollback, and git controls in the delivery phase file unless the target repo already has a stronger convention.
   - Record lessons learned, deferred scope, and next sprint candidates.
   - Update `03-acceptance.yaml.phase_confirmation` with release decision, accepted risks, and follow-up ownership.
   - Update `03-acceptance.yaml.knowledge_assets` and `wiki.md` with verification evidence, defects, accepted risks, release lessons, and next-sprint knowledge.

## Minimal Artifact Set

Use a feature workspace such as `docs/<feature-slug>/` when the target repo has no established place. Keep the MVP loop to one config file per phase, plus one progress ledger for the hub itself:

- `progress.yaml`: current phase, capability queue, gate status, evidence pointers, and next action. This is not a stage document.
- `wiki.md`: local LLM Wiki for phase learnings, durable decisions, reusable rules, commands, prompts, risks, and handoff notes.
- `input/`: user-provided requirements, rough PRDs, samples, screenshots, meeting notes, and sanitized source evidence.

- `00-discovery.yaml`: idea forge, business case, PRD spine, roles, journeys, requirements, MVP scope, governance setup.
- `01-design.yaml`: product/service/system design, UX, IA, design tokens, prototype request plan, architecture, contracts, risks.
- `02-delivery.yaml`: MVP sprint, user stories, tasks, risk/issue/change logs, git, env, deployment, migration, release, rollback.
- `03-acceptance.yaml`: verification evidence, review, quality gate results, release decision, retrospective, knowledge backflow.
- `prototypes/`: visual system previews, prototype prompts, generated mockups, runtime flow diagram, and review notes when design is part of the work.

Create the files manually from `references/templates.md`, or optionally initialize them with:

```bash
python3 aidevops/scripts/init_feature_workspace.py <feature-slug>
```

Optionally validate a generated workspace with:

```bash
python3 aidevops/scripts/validate_workspace.py docs/<feature-slug>
```

## Resource Map

- Read `references/capability-map.md` for the sub-skill map and phase-file routing.
- Read `references/skill-collection.md` for the aggregated PM, designer, architect, reviewer, delivery, and image-prototype capability model.
- Read `skills/registry.yaml` for the local upstream-skill registry and capability routing.
- Read upstream child skills under `skills/<skill-name>/SKILL.md` when executing that capability. Do not rewrite their contents for AidevOps-specific examples.
- Read `references/product-prd-mvp.md` for idea pressure testing, PRD quality, user stories, and MVP slicing.
- Read `references/governance.md` for PRINCE-lite controls embedded in the four phase files.
- Read `references/design-system.md` for design beyond UI screens: product, service, system, interaction, IA, tokens, review, and prototype quality.
- Read `references/workflow.md` for the full end-to-end method and phase gates.
- Read `references/templates.md` when drafting PRDs, user stories, architecture, sprint plans, or acceptance reports.
- Read `references/knowledge-wiki.md` when maintaining `wiki.md` or phase `knowledge_assets`.
- Read `references/vibe-coding.md` when the user wants fast agile development, beginner guidance, or vibe coding.
- Read `references/prototyping.md` when generating design specs, prototype prompts, or `gpt-image-2` image-generation code.
- Read `references/visual-prototype-quality.md` when producing or reviewing `visual-system.html`, generated PNG prototypes, image prompt locks, or visual consistency evidence.
- Read `references/env-example.md` when documenting local `.env` setup or relay credential conventions.
- Read `references/quality-gates.md` when planning tests, pre-code go/hold checks, implementation gates, reviews, git workflow, release, or automated agent delegation.
- Read `references/research-synthesis.md` when explaining the framework influences or refreshing workflow research.
- Read `references/persistent-activation.md` when installing this skill into WorkBuddy, Zcode, Codex project instructions, or any workspace where AidevOps should be reused after the first invocation.

Coding note: there is intentionally no separate `coding` child skill in the Resource Map. Implementation is Codex's native work and is controlled by `02-delivery.yaml` tasks, target-repo conventions, `references/workflow.md` Phase 5, and `references/quality-gates.md`. Use reviewer/testing child skills around coding when a review, test strategy, or delegated implementation audit is needed.

For image API smoke tests:

```bash
python3 aidevops/scripts/gpt_image_smoke.py --env aidevops/.env --mode responses-image-tool --size 1536x1024 --quality high --reference-image docs/<feature>/prototypes/visual-system-desktop.png
```

## Completion Standard

Do not call the workflow done because artifacts exist. Completion requires evidence that:

- Requirements are explicit enough for the chosen MVP.
- The business case, owner, tolerances, and exceptions are visible.
- Each MVP user story is independently testable.
- Product/design/architecture decisions trace to requirements and constraints.
- Prototype output, if requested, reflects approved flows, domain style, and realistic product data.
- Required PNG prototype images exist, or image generation is explicitly blocked with evidence and owner.
- Runtime flow diagram exists when the MVP includes app/backend/data/AI/review/export boundaries.
- Implementation tasks have run or list concrete verification commands.
- Acceptance results map back to PRD IDs or user story IDs.
- Deployment and rollback are either executed or explicitly deferred with an owner.
- Remaining risks and deferred scope are named.
