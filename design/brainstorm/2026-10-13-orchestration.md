# Brainstorm: pushing Claude Console into orchestration (2026-10-13)

- Asked by Fred, thread "Brainstorm: orchestration, routing, handoff"
- Read: `BRAINSTORM.md`, `PLAN.md` (plans 16, 17, 19, 22), `console/tasks.py`, `routing.py`, `compact.py`, `brief.py`, `claude_cli.py`, `runs.py`, `server.Hub.advance`; the Square Orchestrator fork of 2026-08-08 (technical architecture, sliced plan, combined plan, UI design)
- State: brainstorm only, no code changed. Fred decided on 2026-10-13 (section 11); the sections below carry his changes in place.

## 0. Short answer

Keep the scripted chain. Do not build a persistent orchestrator agent. What Fred wants (per-step models, several CLIs, cooldown between providers, a context view with a clean handoff) fits the chain that plans 17, 19 and 22 already built, because every step is a fresh `claude -p` with a 400-word brief in and a HANDOFF block out. The chain is the integration point: a step does not care which CLI wrote the note before it.

The four things to add, in this order:

1. **Harness adapters** (PLAN sub-plan 5, "to write"): Codex first, then OpenCode, then Command Code once its flags are checked. One adapter = build the command, read the final message and the usage, stop.
2. **Rungs across harnesses + cooldown** (sub-plan 18 widened): the `ladder` in config.json stops being "Claude versions per tier" and becomes "any (harness, model) rung per tier", with a per-rung usage window, a cooldown rule and a peak-hours table. `Hub.budget` already feeds `tasks.step_route`; it just returns `{}` today.
3. **A bounded replan step**, so the chain gets the one thing an orchestrator agent has that it lacks, for the price of one brief pass.
4. **The Board**: an expanded window mode (the window already resizes to 900 px) that shows task, steps, notes and briefs as connected cells. Locked design tokens, a mockup before code, as with D11 to D13.

Square Orchestrator is not where to go back to. Its own architecture reached the same conclusion as the Console: "No role remains alive simply to supervise another role" and the Task Manager "waits through durable state, not a live model monitor". What is worth taking from it is listed in section 6; it is small.

## 1. Where the Console stands (facts, not opinions)

| Thing Fred asked for | Already in the Console | Where |
|---|---|---|
| Steps on different models | Yes: kind -> (model, effort, tools) table; verify one model above the step it checks; fix one step up, once | `tasks.RULES`, `tasks.step_route`, `verify_route` |
| Fresh context per step | Yes: each step is its own `claude -p` with `--disallowedTools Agent`, `--max-budget-usd 3`, Opus capped at 12 turns | `claude_cli.run_command`, config `task_step_budget_usd`, `opus_max_turns` |
| Handoff text between steps | Yes: HANDOFF block (Findings / Files touched / Open questions / Next), checked by code; a Haiku brief of at most 400 words, never longer than what it compacts, open questions kept, code fallback | `tasks.check_handoff`, `compact.run_brief`, `compact.check` |
| Context gauge | Yes for Claude sessions: tokens from the transcript, yellow 150K, red 300K, 30 cells of 10K | `State.gauge`, config `gauge_*_tokens` |
| Handoff of a long session | Yes: `/session-handoff` lever, cold-cache guard, "Hand off then Start next chat" seeded with the note; `brief.build` makes a brief with no model call | `levers.py`, `brief.py`, plans 08 and 13 |
| Routing memory | Yes: misses are a floor for 14 days, lessons file, rules review | `routing.floor`, `routing.fresh`, `review.py` |
| Model budget / pace | Designed, not built: `Hub.budget()` returns `{}`; the ladder of older rungs exists | plan 18 "to write" |
| Other CLIs | Designed as a slot (`harness · model · effort`), nothing built | BRAINSTORM 4, PLAN sub-plan 5 |
| Expanded view | No: one 340 to 900 px column, the Task page is a list of step cells | plan 17 Task 5 |

So the current app IS the "scripted step by step" of Fred's last bullet, and the supervisor costs zero tokens: `Hub.advance` is Python, polled once a second.

## 2. Token efficiency: scripted chain vs orchestrator agent vs direct CLI

Three ways to run a 6-step task (scout, design, code, test, verify, fix):

**A. Scripted chain (today).** A code supervisor starts one CLI process per step. Model tokens spent on coordination: Prep ($0.03 measured) plus one brief pass per step ($0.001 to $0.009 measured, Haiku, no tools). About $0.06 of overhead for the whole task. Each step's context is: harness system prompt (fixed, about 15 to 25K for Claude Code, cached when the previous call on the same model was under 5 minutes ago) + step prompt + task goal + one brief (about 550 tokens). The context of step 6 is the same size as the context of step 1.

**B. Persistent orchestrator agent.** A Claude (or Codex) session that calls the other CLIs from its Bash tool and reads their output. Every tool result lands in its context and stays there. With two tool calls per step (start, read the result) that is 12 turns; its context grows from about 20K to 20K + 12 x 3K = 56K; the input tokens billed over the task are roughly 12 x 38K = 450K. If every turn hits the prompt cache (steps shorter than 5 minutes) that is about $0.10 on Sonnet; when steps take longer the cache is cold and it is about $0.90 on Sonnet, $1.80 on Opus, plus its own reasoning output. So the overhead is 2x to 30x the chain's, but still small next to the workers ($2 to $10 per Opus task in Fred's data).

The real costs of B are not tokens:

- Its context is exactly the drift Fred wants to avoid: it accumulates every step's output, so by step 6 it reasons over the mistakes of step 2. A chain step only ever sees the checked brief.
- It must stay alive and be smart enough to orchestrate, so it is a Sonnet or Opus session held open for the length of the task, against the Opus pace Fred wants to protect.
- Its decisions are not reproducible or auditable; the chain's are one line each in `chain.jsonl` with the route notes.
- It is one more thing that can stall, ask a question, or hit a limit in the middle.

What B has that A lacks: it can change the plan when a step reveals the plan was wrong. Section 4 adds that to A for the price of one brief pass.

**C. Direct CLI calls, no Prep, no brief.** That is Run raw. Cheapest per call. Either the work stays in one session (context grows, drift, the handoff is manual) or Fred writes the handoffs himself. Fine for one-step tasks; it is what the plain Run is for.

**Subagents** (the Agent tool inside one session) are a fourth way the Console already left: every subagent result returns into the parent context, which is B with extra steps.

Verdict: A, with a bounded replan. The chain is already the most token-efficient shape available, and its remaining inefficiency is the fixed harness prompt per step, which no orchestrator removes (an orchestrator pays it too, once per worker, plus its own).

**D-1** Keep the scripted chain as the only way tasks run; no orchestrator agent, no subagents in steps. (Recommended: yes.)

## 3. Several CLIs, one chain: the adapter slot

The route was always `harness · model · effort` (BRAINSTORM 4). The adapter contract that the chain needs is small, because the chain only consumes a final message and, when available, usage:

Flags checked on Fred's machine on 2026-10-13 from the pasted `--help` output: `codex-cli 0.162.1` (`codex exec --help`), `opencode run --help` (version not printed; `opencode --version` to add to the plan's facts) and Command Code v1.81.0 (`cmdc --help`; the help text calls the command `cmd`, Fred's shell runs it as `cmdc`: the adapter probes both names; it updated itself from 1.26.0 to 1.81.0 during the `--help` call, so every step passes `--no-auto-update` and the probe records the version at each service start).

| Adapter must | Claude Code (built) | Codex CLI 0.162.1 (checked) | OpenCode (checked) | Command Code 1.81.0 (checked) |
|---|---|---|---|---|
| Run one prompt, non-interactive, in a folder | `claude -p`, prompt on stdin as stream-json | `codex exec -` with the prompt on stdin (a prompt argument plus piped stdin appends stdin as a `<stdin>` block); `-C <dir>` / `--cd`; `--skip-git-repo-check` for a folder that is not a repo | `opencode run` with the message as arguments (no stdin flag, no `--dir` in this version: the service's cwd is the folder); `--file` attaches a file | `cmdc -p "<prompt>"` (the query is an argument; whether `-p` with no query reads stdin is for the live run); `--skip-onboarding` for automated runs; `--no-skills`; cwd is the folder |
| Pick the model | `--model`, `--effort` | `-m <model>`; reasoning effort through `-c model_reasoning_effort="high"` (the `-c key=value` override is checked; the key name comes from the Codex config docs) | `-m provider/model#variant` (the variant is the provider's reasoning level, inside the model string) | `-m <model>`, `--effort low|medium|high` ("depends on the model"); `--list-models` gives the rung names for the settings block |
| Allow edits without prompts | `--permission-mode auto --permission-prompts none` | `-s workspace-write` (edits in the folder, no prompts) ; `--approve-for-me` routes approvals through automatic review; `--add-dir` for a second writable folder | `--auto` | `--permission-mode accept-edits` (edits accepted, commands still prompt: check live; 1.26 called it `auto-accept`) or `--yolo` (bypass all); `-t` trusts the project; `--add-dir` |
| Restrict a read-only step | `--tools Read,Grep,Glob` | `-s read-only` (the default sandbox) | no tool flag: an `--agent` with a read-only permission set in the OpenCode config, which the adapter ships as `console-read` | `--permission-mode plan` is read-only with no side effects; headless runs withhold some tools by default (`--tools-enable` turns them on), to list at the live run |
| Give back the final message | stream-json `result` line | `--json` (JSONL events on stdout; `item.completed` with item type `agent_message` per the docs) and `-o <file>` which writes the last message to a file: the adapter reads the file, the stream is kept for the Steps tab | `--format json` raw events; the fields are not documented: the plan records one live run's events as a fact and the adapter parses the last assistant text from them | `--output-format json`: NDJSON event stream plus a final result line (the shape closest to Claude Code's stream-json; fields recorded at the live run) |
| Give back usage | `result.total_cost_usd`, transcript usage | `turn.completed` carries `usage` (input, cached input, output, reasoning) per the docs; checked at the live run | unknown until the live run; else "cost unknown" (D-3) | in the final result line if anywhere; `/usage` shows the subscription's usage: a `cost unknown` cell until checked |
| Turn or spend cap | `--max-turns`, `--max-budget-usd` | none on the command line: the console's wall-clock timeout per step (`step_timeout_s`, new) and the HANDOFF check are the caps | none: same | `--max-turns <n>` (default 100, exit code 8 on the cap: the adapter maps exit 8 to `cap_reason`); no spend cap |
| Stop cleanly | stream-json `interrupt` on stdin | no interrupt: `taskkill /T` of the step's process tree (its session file stays, `codex exec resume <id>` can pick it up) | same, `--session <id>` to pick it up | same; `--session <id>` or `-r <id>` picks it up |
| Resume for a STOP answer | `--resume <id>` | `codex exec resume <SESSION_ID>`; `codex exec fork <id>` for a copy | `--session <id>`, `--fork` | `-r <id>` / `--session <id or path>`; `--fork-session` for a copy, like Claude Code's |
| Keep it out of the console's own logs | `--settings {"disableAllHooks": true}` for Prep | `--ephemeral` writes no session file (not for steps that may need a resume) | `--standalone` runs a private server instead of OpenCode's background service, so a step does not depend on a service the console did not start | `--no-session` keeps nothing on disk (not for steps that may need a resume); `--no-auto-update` so a step never waits on an update |
| Structured output (not used: the HANDOFF block is text for every harness) | `--json-schema` | `--output-schema <file>` | none | none |

Command Code's print mode is the closest to Claude Code's (`-p`, `--max-turns`, `--output-format json`, `--effort`, `--fork-session`), so its adapter is the smallest of the three. Its account is a subscription with a very low usage allowance (Fred, 2026-10-13; `/extra` buys more at API cost), so it is for cheap `read` rungs only, DeepSeek Flash for example, with a small daily allowance in the fills (section 4) and a low `--max-turns`. Per CLAUDE.md the docs-only or unchecked cells (Codex `model_reasoning_effort`, the JSON event shapes of all three, Command Code's stdin and withheld tools) become facts at plan 5's first live run of each adapter, as plan 17 did with `--max-turns`.

### 3.1 Which CLIs are on: a setting per harness (Fred, 2026-10-13)

The console must work for someone with Claude Code only, Codex only, or any mix, so no adapter is assumed:

- `config.json` gets `harnesses`: `{"claude": {"on": true, "exe": ""}, "codex": {"on": false, "exe": ""}, "opencode": {"on": false, "exe": ""}, "cmd": {"on": false, "exe": ""}}`. `exe` empty means found on PATH (`shutil.which`, the real executable as `claude_cli.find_exe` does for the npm shim); a harness that is on but not found shows an off note (`codex: not found on PATH`), as a missing `claude.exe` does today.
- At start the service probes each harness that is on with `--version` once (no model call) and keeps the version string for the Steps tab and the plan's facts.
- `step_route` skips every rung whose harness is off or not found; a tier with no rung left falls back to Claude's rung of that tier, with a note. The Prep card's rung selects list only rungs of harnesses that are on.
- In the window: a Harnesses block in the settings popover (next to the project picker's Runs allowed list): one row per harness with its state (on / off / not found), its version, and a switch, written to config.json like Allow runs is. Claude Code cannot be switched off while it is the Prep and brief harness.
- Prep and the brief pass stay on Claude's Haiku for now (the schema output is checked there); a later plan may let Codex's `--output-schema` carry them.

**D-8** A per-harness on / off and path in config.json with a switch in the window; rungs of a harness that is off never route. **Fred, 2026-10-13: yes (asked for it).**

Design points:

- **An adapter is a module** `console/harness/<name>.py` with four functions: `run_command(model, effort, cwd, tools, budget, max_turns)`, `final_message(stream)`, `usage(stream)`, `stop(proc)`. `claude_cli.py` becomes the first one with no behaviour change. The chain code (`tasks.py`, `Hub.advance`) does not change: it reads a final message and parses the HANDOFF block, which any model can write.
- **Steps on a non-Claude harness get fewer levers**: no `--resume` for a STOP answer unless the adapter has it (Codex and OpenCode do), no transcript so the gauge is the adapter's usage or an estimate (characters / 4, shown hatched like an estimated spend cell), no hook events so the Steps tab shows only what the adapter's JSON gives.
- **The step prompt is already harness-neutral**: the HANDOFF rules, the STOP footer, "the Agent tool is not available" become "do your own reading". Codex has `--output-schema` which could enforce the HANDOFF shape as JSON; keep the text block for every harness instead, so one parser serves all.
- **Verify on the think tier, across harnesses** (Fred, 2026-10-14; was one tier up): a step written by `opencode · deepseek` or `claude · sonnet` is checked by a think rung, `claude · opus` or `codex · gpt-6-astra`, preferring the other family. The tier order comes from the ladder (section 4), not from a model name list, so `claude_cli.MODELS` ordering stops being the ranking.
- **Cost**: the console prices Claude transcripts at list prices. For other harnesses, usage x a price row in `config.json` `prices` when the adapter reports usage, else an estimate. The Usage page shows them as rungs in the model mix.

**D-2** Order of adapters: Codex, then OpenCode, then Command Code after its flags and models are checked. **Fred, 2026-10-13: yes. OpenCode and Command Code run cheap-tier rungs only** (their subscriptions allow less than Claude's and Codex's): their rungs may appear in the `read` tier and nowhere else, and a pick of one of them on the Prep card is refused above `read` with a note. Only Claude and Codex carry `write` and `think` rungs. **Fred, 2026-10-14: they may take write steps too** (well-designed code can be written by a cheap model such as haiku, DeepSeek or Luna): their cheap rungs also sit in the `write` tier, after Claude's and Codex's; never `think`, `verify` or `fix`. Verify always runs on the think tier, so their code is checked by opus or gpt-6-astra.

**D-3** An adapter's unknowns are shown as unknown, not as zero (Square's "no false zero"): a step with no usage shows "cost unknown" and no gauge. (Recommended.)

## 4. Per-step routing with cooldown and peak hours

Today a tier is a list of Claude rungs:

```json
"ladder": {"opus": ["opus", "claude-opus-4-8", ...], "sonnet": [...], "haiku": [...]}
```

Proposal: the three tiers are named by their job, not by a Claude model, and each holds rungs on any harness, cheapest and preferred first:

```json
"tiers": {
  "think": ["claude:opus/high", "codex:gpt-6-astra/high", "claude:claude-opus-4-8/high"],
  "write": ["claude:sonnet/medium", "codex:gpt-6.1-sol/medium", "codex:gpt-6-sol/medium", "opencode:opencode-go/deepseek-v4.1-flash/-", "cmd:deepseek/deepseek-v4.1-flash/-"],
  "read":  ["claude:haiku/low", "opencode:opencode-go/deepseek-v4.1-flash/-", "cmd:deepseek/deepseek-v4.1-flash/-", "codex:gpt-6-luna/low"]
}
```

The `RULES` table maps kind -> tier (design -> think; code, document, explain, debug -> write; scout, search, draft, edit, test -> read). Fred's pick on the Prep card stays a pick of one rung. Verify = the think tier, always (Fred, 2026-10-14: verify is important and runs on a top model): the spread picks between its rungs, preferring another family than the writer when one is on (Codex's code checked by Claude, Claude's by Codex), effort high; `verify_tier` in config.json (default `think`) is the floor the Models page shows. Nothing else in `step_route` changes: rule, pick, demand, floor, hint, cap, budget, fixed effort, in that order, each one a note.

Model names above are placeholders: the plan lists the exact ids each installed CLI accepts.

**Usage fill per model, balanced** (Fred, 2026-10-13: a global usage that fills up through the day, the week and the month, so the overused model shows against the others and the route balances; no cooldown timers). This is the sixth input of `step_route`, through `Hub.budget()` which today returns `{}`:

- Per model (the model, not the harness: Opus through two CLIs is one fill), three fills: today, this week, this month, as tokens and list-price cost, from the usage the console already prices (Claude transcripts) or the adapter reports. Kept in `usage-days.json` next to the daily history, nothing new on disk.
- Each fill is a share of that model's allowance in config.json, `allowance`: `{"opus": {"day_usd": 10, "week_usd": 50, "month_usd": 150}, ...}`, with a linear pace inside the window (on day 10 of 30 the month allowance is a third full). A fill over its pace is the warning (orange outline, `opus 84 % of pace`), as plan 18 designed.
- Balancing, a spread from the first step (Fred, 2026-10-14: never fill one model to 80 % before moving on, so no model ends up unusable for the rest of the week or month): within the tier Prep's judgment chose, `step_route` takes the rung whose model has the lowest share of pace (its fill over the linear pace of the window that binds, day, week or month), whatever the fills are. A small hysteresis lets the same model run two or three times in a row: the previous step's rung is kept unless another rung of the tier is lower by `balance_margin` (default 0.1, ten points of pace), the warm-cache bonus counting in its favour. `warn_at` (0.8) no longer moves a step; it only marks a model as over pace on the Usage page and holds a `verify` whose rung is over it. The spread mixes only rungs whose model ranks at the tier (a model's rank is its Claude alias, or the tier its harness maps it to in config.json: `gpt-6-astra: opus`); a stronger model placed in a lower tier (opus in `write`) runs only when Prep judges the step hard (`demand.reasoning == "high"`), and verify runs on the think tier whatever ran (Fred, 2026-10-14). This replaces plan 17's budget step 7 (one model down at a higher effort) once plan 18 fills `Hub.budget()`. The note says why: `balance: opus 84 % -> codex:gpt-6-astra 31 %`. A tier with every rung over pace takes the least full and says so; `verify` never goes below the step it checks and holds for Fred as today.
- The window shows the fills as columns of cells per model on the Usage page and the list header (the spend row's cells, one column per model, three rows day / week / month), so the "which one am I overusing" question is read at a glance, not computed.
- `peak_hours` stays optional: per provider, local hours when its rungs count as fuller by a fixed step (`"anthropic": {"hours": "14-19", "add": 0.2}`), a note again. Off until the FAIL-rate view below gives a reason.

On the belief that heavy use of one model degrades it: the model-config docs say rate limits never switch the model and say nothing about quantization (plan 17 checked this). Square called the same idea "an operational heuristic, not a scientific claim". The Console should do the same and also give Fred evidence: the misses and verdicts already carry the route, so the Usage page can show **verify FAIL rate per rung per hour of day** over the last 30 days. If afternoons on one rung fail more, the peak-hours table has its numbers; if not, the cooldown can be relaxed. Cheap to add once the ledger exists; it is a count over lines the console already writes.

**D-4** Tiers think / write / read with rungs on any harness, usage fills per model balanced in `step_route`, the FAIL-rate-by-hour view as the evidence. **Fred, 2026-10-13: yes, as fills (day / week / month per model) and balancing, not cooldown timers.** The alternative, Square's full exposure ledger with normalised exposure units and a ranking of role fit x certification x quality history, is more than this needs and was one of the parts that made it too heavy.

## 5. The context view and the handoff

Inside a task the context problem is mostly solved by construction: each step starts fresh with a brief under 400 words, so the gauge of a step session rarely leaves the first row of cells. What is missing is the view and two mechanisms.

**The context view per task** (Task page, and the Board of section 7):

- One row per step: the brief it read (words, as cells of 50 words), the context it reached (tokens, the existing 10K cells), the note it wrote (words). A step that reads a small brief and ends at 200K is a step that read too much on its own: the "delegate?" badge logic applied per step (`delegate_after_reads`), shown as a hint "scout first".
- The chain of briefs as the task's memory: Findings and Files touched carried forward, Open questions as a running list with the step that opened and the step that closed each one (the brief already keeps them; the view shows them).
- "When to hand off" for a step is "never": a step that hits the turn cap, the budget cap or the red gauge ends, the service retries once from the last good note, and the chain goes on. That is the handoff. The gauge thresholds per harness come from config (`gauge_*_tokens` today, keyed by harness when the adapter reports tokens).

**Mechanism 1: automatic handoff for a long single session** (plain Runs and VS Code chats, where the gauge still climbs). Today Handoff is a lever Fred clicks. Through `Hub.auto_steps`, which already escalates and de-escalates window runs between turns, add: when a window run's turn ends in the red zone, run the handoff turn (`/session-handoff`, which plan 13 already turns into "Start next chat" with the note), then mark the session Done and seed the next task box. For VS Code chats the fork rule stands (never resumed in place): the service forks, hands the fork off, and offers the note. Off by default behind `handoff_auto` in config; Fred asked for a smooth mechanism, and this is one click fewer.

**Mechanism 2: one wrap-up document everywhere** (Fred, 2026-10-13: each step wraps up what the next step needs: the goal, findings, files, troubleshooting; a compacted context for the next model). There are three handoff texts today: the HANDOFF block of a step, `compact.run_brief`'s rendering of it, and whatever `/session-handoff` (dotclaude skill) writes, which `brief.build` wraps as "Handoff note". Make them one format, the HANDOFF block with six headings:

```text
HANDOFF
## Goal
The task goal in one line, and this step's part of it (restated, so a drifted step shows).
## Findings
What was learned or done, with paths and line numbers.
## Files touched
- path (what changed), or: - (none)
## Troubleshooting
What failed and what fixed it, what was tried and does not work, a command that reproduces: the part a fresh
model cannot rediscover cheaply. Or: - (none)
## Open questions
- a question the next step or Fred must settle, or: - (none)
## Next
One line for the next step. Optional: Next model, Replan, Lesson.
END HANDOFF
```

The brief pass keeps the same six headings; `compact.check` requires Goal and Troubleshooting to be carried forward whole (never cut: they are the cheapest insurance against a repeated dead end), and cuts Findings first as today. The step prompt gives the previous brief as "What the earlier steps left you", and the task goal once more above it. The skill ends with the same block, so `tasks.parse_handoff` and `compact.check` serve chats and steps alike, and a handed-off chat can become step 1's note of a new task with no reformatting. The dotclaude skill edit is Fred's copy to `~/.claude`, as always. `brief_max_words` goes from 400 to 500 to pay for the two headings; the "never longer than what it compacts" rule stands.

**Drift guards worth adding to the brief check** (code, no model): the brief must name at least one file from the previous brief's Files touched when that list was non-empty (continuity), and may not contain a path the task's steps never touched (no invented files). Both are one `set` comparison in `compact.check`.

**D-5** Auto handoff at the red threshold for window runs, off by default; one HANDOFF format for skill, step and brief; two continuity checks in `compact.check`. **Fred, 2026-10-13: yes, with Goal and Troubleshooting in the block.**

### 5.1 More context savings (Fred asked, 2026-10-13; all accepted)

The wrap-up is written by the model that did the work, and a model summarises its own work kindly. So code adds the facts it can know for free, and the gap between the note and the facts is the drift signal:

- **Facts under the brief, zero tokens**: `git diff --stat` from the step's start commit to its end commit as the real Files touched (the model's list stays as its claim), and the step's last test command output trimmed to its failing lines when the step ran one (read from the run stream's tool results). Both appended by the service after the brief pass, never compacted.

Then, cheapest first:

1. **The harness prompt is the biggest cost per step**: 15 to 25K tokens before a step reads anything, six times per task. Steps run with `--strict-mcp-config` (no MCP servers) and `--tools` per kind as Prep does; a kind gets MCP only when its rule names a server. Two flags, the largest single saving. Goes in plan 23.
2. **Keep the prompt cache warm**: a cache read costs a tenth of an input token, and two steps on the same model within 5 minutes hit it. Balancing adds a small warm bonus (`cache_bonus`, default 0.1 of pace) to the rung the previous step ran on when fills are close, and the brief pass runs on the same Haiku rung the scout used. Goes in plan 18.
3. **Context pack lite from Prep**: Prep already read the files. Its `where` field gives `path:lines` citations (Square's scouts returned citations, not prose); the service pastes those exact ranges, capped at 8 KB and stamped with the commit hash, under the brief of step 1. The writer step verifies instead of grepping, which is where most of a step's context goes. Goes in plan 5 or a small plan of its own.
4. **Turn caps on read kinds**: only Opus has `--max-turns` today. `scout` and `search` get 15 (`read_max_turns`); a scout at 40 turns is bulk reading, and the retry reason names the cap as it does for Opus. Plan 23.
5. **Cut what repeats**: the task goal rides in every step prompt at up to 6000 characters (`tasks.GOAL_MAX`); 600 is enough once every brief carries its Goal heading. Lessons go into a step prompt only when their kind matches the step. Plan 23.
6. **Measure before guessing**: the Board's column of brief-in words against context reached, per step and per kind, says which kind spends the tokens. After ten tasks that column decides the next tuning, not a guess.

## 6. Square Orchestrator, read again with the Console in hand

What the Console already took (BRAINSTORM 9): the harness slot, Needs you, Quiet / Stall?, STOP questions, route reason and start commit, two writers, context apart from cost, the UI rules.

What Square decided that the Console's chain now also embodies: fresh bounded sessions per role (Scout, Planner, Worker, Reviewer), a deterministic Task Manager that waits on events, a Review Packet that excludes the implementation transcript, finite retry and fix budgets, handover at a context threshold (120K / 150K there, 150K / 300K here), "never copy full transcript by default".

Worth taking now, small:

1. **Context Pack idea, applied to Prep**: Prep's scout already reads CLAUDE.md, PLAN.md History and misses. Square's scouts return citations (path, symbol, range) rather than prose. Ask Prep's `where` field for `path:function` entries and pass them to step 1 as a list; a scout step then verifies rather than searches.
2. **Receipt**: a step's chain line could carry the end commit next to the start commit (`git rev-parse HEAD` after the run). Verify then checks the diff between the two, not the whole tree. One call in `Hub._ended`.
3. **"Model family, not CLI brand, defines diversity"** (SP11 gate G5): a cooldown counts the model, not the harness; running Opus through two CLIs is one rung for the window.
4. **Fleet row content** (UI design, Agent Fleet): role, exact model, state, elapsed, tokens, writer/read-only, one blocker indicator. The step row of the Board can carry the same eight facts.
5. **"No false zero"**: unknown usage shows as unknown (D-3).

Not worth taking, still (BRAINSTORM 2 stands): the daemon with named pipes, ConPTY and xterm, SQLite and content-addressed artifacts, the dock system, the task graph with dependencies, specialist profiles and skill canaries, route certification, exposure units, resource and thermal profiles, the VS Code extension. Every one of these is a reason the fork grew past finishing, and the Console gets the same outcome with a JSON line and a Python loop.

Two things Square had that the Console deliberately lacks and should keep lacking: **parallel writers in worktrees** (plan 20 chose parallel tasks per project without worktrees, with the two-writers warning as the guard) and **a task graph**. A linear chain with one fix insert is enough; if a task needs a DAG it is two tasks.

## 7. Compact and expanded: the Board

The compact mode stays what D11 to D13 locked: the pill, the list, the session page, the Task page, 340 to 400 px. Nothing in it changes for this.

The expanded mode is a page the window shows when it is wider than about 700 px (the resize grip already allows up to 900), reached from the Task page with "Board" and from the list with a wide-window button. Working name: **Cells Board**. Same tokens, same cell motif, same type (Segoe UI, Cascadia Mono, Doto for the one focal figure). Two columns:

- **Left, the chain** (about 300 px): one cell block per step in order: state sprite and word, kind, rung (`codex · gpt-6.1-sol · medium`), cost, the 10K context cells, the brief-in and note-out word cells, attempts as small chips. Between steps a short connector that is the brief: its word count on it, hatched when the brief fell back to code, orange when it cut findings. A fix insert shows as a branch of two cells under the failed verify, rejoining after. Tasks of the same project stack vertically, folded to one row each except the picked one.
- **Right, the inspector** (the rest): whatever is picked on the left, Square's "one selected context" rule. A step shows its goal, its route notes (`rule code: sonnet/medium · cooldown: ... · floor code: ...`), the brief it read, the note it wrote with Findings / Files / Questions / Next as four blocks, the Open and Stop buttons. A connector shows the raw note and the brief side by side with what was cut. The task head shows prompt.md, the running open-questions list and the chain log.
- Keyboard: Up / Down moves the pick along the chain, Left / Right between tasks, Enter opens the step session, Esc returns to the Task page.

Not in the Board: terminals, a DAG canvas, docking, drag to reorder running steps. Reordering happens on the Prep card before the task starts, as today.

Process as before: a mockup in `design/rework/` first, Fred locks it (D-6), then a sub-plan with the final code.

**D-6** A Cells Board mockup for the expanded mode, two columns, chain and inspector, before any code. **Fred, 2026-10-13: ok.**

## 8. A bounded replan step

The one orchestrator ability the chain lacks. Proposal, in the spirit of the brief pass:

- A new step kind `replan`, which Prep may put after a scout or design step, and which the service inserts by itself when a note's `Next` line says `Replan:` (like `Next model:` today).
- It is a Haiku pass with no tools and one turn (`brief_command`), given the task goal, the briefs so far and the remaining steps, answering with JSON: the remaining steps, changed. Code validates it like `plan_steps`: known kinds, at most `task_max_steps` in all, at most two steps added, the verify re-placed after the last edit.
- A changed plan waits for Fred on the Task page (the task `waiting`, "replanned: 2 steps added") unless `replan_auto` is on in config; the chain log carries the before and after.

Cost: about $0.005 per replan. It gives the chain the flexibility Fred is afraid of losing without holding a model open.

**D-7** Add `replan` as a step kind, Haiku, no tools, validated by code, Fred confirms by default. **Fred, 2026-10-13: yes.**

## 9. Suggested order of sub-plans

| # | Sub-plan | Depends on | Size |
|---|---|---|---|
| 5 | Harness adapters: the adapter module, `claude_cli` moved behind it, the `harnesses` setting with the probe and the window switch (3.1), Codex adapter, then OpenCode, the step and Prep rungs, `step_timeout_s`, the Usage mix with other harnesses; the context pack lite from Prep's citations (5.1 item 3); Command Code's adapter (the smallest) | the installed CLIs' `--help` pasted as facts | medium |
| 18 | Tiers think / write / read with rungs across harnesses (OpenCode and Command Code in `read` only), usage fills per model (day / week / month, allowance and pace), balancing in `step_route` with the warm-cache bonus, the fill columns on the Usage page and the list header; the FAIL-rate-by-hour view | 5 for non-Claude rungs, runs on Claude rungs alone first | medium |
| 23 | Handoff everywhere: the six-heading HANDOFF block (Goal, Findings, Files touched, Troubleshooting, Open questions, Next) in the step prompt, the brief pass and the skill; facts under the brief (git diff --stat, failing test lines); auto handoff at red for window runs; the two continuity checks; end commit per step; `--strict-mcp-config` and `--tools` per kind; `read_max_turns`; goal cut to 600 and lessons by kind (5.1) | nothing | small to medium |
| 24 | Replan step kind | nothing | small |
| 25 | Cells Board: mockup, then the page | 18 for the rung text, else runs on today's routes | medium, after the mockup is locked |

Plans 5 and 23 can start now; 18 is the one that changes how routes are written in config.json, so it wants Fred's D-4 first.

## 10. Decisions

| # | Question | Recommended | Fred, 2026-10-13 |
|---|---|---|---|
| D-1 | Scripted chain only, no orchestrator agent, no subagents in steps | yes | yes (implied by taking 1 to 5) |
| D-2 | Adapter order Codex, OpenCode, Command Code | yes | yes; OpenCode and Command Code on cheap models only, on read and write steps (2026-10-14) |
| D-3 | Unknown usage shows as unknown, never zero | yes | not answered; assumed yes |
| D-4 | Tiers think / write / read, rungs on any harness, usage fills per model balanced in `step_route`, FAIL rate by hour as evidence | yes | yes, as global fills per model (day / week / month) and balancing, not cooldown timers |
| D-5 | Auto handoff at red (off by default), one HANDOFF format, continuity checks | yes | yes; the block carries Goal and Troubleshooting too |
| D-6 | Cells Board mockup before code, two columns | yes | ok |
| D-7 | `replan` step kind, Haiku, Fred confirms by default | yes | yes |
| D-8 | Per-harness on / off and path in config.json, a switch in the window, off rungs never route | yes | yes (Fred asked for it) |

## 11. History

- 2026-10-13 - Brainstorm written from the Console code and plans and the Square fork of 2026-08-08; Codex and OpenCode non-interactive flags read on their docs pages, Command Code from one third-party page (command `cmd`).
- 2026-10-13 - Fred took 1 to 5 with three changes: each step wraps up a compacted context document for the next step (goal, findings, files, troubleshooting); OpenCode and Command Code use cheap-tier models only; usage is a global fill per model over the day, week and month, balanced against the others, not a cooldown. Sections 3, 4, 5 and 9 updated in place.
- 2026-10-13 - Fred asked for more ways to save context and took all six (section 5.1): facts under the brief, no MCP and tools per kind for steps, a warm-cache bonus in balancing, a context pack lite from Prep's citations, turn caps on read kinds, a shorter goal and lessons by kind, measure on the Board. Plans 5, 18 and 23 in section 9 carry them.
- 2026-10-13 - Fred pasted `codex exec --help` (codex-cli 0.162.1) and `opencode run --help`: the adapter table now carries the installed flags (Codex: `-m`, `-s workspace-write`, `-C`, `--json`, `-o`, `resume` / `fork`; OpenCode: `-m provider/model#variant`, `--format json`, `--auto`, `--session` / `--fork`, `--standalone`, no `--dir`), neither has a turn or spend cap; then `cmdc --help` (Command Code 1.81.0, self-updated from 1.26.0 during the call: `-p`, `--max-turns` with exit 8, `--output-format json`, `-m`, `--effort`, `--permission-mode`, `--fork-session`, credit-based account). Fred asked for the console to adapt to which CLIs a user has: D-8, a per-harness switch (3.1).
- 2026-10-13 - Plan 5 reviewed against the code and the pasted `--help` outputs (`plans/05-harnesses/README.md` section 6). Where it differs from section 3 here, the plan wins: Codex's final message comes from the `--json` stream, not `-o`; Codex usage is spend, not a context size; read-only OpenCode steps use the `OPENCODE_PERMISSION` variable instead of a shipped agent; OpenCode reads its prompt from a `--file`; a pick whose harness is off at step start falls back to Claude's rung of its tier; context pack lite and the Usage mix moved out of plan 5.
