# Plan: Claude Console (master)

> Context: [BRAINSTORM.md](BRAINSTORM.md) (design, decisions D1-D10), [CLAUDE.md](CLAUDE.md) (rules)

## Goal

Build the companion window in five phases (BRAINSTORM section 12). Each phase is one sub-plan and
ends with working, tested software.

## Sub-plans

| # | Sub-plan | State |
|---|---|---|
| 1 | [plans/01-watch.md](plans/01-watch.md) - hooks, service, tree, gauge, Steps, Needs you, Quiet / Stall?, 2 writers | done 2026-10-10 |
| 2 | [plans/02-run.md](plans/02-run.md) - prompt box, Prep card, Run / Run raw, Chat, Stop, Open in terminal, crash recovery, STOP answers | done 2026-10-10 |
| 3 | [plans/03-levers.md](plans/03-levers.md) - Continue, Verify, Handoff, Escalate + verdict + routing-misses, follow-up hint, Timeline | done 2026-10-10 |
| 4 | [plans/04-polish.md](plans/04-polish.md) - rules-size warning, should-delegate flag, model-mix strip, in-chat handoff Done, move skills to ~/.claude | done 2026-10-10 |
| 5 | Other harnesses - Codex CLI, OpenCode, Command Code | to write |
| 6 | [plans/06-rework.md](plans/06-rework.md) - Visual rework, Console Cells (BRAINSTORM 7.5, `design/rework/locked/console-cells.html`): borderless pill + rail + focus pane, cell motif, estimated cost, activity buckets | written 2026-10-10 |
| 7 | [plans/07-cells-drawer.md](plans/07-cells-drawer.md) - Cells Drawer window (BRAINSTORM 7.5, D12, `design/rework/locked/cells-drawer.html`): list, session page and searchable project picker replace the rail, focus pane and Overview; Chat from transcripts, per-minute Timeline; its live check also closes plan 06 Tasks 7-8 | written 2026-10-10 |
| 8 | [plans/08-cold-handoff.md](plans/08-cold-handoff.md) - cold-cache guard on the levers (second click with the estimated re-read cost) and seeded briefs: Brief a new task / Verify in a new task, built locally with no model call | Tasks 1-4 done 2026-10-11, Task 5 (live check) open |
| 9 | [plans/09-route-trace.md](plans/09-route-trace.md) - Route block on the session page: Prep row (model, turns, cost, or a dim "none"), model and effort per main and agent, escalation time, session model mix, header model chip, step tags where the model differs from main's | written 2026-10-11 |
| 10 | [plans/10-usage.md](plans/10-usage.md) - Usage page (BRAINSTORM D13, `design/rework/locked/usage.html`): cost and tokens per day, week and month from every transcript, calendar and columns of cells, history in usage-days.json | written 2026-10-11 |
| 11 | [plans/11-states.md](plans/11-states.md) - Attention states: `Replied` (own section, 10 min), `Verified` / `Verify failed` from the last turn's verdict, `Empty` chats folded, a reply line under Idle and Replied rows | Tasks 1-2 done 2026-10-11, Task 3 (live check) open |
| 12 | [plans/12-tray.md](plans/12-tray.md) - Tray icon (BRAINSTORM D14): the service in a tray process, the pywebview window as a child process only while open (about 39 MB hidden instead of about 329); icon colour and tooltip from the needs / working counts | Tasks 1-2 done 2026-10-11, Task 3 (Fred's restart and look) open |
| 13 | [plans/13-handoff-next.md](plans/13-handoff-next.md) - Hand off then Start next chat (the new-task box seeded with the skill's note), lever order after Verify from `levers.after_verify` | Task 1 done 2026-10-11, Task 2 (live check) open |
| 14 | [plans/14-logo.md](plans/14-logo.md) - Logo and app icon: a 3 x 3 board of cells with a lit route and an orange signal cell, drawn by `console/icon.py` for the tray states, `assets/app.ico` on the window with its own AppUserModelID; shown name ContextCompanion (temporary, Fred) | Tasks 1-3 done 2026-10-11, Task 4 (Fred's look at the tray) open |
| 15 | [plans/15-attachments.md](plans/15-attachments.md) - Attachments: images, PDF and text files sent inline (stream-json content blocks) with a window-run prompt, Prep job, STOP answer or follow-up; chips with image thumbnails in the Chat for what Fred attached (window stream and transcripts) and what Claude wrote in the folder | Tasks 1-2 done 2026-10-12 (scope c, thumbnails), Task 3 (Fred's live check) open |
| 16 | [plans/16-demand-routing.md](plans/16-demand-routing.md) - Demand routing: Prep rates reasoning and token volume, `console/routing.py` turns them into the route (misses stay a floor); automatic Escalate / de-escalate through `Hub.levers` | Tasks 1-2 done 2026-10-12, live check open |
| 17 | [plans/17-tasks/](plans/17-tasks/README.md) (guided plan, 7 tasks; design in [plans/17-task-folders.md](plans/17-task-folders.md)) - Task folders and step chain: `~/.claude/console/tasks/<id>/` (task.json, steps/NN-<kind>.md handoff notes, chain.jsonl), a code supervisor in the service (`Hub.task_levers`, `Hub.advance`) that checks each handoff, retries once from the last good one and marks stuck; a step-kind rules table (Opus thinks, Haiku reads, Sonnet writes; verify one model up, fix once on the escalated route); every step one `claude -p` with the Agent tool removed; Fable only by Fred's confirm; an effort slider (Auto, or one fixed level for every step) | decisions taken (a) 2026-10-12; plan written, Tasks 1-7 to execute |
| 18 | Model budget: per-model estimated usage over the plan windows (5 h, 7 days) and a linear pace over the billing month on the Usage page, `model_budget` and `warn_at` in config.json, the median cost per model from Fred's own history on the Prep card, budget pressure as an input of plan 17's step router (plan 17 section 4.8) | to write after plan 17's decisions |

## Changes to the design made while planning phase 1

- **Gauge uses token thresholds, not % of the window.** The 5.x models (Opus 5.5, Sonnet 5.5,
  Haiku 5.5, Fable) run with a 1M window by default (code.claude.com/docs/en/model-config), so
  40% / 60% of the window would only warn at 400K / 600K. Defaults: yellow from 150K tokens, red
  from 300K (`gauge_yellow_tokens`, `gauge_red_tokens` in `config.json`). The bar is full at red.
  This replaces BRAINSTORM sections 6 and 13 "context window size per model".
- **Hook time is about 75 ms** per event on this machine (Python start-up), not the 50 ms target.
  It is async, so it never delays a session.
- **STOP questions are shown in phase 1** (display only; answering comes with Continue in phase 2):
  the parse is one regex and the state already exists.
- Phase 1 sessions are only those Claude Code reports through hooks; "Interrupted" needs the
  window's own runs and comes in phase 2.

## Changes to the design made while planning phase 2

- **Stop is an interrupt over stdin, not a signal.** Ctrl+C to a hidden console did nothing; the
  stream-json `control_request` `interrupt` stops the turn cleanly. Runs therefore use
  `--input-format stream-json` and the service keeps their stdin; a run left over from an earlier
  service can only be killed (`taskkill /T`). Closing the window gives stdin EOF: the turn finishes.
- **Prep runs without hooks, skills or MCP** (`--settings {"disableAllHooks": true}`,
  `--disable-slash-commands`, `--strict-mcp-config`, `--tools Read,Grep,Glob`): $0.03 instead of $0.11,
  and Prep never shows as a session.
- **The service picks the session id** (`--session-id`), so the window knows the session before the
  first hook line; source `window` comes from `run_started`, never from the inherited
  `CLAUDE_CODE_ENTRYPOINT` (removed from the child environment with the other session variables).
- **STOP footer added by the service** to every window-run prompt; the global CLAUDE.md line for VS
  Code sessions is an optional Fred step (Claude does not edit it).
- **Answer / Resume only for window runs** in phase 2; Continue for any session stays in phase 3.
- **Allow runs here** (Fred, after tasks 1-6): the window can add a folder to `config.json`
  `"projects"` with one click, only for a folder a Claude Code session already ran in (plan 02 Task 6b).

## Changes to the design made while planning phase 3

- **`haiku` stays an alias.** On CLI 2.1.296 it resolves to `claude-haiku-5-5` (verified); the Haiku
  4.5 of phase 2 came from CLI 2.1.288 (Haiku 5.5 needs 2.1.293+). No full model ids.
- **VS Code / terminal chats are forked, never resumed in place** (Fred): `--resume <id>
  --fork-session --session-id <new>` gives a window copy with the old context; the original chat is
  not touched. Window runs keep resuming their own id.
- **Verify is a button** (Fred) that asks for a `VERDICT: PASS|FAIL` line; the hook reads verdicts
  from `last_assistant_message` on Stop and SubagentStop, so the service writes no `verdict` line.
- **Escalate ladder** (Fred): effort +1 up to high, then the next model at the same effort; once per
  task; `escalated` is a field of `run_started`, not its own event line.
- **routing-misses.md lives in `~/.claude/console/`** (CLAUDE.md data rule), one line per Escalate
  tagged with the project; Prep reads the project's lines. The `route-model` skill keeps its own file
  until phase 4 moves it.
- **Handoff only where the `session-handoff` skill is installed** (Fred): CONTENT MANAGER now,
  everywhere after phase 4.

## Changes to the design made while planning phase 4

- **Rules size from a new hook event** (Fred): `InstructionsLoaded` logs every CLAUDE.md / rules file a
  session loads, with lines and bytes. Warning at 200 lines in one file (docs target) or 16 KB in all;
  a row badge plus the file list in the detail. Fred re-runs `install_hooks.py --write` once.
- **Should delegate** (Fred): 10 or more main-chat Read / Grep / Glob / WebFetch / WebSearch steps in
  one turn give a `delegate?` badge; never a Needs-you state.
- **Model mix** (Fred): sessions and agent runs per model family plus window runs and their cost, in
  the bottom status strip.
- **A handoff inside a chat makes it Done** (Fred): a typed `/session-handoff` (logged as the prompt;
  a typed skill bypasses PreToolUse) or Claude's own `Skill session-handoff` step, then Stop.
- **Skills move through the repo** (Fred): generic `route-model`, `session-handoff` and `verifier`
  live in `dotclaude/`; Fred copies them to `~/.claude` (a protected path for Claude) in that order and
  deletes CONTENT MANAGER's two skill copies; its verifier stays as a project override.
- **route-model writes chat misses to `~/.claude/console/routing-misses.md`** (Fred), in the
  console's format, so Prep reads them; its table is Prep's table (a test checks it).

## Changes to the design made while planning phase 6

- **Estimated cost from the transcripts, read by the service** (Fred): the hook logs `transcript_path`
  on turn lines; `console/usage.py` prices each message once (API list prices in `config.json`
  `"prices"`, fast mode 2x). Window runs stay exact on their session card (their result line). Today's
  spend on the main screen is the Usage calendar's figure for today (list prices, every transcript), so the
  two always agree (Fred, 2026-10-11); the exact / estimated split of the spend row is gone.
- **Spend** (Fred): `daily_budget_usd` 15, $0.50 cells in a growing 30 x 5 grid; the model mix becomes
  each model's share of today's spend (the phase 4 counts and the bottom strip go).
- **Window** (Fred): rail = Needs you + Working (Done in the Overview), the Prep card takes the pane,
  Steps | Timeline | Chat as a seg control, the compose row picks the project, one notes block, the
  form and place remembered in `~/.claude/console/window.json`, a peek card only for new events.
- **Open check closed:** a frameless pywebview window resizes exactly from code on Windows.

## Changes to the design made while planning phase 7

- **Cells Drawer is the target** (Fred, 2026-10-10): `design/rework/locked/cells-drawer.html` (BRAINSTORM D12,
  7.5) replaces the rail, the focus pane and the Overview of plan 06; `console-cells.html` stays the
  reference for tokens and the cell motif. The pill, peek card, states, borderless window and form memory
  stay as plan 06 built them.
- **Chat for VS Code and terminal chats** (Fred): the service reads the last 6 turns (text blocks only)
  from the transcript it already reads for the estimate; window runs keep their stream.
- **Timeline** (Fred): the bar timeline (`Hub.timeline`, `/api/timeline`) goes; the tab shows the activity
  buckets (1-2 / 3-5 / 6-9 / 10+ steps) as one cell per minute, and a click shows that minute's steps from
  `/api/steps`.
- **The Prep card is its own page** (Fred), like the session page, with Back to the list.
- **Notes** (Fred): one muted line under the session head, only when there is a note.
- **Brief open or folded** (Fred): remembered for the window in `~/.claude/console/window.json` (`brief`),
  next to the form, through `/api/draft`.

## Changes to the design made while planning phase 10

- **Usage page** (Fred, 2026-10-11): its own page from a button in the spend breakdown, drawn first as a
  mockup and locked as `design/rework/locked/usage.html` (BRAINSTORM D13). Estimated cost and tokens only;
  projects show for the picked day.
- **Every transcript, not only the shown sessions**: the service reads all of `~/.claude/projects` once at
  start in its own thread (308 files, 1.42 GB, 2.2 s warm on this machine), then each minute only what grew.
- **History outlives the transcripts** (Fred): Claude Code deletes them after 30 days, so the service keeps
  each closed day in `~/.claude/console/usage-days.json`; for a day in both, the larger cost wins.
- **Calendar tones in multiples of the limit** (Fred): under $15, under 3x, under 6x, 6x and more. Real spend
  is $78 a day on average in October, so tones up to the limit would all be the same.
- **Tokens count all four kinds** (Fred), cache reads included (about 97 %); the picked day splits them.

## Changes to the design made while planning phase 12

- **Tray icon, window on demand** (Fred, 2026-10-11, D14): idle RAM is WebView2's, so hiding the window saves
  nothing (208 MB hidden); the window becomes its own process that the tray starts and ends. The tray is Win32
  through ctypes, so the stack stays standard library + pywebview. The page's close button ends the window only;
  Quit is in the tray menu.

## Changes to the design made while planning phase 13

- **Hand off, then Start next chat** (Fred, 2026-10-11): the skill still runs and its end makes the chat
  Done; the session page then offers a new task pre-filled with the skill's last message. Fred runs it;
  nothing starts by itself.
- **After Verify** (Fred, 2026-10-11): PASS gives Hand off then Mark done (the Accept step); FAIL gives
  Escalate then Hand off. `Hub.levers` returns the order (`after_verify`).

## History

- 2026-10-10 - Master plan and sub-plan 01 written. All phase 1 code was run once in a scratch folder
  before being pasted into 01: 37 tests OK, the hook timed on a real transcript (about 75 ms), the
  service smoke-tested with curl (state, static, SSE, foreign Host refused).
- 2026-10-10 - Phase 1 code placed (tasks 0-7, 37 tests OK); Fred ran `install_hooks.py --write`; live: sessions, Steps and the red gauge (this chat at 337.5K) show; hooks also apply to already-open chats. Open: agent-row live check, then Task 8.
- 2026-10-10 - Fred asked for prompting from the window: that is phase 2 (Run); write plans/02-run.md after phase 1 closes.
- 2026-10-10 - Phase 1 done: 37 tests OK; live check passed (an Explore agent row appeared under its session while running, then `✓ Done` with model, steps and tokens; no hook-errors.log). Differed from 01: Fred asked for agent rows to show their state text and a green context bar (`State.gauge(tokens)` now serves sessions and agents; one assertion added, still 37 tests).
- 2026-10-10 - Sub-plan 02 written (zero-decision, final code): verified in a scratch clone (60 tests OK, real Prep through the service, window flows in a browser with a fake claude); the plan re-applied to a fresh clone reproduces that code. Claude could not start a live auto-mode run (its classifier refuses): Task 7 live check is Fred's.
- 2026-10-10 - Phase 2 done: 63 tests OK; live check passed (Prep card, Run with Steps and Chat, Stop, Open in terminal, a run survived closing the window, no error-log lines). Differed from 02: `Allow runs in <name>` button (Task 6b), port 47770, a run that succeeded despite auto-mode denials stays Idle with a note, injected prompt blocks no longer become titles, Open in terminal keeps the run's model and effort. Open: `--model haiku` gives Haiku 4.5 on CLI 2.1.288.
- 2026-10-10 - Sub-plan 03 written (zero-decision, final code): Fred decided fork for VS Code chats, Handoff where the skill is, a Verify button, ladder "effort to high, then model", keep the `haiku` alias (verified Haiku 5.5 on CLI 2.1.296). Verified in a scratch clone: 78 tests OK, tasks replayed in a fresh clone (64, 69, 74, 75, 78), window flows in a browser with the fake claude, fork and `/skill` over stream-json checked with real `claude -p` calls. Task 7 live check is Fred's (Claude cannot start auto-mode runs).
- 2026-10-10 - Phase 3 done: 79 tests OK; live check passed (Verify PASS badge, Continue with the follow-up hint, Escalate sonnet/medium -> sonnet/high with its routing-misses line, which the next Prep read, a fork of this VS Code chat answered from its context and left it untouched, `haiku` ran as claude-haiku-5-5, no error-log lines; Handoff in CONTENT MANAGER not tried). Differed from 03: `STOP: none` was read as a STOP question (fixed in the hook, 1 test); with the skill missing there is no Handoff button, only the off note; a `/session-handoff` typed inside a VS Code chat does not make it Done.
- 2026-10-10 - Sub-plan 04 written (zero-decision, final code): Fred decided the rules limits (200 lines per file or 16 KB in all, via the InstructionsLoaded hook, row badge + detail list), "should delegate" at 10 main-chat reads per turn, the model mix (sessions + agents per model, window runs and cost) in the bottom strip, Done after a handoff inside a chat, the skill move through `dotclaude/` with Fred's copies (handoff, verifier, route-model), chat misses in `~/.claude/console/routing-misses.md`, CONTENT MANAGER keeping its verifier. Verified in a scratch clone: 87 tests OK, tasks replayed in a fresh clone (80, 84, 84, 87), window checked in a browser with the fake claude, InstructionsLoaded fields and the generic skills checked with real `claude -p` calls on 2.1.296. Task 5 (hooks, copies into ~/.claude, live check) is Fred's.
- 2026-10-10 - Phase 4 done: 87 tests OK. Tasks 1-4 placed exactly as written (80, 84, 84, 87); Fred re-installed the hooks, copied the three `dotclaude/` files to `~/.claude` and removed CONTENT MANAGER's two skill copies. Live: `rules 21.0 KB` on a new CONTENT MANAGER chat, `delegate?` after 27 main-chat reads, window Handoff and a typed `/session-handoff` made sessions Done, Verify PASS badge, `/route-model` set the row's route and read the console misses file, no error-log lines. Differed from 04: Verify ignored `~/.claude/agents` and the strip sat below the scrolling page (both fixed, still 87 tests); after the restart Verify ran the `~/.claude` verifier (agent row, PASS); not seen live yet: a route-model miss write.
- 2026-10-10 - Sub-plan 06 written (zero-decision, final code): Fred decided the estimate from transcripts read by the service, list prices, a $15 soft limit with $0.50 cells, activity levels 1-2 / 3-5 / 6-9 / 10+ steps per minute, rail = needs + working, Prep in the pane, a seg control for Steps / Timeline / Chat, a project select in the compose row, one notes block, model shares of spend, a remembered form and place, a peek card for new events only. Verified in a scratch clone: 95 tests OK, the frameless resize and a second start as the pill checked on this machine, the estimate on this project's transcripts; tasks replayed in a fresh clone (88, 91, 92, 93, 95, 95, files equal to the scratch code), the fresh clone checked in a browser at 420 px with the fake claude. Task 7 (the real window on Fred's screen) is Fred's.
- 2026-10-10 - Phase 6 tasks 1-6 placed (95 tests OK); Task 7 (live check) not run yet: it moves to plan 07 Task 5, after the Cells Drawer window replaces the rail.
- 2026-10-10 - Fred locked Cells Drawer (D12) and decided the Chat tab from transcripts, the per-minute Timeline, the Prep page, one muted note line and the brief state in window.json. Sub-plan 07 written (zero-decision, final code): verified in a scratch clone (99 tests OK; each task's new tests fail as written, then pass), the window checked in a browser at 400 and 340 px with the fake claude (every view of the mock, dark, light by hand-set tokens, pill and peek, picker, answer in place, Prep, Run, Stop, empty and offline states, no console errors); tasks replayed in a fresh clone (98, 99, 99, 99, files equal to the scratch code). Tasks 5-6 (the real window, closing plans 06 and 07) are Fred's.
- 2026-10-11 - Fred approved the Usage mockup (D13, `design/rework/locked/usage.html`). Plan 10 placed: `usage.History` reads every transcript per local day, `/api/usage` with 12 weeks and 12 months, history in `usage-days.json`, the Usage page from the spend breakdown; 104 tests OK; checked in headless Edge against the real transcripts at 400 and 340 px. Open: Fred's look in the native window.
- 2026-10-11 - Chat tab (commit ebc9873): turn labels are pills (ink for You, raised for Claude; orange stays "needs you") and Claude replies render Markdown pipe tables as `<table>` through the escape-first `chatHtml` in `web/app.js`; 119 tests OK, checked in headless Edge at 700 and 340 px, not yet in the live window.
- 2026-10-11 - Tray (plan 12, D14): Fred chose A2 of a measured comparison (pywebview hidden, Edge `--app`, Tk). `console/tray.py` and `py -m console --window` placed; 130 tests OK; live on a scratch home: tray process 39 MB private and 0.14 s CPU per minute with the window closed, close from the icon saves the place and frees the 6 WebView2 processes, Quit ends everything. Not committed: `Tray.close` uses the uncommitted pid filter in `window._hwnd`.
- 2026-10-11 - Plan 13 placed: Hand off then Start next chat (`/api/brief?kind=next`, gated by `Hub.levers`), `levers.after_verify` order on the session page; 134 tests OK. Not checked in the live window yet.
- 2026-10-11 - Resize grip: the open window defaults to 400 x 760 (the Chat pane takes the extra height through `.proc` flex); a grip in the page's bottom-right corner calls `WindowApi.resize`, size clamped to 340 x 420 .. 900 x 1600 and kept in `window.json` `"size"` on release; the pill and peek sizes are unchanged. 143 tests OK; dragged live on a scratch home (400 x 760 to 340 x 611, kept after close and reopen). Chat pane filling the height not seen with a real session yet.
- 2026-10-12 - Prep in the background: `POST /api/prep` answers `{job}` at once and `Hub.start_prep` runs `prep.run_prep` in its own thread (card id = job id); the snapshot carries `preps` (running, done with its card, failed with the error), `/api/run` with the card and `/api/prep/drop` take a job off. The window empties the task box on Enter and shows each job on a strip right above the composer (where a failed Prep already sat, cells-drawer.html): Prep with the loading cells, then Ready to run (opens the Prep page; Back and Esc keep the card, Cancel and Edit drop it), or Failed with Try again / Edit / Dismiss. 149 tests OK; checked in headless Edge at 400 px with the fake claude on a scratch home (box empty and usable 0.05 s after Enter, Ready card after the 2 s fake Prep, Run took it off the strip, a failure's Edit put the text back). Not seen in the live window yet; the tray's service needs a restart to serve `preps`.
- 2026-10-12 - Sub-plan 15 written (attachments): stream-json image / document content blocks checked live on CLI 2.1.296 (PNG, base64 PDF, text document, a 5.3 MB PNG); transcript `image` / `document` blocks checked on local transcripts (format not on code.claude.com). Built on a scratch copy of the working tree with the Prep jobs: 157 tests OK, the window driven in headless Edge at 400 and 340 px; both diffs re-applied to a fresh copy equal the scratch files. Not placed: scope (a / b / c) waits for Fred.
- 2026-10-12 - Plan 16 Task 1 placed: Prep's route carries `reasoning` and `volume`; `routing.pick` gives opus/high for high reasoning, haiku/low (sonnet/medium with medium reasoning) for high volume, else Prep's pick, never under the newest miss of the task type; 155 tests OK. Checked live on CLI 2.1.296: each window-run turn is its own `--resume` process, so a route already changes at any turn boundary without a fork; stream-json `set_model` and `apply_flag_settings` also switch a live process between turns. Task 2 (automatic steps: suggest or take) waits for Fred.
- 2026-10-12 - Plan 16 Task 2 placed (Fred chose automatic): `Hub.pull` holds the lever body for clicks and the service alike, behind `Hub.levers`; `Hub.auto_steps` in the hub loop escalates a window run after a FAIL and de-escalates it after a PASS back to its `start_route` (no new turn, the next one runs on it); only verdicts since the service started, never a VS Code or terminal chat. 158 tests OK. Not seen in the live window yet.
- 2026-10-12 - Plan 15 Tasks 1-2 placed (Fred chose scope c, thumbnails if possible): files ride with the new-task box, the Prep job (service memory), the STOP answer and the follow-up (through `Hub.pull`); the page draws a 160 px JPEG thumbnail kept with the prompt; `GET /api/image` reads a pasted image from a transcript line or an image Claude wrote inside the session's folder. 169 tests OK; checked in headless Edge at 400 and 340 px with real PNGs. Not seen in the live window yet; the tray's service needs a restart.
- 2026-10-12 - Sub-plan 17 written as design only (Fred asked for the plan before any code): task folders under `~/.claude/console/tasks/` (the CLAUDE.md data rule; per-project, AppData and Documents rejected), a linear step chain advanced by the service with a handoff check, retry once and stuck, routes per step kind from Fred's Haiku / Sonnet / Opus chart, no subagents (`--disallowedTools Agent`, verified in the CLI reference). BRAINSTORM section 2 conflict: the chain needs a clarification (D16) that a linear chain is not a task graph or a scheduler; locks, daemon and leases are not touched. Fred added 2026-10-12: watch per-model usage over the plan windows so one model is not used up (sub-plan 18, to write), and Fable only on Fred's confirm since print mode bills Fable to credits without asking (docs). Fred's method (2026-10-12): Opus is scarce and paced; Opus thinks, Haiku reads, Sonnet writes. Effort slider on the compose row (Fred, 2026-10-12): Auto, or one fixed level for every step of the task on whatever model, clamped to the model's cap. 16 decisions open in 17 section 8.
- 2026-10-12 - Fred took option (a) on all 16 decisions of plan 17 and asked for the plan only (no code). Guided plan written as `plans/17-tasks/` (README with the contract: task.json shape, chain log, rules table, the eight routing steps, the handoff block, the transition table, hard rules and drift guards; then 01 tasks module, 02 CLI and runs limits, 03 Prep steps, 04 service supervisor and routes, 05 window, 06 Fred's live check, 07 close), each task with files, signatures, test names and ordered TDD steps. Checked live on CLI 2.1.296: haiku, sonnet and opus all accept `--effort xhigh` and `max`, so no per-model cap table, only a guard. The web-lookup kind is named `search` (a `lookup` row would collide with the Prep type table test). Fred added two points the same day: older models (Opus 4.6 / 4.7 / 4.8, Haiku 4.5) as extra rungs of each tier, picked by code only under budget pressure (design 4.10, decision 17; the docs list those ids as still served; whether the plan counts them apart from the newest is an open fact for the live check), and storage (design 4.11, decision 18: the retention table, a 20 KB note cap, a folder-size line on the Usage page with `storage_warn_mb` 500). Then: clear on done (decision 19): a done task keeps task.json, chain.jsonl, prompt.md and its last note; its step streams and other notes are deleted; a Clear lever for any task not running. Then: a brief between steps (decision 20): a Haiku pass with no tools and one turn compacts the raw note plus the previous brief into a rolling brief of at most 400 words for the next step, code-checked with a code fallback, saved as `steps/NN-<kind>.brief.md`; the next step reads the brief only. Fred confirmed 17 to 20 as (a); plan committed, ready to execute from Task 1.
- 2026-10-12 - Plan 17 Task 1 and Task 1b executed, tests first: `console/tasks.py` (rules, `step_route` with the eight routing steps, handoff parse and check, chain transitions on dicts, task files, prune and clear), `console/step_prompt.md`, `console/compact.py` and `compact_prompt.md` (the brief pass), `claude_cli.brief_command`, the fake claude's brief words, the 12 config keys; 169 -> 223 tests OK. Differences from the plan: (1) `new_task` also stores `goal` (prompt.md's text, cut at 6000 characters) in task.json, because `step_prompt(task, step, prev_note, retry_reason)` has no home argument to read prompt.md from; (2) every step dict carries `checked` and `verdict_detail` (0 / empty unless verify or fix), and `tasks.checked_route(task, step)` is a new helper (tier and effort of the checked step) for Task 4; (3) a fix of a step that ran on fable keeps fable (the `fable/max` test row), any other fable that is not a pick becomes opus, in fixed effort too; (4) `clear(keep_last=True)` keeps the last good note and its brief (design 4.12; README 3.9 said note only); (5) `tasks.folder` raises ValueError on an unsafe id (it guards the rmtree); (6) `--max-turns` is missing from `claude --help` 2.1.296 but the CLI accepts it, and one live brief pass (haiku, `--tools ""`, `--max-turns 1`, `--json-schema`) returned a valid brief for $0.001. Open: `tasks.write_brief` is named in 04-service.md but defined in no task; the step prompt allows nothing after END HANDOFF while `levers.VERIFY_TEXT` says to end with a VERDICT line (the live check shows where the model puts it).
- 2026-10-12 - Plan 17 Task 2 placed, tests first: `claude_cli.run_command` takes `disallow`, `tools`, `budget`, `max_turns` (flags after `--verbose`), plus `tier_of` and `known_model`; `runs.start` keeps the limits in the run meta and a resumed turn without limits reuses them; `RunManager.forget`; `state.Session.task` / `.step` from `run_started` and on the snapshot row. 223 -> 228 tests OK (five new tests, as listed in the task file). Nothing differed from the plan; `--max-turns` is hidden from `claude --help` on 2.1.296 but accepted (checked 2026-10-12).
- 2026-10-12 - Plan 17 Task 3 placed, tests first: Prep's `SCHEMA` has an optional `steps` list (`kind` enum = `tasks.PREP_KINDS`, `goal`), `run_prep` puts `card["steps"]` (through `tasks.plan_steps` with `task_max_steps`, verify appended) and `card["demand"]` on the card, `prep_prompt.md` has the kinds table after the demand block (the type table is unchanged) and `steps` in Fields and the output rules, the fake claude has the `CHAIN` word. 228 -> 230 tests OK (two new tests, two extended). Differences from the plan: (1) `tasks.py` and `prep.py` imported each other (`from .prep import new_id` at the top of tasks, `tasks.PREP_KINDS` in prep's `SCHEMA`), which fails on import either way; `tasks.new_task` now imports `new_id` inside the function, nothing else in tasks.py changed; (2) the prompt's output rules say `exactly these 9 keys` (was 8), since `steps` is always written although the schema does not require it.
