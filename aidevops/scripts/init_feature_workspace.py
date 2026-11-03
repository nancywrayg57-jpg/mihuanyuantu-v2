#!/usr/bin/env python3
"""Create an AidevOps MVP workspace with phase configs and a progress ledger."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "feature"


TEMPLATES: dict[str, str] = {
    "progress.yaml": """workflow: aidevops
status: draft
run_mode: delivery
current_phase: discovery
active_capability: idea-forge

clarification_policy:
  mode: __CLARIFICATION_MODE__
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
  - capability: intake
    phase_file: 00-discovery.yaml
    status: pending
  - capability: idea-forge
    phase_file: 00-discovery.yaml
    status: pending
  - capability: prd
    phase_file: 00-discovery.yaml
    status: pending
  - capability: mvp-slicing
    phase_file: 00-discovery.yaml
    status: pending
  - capability: governance
    phase_file: 00-discovery.yaml
    status: pending
  - capability: designer
    phase_file: 01-design.yaml
    status: pending
  - capability: prototype-image-request
    phase_file: 01-design.yaml
    status: pending
  - capability: architect
    phase_file: 01-design.yaml
    status: pending
  - capability: delivery-planner
    phase_file: 02-delivery.yaml
    status: pending
  - capability: reviewer
    phase_file: 03-acceptance.yaml
    status: pending
  - capability: retro-knowledge
    phase_file: 03-acceptance.yaml
    status: pending

phase_gates:
  discovery:
    file: 00-discovery.yaml
    status: pending
    evidence: []
  design:
    file: 01-design.yaml
    status: pending
    evidence: []
  delivery:
    file: 02-delivery.yaml
    status: pending
    evidence: []
  acceptance:
    file: 03-acceptance.yaml
    status: pending
    evidence: []

evidence_pointers:
  prd: 00-discovery.yaml
  design: 01-design.yaml
  delivery: 02-delivery.yaml
  acceptance: 03-acceptance.yaml
  wiki: wiki.md
  prototypes: []
  test_reports: []
  commits_or_prs: []

next_action:
  owner: ""
  action: "Complete idea forge and PRD spine"
  blocker: ""
""",
    "wiki.md": """# Local LLM Wiki: __FEATURE_SLUG__

## Project Snapshot
- Goal:
- MVP slice:
- Current phase: discovery
- Protected decisions:
- Vibe coding mode: enabled

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
""",
    "00-discovery.yaml": """phase: discovery
status: draft

phase_confirmation:
  status: draft
  mode: __CLARIFICATION_MODE__
  user_questions: []
  auto_filled_for_test: []
  confirmed_decisions: []
  accepted_risks: []
  blockers: []
  confirmed_by: ""
  confirmed_at: ""
  change_log: []

knowledge_assets:
  wiki: wiki.md
  phase_summary: ""
  outcomes: []
  lessons: []
  reusable_rules: []
  prompts_or_commands: []
  evidence_links: []
  update_wiki: []

clarification:
  policy: __CLARIFICATION_MODE__
  questions_to_ask: []
  auto_filled_for_test: []
  pending_user_decisions:
    - technical_stack
    - auth_identity
    - deployment_target
    - data_policy
    - ai_model_boundary

idea_forge:
  idea: ""
  assumptions: []
  cracks: []
  locks: []
  kill_criteria: []
  fast_evidence: []

business_case:
  problem: ""
  target_outcome: ""
  expected_value: ""
  current_alternative: ""
  constraints:
    platform: ""
    timeline: ""
    budget_or_effort: ""
    integrations: []
    data_security: []

governance:
  roles:
    executive: ""
    product_owner: ""
    delivery_owner: ""
    design_owner: ""
    reviewer: ""
  tolerances:
    scope: ""
    schedule: ""
    effort_cost: ""
    quality: ""
    risk: ""
    privacy_security: ""
  decision_log: []

prd:
  product_name: ""
  promise: ""
  glossary: []

target_users:
  primary: []
  secondary: []
  excluded_for_mvp: []
roles:
  - id: role-1
    name: ""
    permissions: []
journeys:
  - id: UJ-1
    role: role-1
    entry_state: ""
    path: []
    value_moment: ""
    edge_cases: []
requirements:
  functional:
    - id: FR-1
      statement: ""
      maps_to: [UJ-1]
      acceptance:
        - id: AC-1.1
          scenario: ""
  non_functional:
    - id: NFR-1
      category: security
      statement: ""
mvp_scope:
  in: []
  out: []
  deferred: []
success_metrics:
  - id: SM-1
    metric: ""
    target: ""
    counter_metric: ""
assumptions: []
open_questions: []
gate:
  ready: false
  blockers: []
""",
    "01-design.yaml": """phase: design
status: draft

phase_confirmation:
  status: draft
  mode: __CLARIFICATION_MODE__
  user_questions: []
  auto_filled_for_test: []
  confirmed_decisions: []
  accepted_risks: []
  blockers: []
  confirmed_by: ""
  confirmed_at: ""
  change_log: []

knowledge_assets:
  wiki: wiki.md
  phase_summary: ""
  outcomes: []
  lessons: []
  reusable_rules: []
  prompts_or_commands: []
  evidence_links: []
  update_wiki: []

product_design:
  product_model: ""
  terminology_decisions: []
  value_moment: ""
  non_goals: []

service_system_design:
  actors: []
  handoffs: []
  external_systems: []
  manual_backoffice_steps: []
  failure_recovery: []

interaction_design:
  flows:
    - id: flow-1
      maps_to: [UJ-1]
      steps: []
      feedback: []
      validation: []
  state_model:
    default: ""
    empty: ""
    loading: ""
    error: ""
    permission: ""

information_architecture:
  navigation: []
  hierarchy: []
  labels: []
  permissions: []

design_spines:
  design_md: prototypes/DESIGN.md
  experience_md: prototypes/EXPERIENCE.md
  visual_board: prototypes/visual-system.html
  status: pending
  notes: []

visual_system:
  style_direction:
    product_category: ""
    density: ""
    tone: ""
    references: []
    anti_references: []
  tokens:
    colors: []
    typography: []
    spacing: []
    radius: []
    icons: []
  component_rules: []
  accessibility: []

screens:
  - id: screen-1
    name: ""
    maps_to: [UJ-1]
    primary_action: ""
    states: [default, empty, loading, error]
    data_needed: []

prototype_image_request:
  required: false
  validation_mode: simple_return
  recommended_count: 3
  decomposition:
    - entry_or_workspace
    - primary_action
    - result_or_detail
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

architecture:
  stack: ""
  system_context: []
  data_model:
    entities: []
    ownership: []
    retention: []
    migrations: []
  api_contracts:
    endpoints: []
    events: []
    errors: []
  security_privacy:
    auth: ""
    authorization: ""
    secrets: []
    data_boundaries: []
    abuse_cases: []
  observability:
    logs: []
    metrics: []
    audit: []
    debug_paths: []
  decisions:
    - id: ADR-1
      decision: ""
      rationale: ""
      alternatives_rejected: []
      maps_to: []
  risks: []
design_review:
  findings: []
  approved_decisions: []
  rejected_directions: []
  spine_checks: []
gate:
  ready: false
  blockers: []
""",
    "02-delivery.yaml": """phase: delivery
status: draft

phase_confirmation:
  status: draft
  mode: __CLARIFICATION_MODE__
  user_questions: []
  auto_filled_for_test: []
  confirmed_decisions: []
  accepted_risks: []
  blockers: []
  confirmed_by: ""
  confirmed_at: ""
  change_log: []

knowledge_assets:
  wiki: wiki.md
  phase_summary: ""
  outcomes: []
  lessons: []
  reusable_rules: []
  prompts_or_commands: []
  evidence_links: []
  update_wiki: []

sprint:
  goal: ""
  mvp_story_ids: [US-1]
  stories:
    - id: US-1
      priority: P1
      statement: ""
      independent_test: ""
      acceptance_refs: []
      status: pending
tasks:
  - id: T001
    story: US-1
    type: setup
    description: ""
    files: []
    depends_on: []
    verify: ""
    acceptance_refs: []
    status: pending
governance_controls:
  risk_log: []
  issue_log: []
  change_log: []
  quality_log: []
  exceptions: []
deployment:
  environments: []
  config_env: []
  migrations: []
  release_steps: []
  rollback: []
git:
  branch: ""
  git_installed: unknown
  repository_initialized: unknown
  install_guidance_required: false
  version_control_required_before_code: true
  feature_branch_required: true
  commit_policy: small-coherent
  ignored_secrets:
    - .env
    - "*.key"
    - "*.pem"
  pr_checklist: []
verification:
  focused_checks: []
  broad_checks: []
  manual_checks: []
gate:
  ready: false
  blockers: []
""",
    "03-acceptance.yaml": """phase: acceptance
status: draft

phase_confirmation:
  status: draft
  mode: __CLARIFICATION_MODE__
  user_questions: []
  auto_filled_for_test: []
  confirmed_decisions: []
  accepted_risks: []
  blockers: []
  confirmed_by: ""
  confirmed_at: ""
  change_log: []

knowledge_assets:
  wiki: wiki.md
  phase_summary: ""
  outcomes: []
  lessons: []
  reusable_rules: []
  prompts_or_commands: []
  evidence_links: []
  update_wiki: []

verification:
  commands_run: []
  manual_checks: []
  requirement_evidence:
    - id: FR-1
      evidence: ""
      result: pending
review:
  findings: []
  security_privacy: []
  ux_accessibility: []
  design_consistency: []
  test_gaps: []
quality_gates:
  prd: pending
  design: pending
  architecture: pending
  sprint: pending
  code_review: pending
  release: pending
release_decision:
  verdict: pending
  blockers: []
  accepted_risks: []
  rollback_or_manual_fallback: ""
retro:
  shipped: []
  changed_from_plan: []
  lessons: []
  reusable_rules: []
  knowledge_backflow: []
  next_sprint_candidates: []
gate:
  complete: false
  blockers: []
""",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize an AidevOps MVP workspace.")
    parser.add_argument("slug", help="Feature slug or title")
    parser.add_argument("--root", default="docs", help="Workspace root")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--clarification-policy",
        choices=("ask-user", "auto-assume"),
        default="ask-user",
        help="Use ask-user for real delivery, auto-assume for explicit test/evaluation runs.",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Shortcut for --clarification-policy auto-assume.",
    )
    args = parser.parse_args()

    clarification_policy = "auto-assume" if args.test_mode else args.clarification_policy
    slug = slugify(args.slug)
    target = Path(args.root) / slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "input").mkdir(parents=True, exist_ok=True)
    (target / "prototypes").mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    skipped: list[str] = []
    for filename, content in TEMPLATES.items():
        path = target / filename
        if path.exists() and not args.force:
            skipped.append(str(path))
            continue
        content = content.replace("__CLARIFICATION_MODE__", clarification_policy)
        content = content.replace("__FEATURE_SLUG__", slug)
        path.write_text(content, encoding="utf-8")
        written.append(str(path))

    print(f"workspace={target}")
    print(f"input_dir={target / 'input'}")
    print(f"prototypes_dir={target / 'prototypes'}")
    for path in written:
        print(f"written={path}")
    for path in skipped:
        print(f"skipped={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
