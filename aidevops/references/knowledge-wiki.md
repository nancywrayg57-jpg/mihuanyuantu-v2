# Local LLM Wiki

Use this reference when maintaining the feature-level `wiki.md` and each phase file's `knowledge_assets`.

## Purpose

The wiki is the local memory for a feature. It preserves what the agent and user learned while moving through discovery, design, delivery, and acceptance.

It is mandatory for complete AidevOps flows because progress alone is not enough. A future agent should be able to read `wiki.md` and understand:

- Why the MVP was scoped this way.
- Which decisions were confirmed, assumed, or rejected.
- Which prompts, commands, checks, and patterns worked.
- Which fast-lane or vibe-coding loops produced visible output.
- Which risks, defects, and tradeoffs should not be rediscovered.
- What should be reused in the next sprint or similar feature.

## Location

Store the wiki at:

```text
docs/<feature-slug>/wiki.md
```

Keep paths shallow. Do not create nested wiki folders unless the target repo already has a stronger documentation convention.

## Phase Knowledge Assets

Every phase file must include:

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

Use `knowledge_assets` for phase-local notes and `wiki.md` for the durable cross-phase synthesis. At the end of each phase, copy the important items from `knowledge_assets.update_wiki` into `wiki.md`.

## Wiki Shape

Use this compact structure:

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

## Writing Rules

- Write for the next agent and the next human reviewer, not for ceremony.
- Prefer concise bullets with source links to phase files, prototypes, reports, commits, or commands.
- Keep Chinese guidance for domestic beginner users; keep filenames, commands, config keys, API/model names, and code identifiers in English.
- Do not store secrets, real credentials, raw customer data, private personal data, or sensitive screenshots.
- For test/evaluation runs, mark synthesized items with `[AUTO-FILLED FOR TEST: reason]`.
- If a lesson changes a reusable AidevOps rule, add it to the phase `knowledge_assets.update_wiki` first, then update `wiki.md`.
- For beginner fast-lane work, record each visible slice in `## Vibe Coding Loops` with the local URL, command, screenshot, or test evidence.

## Completion Gate

A phase is not complete until:

- Its `phase_confirmation` is updated.
- Its `knowledge_assets.phase_summary` is non-empty.
- Important lessons and outcomes are linked or copied into `wiki.md`.
- `progress.yaml.evidence_pointers.wiki` points to `wiki.md`.
