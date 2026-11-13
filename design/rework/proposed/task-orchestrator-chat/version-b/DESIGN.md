---
name: Console Task Orchestrator — Version B
description: Local projects-and-dock design prototype combining 52-B navigation with the task-scoped conversation and evidence workspace.
colors:
  page: "#0b0c0e"
  win: "#121315"
  raise: "#1a1c1f"
  off: "#24272b"
  ink: "#ebe8e1"
  mut: "#9a9993"
  line: "#26292d"
  you: "#ff8a3d"
  bad: "#ff5a4e"
  ok: "#5ed39a"
  page-light: "#dedcd6"
  win-light: "#f4f3ef"
  raise-light: "#e7e5e0"
  off-light: "#d6d4ce"
  ink-light: "#17181b"
  mut-light: "#5f5e59"
  line-light: "#d2d0ca"
  you-light: "#943d00"
  bad-light: "#c0352b"
  ok-light: "#17683f"
typography:
  display:
    fontFamily: 'Doto, "Cascadia Mono", monospace'
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-.04em"
  headline:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif'
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.35
  title:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif'
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: '"Cascadia Mono", "JetBrains Mono", Consolas, monospace'
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  compact: "3px"
  control: "4px"
  field: "6px"
  surface: "8px"
spacing:
  tight: "4px"
  small: "6px"
  compact: "8px"
  standard: "12px"
  panel: "16px"
  wide: "20px"
components:
  button-ink:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.win}"
    rounded: "{rounded.control}"
    padding: "4px 12px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "5px 11px"
  task-badge:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "2px 7px"
  project-task:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 7px"
  project-task-current:
    backgroundColor: "{colors.raise}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 7px"
  composer-field:
    backgroundColor: "{colors.win}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "8px 10px"
---

# Design System: Console Task Orchestrator — Version B

## Overview

**Creative North Star: "Console workbench"**

A dense operator workspace uses quiet surfaces, thin rules and small square cells to keep task identity, conversation, evidence and decisions distinct. The project navigator and persistent decision dock extend the existing task workspace. Reading type stays ordinary; Doto gives shared usage figures their established instrument-like accent.

This document describes the finished local Version B artifact, not the production application or a new global product identity. Its authority is the implemented source plus the local [surface brief](surface-brief.txt); product constraints remain in `CLAUDE.md`, `plans/62-task-orchestrators.md` and its `03-mockup-contract.md`. All sample tasks and measurements are fictional.

**Key Characteristics:**

- Dark and light themes share the same semantic surface and status roles.
- Conversation and evidence scroll independently; the decision and action dock stays outside those scroll regions.
- One task has one assigned orchestrator and one composer recipient.
- Small cells, mono measurements and restrained Doto figures carry the Console identity.

## Colors

The palette is near-neutral with warm attention, green verification and red failure. Frontmatter records the exact shared CSS primitives; names with `-light` are the corresponding `data-theme="light"` overrides.

### Primary

- **Needs-you orange** (`you`): pending replies, approval cues, decision tags and selected explicit answer emphasis.
- **Reading ink** (`ink`): primary text, active tab rules, filled usage cells and the strongest neutral action. Its inverse action foreground is the window surface.

### Secondary

- **Verified green** (`ok`): passed checks and positive receipts.
- **Failure red** (`bad`): failed evidence and destructive utility affordances. Status text accompanies color.

### Neutral

- **Page** (`page`): outside canvas, project navigator and shared usage strip.
- **Window** (`win`): conversation, evidence, composer and decision/action foundations.
- **Raised** (`raise`): user messages, current task/step and hover treatment.
- **Off** (`off`): unfilled meter cells and quiet tracking surfaces.
- **Muted** (`mut`): metadata, supporting copy and inactive controls.
- **Rule** (`line`): panel edges, dividers and quiet control borders.

**The Semantic Pair Rule.** Theme changes replace each role in place; preserve the role rather than copying a dark-theme color into a new component.

## Typography

**Display Font:** Doto, with Cascadia Mono and monospace fallback.  
**Body Font:** Segoe UI Variable Text, Segoe UI, system-ui, sans-serif.  
**Label/Mono Font:** Cascadia Mono, JetBrains Mono, Consolas, monospace.

The type hierarchy is deliberately shallow. Task headings orient the workspace; body copy carries evidence; mono labels distinguish source, speaker and measured quantities. Tabular numerals support usage comparison.

- **Display:** shared estimated-cost figure; reduces to 28px in the medium frame and 23px in compact chrome.
- **Headline:** task title; reduces to 15px at the mobile peer-panel breakpoint.
- **Title:** desktop orchestrator heading. Compact mobile chrome hides that repeated heading while retaining owner identity and activity.
- **Body:** conversation text; evidence paragraphs may use 1.7 line height. Supporting text is generally 10–11px.
- **Label:** speaker and metadata; the densest mobile metadata reaches 9px.

**The Reading First Rule.** Keep Doto on the established usage accent and ancillary page display; task prose and task headings use the UI stack.

## Layout

The outer review frame is at most 1460px wide and fills the available viewport height. Its window is a size-query container. Header, shared usage, task heading and footer are fixed flex regions; conversation and evidence take the remaining height.

The default wide task workspace combines an optional 232px project dock, a 300px conversation and flexible evidence. At a container width of 1180px or below, dock and conversation narrow to 200px and 270px; decision buttons move under the decision text. At 1050px or below, the project dock becomes a dismissible overlay up to 270px wide and the conversation uses 290px.

At 760px or below, Orchestrator, Overview, Step chat and Context become peer views. Only the selected conversation/evidence view occupies the body. The project drawer remains available, owner chrome condenses, repeated usage detail disappears, and the single Send button sits beside the textarea. The decision/action dock stays accessible below the selected peer view and may scroll within its 40% height cap.

Viewport media queries compact outer review chrome below 600px and reduce repeated vertical chrome at heights of 760px or less. These are separate from frame container queries. The final 340×760 capture retains approximately 167px of transcript; this is a verified result of that composition, not a fixed transcript-height token.

Spacing uses the small repeated steps recorded above. Thin row rules carry evidence organization. Brief paragraphs cap at 72 characters; project labels and task/evidence text wrap instead of widening a panel.

## Elevation & Depth

The workbench uses tonal layers and one-pixel borders rather than drop shadows. The project drawer overlays the body at a higher stacking level, distinguished by its edge. Native dialogs use a dim black backdrop and a stronger muted border. Current-step connectors and usage cells provide structure without raised cards.

**The Quiet Depth Rule.** Use surface role and border changes for workbench depth; keep the transcript and evidence flat.

## Shapes

Controls use compact corners; fields have slightly softer corners and the app window uses a larger surface corner. Tiny square cells recur in the brand, status marks, usage meters and step sequence. Pills are not the default form. Borders are thin, with dashed borders reserved for observed/read-only or unavailable-source treatments already present in the artifact.

## Components

### Buttons

Neutral outline controls use the rule border and shift to raised fill plus muted border on hover. Ink-filled buttons invert ink/window roles. The answer-emphasis variant uses attention color; its light-theme text is white. A visible two-pixel ink outline with offset supplies keyboard focus. Disabled controls retain their label and use reduced opacity. Under ordinary motion preference a press moves down by one pixel; reduced-motion preference removes transforms supplied through animation or transition and disables smooth scrolling.

### Chips

Task badges combine a small cell with a readable state label. Attention badges tint the border toward the attention role. Autonomy controls express their selected state with a border; Auto also uses ink/window inversion. Project mode labels are compact rectangular metadata.

### Cards / Containers

The project navigator separates pinned Needs you from the scrollable project groups. Selected task rows use raised fill and a rule border. Worker-step evidence uses horizontal ruled rows and a thin vertical sequence connector. Existing task-list tiles retain raised headers and a flat body; source/evidence disclosure containers retain quiet outlined corners.

### Inputs / Fields

The sole composer labels its recipient as the current task's orchestrator. Desktop guidance text sits below the textarea; compact mobile layout places Send adjacent to it. Inspecting worker chat, received assignments, handoff or files never adds a worker composer. Fields use the window surface, rule border, field corner and the shared visible focus outline.

### Navigation

Top navigation leads to Tasks, New task, Usage and Settings. The project dock supports task and step selection, a current marker and Escape dismissal when overlaid. Evidence tabs use an ink underline for selection and keyboard navigation. At the compact breakpoint Orchestrator joins the other tabs as a peer view.

### Decision and action dock

The decision region presents current actionable state separately from conversation chronology, using a faint attention-tinted window surface, explicit wording and state-specific actions. The lower bar retains folder, terminal, handoff and protected deletion utilities, task spend, explicitly labelled orchestrator context, and visible state actions. Pause and Stop remain distinct.

### Evidence inspection

Step chat exposes Chat, Received, Handoff and Files with previous/next step navigation. Inspection stays read-only. Native dialogs preview source, rules, utilities and unavailable actions with a visible Close button and focus return.

This artifact loads adjacent `../reference-tokens.css`, `../style.css` and `../app.js`, then its local `version-b.css` and `version-b.js`. Copying this directory alone omits required Version A assets. Content Security Policy blocks connections; provider/service calls, real files/diffs, desktop launches, export/follow-up linking, persistence and live recovery are absent. Refresh resets local changes. Fable remains an unavailable fixture route; choosing eligible Opus changes only the simulated worker, retaining Astra as orchestrator.

Recorded local checks in [check-results.json](check-results.json) passed 19/19 with no browser errors or network requests. Final captures include desktop dark/light, 340px dark mobile, 375px light mobile, 900px light step inspection and the model hold. Independent review resolved the narrow transcript and impossible Fable-primary findings; that verdict covers those fixes and does not approve the whole surface or runtime integration. [review.html](review.html) owns the full state map and runtime limitations.

## Do's and Don'ts

### Do:

- **Do** preserve one composer addressed to the assigned task orchestrator.
- **Do** keep current decisions accessible while switching evidence views.
- **Do** pair status color with readable state text and preserve visible keyboard focus.
- **Do** use the adjacent shared assets and local B overrides together when reviewing this variant.

### Don't:

- **Don't** infer acceptance from worker exit or replace current verification with stale evidence.
- **Don't** enable a worker route without proven availability.
- **Don't** present simulated receipts, files, estimates or utility previews as live runtime results.
- **Don't** treat this local artifact or the two resolved review findings as production approval.
