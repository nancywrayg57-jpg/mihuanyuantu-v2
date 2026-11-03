# Vibe Coding Fast Lane

Use this reference when the user wants fast AI-assisted development, especially beginner-friendly "vibe coding" from a rough idea to a working MVP slice.

## What Vibe Coding Means Here

Vibe coding is a guided rapid loop, not unbounded code generation. The agent helps a beginner turn a rough intent into a visible, runnable slice while keeping requirements, design, verification, and safety visible in local docs.

Use this mode when the user says things like:

- "快速做个 MVP"
- "vibe coding"
- "我不会写代码，你带我做"
- "先跑起来再优化"
- "从这个 PRD/想法开始自动推进"

## Source Patterns to Keep

- Agile: prefer working software, frequent delivery, technical excellence, and sustainable pace.
- Spec-driven development: clarify first, then spec, plan, tasks, implement, and verify one independently testable story.
- Agentic coding best practice: maintain project instructions, use planning mode for non-trivial changes, run tests, and treat agent output as needing verification.
- Beginner product builders: prompt with clear goal, user, workflow, constraints, and success signal; avoid huge one-shot prompts.

## Beginner Contract

For domestic Chinese beginners:

- Explain the next action in Chinese, briefly and concretely.
- Keep commands, filenames, env vars, APIs, and code identifiers in English.
- Prefer one command or one decision at a time.
- Say what the user should put under `docs/<feature>/input/`.
- Offer a recommended default, but mark protected decisions as unconfirmed until the user approves.
- Avoid jargon unless it is immediately explained.

## Fast Lane Loop

Use this loop inside the existing four phase files:

0. **Reference scan**
   - Search GitHub and, when relevant for Chinese users, Gitee for similar apps, templates, or admin systems.
   - Scan any user-provided reference framework/base code before choosing directories or implementation patterns.
   - Extract only reusable product functions, IA, data model hints, code structure, component conventions, and validation ideas.
   - Do not copy licenses, secrets, business-specific data, or code blindly.
   - Record findings in `00-discovery.yaml.reference_scan`, `02-delivery.yaml.code_structure`, and `wiki.md`.

1. **One-sentence intent**
   - Product:
   - Target user:
   - One painful job:
   - Visible success:

2. **Five-question cap**
   - Ask at most 5 questions that change value, architecture, security, data, or release risk.
   - In explicit test mode, auto-fill non-sensitive answers and mark `[AUTO-FILLED FOR TEST: reason]`.

3. **Thin PRD**
   - Write only the MVP journey, P1 story, acceptance criteria, and non-goals needed for the first slice.
   - Put the rest into deferred scope.

4. **Design before code**
   - For UI work, create or update `DESIGN.md`, `EXPERIENCE.md`, and a visual/prototype board before coding the screen.
   - If this is throwaway exploration, say so in `progress.yaml.vibe_coding.prototype_intent`.

5. **One vertical slice**
   - Build only one independently demoable story.
   - Keep setup/foundation work minimal.
   - Prefer local-first stacks: Go, Python, Node.js, or plain HTML; SQLite for first local MVP database.

6. **Run and see**
   - Start the dev server when needed.
   - Give the local URL.
   - Verify with compile/tests and a manual browser check when UI exists.
   - Capture screenshots or prototype evidence when helpful.

7. **Review and learn**
   - Inspect the diff, test result, UI, and requirement mapping.
   - Update `knowledge_assets`, `wiki.md`, and `progress.yaml`.
   - Choose: continue, fix, or stop.

## Vibe Coding Ledger

Add this block to `progress.yaml`:

```yaml
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
```

## Planning Micro-Prompts

Use these with the user:

- "请把当前需求、草稿 PRD、截图或样例放到 `docs/<feature>/input/`；如果已经在别处，我会复制或引用过去。"
- "我会先搜索 GitHub/Gitee 的类似应用，并扫描你指定的参考框架或底座代码，只提炼功能和目录规范，不照搬代码。"
- "我先问最多 5 个会影响架构/成本/安全的问题；测试模式下我会自动补齐并标注假设。"
- "我建议先做一个 P1 闭环：<role> 完成 <job>，用 <evidence> 验证。是否确认？"
- "这是 throwaway prototype 还是生产意图代码？生产意图代码需要先确认 Git、技术栈、身份、部署和数据边界。"
- "这一轮我只做一个可见切片，完成后给你 URL/截图/测试结果，再决定继续还是修。"

## Beginner Quality Bar

Pass when:

- The user can state what was built in one sentence.
- The first slice is visible or runnable, not only described.
- There is a local command or URL for the user to try.
- The output maps to one user story and acceptance criteria.
- The agent has recorded what changed, what was assumed, and what remains risky.

Hold when:

- The user has not confirmed whether work is throwaway or production-intended.
- The PRD is vague and the run is not explicit test mode.
- The app cannot be run or inspected locally.
- The UI exists but no one checked the main workflow.
- A protected decision was guessed and the agent is about to write production-intended code.

## Wiki Update

After every fast-lane loop, update `wiki.md`:

- What was tried.
- What worked.
- What failed.
- The command or URL used.
- The next safest step.
- Any beginner-facing explanation that should be reused.
