# Task 8: the design lock (UI for plan 49)

Locked by Fred, 2026-10-20: `design/rework/locked/workflow-autopilot.html` (from the explored mock
`design/rework/explored/49-b-projects-dock.html`; variant A, `49-a-sections.html`, was not taken). Tokens, type and
the cell motif are Console Cells, unchanged. Design only: `web/` is a later task, which reads `actions` (Task 6)
and places what this file shows.

## Decisions

| # | Topic | Taken |
|---|---|---|
| UI-1 | Left list | Needs you pinned on top across projects; then one group per project, the name only (no counts, no level tag). No tags on rows: a run is a filled card, an observed chat a dashed card with its app in the status line (`VS Code · working`). A running row blinks its mark (off with Windows animation effects). |
| UI-2 | Steps in the list | A running run lists its steps under its row (glyph, `01 scout`, model, state); each line opens that step's page; the task row returns to the task. |
| UI-3 | Head, every page | One layout on the task, step and observed pages: eyebrow (project; on a step, `← task title` as the way back), title on one line, one meta line (status pill and labelled facts: Now, Model, Took). The right column is fixed width: the gated / auto switch (step page: ‹ › arrows) above the cost in Doto. No "this task" / "this step" label. |
| UI-4 | Body | One section pattern: label column (name, one muted line) and a hairline. Prompt and brief fold to one line and open in place into a selectable box, about 5 lines tall, scrolling, with a copy icon. The brief's route shows as plain chips (Risky, Deep reasoning, Opus high effort) and its files as a fold list of names only. |
| UI-5 | Plan timeline | One row per step: rail mark, number, kind, model, plain check word (done, running, waits for you, failed, passed), cost. Rows are links (hover, focus, chevron) to the step page. Supervisor actions are muted `◆ Supervisor` lines where they happened, linking to their reason in supervisor.jsonl. |
| UI-6 | Step page | Tabs Chat, Received, Handoff, Files. Chat is a thread: Console's message as a right bubble, the model's turns on the left, tool calls folded into one pill per run, a live "working" turn while running. |
| UI-7 | Needs-you dock | One card docked between the card and the message box, never scrolled away, empty most of the time. A tag, one plain sentence, at most one line of why, its own buttons with the primary orange at the right. Plan: Read or edit the plan / Confirm and auto accept / Confirm. Decision: options as selectable rows, default preselected; Take default and auto accept / Confirm a. Failed twice: See the failure / Accept step result / Retry on a stronger model. Supervisor suggests: Reject / Approve and auto accept / Approve. Held (Fable): Run on opus instead / Confirm Fable. The "and auto accept" button shows only where auto would pass that gate and the task is not already auto (plan 49 section 2, remember auto). |
| UI-8 | Footer | The message box is always open when the state takes words, with a plain hint per mode ("Message the agent while it works...", "Or write your own answer", "Why not, or what to do instead", "Ask for something more: it becomes the next step"). The bar: icon tools left (Hand off, Terminal, Folder, Delete; names in tooltips), usage (context cells, tokens, spend), the state's own actions, primary at the right edge. No ⋯ menu. |
| UI-9 | Departure from section 3 | README section 3 puts Delete, Hand off and Open in terminal behind a menu; Fred took them out as icon buttons. Edit plan moved from the bar onto the plan card's first button. Approve / Confirm sit in the dock card, not the bar. Task 6 `actions` is unchanged: the UI draws `menu` entries as icons and `primary` of the gate states inside the dock card. |

## Not covered

The 400 px compact window (the mock is the 900 px Board size), the folded pill, the Prep page and the Usage page
keep their locked files. Preparing, paused, stopped, stuck and handed states use the same dock card and bar
rules; they were not drawn.
