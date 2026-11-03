# AidevOps Templates

Default to the minimal closed-loop shape: one phase, one config file, plus a hub progress ledger. Python is optional. Create these files manually from this reference, or use `scripts/init_feature_workspace.py` only as a convenience:

- `progress.yaml`: orchestration status, capability queue, gates, evidence pointers, next action.
- `wiki.md`: local LLM Wiki with cross-phase lessons, outcomes, decisions, prompts, commands, risks, and handoff notes.
- `00-discovery.yaml`: brief, PRD spine, roles, journeys, requirements, MVP scope.
- `01-design.yaml`: product/service/system design, interaction, IA, visual system, prototype prompts/assets, architecture, data/API/security decisions.
- `02-delivery.yaml`: sprint, user stories, tasks, git, deployment, rollback.
- `03-acceptance.yaml`: evidence, review, release decision, retrospective.

Deployment belongs in `02-delivery.yaml`; do not create a separate deploy document for the MVP unless the target repo already requires one.

Use the detailed templates below only when a phase config needs to be expanded into stakeholder-facing documentation. Keep IDs stable once downstream artifacts reference them.

Every phase file should include `phase_confirmation`. This is where final decisions are confirmed inside the phase document itself; `progress.yaml` only points to the latest phase and evidence.

Every phase file should also include `knowledge_assets`. This is where process assets, experience, phase outcomes, reusable rules, prompts/commands, and wiki update items are captured before they are summarized into `wiki.md`.

## Progress Ledger

```yaml
workflow: aidevops
current_phase: discovery
active_capability: idea-forge
clarification_policy:
  mode: ask-user
  max_questions_per_round: 5
  auto_fill_allowed_when: "Only when the user explicitly says this is a test, evaluation, demo, dry run, or should be automatically completed."
  unresolved_marker: "[NEEDS CLARIFICATION]"
  auto_assumption_marker: "[AUTO-FILLED FOR TEST]"
  protected_decisions:
    - technical_stack
    - auth_identity
    - deployment_target
    - data_policy
    - ai_model_boundary
vibe_coding:
  enabled: true
  audience: beginner
  loop_style: one_visible_slice
  timebox_minutes: 30
  prototype_intent: reviewable_mvp
  current_loop:
    goal: ""
    user_value: ""
    visible_output: ""
    verify: ""
    status: pending
  next_user_action: ""
  agent_rules:
    explain_next_step: true
    ask_max_questions: 5
    prefer_recommended_default: true
    do_not_hide_blockers: true
    update_wiki_each_loop: true
  safety:
    production_code_requires_git: true
    protected_decisions_need_confirmation: true
    secrets_never_in_docs_or_prompts: true
capability_queue:
  - capability: idea-forge
    phase_file: 00-discovery.yaml
    status: pending
phase_gates:
  discovery:
    file: 00-discovery.yaml
    status: pending
    evidence: []
evidence_pointers:
  prd: 00-discovery.yaml
  design: 01-design.yaml
  delivery: 02-delivery.yaml
  acceptance: 03-acceptance.yaml
  wiki: wiki.md
next_action:
  owner: ""
  action: ""
  blocker: ""
```

## Common Phase Confirmation

Copy this block into each phase file and update it at the end of that phase.

```yaml
phase_confirmation:
  status: draft
  mode: ask-user
  user_questions: []
  auto_filled_for_test: []
  confirmed_decisions: []
  accepted_risks: []
  blockers: []
  confirmed_by: ""
  confirmed_at: ""
  change_log:
    - date: ""
      change: ""
      reason: ""
```

Allowed `status` values:

- `draft`: working version, not ready for confirmation.
- `needs_user`: waiting for user answers.
- `auto_filled_for_test`: completed for test/evaluation with marked assumptions.
- `confirmed`: user-confirmed and ready for the next phase.
- `accepted_risk`: allowed to proceed with named risk owner.
- `blocked`: cannot proceed without a user or external-state decision.

For test/evaluation runs, do not delete `auto_filled_for_test` entries after moving on. They are the audit trail proving what was synthesized.

## Common Knowledge Assets

Copy this block into each phase file and update it before leaving the phase.

```yaml
knowledge_assets:
  wiki: wiki.md
  phase_summary: ""
  outcomes: []
  lessons: []
  reusable_rules: []
  prompts_or_commands: []
  evidence_links: []
  update_wiki: []
```

## Local LLM Wiki

Create `docs/<feature-slug>/wiki.md` for every complete flow.

```markdown
# Local LLM Wiki: <feature>

## Project Snapshot
- Goal:
- MVP slice:
- Current phase:
- Protected decisions:
- Vibe coding mode:

## Decision Ledger
| Date | Phase | Decision | Status | Source |
| --- | --- | --- | --- | --- |

## Phase Knowledge
### Discovery
- Outcomes:
- Lessons:
- Reusable rules:
- Open questions:

### Design
- Outcomes:
- Lessons:
- Reusable rules:
- Prompt notes:

### Delivery
- Outcomes:
- Commands:
- Implementation rules:
- Deploy/rollback notes:

### Acceptance
- Evidence:
- Defects:
- Accepted risks:
- Next sprint knowledge:

## Reusable Prompts and Commands
- Prompt:
- Command:

## Vibe Coding Loops
| Loop | Visible Output | Verify | Result | Next |
| --- | --- | --- | --- | --- |

## Risks and Watchpoints
- Risk:
- Mitigation:

## Backlog Knowledge
- Next:
- Deferred:
```

## Product Brief

```markdown
# Product Brief: <name>

## Problem
Who has what problem, in what moment, and why does it matter now?

## Target Users
- Primary:
- Secondary:
- Non-users for MVP:

## Current Alternative
How users solve this today, including manual workarounds.

## Proposed Value
The smallest product promise the MVP must prove.

## Constraints
- Platform:
- Timeline:
- Budget/team:
- Integrations:
- Data/security:

## Success
- Primary success signal:
- Counter-metric:

## Open Questions
- [NEEDS CLARIFICATION: ...]
- [AUTO-FILLED FOR TEST: ...]
```

## PRD

```markdown
# PRD: <product or feature>

## 0. Document Purpose
Audience, source inputs, and how this document should be used.

## 1. Vision
Two or three paragraphs describing the product, user value, and strategic bet.

## 2. Roles and Jobs
| Role | Job to be Done | Permissions/Constraints | MVP? |
| --- | --- | --- | --- |

## 3. Glossary
- **Term**: Definition. Use this exact term throughout.

## 4. User Journeys
### UJ-1: <title>
- Persona/context:
- Entry state:
- Path:
- Value moment:
- Resolution:
- Edge case:

## 5. Functional Requirements
### FR-1: <capability>
<Actor> can <action> under <conditions>. Realizes UJ-<n>.

Acceptance:
- AC-1.1 Given <state>, when <action>, then <observable result>.
- AC-1.2 ...

Out of scope:
- ...

## 6. Non-Functional Requirements
- NFR-1 Security:
- NFR-2 Performance:
- NFR-3 Accessibility:
- NFR-4 Observability:

## 7. MVP Scope
### In
- ...
### Out
- ... because ...

## 8. Success Metrics
- SM-1: <metric>, target <value/time>. Validates FR-<n>.
- SM-C1: Counter-metric to avoid optimizing the wrong thing.

## 9. Assumptions and Open Questions
- [ASSUMPTION: ...]
- [NEEDS CLARIFICATION: ...]
- [AUTO-FILLED FOR TEST: ...]

## 10. Phase Confirmation
- Status: draft | needs_user | auto_filled_for_test | confirmed | accepted_risk | blocked
- Confirmed decisions:
- Open user questions:
- Test-only assumptions:
- Change log:
```

## User Story

```markdown
### US-1: <brief title> (Priority: P1/MVP)

As a <role>, I can <capability>, so that <value>.

**Why this priority**
<Value and risk rationale.>

**Independent test**
<How this story can be verified without completing later stories.>

**Acceptance scenarios**
1. Given <state>, when <action>, then <result>.
2. Given <edge state>, when <action>, then <safe result>.

**Dependencies**
- <none or concrete dependency>
```

## Design Spec

```markdown
# Design Spec: <feature>

## Design Intent
Domain, audience, product promise, tone, and visual priorities.

## Product Design
- User job:
- Value moment:
- Feature boundaries:
- Product terminology:

## Service and System Design
- Actors:
- Handoffs:
- External systems:
- Manual/back-office steps:
- Failure recovery:

## Interaction Design
- Primary flow:
- Controls and feedback:
- Validation:
- Empty/loading/error/permission states:

## Information Architecture
- Top-level surfaces:
- Navigation rules:
- Permission or role differences:

## Screen Inventory
| Screen | Purpose | Primary Action | States | Data Needed |
| --- | --- | --- | --- | --- |

## Visual System and Components
- Use existing design system:
- Tokens:
- New components:
- Accessibility:
- Responsive behavior:

## Prototype Prompt Pack
See `references/prototyping.md` and `references/visual-prototype-quality.md`.

For phase config files, use this structure when PNG prototypes are requested. List only real `gpt-image-2` screen PNGs in `generated_assets`; keep the visual board screenshot and runtime flow diagram in their own fields.

```yaml
prototype_image_request:
  required: true
  validation_mode: simple_return
  recommended_count: 3
  decomposition: []
  reference_screenshot: prototypes/visual-system-desktop.png
  preserve_returned_bytes: true
  prompt_requirements:
    include_target_size: true
    include_quality: true
    target_size: 1536x1024
    quality: high
  style_quality_bar:
    inherits_design_spine: true
    visual_consistency_required: false
    strict_visual_consistency_only_when_requested: true
    polished_domain_specific_mockup: true
    avoid_generic_wireframe: true
    realistic_sample_data: true
    no_lorem_ipsum: true
    reject_visual_board_screenshots: true
  design_system_lock:
    source_of_truth:
      - prototypes/DESIGN.md
      - prototypes/EXPERIENCE.md
      - prototypes/visual-system.html
    palette: {}
    layout: {}
    components: []
    typography: []
    anti_references: []
  prompts: []
  api_route: responses_image_tool
  generated_assets: []
  validation_reports: []
  rejected_assets: []
  visual_consistency_review:
    status: not_required_draft
    compared_against:
      - prototypes/DESIGN.md
      - prototypes/EXPERIENCE.md
      - prototypes/visual-system.html
    checks:
      same_product: pending
      palette_match: pending
      density_match: pending
      shell_match: pending
      component_match: pending
      workflow_specific: pending
      content_quality: pending
      anti_slop: pending
      not_screenshot: pending
    notes: []
  review_notes: []

system_flow_diagram:
  html: prototypes/system-flow.html
  png: prototypes/system-flow.png
  purpose: "Show the MVP runtime path from user input through app/backend/data/AI boundary to reviewed output."
  validation: "Rendered by Chromium; not counted as gpt-image-2 prototype generated_assets."
```

## Phase Confirmation
- Status:
- Confirmed design/architecture decisions:
- Open user questions:
- Test-only assumptions:
- Change log:
```

## Architecture

```markdown
# Architecture: <feature>

## Summary
One paragraph tying the technical approach to PRD goals.

## Context
- Existing repo conventions:
- Target runtime:
- External systems:

## Decisions
| ID | Decision | Rationale | Alternatives Rejected |
| --- | --- | --- | --- |
| ADR-1 | | | |

## Data Model
| Entity | Fields | Ownership | Retention | Notes |
| --- | --- | --- | --- | --- |

## API / Contract
| Route/Event | Auth | Request | Response | Errors | FR |
| --- | --- | --- | --- | --- | --- |

## Security and Privacy
- Auth/authz:
- Secrets:
- Data boundaries:
- Abuse/failure modes:

## Observability
- Logs:
- Metrics:
- Audit:
- Debug path:

## Deployment and Rollback
- Config/env:
- Migration:
- Release:
- Rollback:

## Risks
| Risk | Impact | Mitigation | Owner |
| --- | --- | --- | --- |

## Phase Confirmation
- Status:
- Confirmed architecture decisions:
- Open user questions:
- Test-only assumptions:
- Change log:
```

## Sprint Plan

```markdown
# Sprint Plan: <feature>

## Sprint Goal
Ship <US-n> so <user/value>.

## MVP Slice
- Included stories:
- Explicitly deferred:

## Tasks
- [ ] T001 [Setup] <task>. Verify: <command/check>.
- [ ] T002 [Foundation] <task>. Depends: T001. Verify: <command/check>.
- [ ] T003 [US-1] <task with path>. Depends: T002. Verify: <command/check>. AC: AC-1.1.

## Definition of Done
- PRD acceptance criteria mapped to evidence.
- Tests/checks run or manual verification recorded.
- Review completed and release blockers resolved or accepted.
- Docs updated for changed behavior.

## Phase Confirmation
- Status:
- Confirmed sprint/deploy/git decisions:
- Open user questions:
- Test-only assumptions:
- Change log:
```

## Acceptance Report

```markdown
# Acceptance Report: <feature>

## Verdict
pass | concerns | fail

## Evidence
| Requirement/Story | Check | Evidence | Result |
| --- | --- | --- | --- |

## Manual Review
- UX:
- Security/privacy:
- Error handling:
- Performance:
- Docs:

## Release Blockers
- ...

## Follow-ups
- ...

## Phase Confirmation
- Status:
- Release decision:
- Accepted risks:
- Open user questions:
- Change log:
```
