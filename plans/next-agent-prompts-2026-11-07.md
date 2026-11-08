# Agent prompts for what is next (2026-11-07)

Written for: task agents (fresh Claude Code or Console sessions) that start with no memory of this chat. Fred pastes
the SHARED RULES block, then one prompt. Each prompt is self-contained apart from the shared rules.

State at `4ebe0e1` (master, clean tree):

- Plan 52 (workflow autopilot) Tasks 1 to 6 are built and committed (`c9b9f00`, `a6035ea`, `20e2c58`, `ce9d64f`,
  `a06147f`, `282feca`). Task 7 (headless checks, Fred's live check, close) is not started. Task 8 (design lock) is done
  as a mock only: `design/rework/locked/workflow-autopilot.html`. `GET /api/task` already serves `actions`
  (`console/server.py` line 4792); `web/app.js` does not read it yet.
- Plan 54 (atomic saves with open metadata readers, the Listary WinError 5 fix) is implemented; the running service has
  not been restarted on it. It has no row in `PLAN.md`.
- Plan 53 (Build: ordered sub-plans run one task at a time) is written, not built. It stacks on plan 52.
- No plan exists yet for: the web build of the locked autopilot UI (plan 52 D9), the skill library (plan 44
  section 14, decided D14 to D18).
- Branch `origin/claude/project-thread-jctz3k` holds Codex task fixes never merged (its "plan 38" collides with the
  UI audit plan 38; 4+ conflicting files).
- Plan 38 (UI audit fixes): Tasks 4 to 7 and 9 open. Plan 27 Task 6 waits on plan 5's live check.

Order: prompt 1 first. Prompts 2, 3, 4 are plan-only, touch disjoint folders, run in parallel. Prompt 5 is code: its own
branch or worktree. Prompt 6 is a reusable review for Fred's app folder. Plan 53 is not built until plan 52's live check
passes and Fred answers its D1 to D8 (D2 first).

Fred only (no agent can do these): restart the tray service for plan 54; Models page "Reset to repo copy" for
`supervisor.md` (plan 52 Task 2b) and `design.md` (Task 3); plan 52's live check on a real prompt in
ARTCOUSTIC-AUDIO-REPORT; the answers to plan 53 D1 to D8 and to each new plan's decisions; every older live check in
the PLAN.md table.

---

## SHARED RULES (paste above every prompt)

You work in `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE` (Windows 11, Git Bash and PowerShell, Python 3.14, pywebview, plain
HTML/CSS/JS, no build step). Before editing anything read `CLAUDE.md`, then `PLAN.md`, then the plan files your prompt
names. Obey `CLAUDE.md` to the letter. The rules that bite most:

1. Standard library only (plus pywebview). No database, no daemon, no build step. Anything on the BRAINSTORM
   "Non-goals" list is out of scope. If a step needs a decision the plan does not make, stop and ask Fred, then record
   the answer in the plan. Do not guess.
2. Never edit `~/.claude/settings.json`, `~/.codex/hooks.json`, `~/.commandcode/settings.json` or the OpenCode plugin.
   Never write outside `~/.claude/console/` at runtime. Tests and checks use a scratch `CC_CONSOLE_HOME` and fake
   runners (`tests/fake_claude.py`). Never call a paid provider. Never touch the running service on port 47770.
3. Tests first, one commit per task. Full suite: `py -m unittest discover -s tests` takes about 10 minutes, so run it
   in the background and read the finished output. Last known good: 1167 tests OK (plan 54). Also run
   `node --check web/app.js` after any web change. Report real counts and failures, never "should pass".
4. Other chats edit `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md` and `web/app.js` in parallel. Make anchored edits, stage
   explicit paths (`git add <path>`, never `git add -A` or `git commit -a`), stage only your own lines, and never stage
   `console/__main__.py` unless your prompt says so. Plan numbers collide between chats: run `ls plans` and read the
   `PLAN.md` table right before you create a plan file, and use the number your prompt assigns only if it is still free.
5. Styling lives in `web/style.css`, tokens first. The visual targets are the files in `design/rework/locked/`; files
   in `design/rework/explored/` and `design/rework/proposed/` are not targets.
6. No emojis and no em-dashes in prose (code, commit types and quoted errors are exempt). Verify CLI flags and hook
   fields against code.claude.com docs before relying on them.
7. In Bash, a `"\n"` inside a heredoc that holds Python becomes a real newline. Edit code with the Edit or Write tool,
   not with heredoc scripts.
8. A plan-writing session stops at the plan. Do not write product code in a prompt that says "plan only".
9. Model use: Opus thinks, Haiku reads, Sonnet writes. Opus is scarce; do not use Fable.
10. Finish by reporting: what changed (paths and commits), what you ran with counts, what you did not do, and the
    questions for Fred. Keep the report under 40 lines.

---

## PROMPT 1: plan 52 Task 7, headless acceptance and close (code and docs; Sonnet)

Goal: finish the part of plan 52 Task 7 that does not need Fred. Read
`plans/52-workflow-autopilot/README.md` (sections 2, 3 and 6) and `plans/52-workflow-autopilot/07-live-check.md` first.

Why: Tasks 1 to 6 landed with unit tests but no end-to-end pass over the real HTTP service and the real page. Plan 53
stacks on this foundation, and Fred runs his live check only after this is green.

Do, in order:

1. Write `tests/live_autopilot_check.py`, in the style of `tests/live_task_chat_check.py` (Playwright with the installed
   Edge, headless, `TaskServerTest` fixture, the fake claude, scratch home, a worker thread ticking
   `hub.poll_once()` and `hub.advance()`). Cover the five headless items of `07-live-check.md`: (1) gated chain scout,
   design with `PLAN-OK`, one plan Confirm, code, verify `VERDICT-PASS`, done, finish summary, Accept, exactly one
   supervisor pass in `supervisor.jsonl`; (2) auto with the fake word `DECIDE-NAME`, a fake clock past
   `decision_timeout_s`, the default taken and logged and written to plan.md Decisions; (3) a crash on step 03 twice,
   the chain retry, then stuck, one sonnet wake, a Retry card with a note, Approve runs attempt 3; (4) a task started
   at suggest and switched to auto at a hold dispatches the standing card with no "Paused" note; (5) 900, 400 and
   340 px, dark and light, reduced motion: no horizontal scroll, no `pageerror`. If the fake claude lacks a crash word,
   add one to `tests/fake_claude.py` and record it.
2. Add two checks the task file lacks: (6) the Models page Supervisor card shows the four words off, suggest, gated,
   auto, with gated the default, at 900, 400 and 340 px (plan 50's headless check was never run and Task 5 changed the
   words); (7) `GET /api/task` `actions` at every state of check 1 (planning, running, plan wait, decision, stuck,
   done, accepted) matches the wire contract in README section 3 and changes nothing on disk (compare task.json bytes
   before and after the GET).
3. Run the check script, then the full suite in the background, then `node --check web/app.js`. Record counts, durations,
   failures, warnings.
4. If a check finds a production bug: write a failing test first, report it, and fix it in its own commit only if the
   fix is small and inside code that Tasks 1 to 6 added. Otherwise stop and report with the failing line. Do not
   redesign anything.
5. Close the docs (anchored edits, your lines only): `PLAN.md` row 52 (Tasks 1 to 6 built 2026-11-07, Task 7 headless
   done, Fred's live check and the UI build open) and a new row 54 for `plans/54-console-persistence.md`, plus History
   lines; the `BRAINSTORM.md` 7.6 paragraph named in `07-live-check.md`; the notes it lists for plans 44, 48, 49, 50 and
   36; and fix plan 52 README section 6, which still says the WinError 5 bug "remains unresolved" (plan 54 fixed it;
   link it). Add a Task 7 results paragraph to section 6.

Do not: change `web/app.js` (the UI build is a separate plan), change any kind file, run Fred's live check, restart the
service, or start plan 53. Commits: one for the check script (and fake_claude word), one for the docs.

Done when: the script passes, the full suite and `node --check` pass with real counts in section 6, the docs are
closed, and the report lists what Fred must do (restart the service, Reset to repo copy on Models for `supervisor.md`
and `design.md`, the live check and the comparison against task 20261020-081005-06c2).

---

## PROMPT 2: plan 55, the web build of the locked autopilot UI (plan only; Opus)

Goal: write the guided plan that builds `design/rework/locked/workflow-autopilot.html` into `web/`. Plan 52 D9 (a)
says this is "a plan of its own after Task 6, reading `actions` only". Write `plans/55-autopilot-ui/` (README plus one
file per task, zero-decision, with final code or exact anchored edits, tests first), in the style of
`plans/48-three-moments.md` and `plans/53-build/`. Plan only: write no product code. If `plans/55-*` already exists,
take the next free number and say so.

Read first: `plans/52-workflow-autopilot/08-design-lock.md` (UI-1 to UI-9), `06-actions-contract.md`, README sections 2,
3 and 6 (the wire contract and the `actions` shape), the locked mock itself (open it in headless Edge at 900 and 400 px
and read its CSS and markup), `web/app.js` (4239 lines: find every place that draws the list, the opened task, the
supervisor card `supCard`, the bar and the more menu, the message box and the decision and finish cards), `web/style.css`,
`tests/test_web.py`, `tests/live_task_chat_check.py`, CLAUDE.md's Board paragraph.

The plan must settle, each as a decision for Fred with a recommended default (stop and ask Fred before you call any of
them closed):

1. The seam: the page reads `GET /api/task` `actions` and nothing else to decide what to show or enable. No gate is
   rebuilt in JS (CLAUDE.md "Plan 52 Task 6"). List every client-side availability test in today's `app.js` that
   `actions` replaces, and delete it in the same task that adds its replacement.
2. What of plans 48, 50 and 51 the new layout replaces (the opened-task layout, `supCard`, the more menu, the list
   grouping, the card after Reject) versus keeps (moments 1 and 2, the message box modes, plan 50's Models card, the
   recovery box). Use the "What plan 52 replaces / keeps" tables in README section 6 as the starting point and check
   them against the code.
3. Plan 38's open tasks 4 to 7 and 9 (Settings out of the picker, 340 px overflow, type and target floor, home pane,
   contrast, clickable looks clickable): which the new layout makes moot, which still apply, and where each lands. Plan 38
   is Fred's earlier decision (D1 to D6); do not re-decide it, only place its leftovers.
4. Task order by user value, each task shippable alone and green: for example list (UI-1, UI-2), head (UI-3), dock card
   (UI-7), footer and bar (UI-8, UI-9), body sections and plan timeline (UI-4, UI-5), step page (UI-6). Justify the
   order. Name for each task the test names, the headless checks (900, 400, 340 px, dark and light, reduced motion, 130
   percent text scaling) and the exact functions in `app.js` it touches.
5. The 400 px compact window, the pill, Prep and Usage keep their locked files (design lock "Not covered"). Say how the
   new Board coexists with them, and what the unshown states (preparing, paused, stopped, stuck, handed) look like by
   reuse of the dock card and bar rules, flagged as new design for Fred to look at.
6. A stop condition: where the plan needs Fred to look at a screenshot before the next task starts.

Constraints: keep it small (CLAUDE.md "Keep it small"); no framework, no bundler; all styling in `style.css`, tokens
first; no emojis or em-dashes in UI copy; the mock's strings are the copy, change none without flagging it. Plan 53 Task
4 draws a build row and page with the same parts: leave a named seam for it and do not draw it.

Deliverables: the plan folder, a `PLAN.md` row (anchored, your line only), the decisions list at the top of the README,
and a one-page summary for Fred. Commit the plan alone.

---

## PROMPT 3: plan 53 refresh against the built plan 52 (plan only; Sonnet)

Goal: bring `plans/53-build/` in line with the code that now exists, and report whether it is ready to build. Plan 53 was
written when plan 52 was built through Task 4 (`ce9d64f`); Tasks 5 and 6 and plan 54 have landed since, and the UI plan
(prompt 2, plan 55) is being written. Plan only; write no product code.

Read first: `plans/53-build/README.md` and its six task files, `plans/52-workflow-autopilot/README.md` section 6 and
`06-actions-contract.md`, `plans/54-console-persistence.md`, `CLAUDE.md`, and the code the plan names (`console/tasks.py`,
`console/server.py` `Hub.advance`, `create_task`, `Hub.actions`, `console/planner.py`, `console/prep.py`, `console/paths.py`).
Memory-style conditions Fred already set: sub-plans must be small (one to three code steps, a done check that is a
command, one folder, a goal file with closed decisions); the first build runs on a throwaway branch at `gated`; build
cap 60 for a first app; D7 (the design step adopts the file) and D3 (drift judged by the planner) are the weakest
decisions and must downgrade cheaply to D7 (b) and D3 (b).

Do:

1. For every code reference in plan 53 (function names, line numbers, field names, route names, config keys, the
   `ce9d64f` baseline), check it against HEAD and correct it. Say what moved.
2. Replace the assumption "Task 5 levels recommended first" with the built facts: the four levels, gated the default,
   the `remember: "auto"` routes, and how a build's own `gated`/`auto` (D1) composes with the task's level without a
   second gate. Check D6 (auto accept) against the built Accept (`POST /api/task/accept`, the finish summary, the
   open-question rule) and the built `actions`.
3. Make `build.json` and every build file write through `paths.write_text_atomic` (plan 54) and keep its locks, and
   say so in Task 1 and in a test.
4. Align Task 4 (window) with the locked design and with plan 55: the build row, build page, dock card kinds, New build
   form. Name the seam, do not draw anything new. If plan 55 does not exist yet, write the seam as a short contract and
   flag it.
5. Walk the failure paths a long unattended build will hit (service restart mid-item, a usage limit at 03:00, a task
   Deleted by Fred, a sub-plan file edited between preview and start, a project folder moved, two builds on one
   project) and confirm each has a stated outcome and a test; add what is missing.
6. Write section 9 "Readiness": a table of the preconditions (plan 52 live check passed, plan 55 or its seam, Fred's D1
   to D8 answers, sub-plan folder lint passed, throwaway branch) with their state today.

Deliverables: edited plan 53 files (anchored, no rewrite of decisions), a short change list at the top of the README, the
`PLAN.md` row 53 state updated (your line only). Do not build. Do not answer D1 to D8 for Fred. Commit the plan alone.

---

## PROMPT 4: plan 56, the skill library (plan only; Sonnet writes, Opus reviews the plan once)

Goal: turn the decided design into a guided plan. `plans/44-supervisor/BRAINSTORM.md` section 14 (the Console's own
skill library) and section 15 (Fred took D14 a, D15 b, D16 a, D17 a, D18 no limit, 2026-10-17) are decided and
unplanned. Write `plans/56-skill-library/` (README plus task files), in the style of `plans/44-supervisor/` and
`plans/52-workflow-autopilot/`. Plan only; if `plans/56-*` is taken, use the next free number.

Read first: that brainstorm sections 14 and 15 and its non-goals, `console/kinds.py` (the `ensure` seeding that
`skills.ensure` must mirror), `console/tasks.py` `step_prompt`, `console/harness/` adapters (`claude_cli.py`, codex,
opencode, commandcode), `dotclaude/console/kinds/`, `console/tuning.py`, the step prompt and `received.md` writers, and
plan 23 README (the handoff contract: the six headings, `tasks.HEADINGS`, which the skills text must not disturb).

The plan must cover and test:

1. `console/skills.py`: seed `dotclaude/console/skills/` into `~/.claude/console/skills/` like kinds, the hand-edited
   `index.json` registry (name to description, kinds, tags, paths, always), load and validate it, fail closed on a bad
   file.
2. Selection by code from kind, tags and paths; the supervisor may add names through the existing check path
   (`supervisor.check`, untrusted JSON); Fred overrides last. No count or size limit (D18).
3. Enforcement (D17 a): chosen skill bodies inlined whole in the step prompt and saved as `skills.md` in the step
   folder; `--disable-slash-commands` on every step run. Verify the flag against code.claude.com docs. State what the
   other harnesses (Codex, OpenCode, Command Code) do, since the flag is Claude's only; do not invent flags.
4. Redaction: skill text passes `redact.mask` wherever it lands in a prompt or file.
5. Where it shows: the Skills tab next to Kinds on the Models page (write through `POST /api/config/models` or a new
   route, and say which; if new, name it in the CLAUDE.md rules paragraph) and the plan parts' `tags`. Mark the UI task
   as dependent on plan 55 and give only the contract, not a design.
6. Tests first for each task, the golden cases for selection (a table of kind/tags/paths to expected names), and a
   migration note: tasks started before the library keep working with no `skills.md`.

Stop and ask Fred before closing any choice the brainstorm does not make (for example: which starter skills ship in
`dotclaude/`, and whether `session-handoff` and `route-model` move in). Deliverables: the plan folder, a `PLAN.md` row,
a decisions list for Fred. Commit the plan alone.

---

## PROMPT 5: port the Codex task fixes from `origin/claude/project-thread-jctz3k` (code; Sonnet; own branch)

Goal: land the unmerged Codex fixes on master without losing either side. Work on a new branch
`claude/port-codex-fixes` from master, in a separate git worktree (`git worktree add`). The old branch has one commit
(`424548f`, 2026-10-16) that touches `console/harness/codex.py`, `console/server.py`, `console/step_prompt.md`,
`console/tasks.py`, `dotclaude/console/kinds/prep.md`, `tests/fake_claude.py`, `tests/test_harness.py`,
`tests/test_kinds.py`, `tests/test_server.py`, `tests/test_tasks.py`, `web/app.js`, `web/style.css`, `PLAN.md`, a task
folder `plan.md` and `troubleshooting/2026-10-16-codex-task-5dff.md`. A trial `git merge-tree` against master conflicts in
at least `PLAN.md`, `console/harness/codex.py`, `console/tasks.py` and `tests/test_tasks.py`.

Read first: the old branch's `plans/38-codex-task-fixes.md` and the troubleshooting note (use `git show
origin/claude/project-thread-jctz3k:<path>`), plan 43 (Codex write check, which also edited `codex.py`), plan 52 Task 3
(DECISION and Plan gap blocks in `tasks.py`/`server.py`), plan 52 Task 6 `actions`.

Do not run `git merge`. Port by hand, decision by decision, tests first:

1. Rename the plan: master's plan 38 is the UI audit. Use the next free number (expected 57; check `ls plans`), keep the
   four decisions of the old plan: Codex discovery that runs the native binary (never the `.cmd` shim), a
   `Status: blocked: <why>` line in the handoff `## Next` that makes the step wait, a nested Codex error keeping its
   message in the Chat, and Prep routing read-only audits to explain.
2. Reconcile decision 2 with plan 52: a blocked step must wait the way a `Plan gap:` or a `DECISION:` block waits, must
   appear in `GET /api/task` `actions`, and must not collide with those blocks or with the plan 52 level gates. Decide
   the smallest consistent behavior and ask Fred if the plan does not settle it.
3. Reconcile decision 1 with plan 43 (`codex.write_block`, owner and sandbox checks) and keep its tests green.
4. Take the `prep.md` kind change as a repo-copy change only; Fred applies it on the Models page with Reset to repo copy.
   The old `web/app.js` and `web/style.css` hunks target code that has since moved: re-derive them against HEAD or
   drop them and say which.
5. Keep the task-folder `plan.md` and the troubleshooting note as history (copy the note, not the 293-line plan.md).

Full suite and `node --check web/app.js` at the end, real counts. Open no PR; report the branch and the commits, and say
that the live Codex turn (the old plan's step 4) is Fred's.

---

## PROMPT 6: sub-plan folder review for a Build (read-only; Sonnet; reusable)

Goal: before Fred points plan 53's Build at a folder of sub-plans, check that folder against the conditions that make a
build run unattended. Replace `<FOLDER>` and `<GOAL FILE>` with the paths Fred gives you. Read-only: edit nothing, run no
code in the folder, call no provider.

Read `plans/53-build/README.md` sections 3 to 5 (D5: which files are items, in what order) and
`plans/53-build/01-build-module.md` (how items are discovered), then the folder.

For each item file report, in one table row: number and title; the code steps it implies (one to three is good); whether
it names a done check that is a single runnable command; the files and folder it touches (one folder is good); decisions
it leaves open (any open decision is a stop); whether it depends on an earlier item's output and says exactly what; and a
rating small, ok, or too big with the reason. Then check the whole: every file is picked up by the D5 pattern (`NN-*.md`
or `NN-*/README.md`, number order) and nothing meant as an item is skipped; the goal file closes every cross-cutting
decision (stack, layout, naming, test command, how to run the app); items do not contradict the goal file or each
other; the first item can run on an empty or throwaway branch; no item asks for network credentials, paid services or
secrets. Finish with: items to split, decisions Fred must close before Start, and a go or no-go for a first `gated`
build with the cap at 60. Keep the report under 60 lines.
