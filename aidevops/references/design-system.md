# Design System and Prototype Quality

Use this reference when the work needs design beyond plain implementation. Design includes product model, service/system shape, interaction, IA, visual system, prototype prompts, and review.

## Designer Skill Contract

When design quality matters, produce two peer design spines before judging or generating mockups:

- `DESIGN.md`: how it looks. Include token summaries when useful, then brand/style, colors, typography, layout/spacing, elevation, shapes, components, and do/don't rules.
- `EXPERIENCE.md`: how it works. Include foundation, IA, voice and tone, component behavior, state patterns, interaction primitives, accessibility floor, and key flows.

`DESIGN.md` and `EXPERIENCE.md` win over generated images when they conflict. Images are evidence and discussion material, not the source of requirements.

For the minimal AidevOps workspace, put these under `docs/<feature-slug>/prototypes/` unless the target repo has an existing design-doc convention.

## Design Layers

Work from abstract to concrete:

1. **Product design**: user job, value moment, feature boundaries, terminology, success signal.
2. **Service/system design**: actors, handoffs, external systems, back-office work, failure recovery.
3. **Interaction design**: user flows, controls, feedback, validation, state transitions.
4. **Information architecture**: navigation, hierarchy, labels, permissions, empty/loading/error states.
5. **Visual system**: typography, spacing, color, density, icons, components, accessibility.
6. **Prototype asset**: image prompts or screen specs that visualize approved decisions.

Do not jump to image generation before the first four layers are stable enough.

## Design Brief

Capture:

- Product category and audience.
- Language strategy: Chinese-first, English-first, or bilingual.
- Primary workflow and screen inventory.
- Data objects and realistic sample data.
- Role/permission differences.
- Platform and viewport priorities.
- Tone and density.
- Existing design system or component library.
- Accessibility constraints.
- Visual references and anti-references.

## Visual Board

If the user asks for prototypes, visual quality, or implementation-ready UX, create a polished `prototypes/visual-system.html` board. It should show:

- Product frame: app shell, navigation model, page density, and role-specific entry points.
- Token swatches: background, surface, text, muted text, border, primary, success, warning, danger.
- Typography and spacing examples at realistic UI sizes.
- Components: buttons, inputs, segmented controls, status badges, tables/lists, editor areas, empty/loading/error states.
- Screen thumbnails for the decision-critical MVP screens.
- Accessibility notes and anti-patterns.

Do not make it a marketing landing page. For SaaS/admin/internal tools, use dense but organized information, restrained visual styling, predictable navigation, and real product data. Avoid decorative backgrounds, generic cards, oversized hero text, lorem ipsum, and fake features outside the PRD.

Before generating PNG prototypes, review the board itself against the design spine. If the board is weak, generic, or visually under-specified, improve it first. A weak board produces weak image prompts and should not be used as the source of truth.

## Token and Component Guidance

For MVPs, keep tokens pragmatic:

- Color: background, surface, text, muted text, border, primary, danger, success, warning.
- Type: display only for real heroes; compact panels use smaller headings.
- Spacing: 4/8px rhythm unless the existing system differs.
- Radius: 8px or less for cards and controls unless the repo already uses another rule.
- Icons: use the existing icon library; for React apps, lucide is a good default only when already available or easy to add.
- Controls: use familiar controls for the job: segmented controls for modes, toggles for binary settings, sliders/inputs for numeric values, tabs for views, menus for option sets.

Avoid decorative layouts that hide the product. Operational SaaS, CRM, admin, and devtools should be dense, calm, scannable, and work-focused.

## Prototype Image Quality Bar

The default should be a polished product mockup, not a generic wireframe.

Generated PNG prototypes must be guided by the design spine. A PNG is not useful simply because it is a valid image file; it should follow `DESIGN.md`, `EXPERIENCE.md`, and `visual-system.html` closely enough to support discussion.

Default to draft prototype mode for normal MVP work. In draft mode, preserve the returned PNG bytes unchanged, keep the API report, and record visible differences as review notes. Do not run a formal design acceptance gate unless the user asks for approved UI, production-ready design, or exact visual matching.

Use `references/visual-prototype-quality.md` as the strict acceptance rule only in that strict mode. The most common failure is a generated PNG that is technically valid but has no visual relationship to the visual board; in strict mode, reject that image and regenerate it.

Require prompts to include:

- Domain-specific screen purpose.
- Realistic product terms and sample data.
- Exact UI language. For Chinese beginner/internal users, use Chinese UI copy and realistic Chinese sample data; keep technical labels only when users expect them.
- Navigation model and primary action.
- State shown: default, empty, loading, error, permission, or result.
- Visual direction and anti-reference.
- Component density and accessibility requirements.
- Constraints against lorem ipsum, fake features, unreadable text, and marketing hero composition unless the screen is actually a landing page.

Avoid prompts that say only "dashboard", "modern UI", "clean wireframe", or "SaaS app"; they reliably produce generic output.

For image prompts aimed at general image models, a practical pattern is English layout/style instructions plus exact Chinese UI text:

```text
Create a high-fidelity desktop web app mockup...
Use exact Chinese UI labels from the product glossary, for example "<当前任务>", "保存草稿", "提交<对象名>".
Use realistic Chinese sample data, no lorem ipsum.
```

## Image Count

Generate by decision-critical screen/state, not by user story:

- **1 image**: low-risk layout direction or single-screen utility.
- **2 images**: list/workspace plus create/detail.
- **3 images**: default MVP set: entry/workspace, primary action, result/detail.
- **4 images**: add empty/error when recovery changes the design.
- **5 images**: add mobile only when mobile is first-release critical.

More than 5 images usually means the PRD or screen inventory should be tightened before generation.

## Design Review

Review prototypes against:

- Does each screen map to a journey and requirement?
- Does the PNG roughly use the same palette, density, app shell, and component style as the visual board in draft mode, or match them closely in strict mode?
- Is the primary action obvious?
- Does the content hierarchy fit real data?
- Are empty/error states recoverable?
- Does visual style match product category and user workflow?
- Are generated features outside the PRD removed from the plan?
- Are decisions written back to `01-design.yaml`?

Also verify:

- `DESIGN.md` and `EXPERIENCE.md` exist when the task asked for design quality.
- The visual board reflects the same tokens, terminology, and screen inventory.
- Required PNG prototypes are real generated PNG files, not screenshots of `visual-system.html`.
- In draft mode, inconsistent PNGs are kept only as draft discussion assets with notes. In strict mode, inconsistent PNGs are moved to `prototypes/rejected/` and not listed as `generated_assets`.
- `01-design.yaml.prototype_image_request.design_system_lock` exists before generation.
- `01-design.yaml.prototype_image_request.validation_mode: simple_return` is enough for draft work. `visual_consistency_review.status: pass` is required only for strict visual acceptance.
- Text fits inside UI elements at desktop and mobile preview widths.
- Internal/business systems look useful for repeated work, not like a public marketing page.
