# Task 7: Fred's live check with real passes, then the docs

> Contract: [README.md](README.md) section 1 (done when), 3.13 (the behaviour change). Decisions D1, D2.
> Runs after Tasks 1 to 6 are committed and the full suite is green. Fred drives the window; the commands below are
> copied from here. Every pass in this check is a real paid Haiku pass. For scale: plan 44's four real Haiku passes
> settled at $0.0015 to $0.0028 each (usage-days.json, 2026-10-20); a super agent pass reads more (every item and
> every live task), so expect a few tenths of a cent. The day limit holds the total at $1.00.

**Files**
- Modify: `plans/58-super-agent/README.md` (status, section 7), `PLAN.md` (row 58), `CLAUDE.md` (one paragraph),
  `BRAINSTORM.md` (one line in 7.7), `design/brainstorm/2026-11-08-super-agent.md` (History)
- Other chats edit `PLAN.md`, `CLAUDE.md` and `BRAINSTORM.md`: stage only this task's lines (README rules)

Commit boundary: `docs: plan 58 live-checked, super agent v1 (no acts)`.

## 7.1 Live check (Fred)

- [ ] 1. Restart the service: `py -m console`. In the window, set up items in two projects: a task waiting on a plan
      confirm, a task stuck or failed twice, a finished task with a supervisor suggestion, and a VS Code chat that
      stopped on a question. `~/.claude/console/super/orders.md` exists with its two comment lines; add one order, for
      example `Rank Claude Console items before other projects.`
- [ ] 2. Within about two minutes (20 s after the last new item, at most 120 s after the first), the first pass runs
      by itself. Read the queue:
      `Invoke-RestMethod http://127.0.0.1:47770/api/super | ConvertTo-Json -Depth 8`
      Expect `state` `ranked`, a `say` line on every item, always items first, the stuck task above the finished one.
- [ ] 3. Sort by hand (D6):
      `Invoke-RestMethod -Method Post -Headers @{"X-CC"="1"} -ContentType application/json -Body '{"action":"sort"}' http://127.0.0.1:47770/api/super`
      Then `sorting` is set until the pass ends; read the queue again.
- [ ] 4. Read `~/.claude/console/super/last-prompt.md`: the role text, the reminder, then the digest (head, orders,
      notes, items with handles, live tasks, signals); no secret, no CLAUDE.md text. Read `super.jsonl`: one
      `claimed` and one `result` line per pass.
- [ ] 5. Answer one item in the window (or in VS Code); after the next tick (5 s) the queue no longer shows it.
- [ ] 6. Pause and Resume: the same command with `{"action":"pause"}` gives `state` `unranked`, `why` `paused`;
      `{"action":"resume"}` runs a pass at once.
- [ ] 7. A failure: set `"super_pass_usd": 0.0001` in `~/.claude/console/config.json`, open the window's Models page
      (its GET /api/config rereads the file), sort. The queue comes back `unranked` with the pass's error as `why`,
      and `last.cost` is what the CLI reported. Set `super_pass_usd` back to 0.2 (or remove the key).
- [ ] 8. Measure the cost per pass (run after a few hours of normal work):
      `py -c "import json,statistics,pathlib; p=pathlib.Path.home()/'.claude'/'console'/'super'/'super.jsonl'; r=[json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]; c=[x['cost'] for x in r if x.get('phase')=='result' and x.get('ok') and isinstance(x.get('cost'),(int,float))]; print(f'{len(c)} ok passes, median {statistics.median(c):.4f} USD' if c else 'no ok pass yet')"`
- [ ] 9. The Usage page shows a "Super agent passes" block under the supervisor's: today's passes and spend of $1.00
      a day.
- [ ] 10. Note for the record: the median cost per pass, the passes in a day, any rank that was wrong (which item,
      what it should have been), whether the say lines helped, and anything the window (slice 2) must show.

## 7.2 Docs (after the check)

- [ ] 1. `plans/58-super-agent/README.md`: status `built and live-checked <date>`; section 7 gains the measured median
      cost per pass, the passes a day and Fred's notes from 7.1 step 10.
- [ ] 2. `PLAN.md` row 58: the same status.
- [ ] 3. `CLAUDE.md`, a paragraph after the plan 44 paragraph:

      ```
      Plan 58 super agent, slice 1 (no acts): Hub._super_tick (every 5 s) sorts the Needs you set with one bounded,
      tool-free pass at a time (superagent.run through compact._ask, safe mode, cwd ~/.claude/console/super), on new
      items, items back from Later, ended tasks and a fingerprinted sweep. Code decides what needs Fred, the always
      forwarded list, the order and every limit; the answer only ranks, batches, puts later and writes say lines.
      GET /api/super starts nothing and writes nothing; POST /api/super takes pause, resume or sort. Data:
      ~/.claude/console/super/ (state.json, notes.md, orders.md, super.jsonl, last-prompt.md) and the usage-days.json
      super section. super_day_usd 0 turns it off. Contract: plans/58-super-agent/README.md.
      ```

- [ ] 4. `BRAINSTORM.md` 7.7: after the slices sentence, `Slice 1 built and live-checked <date> (plan 58).`
- [ ] 5. `design/brainstorm/2026-11-08-super-agent.md` History: `- <date>: slice 1 built and live-checked (plan 58);
      median $X per pass, N passes a day.`
- [ ] 6. Stage the plan files by path and only this task's lines of the shared docs; commit with the message above.
