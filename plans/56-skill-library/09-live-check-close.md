# Task 9: Fred's live check on all four CLIs, and the close

> Contract: [README.md](README.md) section 2 (what each CLI does) and 3.11 (migration). Nothing in this task changes
> product code unless a check fails; a failed check is a fix in the task it belongs to, then this check is run again.
> Claude never runs these: they call real providers or Fred's own CLIs. Fred runs them on a scratch project.

## 9.1 Free check first (no provider)

1. `claude --help` lists `--disable-slash-commands` on the installed version. The flag is in the CLI reference of
   2026-11-07 and Prep and the brief pass have passed it for weeks (with `-p --output-format json`). What the fakes
   cannot show is the same flag together with `--input-format stream-json`, which only task steps use. If the CLI
   rejects that combination, stop: Task 3's flag is wrong for steps and this plan needs Fred before anything else.

## 9.2 Live checks (Fred; small prompts; record each result under README section 7)

| # | Check | Pass when |
|---|---|---|
| 1 | Start the service, open Models > Skills | `~/.claude/console/skills/` holds `index.json`, `handoff-quality/` and `ui-ux-review/`; the tab lists both rows with `why` empty and a size |
| 2 | A one-step code task on Claude | the step folder has `skills.md` equal to the prompt's skill block; `received.md` lists `skills/handoff-quality/SKILL.md`; the chain start line says `skills handoff-quality`; the run's `system` init line in `~/.claude/console/runs/<sid>.jsonl` lists none of Fred's personal skills (record what it does list: the init record's skill and command fields are not documented in what was read for this plan) |
| 3 | The same task with tags: a Prep card for a UI prompt | `tags` on the card include `ui-ux` or `web`; the code step carries `ui-ux-review` too (`skills_by: code`); the design step's plan has `Tags:` lines |
| 4 | Hand off on a task step (the old lever) | `/session-handoff` expands and writes its note: the flag is off for that turn |
| 5 | A chat task | `/session-handoff` and Fred's personal skills still load; no `skills.md` |
| 6 | A step of the same kind on a project that has `.claude/skills/` and `.claude/commands/` | neither is visible to the step (the behaviour change of README 3.11) |
| 7 | Command Code step | the skill block is in the prompt; `--no-skills` was already passed; a skill over 30,000 characters makes the step stuck with `prompt too long for cmd (N characters; skills M)` |
| 8 | Codex step, with a skill in `~/.agents/skills` if Fred has one | **record only**: does `codex exec` list it? (README section 2 says it is not switched off) |
| 9 | OpenCode step, with the skills in `~/.claude/skills` | **record only**: does OpenCode list them? If yes and unwanted, a `skill` deny route is a later plan |
| 10 | A real supervisor pass at a boundary with the library present | the digest carries `Skills available`; if the pass names skills, `supervisor.jsonl` carries `skills` and `skills_dropped`; the step shows `skills_by` |
| 11 | Edit a skill in the Skills tab, run a step | the step reads the edited text; the first save normalized `index.json`; a bad hand edit of `index.json` shows `skills: index.json invalid` and steps still start |

## 9.3 Close (after Fred's checks, one docs commit, Claude)

- [ ] 1. `PLAN.md`: update the plan 56 row's state with the build commits and the live-check result (your line only,
      anchored on the row); add a History line.
- [ ] 2. `plans/44-supervisor/BRAINSTORM.md`: under section 14.7 add one dated line: slices A and B and the Skills tab of
      slice C are built by plan 56; the `--add-dir` mode is left out (D5). Section 15 stays as it is.
- [ ] 3. `plans/56-skill-library/README.md`: status line, section 7 history with the check results, D1 to D9 as Fred
      answered them.
- [ ] 4. `CLAUDE.md`: confirm the Task 7 bullet is present; no other rule changes.
- [ ] 5. `tests/golden_prep.py` (Fred's live Prep run): print the card's `tags` next to the route so a run shows them;
      not part of the automated suite.
- [ ] 6. Fred's checklist, copied into the README history: nothing to copy by hand (the library seeds itself); to bring a
      personal skill into task steps, add an entry with `"source": "~/.claude/skills/<name>"`; to turn a seed off, set
      its entry's `always`/`tags` or remove the entry (it stays removed, D3).
- [ ] 7. Full suite green; `node --check web/app.js`; commit: `docs: close plan 56, the skill library (live check)`.
