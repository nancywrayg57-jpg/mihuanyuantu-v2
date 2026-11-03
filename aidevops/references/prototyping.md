# Prototype and gpt-image-2 Workflow

Use this reference when the user wants UX design, multi-screen prototype sketches, or OpenAI image-generation integration.

Current official OpenAI guidance separates single-image generation from multi-turn or contextual image workflows. Use the local script to test the route actually available in the user's relay account; do not assume model support from memory.

## When to Generate Images

Generate or request image generation only when:

- The PRD has stable target users, MVP flow, and screen inventory.
- The user has approved or supplied a visual direction.
- The output will help decide layout, information hierarchy, or interaction details.

If the flow is still unstable, produce `01-design.yaml` updates and a prompt pack first. Images are a design decision aid, not a requirements source.

Before generating, ensure the designer capability has produced or updated the design spine (`DESIGN.md` and `EXPERIENCE.md`) when the screen has meaningful UX/visual decisions. Also ensure `visual-system.html` is strong enough to serve as a visual source of truth; if it looks generic or weak, improve it before generating PNGs.

If the user asked for PNG prototype images, set `01-design.yaml.prototype_image_request.required: true`. Default to **draft prototype mode** unless the user explicitly asks for strict visual acceptance. In draft mode:

- Generate one real PNG file per requested decision-critical screen/state.
- First render `prototypes/visual-system.html` to `prototypes/visual-system-desktop.png` and use that PNG as the visual reference image when the image route supports image inputs.
- Store them under `docs/<feature>/prototypes/` with stable names.
- Store request/response validation reports next to the generated PNGs under `prototypes/`.
- Do not count `visual-system.html`, browser screenshots of HTML, SVG mockups, or prompt packs as generated PNG prototype images.
- Do not use a contact sheet as the final substitute for the generated prototype PNG set. Contact sheets are allowed only as early exploration artifacts when explicitly labeled as exploration.
- Generated PNGs should be guided by `DESIGN.md`, `EXPERIENCE.md`, and `visual-system.html`: palette family, density, product shell, component style, screen inventory, and terminology.
- In draft mode, keep returned PNGs as discussion assets even when they are imperfect, and record visible drift in `review_notes`. Do not move files to `prototypes/rejected/` unless strict mode is active.
- Record generated images in `generated_assets`, API reports in `validation_reports`, and draft notes in `review_notes`.
- Preserve returned image bytes as the canonical asset. Do not recompress, resize, re-encode, optimize, or otherwise post-process the PNG returned by the image route unless the user explicitly asks for a derived version. If post-processing is requested, keep the original returned PNG and write the derived file as a separate asset.

Draft mode does not require a formal visual acceptance gate. It requires:

- `validation_mode: simple_return`
- the reference screenshot path when available
- generated PNG paths
- API report paths
- `system_flow_diagram` paths when the MVP has app/backend/data/AI/review/export boundaries
- a short note that images are draft references, not approved UI

Use strict design review only when the user asks for approved UI, high-fidelity stakeholder signoff, exact visual matching, or production-ready design.
- In strict mode, do not accept PNGs that ignore the design spine. Move inconsistent or low-quality PNGs under `prototypes/rejected/`, record them in `rejected_assets`, and set `visual_consistency_review.status` only after every accepted screen passes.
- If generation fails, keep the failed command, HTTP/status/error summary, and next action in `01-design.yaml`, `03-acceptance.yaml`, and `wiki.md`.
- Do not mark `prototype-image-request` complete until PNG files exist or the user explicitly defers image generation.

## Design-System Lock for PNG Prompts

When generating PNG prototypes from an AidevOps design spine, each prompt must include a compact "design-system lock":

- Source of truth: `DESIGN.md`, `EXPERIENCE.md`, `visual-system.html`.
- Palette: exact or near-exact tokens from `DESIGN.md`, for example background, surface, primary, teal, success, warning, danger.
- Layout: app shell, navigation, page density, top bar, table/editor/panel structure.
- Components: buttons, badges, inputs, tables, editor sections, source reference panels, empty/loading/error states.
- Typography: Chinese enterprise UI, compact 12-16px scale, no hero typography.
- Anti-references: no marketing landing page, no decorative gradients, no generic monochrome wireframe, no unrelated features.

After generation, review against these checks. In draft mode, record notes but keep the returned PNG as a draft discussion asset. In strict mode, pass every check before listing the image as accepted:

- Does the image look like the same product as `visual-system.html`?
- Are palette and density close enough?
- Does the screen show the intended workflow, not a generic dashboard?
- Is text broadly readable and business-specific?
- Are fake features, lorem ipsum, or sensitive real data absent?

If any answer fails in strict mode, reject and regenerate with a more constrained prompt.

For detailed strict rejection and review rules, read `references/visual-prototype-quality.md`.

## Visual Board Reference Image

Before image generation, refresh the visual board screenshot:

```bash
chromium --headless --no-sandbox --disable-gpu \
  --screenshot=docs/<feature>/prototypes/visual-system-desktop.png \
  --window-size=1440,1400 \
  file:///absolute/path/to/docs/<feature>/prototypes/visual-system.html
```

Then pass it to the Responses image route when supported:

```bash
python3 aidevops/scripts/gpt_image_smoke.py \
  --env aidevops/.env \
  --mode responses-image-tool \
  --text-model gpt-5.4 \
  --model gpt-image-2 \
  --size 1536x1024 \
  --quality high \
  --reference-image docs/<feature>/prototypes/visual-system-desktop.png \
  --prompt "<high quality, target canvas 1536x1024 pixels...>"
```

If the reference-image route fails, fall back to text-only prompts and record the failed report. Do not block draft prototype mode solely because the reference image could not be used.

## Environment Handling

Before making API calls:

1. Check `.env` for variable names without printing values.
2. Use `OPENAI_API_KEY` as the default credential name.
3. Support optional `OPENAI_BASE_URL`, `OPENAI_ORG_ID`, and `OPENAI_PROJECT` only if present or required by the local SDK setup.
4. If no standard key names are detected, ask the user to confirm the credential variable names before making API calls.
5. Never include secrets in generated prompts, logs, images, screenshots, commits, or reports.
6. Verify the current official OpenAI image generation docs before writing new API code; prefer the installed SDK patterns in the target repo when they exist.

Default model target: `gpt-image-2`, unless the user or current official docs require a different model.

Do not embed credentials in prompts, examples, screenshots, generated assets, or phase files. Store credentials in `.env` or the target repo's existing secret manager only.

## Relay Findings for OpenAI-Compatible Image Routes

When using an OpenAI-compatible relay for OpenAI/Codex image generation:

- Prefer `/v1/responses` with an explicit `image_generation` tool for prototype generation.
- Use a Responses-capable text model at the top level, such as `gpt-5.4`, and put `gpt-image-2` on the tool:

```json
{
  "model": "gpt-5.4",
  "input": [
    {
      "role": "user",
      "content": [{ "type": "input_text", "text": "<prototype prompt>" }]
    }
  ],
  "stream": false,
  "tools": [
    {
      "type": "image_generation",
      "model": "gpt-image-2",
      "size": "1024x1024",
      "output_format": "png"
    }
  ],
  "tool_choice": { "type": "image_generation" }
}
```

- Do not rely on HTTP 200 alone. Validate the final PNG dimensions and the response metadata because sub2api issue #3302 documents silent model/size/quality normalization risks.
- Inspect `tool_usage`, especially `tool_usage.image_gen`, because sub2api issue #1999 discusses image-tool usage accounting on Responses.
- When OpenAI grouped Codex `/responses` requests are configured to auto-inject `image_generation`, keep that enabled only for routes backed by accounts that support image generation. Treat it as a convenience path; still prefer explicit `tools` and `tool_choice` for reproducible prototype generation.
- If Codex image bridge is enabled, Codex-looking `/v1/responses` text requests may get image tools injected automatically, but this should be treated as convenience routing only. `tool_choice:auto` does not guarantee the model will call the image tool. Use explicit `tool_choice` for deterministic prototype generation.
- `/v1/images/generations` can work in principle, but in this workspace it hit a Cloudflare 524 after about 120 seconds through `2apitest.aisws.com`; prefer Responses SSE for long-running relay calls.

Smoke test:

```bash
python3 aidevops/scripts/gpt_image_smoke.py --env aidevops/.env --mode models
python3 aidevops/scripts/gpt_image_smoke.py --env aidevops/.env --mode responses-text --text-model gpt-5.4
python3 aidevops/scripts/gpt_image_smoke.py --env aidevops/.env --mode responses-image-tool --text-model gpt-5.4 --model gpt-image-2 --size 1536x1024 --quality high --strict-size
```

Use `--quality high --strict-size` when the user explicitly requires high-quality or exact pixel output. Without `--strict-size`, a successful image with normalized dimensions still produces a report for review but must not be treated as exact-pixel support. Run `--mode models` and `--mode responses-text` first when diagnosing a relay account before spending image tokens. Inspect `requested_image_tool`, `image_metadata`, `image_tool_usage_present`, `image_tool_usage_detected`, and actual PNG dimensions together; a text response can expose a zero-valued `image_gen` usage bucket without performing image generation.

Observed relay behavior in this workspace on 2026-06-30 with the current deployed sub2api route:

- `/v1/responses` explicit `image_generation` tool with `model: gpt-image-2`, `quality: high`, `size: 1536x1024`, `action: generate`, and `--strict-size` returned PNG `1586x992`; response metadata reported `quality: medium`.
- `/v1/responses` explicit `image_generation` tool with `quality: high`, `size: 1024x1024`, and `--strict-size` returned PNG `1254x1254`; response metadata reported `quality: medium`.
- `/v1/images/generations` with `quality: high`, `size: 1024x1024`, and `--strict-size` returned PNG `1254x1254`.

Treat this as **not fixed for high/exact-pixel mode** until a future strict smoke test returns both matching metadata and matching PNG dimensions. Do not resize or compress returned images to hide route behavior. If the user explicitly requests a derived presentation asset, keep the returned PNG unchanged and record the derived file separately.

## Visual Direction Intake

Ask only what changes the output:

- Product category: SaaS admin, CRM, marketplace, consumer app, devtool, game, internal tool, etc.
- Primary platform: desktop web, mobile web, native mobile, tablet, kiosk.
- UI language: for domestic Chinese beginner users, default to Chinese UI text and Chinese sample data; keep API/config/model names in English.
- Brand/style anchors: 2-3 adjectives, reference products, anti-references.
- Density: dashboard-dense, balanced, editorial, playful, data-heavy.
- Accessibility: contrast, font size, keyboard/focus needs.
- Required screens: screen names, states, and responsive variants.

If no style is provided, default to a restrained, production-ready UI suited to the domain. For operational SaaS/internal tools, prefer dense but organized screens, clear navigation, restrained color, and scannable tables/forms over decorative marketing composition.

Default anti-reference: do not ask for "a clean monochrome wireframe" unless the user explicitly wants wireframes. For MVP product review, ask for a high-fidelity product UI mockup with realistic data and domain-specific component choices.

## Screen Prompt Structure

Create one prompt per screen. Use a contact sheet prompt only for explicitly marked early exploration, never as the final required PNG set. Store approved prompts under `01-design.yaml.prototype_image_request.prompts`; use a `prototypes/` folder for generated PNGs, validation reports, visual board screenshots, and runtime flow diagrams.

```markdown
## Prototype Prompt: <screen name>

Create a high-fidelity product UI mockup for <platform/viewport>.

Product:
- Name:
- Domain:
- Target user:
- Primary job:

Screen:
- Screen name:
- User state:
- Primary goal:
- Main content hierarchy:
- Primary actions:
- Secondary actions:
- Empty/loading/error states to show:
- Realistic sample data:

Style:
- Visual tone:
- Layout density:
- Typography:
- Color direction:
- Component style:
- Accessibility requirements:
- UI language and exact labels:

Constraints:
- Do not include marketing hero content unless this is actually a landing page.
- Do not use placeholder lorem ipsum.
- Do not invent features outside PRD IDs: <FR list>.
- Keep text legible and inside UI components.
- Show the actual product state, not abstract atmosphere.
- Avoid generic monochrome wireframe style unless explicitly requested.
```

## Multi-Screen Set

For MVP product flows, generate 3-5 images by default:

1. Entry/dashboard or main workspace.
2. Primary creation/action screen.
3. Detail or result screen.
4. Error/empty state if it changes the product decision.
5. Mobile variant only when mobile is MVP-critical.

Use fewer images for low-risk MVPs:

- **1 image**: single-screen utility, CLI companion UI, or layout direction only.
- **2 images**: list/dashboard plus create/detail.
- **3 images**: normal MVP default: entry, primary action, result/detail.
- **4 images**: add empty/error state when failure handling affects UX.
- **5 images**: add mobile only when mobile is a first-release requirement.

Do not generate one image per user story. Generate one image per decision-critical screen/state. A screen qualifies only if it changes navigation, data hierarchy, permissions, validation, or visual system decisions.

Normal decomposition for a new MVP:

1. **Entry/workspace**: where the primary role starts and sees state.
2. **Primary action**: the create/edit/approve/run flow that creates value.
3. **Result/detail**: completed state, output, audit trail, or next decision.
4. **Recovery state**: empty/error/permission only when it changes behavior.
5. **Responsive variant**: mobile/tablet only when first-release usage requires it.

Keep visual system consistent across screens:

- Same navigation model.
- Same typography and spacing scale.
- Same entity names and sample data.
- Same primary action styling.
- Same role/permission assumptions.

## Runtime Flow Diagram

When the MVP has app, backend, data, AI/model, human review, export, deployment, or fallback boundaries, add a deterministic runtime flow diagram:

- `docs/<feature>/prototypes/system-flow.html`
- `docs/<feature>/prototypes/system-flow.png`

The diagram should show the path from user input through UI, backend/API, database/files, AI/model boundary if any, fallback path, human confirmation, and final output/export. Render it from HTML/SVG/Canvas with Chromium or another deterministic local renderer.

Record it in `01-design.yaml.system_flow_diagram`:

```yaml
system_flow_diagram:
  html: prototypes/system-flow.html
  png: prototypes/system-flow.png
  purpose: "Show the MVP runtime path from user input through app/backend/data/AI boundary to reviewed output."
  validation: "Rendered by Chromium; not counted as gpt-image-2 prototype generated_assets."
```

Do not list `system-flow.png` in `prototype_image_request.generated_assets`; it is not a `gpt-image-2` prototype screen.

## Iteration Loop

1. Generate first draft prompts from `00-discovery.yaml` and `01-design.yaml`.
2. Ask the user to approve style direction or choose among alternatives.
3. Generate images.
4. Review images against the PRD:
   - Missing required screen/state?
   - Text impossible to read?
   - UI suggests unapproved features?
   - Key data hierarchy wrong?
   - Mobile/desktop mismatch?
5. Update `01-design.yaml` with decisions and rejected directions.

## Output Paths

Recommended:

```text
docs/<feature-slug>/
|-- progress.yaml
|-- 01-design.yaml
`-- prototypes/
    |-- DESIGN.md
    |-- EXPERIENCE.md
    |-- visual-system.html
    |-- visual-system-desktop.png
    |-- prototype-01-workspace.png
    |-- prototype-01-workspace-report.json
    |-- prototype-02-primary-action.png
    |-- prototype-02-primary-action-report.json
    |-- prototype-03-result-detail.png
    |-- prototype-03-result-detail-report.json
    |-- system-flow.html
    `-- system-flow.png
```

## Review Checklist

- Every generated screen maps to a user journey or acceptance scenario.
- Screen text reflects real product terms from the glossary.
- No generated UI element creates new unplanned scope.
- Primary action is visually obvious.
- Error/empty states explain recovery.
- Layout works for the target viewport.
- Colors and density match the product category.
- Returned PNG bytes are preserved unchanged; derived/compressed versions, if requested, are separate files.
