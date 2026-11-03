# Research Synthesis

This snapshot summarizes local research performed on 2026-06-30. The cloned repositories live under `/root/dev/aidevops/research/repos/`. Refresh by browsing and pulling primary sources when the user asks for current comparisons or when repo behavior matters.

## Local Sources

| Project | Local Path | Upstream | Snapshot |
| --- | --- | --- | --- |
| Maestro-Flow | `research/repos/maestro-flow` | https://github.com/catlog22/maestro-flow | `6f1d8b6` |
| OpenAI Codex CLI | `research/repos/openai-codex` | https://github.com/openai/codex | `cfead68` |
| Claude Code Action | `research/repos/claude-code-action` | https://github.com/anthropics/claude-code-action | `4633baf` |
| Claude Code Base Action | `research/repos/claude-code-base-action` | https://github.com/anthropics/claude-code-base-action | `3a480e6` |
| BMAD Method | `research/repos/BMAD-METHOD` | https://github.com/bmad-code-org/BMAD-METHOD | `67f4499` |
| GitHub Spec Kit | `research/repos/spec-kit` | https://github.com/github/spec-kit | `ada293e` |
| Sub2API | `research/repos/sub2api` | https://github.com/Wei-Shaw/sub2api | local clone for OpenAI relay behavior |

## Local Process Assets

The AidevOps workflow also distills reusable process rules from `~/dev/aojuai/docs` while removing project-specific nextjs-base details:

| Source | Reused General Pattern |
| --- | --- |
| `/root/dev/aojuai/docs/dev/ai/AI_ASSISTED_DEVELOPMENT.md` | AI development as a controlled loop: requirements, plan, implementation, verification, retrospective; independent verification after delegated coding work. |
| `/root/dev/aojuai/docs/dev/flows/DEVELOPMENT_WORKFLOW.md` | End-to-end delivery artifacts: requirements, model/contracts, install/upgrade, verification, logs, and retrospective. |
| `/root/dev/aojuai/docs/dev/flows/NEW_MODULE.md` | Start with classification, requirements, data/API design, implementation sequence, tests, and issue backflow. |
| `/root/dev/aojuai/docs/dev/checklists/DEV_CHECKLIST.md` | Gate order: security, data integrity, correctness, UX, performance; checklist-driven acceptance. |
| `/root/dev/aojuai/docs/public/open-edition-base-hardening.md` and `assistant-foundation-boundary.md` | Keep reusable base workflow separate from business/customer-specific details. |

## What to Adopt

### 2026-06 Web Refresh: Beginner Vibe Coding

Current public workflow guidance converges on the same pattern:

- Use small, specific prompts instead of one huge request.
- Maintain project-level instructions and reusable rules so the agent does not rediscover context every run.
- Clarify before implementation when a decision affects architecture, security, data, cost, or release.
- Prefer one independently testable slice, then run and inspect the result.
- Treat AI-generated code as untrusted until tests, review, or manual workflow evidence confirms it.

Sources to refresh when this topic changes:

- Agile principles: https://agilemanifesto.org/principles.html
- GitHub Spec Kit quickstart and spec-driven workflow: https://github.github.com/spec-kit/quickstart.html
- Anthropic Claude Code best practices: https://docs.anthropic.com/en/docs/claude-code/best-practices
- Cursor project rules and context docs: https://docs.cursor.com/context/rules
- Lovable prompting/best-practice docs: https://docs.lovable.dev/tips-tricks/best-practice
- OpenAI Codex guidance and project instructions: https://developers.openai.com/codex/

Adaptation for AidevOps:

- Add `progress.yaml.vibe_coding` as a beginner-facing loop ledger.
- Keep `docs/<feature>/input/` for rough requirements and screenshots.
- Use the same four phase files, but work in one visible slice at a time.
- Require a local URL, screenshot, command output, prototype asset, or test result before calling a loop done.
- Preserve new lessons in `knowledge_assets` and `wiki.md` after each loop.
- Separate `throwaway prototype` from `production-intended code`; only the latter may proceed after Git and protected decisions are confirmed.

### Maestro-Flow

Useful patterns:

- Natural-language intent routing into lifecycle paths.
- Lifecycle states from brainstorming and blueprinting through plan, execute, verify, review, test, and milestone.
- Quality modes that trade speed for verification depth.
- Knowledge capture and injection so future runs inherit project rules.
- Multi-agent patterns: delegate, team, wave, and swarm.

Adaptation for AidevOps:

- Keep the lifecycle and learning loop.
- Avoid requiring a heavyweight orchestrator for small projects.
- Use simple phase gates and artifacts instead of many commands.

### OpenAI Codex CLI

Useful patterns:

- Local repo-first coding agent that reads, edits, verifies, and explains changes.
- Skills as reusable task workflows.
- Clear separation between local CLI, IDE, app, and hosted surfaces.

Adaptation for AidevOps:

- Make the skill self-contained and repo-aware.
- Prefer current repo conventions and verification over generic generated code.

### Claude Code Action and Base Action

Useful patterns:

- PR/issue-triggered automation.
- Automatic code review, custom checklists, security-focused reviews, doc sync, and maintenance tasks.
- Explicit trust model: running an agent in a directory is equivalent to giving it that directory's context and tools.
- Restrict tools and permissions for untrusted input.

Adaptation for AidevOps:

- Use GitHub automation for review and maintenance only after prompts, permissions, and trust boundaries are explicit.
- Treat agent output as untrusted until independently verified.

### BMAD Method

Useful patterns:

- Progressive context engineering: analysis, planning, solutioning, implementation.
- Role-based expert collaboration: PM, architect, UX, developer, QA.
- PRD and UX coaching with validation rubrics.
- Sprint planning, story creation, dev story loop, code review, corrective course, and retrospective.
- Web bundle concept for doing planning in chat before IDE implementation.
- UX Coach pattern: keep `DESIGN.md` and `EXPERIENCE.md` style spines before mockups; use visual tokens, IA, journeys, concern scans, and handoff prompts.
- Forge/elicitation pattern: pressure-test assumptions with cracks, locks, pre-mortems, red-team critique, and one high-impact question at a time.

Adaptation for AidevOps:

- Keep the phased planning and validation rubrics.
- Collapse roles into lightweight perspectives unless the project stakes justify more ceremony.
- Preserve PRD quality dimensions: decision-readiness, done-ness clarity, scope honesty, downstream usability.
- Put BMAD-style role outputs into the four phase files instead of creating a separate role document per expert.
- Keep original external skills as research/reference material when useful, but translate guidance into Chinese for beginner users inside AidevOps outputs.

### GitHub Spec Kit

Useful patterns:

- Specification-driven development: specs as source of truth, code as implementation.
- Commands/artifacts: constitution, specify, clarify, plan, tasks, analyze, implement, converge.
- Stable feature branches and `specs/<feature>/` structure.
- User stories prioritized by independent testability.
- Task lists grouped by user story with parallelization markers.
- Governance gate pattern: use constitution-style gates before implementation and group tasks by independently testable story.

Adaptation for AidevOps:

- Use spec -> plan -> tasks -> implement as the backbone.
- Keep `[NEEDS CLARIFICATION]` markers for unknowns.
- Use story-level MVP slices and acceptance evidence instead of broad backlog dumps.
- Keep `progress.yaml` as the lightweight execution ledger instead of a larger command system.

### Sub2API Image Relay

Useful patterns and caveats:

- Sub2API recognizes image intent on `/v1/images/generations`, `/v1/images/edits`, and `/v1/responses` requests that use an image model, `tools:[{"type":"image_generation"}]`, or image `tool_choice`.
- OpenAI group keys can require `allow_image_generation`; otherwise image requests return a stable 403 permission error.
- Codex image bridge can inject `image_generation` for official Codex-looking `/v1/responses` requests when the group and channel allow it, but injected `tool_choice:auto` does not guarantee that the model will call the tool.
- Prefer explicit `/v1/responses` image tool requests for prototype generation through Sub2API.
- Issue https://github.com/Wei-Shaw/sub2api/issues/3302 shows why callers must validate model/size/quality metadata and final PNG dimensions rather than trusting request parameters.
- Issue https://github.com/Wei-Shaw/sub2api/issues/1999 shows why callers should inspect Responses tool usage, especially image-generation usage, when validating billing/accounting behavior.

## Cross-Framework Composite

The common successful loop is:

```text
Intent
-> clarify
-> PRD/spec with assumptions and acceptance criteria
-> UX/architecture spine
-> implementation plan
-> independently testable tasks
-> one slice implementation
-> verify/review/test
-> accept or correct course
-> retrospective and knowledge backflow
```

For beginner vibe coding, compress the same loop into:

```text
one-sentence intent
-> at most 5 questions
-> one P1 story
-> visible design/prototype/code slice
-> local run or screenshot evidence
-> wiki update
-> continue/fix/stop decision
```

## Anti-Patterns to Avoid

- Vibe coding from a vague idea without a PRD or acceptance criteria.
- Vibe coding a full app in one shot instead of one visible, verified slice.
- Creating many agents/roles before the work needs them.
- Treating generated prototype images as requirements.
- Letting automation comment on or modify untrusted PR input with broad permissions.
- Declaring done from agent claims without independent tests or manual evidence.
- Generating a large backlog where no story is independently demoable.
