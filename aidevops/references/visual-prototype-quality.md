# Visual Prototype Quality

Use this reference when a workflow produces UI prototype images, visual boards, or bitmap mockups. It exists because a valid PNG can still be unusable when it ignores the approved design spine.

Default AidevOps PNG generation is draft mode unless the user asks for approved UI, production-ready design, or exact visual matching. In draft mode, preserve returned PNG bytes unchanged, keep API reports, and record drift as notes. Use the strict rejection and pass/fail rules below only for strict visual acceptance.

## Practical Failure to Prevent

In strict mode, reject the output when any of these happen:

- `visual-system.html` and generated PNGs look like different products.
- The PNG uses a different palette, density, app shell, typography, or component style than `DESIGN.md`, `EXPERIENCE.md`, and `visual-system.html`.
- The PNG is a generic SaaS dashboard, monochrome wireframe, marketing page, or decorative concept image instead of a product workflow screen.
- The PNG invents unapproved features, hides the primary workflow, uses unreadable text, or contains lorem ipsum.
- A browser screenshot of `visual-system.html` is listed as a generated prototype PNG.
- A contact sheet is used as the final required PNG set instead of one generated PNG per decision-critical screen.

Move strict-mode rejected files to `prototypes/rejected/` and record the reason in `01-design.yaml.prototype_image_request.rejected_assets` and `review_notes`. In draft mode, do not move or mutate the returned PNG; keep it as a draft asset and write the mismatch in `review_notes`.

## Skill Sources to Apply

Use the bundled child skills as quality inputs, without rewriting their upstream snapshots:

- `skills/frontend-design/SKILL.md`: ground the design in the subject, avoid templated defaults, create a compact token plan, self-critique before building.
- `skills/team-uidesign/specs/design-standards.md`: use token hierarchy, 4/8px rhythm, CTA hierarchy, interaction states, focus and responsive rules.
- `skills/team-uidesign/specs/anti-patterns.md`: reject AI-slop patterns such as generic gradients, nested cards, all-primary buttons, everything centered, pure black/white, generic typography, and meaningless decorative charts.
- `skills/team-uidesign/specs/scoring-guide.md`: treat scores below `Good` as revision-needed; any blocking visual dimension requires iteration.
- `skills/team-uidesign/specs/ux-writing.md`: labels must be action-specific and business-specific.
- `skills/ui-ux-pro-max/SKILL.md`: apply critical/high UX checks first: accessibility, interaction/touch targets, layout/responsive, style consistency, typography and color.

## Required Sequence

1. Read the PRD, `00-discovery.yaml`, `01-design.yaml`, `DESIGN.md`, `EXPERIENCE.md`, and `visual-system.html`.
2. If the visual board is weak, generic, or inconsistent with the design spine, improve the board before generating PNGs.
3. Freeze a compact `design_system_lock` in `01-design.yaml.prototype_image_request`:
   - source files
   - palette tokens
   - layout shell
   - typography and density
   - component rules
   - exact UI language
   - anti-references
4. Generate one PNG per decision-critical screen/state.
5. Inspect each PNG before marking the capability complete. Use local image viewing and compare to the visual board at the active validation level.
6. If the product has app/backend/data/AI/review/export boundaries, create `prototypes/system-flow.html` and `prototypes/system-flow.png`, and record them in `system_flow_diagram`, not `generated_assets`.
7. In draft mode, keep generated paths, reports, preserved-byte notes, and rough-flow notes. In strict mode, accept only images that pass the consistency checklist and reject/regenerate the rest.
8. Update `01-design.yaml`, `03-acceptance.yaml`, `progress.yaml`, and `wiki.md` with generated paths, rejected paths when strict mode applies, reports, runtime flow diagram paths, and review notes.

If the user requires high quality or exact pixel dimensions, run the image route with `--quality high --strict-size` and only accept the route as fixed when both the returned metadata and actual PNG dimensions match the request. Preserve the returned image as-is. Do not recompress, resize, re-encode, or otherwise mutate the returned PNG to make it look compliant. If the user explicitly requests a derived presentation asset, keep the original returned PNG and record the derived file separately.

## Design-System Lock Template

```yaml
prototype_image_request:
  design_system_lock:
    source_of_truth:
      - prototypes/DESIGN.md
      - prototypes/EXPERIENCE.md
      - prototypes/visual-system.html
    palette:
      background: ""
      surface: ""
      text: ""
      muted: ""
      border: ""
      primary: ""
      success: ""
      warning: ""
      danger: ""
    layout:
      app_shell: ""
      navigation: ""
      density: ""
      viewport: ""
    components:
      - ""
    typography:
      language: ""
      scale: ""
    anti_references:
      - ""
```

## Prompt Pattern for PNGs

Use English for layout/style precision and exact Chinese for UI copy when the product is Chinese-first:

```text
Use case: ui-mockup
Asset type: high-fidelity desktop web app prototype PNG
Primary request: <screen name and role goal>
Source of truth: match the attached or described design spine exactly: DESIGN.md, EXPERIENCE.md, visual-system.html.
Design-system lock: palette <tokens>; left nav <width>; top bar <height>; compact enterprise SaaS density; table/form/editor components; radius <= 8px.
Screen content: <business-specific hierarchy, primary action, states, sample data>.
Text (verbatim): "<exact Chinese labels>"
Constraints: render the actual product workflow, not a generic dashboard. Same product shell and palette as the visual board. Use synthetic data only. No lorem ipsum. No marketing hero. No decorative gradient background. No unrelated features. No watermark.
```

## Visual Consistency Checklist

For strict mode, record this as `visual_consistency_review`:

- `same_product`: the PNG looks like the same product as `visual-system.html`.
- `palette_match`: colors use the same family and emphasis hierarchy.
- `density_match`: spacing, table density, and control scale match the board.
- `shell_match`: navigation, top bar, page shell, and primary content model match.
- `component_match`: buttons, badges, inputs, tables, editor panels, and source references match.
- `workflow_specific`: the screen shows the intended workflow and primary action.
- `content_quality`: Chinese text is business-specific, readable enough for review, and uses synthetic data.
- `anti_slop`: no major AI-slop patterns from `team-uidesign/specs/anti-patterns.md`.
- `not_screenshot`: the accepted file is a generated PNG, not a screenshot of the visual board.

Only set `status: pass` when every required screen passes. If any screen fails, keep the strict gate on hold. In draft mode, use `validation_mode: simple_return` and keep `visual_consistency_review.status` as `not_required_draft`, `pending`, or omitted.
