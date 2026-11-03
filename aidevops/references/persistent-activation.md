# Persistent Activation

Use this reference when AidevOps should keep being applied in WorkBuddy, Zcode, Codex, or another coding agent after the first explicit skill invocation.

## Reality Check

`SKILL.md` cannot make itself permanently resident in the model context. Each host decides what to load each turn. The reliable pattern is project-level activation:

- a small marker file: `.aidevops-active.yaml`
- a project instruction file such as `AGENTS.md`
- optional copy of the same instruction into WorkBuddy/Zcode project memory or rules

## Activation Command

From the target workspace:

```bash
python3 aidevops/scripts/activate_workspace.py --workspace . --skill-path aidevops/SKILL.md
```

If Python is unavailable, create the two files manually.

## Marker File

Create `.aidevops-active.yaml`:

```yaml
active: true
skill_path: aidevops/SKILL.md
version: v20260701-persistent-activation
activation_scope:
  - PRD
  - user stories
  - design
  - visual prototype
  - gpt-image-2 prototype image
  - architecture
  - sprint
  - implementation loop
  - review
  - acceptance
  - deployment
  - rollback
  - vibe coding
rule: "For relevant product/software delivery work, read aidevops/SKILL.md before acting even when the user does not repeat the skill name."
```

## Project Instruction Block

Add this block to `AGENTS.md` or the target tool's project custom instructions:

```markdown
<!-- AIDEVOPS-ACTIVE:START -->
This workspace has AidevOps activated.

For PRD, user story, design, visual prototype, gpt-image-2 image prototype, architecture, sprint, implementation, review, acceptance, deployment, rollback, or beginner vibe-coding work:

1. Read `aidevops/SKILL.md` before acting, even if the user does not repeat the skill name.
2. Continue from `docs/<feature>/progress.yaml` and the phase files when they exist.
3. Keep Chinese guidance by default for domestic beginner users; keep code/API/env/model identifiers in English.
4. Do not treat this activation as permission to skip clarification, Git checks, protected decisions, or quality gates.

For unrelated small coding questions, answer normally without forcing the full AidevOps workflow.
<!-- AIDEVOPS-ACTIVE:END -->
```

## Tool Notes

- Codex-style agents commonly honor `AGENTS.md`.
- WorkBuddy/Zcode may use a different project memory or rules surface. If they do not automatically read `AGENTS.md`, paste the same block into their project-level instructions.
- If a host has a global skill registry, install or pin this skill there as well, but keep the project marker so future agents can recover context from files.

## Renewal Rule

When the skill changes meaningfully, rerun activation or update the project instruction block only if the skill path or activation scope changed. Routine reference updates do not require a new block.
