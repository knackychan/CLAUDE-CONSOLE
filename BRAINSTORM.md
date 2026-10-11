# Claude Console - Brainstorm and design

- Date: 2026-10-10
- State: design approved section by section with Fred; plan not written yet
- Origin: Content Manager session (Context Playbook + Model Routing Playbook turned into the
  `route-model`, `session-handoff` skills and the `verifier` agent, installed in that repo on 2026-10-10)
- Working name: Claude Console (folder `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\`, its own git repo)

## 1. Purpose

A small always-on-top companion window that shows how every Claude Code task is handled, in any
project: which session is working on what, its route (harness, model, effort), its subagents, how
full its context is, and what needs Fred. It also starts tasks: a prompt box runs Fred's "prompt
enhancement" step (Prep) on Haiku, shows the enhanced prompt and route for review, then launches
the run.

It applies the two playbooks (source notes in Content Manager `data/notes/context-playbook.md` and
`data/notes/model-routing-playbook.md`):

- Routing: effort first, one tier below the top by default, rules by task type and risk, verify
  then escalate once, log every miss.
- Context: one task = one chat, rules in a short file, one-line decision notes, heavy reading in
  subagents, compact on purpose.

## 2. Non-goals

Lessons from square-orchestrator (`D:\WORK\10 - AI\SQUARE LAB\TOOLS\square-orchestrator`), which
grew too big to finish. This tool does NOT have: a daemon with named pipes, embedded terminals
(ConPTY / xterm), a docking system or layout presets, a task graph, hash-bound manifests, locks or
a scheduler, worktree management, disk telemetry, a VS Code extension, adapter certification,
controller leases, or a practice lab. No database. No model calls except through the harness CLIs.
No cloud, no network calls of its own.

## 3. Decisions (Fred, 2026-10-10)

| # | Question | Decision |
|---|---|---|
| D1 | Where it lives | C: standalone mini window, for every project (not inside Brainamp) |
| D2 | Run or watch | C: both. Global hooks log every session; the window also starts runs |
| D3 | Routing in the prompt box | A, extended: Fred's prompter becomes the Prep step (Haiku scouts, enhances, routes in one pass) |
| D4 | Review the Prep card | A: always review; the card waits for Run |
| D5 | Permissions for window runs | A: `--permission-mode auto --permission-prompts none`; a denial is a red event with Open in terminal |
| D6 | Context Playbook | All five levers. First: gauge, Handoff, one session per Run. Later: rules-size warning, "should delegate" flag |
| D7 | Agent view layout | A Tree as the main view; C Timeline as a tab in the session detail |
| D8 | Folder | `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\`, own git repo |
| D9 | square-orchestrator ideas | Take 1-8 of section 9; leave the rest (section 2) |
| D10 | Visual style | Borrow the square-orchestrator UI (section 7.4) |
| D11 | Visual rework (2026-10-10) | Locked: "Console Cells", `design/rework/locked/console-cells.html` (section 7.5) |
| D12 | Open window layout (2026-10-10) | Locked: "Cells Drawer", `design/rework/locked/cells-drawer.html` (section 7.5): a list instead of the rail, a full-width session page, a searchable project picker. Console Cells stays the reference for tokens and the cell motif |
| D13 | Usage page (2026-10-11) | Locked: `design/rework/locked/usage.html` (section 7.5): estimated cost and tokens per day, week and month from every transcript, a calendar of days and columns of cells over time; history kept in `~/.claude/console/usage-days.json` |

## 4. Architecture

```text
 VS Code session      terminal session      run started by the window
        \                    |                    /
     global hooks in ~/.claude/settings.json (async, always exit 0)
                             |
        1. cc-events   appends one JSON line per event
                             |
              ~/.claude/console/events-YYYY-MM-DD.jsonl
                             |
        2. console service   Python stdlib, 127.0.0.1 only
           reads the log -> sessions / agents / steps -> live push (SSE)
           runs: Prep, Run, Continue, Handoff, Escalate, Stop, Open in terminal
                             |
        3. mini window   pywebview, always on top, about 420 x 640, plain HTML/JS
```

- Stack: Python 3.14 standard library (`http.server`, threads, SSE) + pywebview (already installed
  for Brainamp). Plain HTML/CSS/JS, no build step. Low RAM is a requirement.
- Hook events used: SessionStart, UserPromptSubmit, PreToolUse, SubagentStart, SubagentStop,
  PermissionDenied, Stop, StopFailure, PreCompact, PostCompact, SessionEnd.
- Every hook input carries `session_id`, `cwd`, `transcript_path`, `permission_mode`, `effort`,
  and inside a subagent `agent_id` / `agent_type` (checked in code.claude.com/docs/en/hooks).
- Harness slot: a route is `harness · model · effort`. One adapter per harness builds the run
  command and reads its events. Only Claude Code is built. Codex CLI (`codex exec`), OpenCode
  (`opencode run`) and Command Code (`cmdc`) are later adapters; their flags and output formats are
  not checked yet.

### Claude Code commands (checked against code.claude.com docs and `claude --help`, v2.1.288)

| Action | Command |
|---|---|
| Prep | `claude -p <prep prompt> --model haiku --effort low --allowedTools Read,Grep,Glob --permission-mode dontAsk --output-format json` (+ `--json-schema`, see open checks) |
| Run | `claude -p <enhanced prompt> --model <m> --effort <e> --permission-mode auto --permission-prompts none --output-format stream-json --verbose` |
| Continue / answer STOP | same as Run plus `--resume <session-id>` |
| Handoff | `claude -p "/session-handoff" --resume <session-id>` (`-p` expands `/skill-name`) |
| Resume after a crash | Continue with env `CLAUDE_CODE_RESUME_INTERRUPTED_TURN=1` |
| Open in terminal | new terminal in the project folder running `claude --resume <session-id>` |

Stream facts used: subagent messages carry `parent_tool_use_id` (rebuilds the tree); denials arrive
as `permission_denied` system messages and in the result's `permission_denials`; `api_retry` events
carry attempt / max; the final `result` line carries `session_id` and `total_cost_usd`.

## 5. Data model

No database. Append-only daily log, kept 14 days; the service rebuilds state on startup and skips
any half-written line.

```json
{"ts":"...","event":"PreToolUse","session_id":"...","project":"CONTENT MANAGER","cwd":"...",
 "agent_id":null,"agent_type":null,"permission_mode":"auto","effort":"medium",
 "tool":"Edit","what":"updater.py","tool_use_id":"..."}
```

- `what` is a short summary (file path, or the first 80 characters of a command); prompts keep
  their first 120 characters. Full tool inputs and prompt bodies are never logged. Token-like strings
  are masked (`sk-...`, `ghp_...`, `key=...`).
- `Stop` lines add `context_tokens` = `input_tokens + cache_read_input_tokens +
  cache_creation_input_tokens` of the last assistant line in the transcript (checked on this
  machine's transcripts), and the `Route:` / `STOP:` lines found in `last_assistant_message`.
- `PermissionDenied` lines add the reason. `StopFailure` lines add the error category.
- The service adds its own lines: `prep_done` (route, reason, Prep file), `run_started` (source
  window, pid), `escalated`, `verdict` (PASS / FAIL from the verifier's `VERDICT:` line).

State built from the log:

- **Session** (one task): id, project, cwd, title (Prep Goal, or first 60 characters of the prompt),
  source (vscode / terminal / window, from the transcript `entrypoint`), harness, model, effort,
  route + reason (or "unrouted"), state (section 6), context tokens / % / tone, follow-up count,
  start commit, verdict.
- **Agent** (one subagent run): id, type, model / effort when known, state, current step, steps.
- **Step** (one tool call): tool, `what`, time. Feeds the tree's "doing now" line and the Timeline.

Files under `~/.claude/console/`: `events-*.jsonl`, `preps/<id>.json` (raw prompt, scouted files,
enhanced prompt as edited, route, reason, start `git rev-parse HEAD` + `git status --short`),
`runs/<id>.jsonl` (copy of each window run's stream), `draft.txt` (unsent prompt, saved while
typing), `config.json` (project folders, context window size per model, thresholds).

## 6. States

Each state is a symbol + text + tone, never colour alone (from square-orchestrator's
`statePresentations`).

| State | Symbol | Tone | When |
|---|---|---|---|
| Running | ▶ | info | events within the last 3 min |
| Quiet | … | info | no events for 3 min, process alive or unknown |
| Stall? | ◷ | warning | no events for 10 min and the run's process is alive |
| STOP | ? | warning | last message ends with `STOP: <question>` |
| Blocked | ■ | danger | PermissionDenied since the last prompt |
| Interrupted | ‖ | warning | no Stop / SessionEnd and the window-run process is gone |
| Stale? | △ | warning | VS Code / terminal session, no events for 30 min |
| Failed | × | danger | StopFailure (rate_limit, overloaded, ...) |
| Idle | ○ | info | Stop received, waiting for a follow-up |
| Done | ✓ | success | SessionEnd or Handoff; shows PASS / FAIL when a verdict exists |

"Needs you" group, top of the tree: STOP, Blocked, Stall?, Interrupted, Failed, and any session with
a red gauge. Healthy sessions stay quiet; rows are not reordered on every event.

Context gauge: green below 40%, yellow "handoff soon" from 40%, red "handoff" from 60%.

## 7. The window

### 7.1 Home

Project picker (only folders added in `config.json`), the tree (Needs you / Working / Done today),
the prompt box (Enter = Prep, Ctrl+Enter = Run raw), the status strip (service state, today's runs
and equivalent cost, model mix, "2 writers" warnings).

### 7.2 Prep card

Shows the raw prompt, what Haiku read, the enhanced prompt (Goal / Where / Keep / Done when / Last
decisions from the project's PLAN.md History / open question), and the route with its reason (a
dropdown to change it). It always waits: Run, Run raw, Edit, Cancel.

Prep prompt: Fred's prompter ("You are a prompt formatter ... scout ... enhance the prompt to be the
most easy to understand by another LLM") + the `route-model` route table + the project's
`routing-misses.md` + an instruction to return JSON with goal, where, keep, done_when,
last_decisions, question, route {harness, model, effort, type}, reason.

### 7.3 Session detail

Header: title, route, gauge, follow-ups. Tabs: Steps, Timeline, Prep, Chat (streamed text only for
window runs). Buttons:

- **Continue**: resumes the session with a follow-up (or the answer to a STOP question).
- **Escalate**: only after a FAIL verdict; one step up (effort first, then model), once per task;
  writes the `routing-misses.md` line.
- **Handoff**: runs `/session-handoff`, then marks the session Done. Highlighted when the gauge is
  red or after 2 follow-ups.
- **Open in terminal**, **Stop** (clean interrupt, not a kill).

Run always starts a new session (one task = one chat).

### 7.4 Visual style (from square-orchestrator's UI design and interactive reference)

Segoe UI for text, Cascadia Mono for IDs, routes, numbers and steps; borders instead of cards;
28 px rows; tabular numbers; light / dark from the system; no decorative animation; buttons stay
pending until the service confirms; closing the window never stops a run. Fred, 2026-10-10: the
look is very compact; accepted for now, a visual rework comes later (keep styling in one CSS file
with tokens so it is cheap to redo). Mockup:
`design/brainstorm/window-style-v2.html` (all brainstorm screens are in `design/brainstorm/`).
Replaced by 7.5 once the rework sub-plan is done.

### 7.5 Visual rework: Console Cells (locked by Fred, 2026-10-10)

Locked mockup: `design/rework/locked/cells-drawer.html` (D12, Cells Drawer). The tokens, type and
cell motif come from `design/rework/locked/console-cells.html` (D11), which Cells Drawer builds on. The
explored directions and how they were chosen are in `design/rework/README.md`; the image references are
in `design/references/`.

- Borderless window with two forms. Folded: a 380 x 48 pill with one cell chip per live session
  and today's spend; a new question, denial or failure opens one card under it (answer in place).
  Open: 400 x 640, one column and no rail, three pages:
  - The list: a header with a searchable project picker (a page-drawn popover; Ctrl+P; groups Runs
    allowed / Runs off, Allow runs in place) and the "N need you" chip; today's spend as one row of
    cells with its breakdown one click away; sessions grouped Needs you / Working / Done today, each a
    card in words (state, title, project, route, cost, context) with the answer or the unblock in
    place; the composer with its target project named under the task box.
  - The session page (Back, ‹ › and Up / Down between sessions): head, the ask or denial, one muted
    note line, the brief (path, then spent / $ per min / context / time / steps; click or Space opens
    context, agent lanes and activity), the process tabs Steps / Agents / Timeline (one cell per minute,
    click a minute for its steps) / Chat (the last turns in words, also for VS Code and terminal
    chats), and the levers bar.
  - The Prep page, with Back to the list.
  - The Usage page (D13, `design/rework/locked/usage.html`), from a button in the spend breakdown, with Back
    to the list: the month's estimated total, today / this week / average / days over the limit, a calendar
    (one cell per day, four tones in multiples of `daily_budget_usd`, today ringed in orange), the picked day
    (tokens in, out, cache write, cache read; projects; model shares), Days / Weeks / Months as columns of cells
    in $ or tokens (tokens count cache reads), the limit line on Days in $.
  The window is a CSS container: no horizontal scroll at 400 or 340 px.
- Motif: every quantity is counted in cells. Context: 30 cells of 10K (two rows of 15; the second
  row is the hand-off zone). Spend: cells of $0.50, solid = exact, hatched = estimated, orange
  outline at 80 % of a soft daily limit. Activity: one cell per minute, four intensity steps.
  Agents: one cell per 2 steps.
- Colour: monochrome off-white on near-black (dark first, light theme kept working); orange only
  for "needs you", red and green only for state. State is never colour alone (glyph + word).
- Type: Segoe UI for titles and text, Cascadia Mono for figures, Doto (dot matrix, bundled as a
  local woff2, OFL) for the one focal figure per screen.
- Dials (anti-slop Design Read): ENERGY 2 / RHYTHM 2 / MOTION 1; the only motion is one blinking
  cell on the working agent, off for reduced-motion.
- Needs from the service: estimated cost per session and agent (transcript usage x a price table
  in `config.json`), per-minute activity buckets, `daily_budget_usd`. Open check: resizing a
  frameless pywebview window from code on Windows (pill to open window).

## 8. Error handling

- **Crash / shutdown during a run**: transcripts are written line by line, edits stay on disk, only
  the current turn is lost. On restart, sessions without Stop / SessionEnd whose process is gone
  become Interrupted with Resume (adds "check `git diff` first, then continue toward: <Done when>"),
  Open in terminal, Close. The Prep file's start commit gives "changed since start: N files". The
  tool never reverts anything.
- **Window closed / service crash**: runs start detached and keep going; `runs/<id>.jsonl` and the
  hooks keep recording; a restarted service rebuilds the same state.
- **API errors / limits**: `api_retry` shows "retrying n/m"; StopFailure shows Failed with Resume.
- **Sleep / hibernate**: processes pause; nothing to do.
- **Hook script**: never raises, always exits 0, runs async, so it cannot slow or break a session.

## 9. Ideas taken from square-orchestrator

1. Harness slot in the route (`harness · model · effort`); Claude Code only for now.
2. "Needs you" attention group on top; quiet healthy rows.
3. Quiet (3 min) and Stall? (10 min, process alive).
4. `STOP: <question>` convention, answered from the window.
5. Route reason + start commit recorded per run.
6. "2 writers" warning when two sessions edit files in the same repo at once.
7. Context pressure shown apart from cost; a model-mix line in the status strip.
8. UI rules: state never by colour alone, closing a view never stops a process, pending until
   acknowledged, monospace for data.

## 10. Security

- The service binds 127.0.0.1 only, rejects foreign `Host` headers, and requires a custom header
  on every POST (same guard as Brainamp's `server/guard.py`): it can start processes, so a web page
  must not be able to reach it.
- Runs only in folders listed in `config.json` (`claude -p` runs a project's hooks even in a folder
  never trusted).
- Prep is read-only (`--allowedTools Read,Grep,Glob --permission-mode dontAsk`); scouted text is
  data; every card is reviewed before it runs (D4).
- Commands are built as argument lists, never shell strings.
- Logs hold summaries only, masked, local only.

## 11. Testing

- Python `unittest`: log parsing (fixtures with a half-written line), state builder (tree,
  Needs you, Quiet / Stall? / Interrupted / Stale?, gauge thresholds), `Route:` / `STOP:` /
  `VERDICT:` parsing, masking, the localhost guard, command building per route.
- Hook script with recorded hook inputs; target under 50 ms per event.
- One opt-in end-to-end test (tiny Haiku prompt in a temp folder; uses the subscription).
- A manual check list for the window (light / dark, 420 px, keyboard).

## 12. Phases

1. **Watch**: hooks + service + tree + gauge + Steps; Needs you, Quiet / Stall?, 2 writers.
   Already useful for VS Code sessions.
2. **Run**: prompt box, Prep card, Run / Run raw, Chat, Stop, Open in terminal, crash recovery,
   STOP questions (add the `STOP: <question>` line to `route-model` and the CLAUDE.md rules),
   route reason + start commit.
3. **Levers**: Continue, Handoff, Escalate + verdict + routing-misses, follow-up hint, Timeline.
4. **Polish**: rules-size warning, "should delegate" flag, model-mix strip, move `route-model`,
   `session-handoff` and `verifier` from Content Manager to `~/.claude/`; later a Jarvis widget link.
5. **Other harnesses**: Codex CLI, OpenCode, Command Code adapters, after checking their flags.

## 13. Open checks for the plan

- Exact input fields of SubagentStart / SubagentStop / PermissionDenied / StopFailure.
- `--json-schema` together with tool use in Prep (else: parse a fenced JSON block).
- Context window size per model (transcripts have no size field; keep a table in `config.json`).
- Clean interrupt of a detached `claude -p` on Windows (SIGINT equivalent).
- Which terminal "Open in terminal" uses (Windows Terminal `wt` if present, else `cmd /c start`).
- Whether the hook entries go in `~/.claude/settings.json` by hand (Fred pastes them; Claude edits
  to its own settings are blocked by the permission check).

## History

- 2026-10-10 - Brainstorm with Fred in the Content Manager session; D1-D10 decided; design
  sections 1-4 approved; visual companion mockups copied to `design/`.
- 2026-10-10 - Fred reviewed the spec: accepted; visual density to be reworked later.
- 2026-10-10 - Visual rework explored (A Pill and Drawer, B Triage Board, C Rail and Focus, C + A
  Rings and Pill, then Console Cells from Fred's references, refined with the anti-slop filter).
  Fred locked Console Cells (D11, section 7.5); brainstorm screens moved to `design/brainstorm/`.
