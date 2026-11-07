# Task 7: the library's routes (read in `GET /api/config`, edit through `POST /api/skill`)

> Contract: [README.md](README.md) 3.2, 3.3, 3.8, 3.10. Decisions D8 (create, no delete). BRAINSTORM 14.3 and slice C.
> **A new write route, not `POST /api/config/models`.** That route is the config.json whitelist (all or nothing, "never
> writes models.json"); the library is files under `~/.claude/console/skills/`, exactly like the kind files that the
> Kinds tab edits through `POST /api/kind`. The CLAUDE.md rules paragraph names the new route (step 3 below).

**Files**
- Modify: `console/skills.py` (`save`, `entry_of`, `seed_of`, the module lock)
- Modify: `console/server.py` (`Handler._config`, `Handler._skill`, `Handler._skill_save`, the `do_GET` branch and the
  `routes` dict entry next to `/api/kind`)
- Modify: `CLAUDE.md` (one bullet, step 3)
- Modify: `tests/test_skills.py` (`SaveTest`), `tests/test_server.py` (`SkillRoutesTest`)

Commit boundary: `feat: read the skill library in /api/config and edit it through POST /api/skill (plan 56 T7)`.

## 7.1 Contract

`GET /api/config` gains, from `Hub.skill_registry()`: `skills` (the rows of README 3.3 with `description` masked),
`skills_error` (`""` or `index.json invalid: ...`), `skills_tags` (`skills.vocabulary`). The existing keys are unchanged.

`GET /api/skill?name=<name>` -> `{"name", "text", "path", "entry", "row", "seed", "seed_entry", "pointer"}`:
`text` is the raw SKILL.md (for a pointer, the pointed-to file), `""` when missing; `path` its absolute path; `entry`
the raw `index.json` object or `null`; `row` the registry row or `null`; `seed` and `seed_entry` the repo copy or `""` /
`null`; `pointer` true for a `source` entry. 400 `bad name`; 404 `unknown skill` when the name has neither a folder nor
an entry. Raw text is deliberate (README 3.8): it is Fred's own file in his own editor.

`POST /api/skill` body `{"name", "text"?, "entry"?, "reset"?}` -> the same object as the GET after the save. Only these
four keys (anything else: 400 `unexpected field`).

| Refusal (nothing is written) | Status and message |
|---|---|
| `name` not `NAME_RE` | 400 `bad name` |
| none of `text`, `entry`, `reset` | 400 `nothing to save` |
| `reset` with `text` or `entry` | 400 `reset takes no other field` |
| `reset` for a skill with no seed | 400 `no seed for <name>` |
| `text` not a string, blank, or holding a NUL | 400 `text: the skill as text` |
| `text` with a marker line (README 3.7) | 400 `marker line: <m>` |
| `text` for a pointer skill | 400 `this skill points to ~/.claude/skills/<name>; edit it there` |
| a new name with neither `text` nor an `entry.source` | 400 `a new skill needs its text` |
| `entry` not an object, or `skills.check_entry` fails | 400 with `check_entry`'s reason (`index: ...`) |
| `entry` while `index.json` is unparseable | 409 `index.json is invalid: fix it by hand first` (a text-only save is still allowed) |
| a body over `MAX_BODY` (256 KB, the transport) | the existing 413; the library itself has no cap (D18) |

`skills.save(home, user_home, name, text=None, entry=None, reset=False) -> dict` does the work and raises
`ValueError(reason)` (the table's messages) or lets `OSError` through. Rules:
- the folder is `Path(home)/"skills"/name`, created on the first save of a new name (D8; there is no delete route);
- `reset` writes the seed `SKILL.md` and, when `index.json` has no entry for the name, the seed entry; an existing
  entry is kept;
- `entry` replaces the named entry's known keys (`description`, `kinds`, `tags`, `paths`, `always`, `source`); the old
  entry's other keys are kept (README 3.2); every other entry is written back as read;
- everything is validated first; then `SKILL.md` is written (`paths.write_text_atomic`, text with one trailing
  newline, `\r\n` -> `\n`), then `index.json` (`paths.write_text_atomic(json.dumps(data, indent=2, ensure_ascii=False)
  + "\n")`). If the second write fails the first stays and the route answers 500 `SKILL.md was saved; index.json was
  not: <reason>`. A module-level `threading.Lock` serialises saves (and `ensure`'s index write);
- the first window save normalizes the formatting of a hand-edited `index.json` (key order and values are kept); this is
  the cost of a validated write and is said once in the Skills tab's help line (Task 8);
- no cache call is needed: the registry signature (3.3) changes with the files.

## 7.2 Tests first (red before the code)

`tests/test_skills.py` `SaveTest` (scratch home and user_home)
- `test_create_edit_entry_only_and_reset`: a new name with text and entry creates the folder, the file and the entry;
  a text-only save leaves the entry as it was; an entry-only save leaves the text; `reset` on a seed skill restores
  the seed text and keeps an edited entry; `reset` on a non-seed skill is refused.
- `test_every_refusal_writes_nothing`: each row of the table above; the folder listing and every file's bytes and mtime
  are unchanged after the refusal.
- `test_unknown_keys_and_other_entries_survive`: an entry with `"x": 1` keeps it after an entry save; the other entries
  are equal as parsed JSON.
- `test_atomic_writes_and_the_partial_failure_message`: both files go through `paths.write_text_atomic` (monkeypatched
  recorder); failing the second reports `SKILL.md was saved; index.json was not` and the first file is the new text;
  failing the first writes neither; a pointer skill can be created with `entry` only.
- `test_unparseable_index_blocks_entry_saves_but_not_text_saves`: the bad file's bytes are never touched.
- `test_a_300_kb_text_saves_whole` (D18, called directly, below the HTTP cap): read back identical.
- `test_concurrent_saves_keep_both_entries`: two threads saving two names; the index holds both.

`tests/test_server.py` `SkillRoutesTest`
- `test_config_lists_the_library`: rows with `ok`, `hand`, `indexed`, `kb`, `why`; a trap row's `why`; `skills_error`
  empty, then `index.json invalid: ...` after a bad hand edit with the last good rows still listed; `skills_tags`;
  a description holding a secret-shaped token is masked.
- `test_get_skill_shapes`: a skill, a pointer, an unindexed folder, an entry with no folder, `bad name` 400, an unknown
  404; the raw text is not masked.
- `test_post_skill_end_to_end`: create, edit, then the next `Hub.start_step` of a matching task reads the new text
  (the registry saw the change without a restart).
- `test_post_skill_refusals_map_to_statuses`: the table's statuses; a request with a stray key; a request from another
  Host header is refused by the guard like every route (reuse the existing guard test helper).
- `test_config_models_route_does_not_take_skills`: `POST /api/config/models {"skills": ...}` -> 400 with `not a setting
  this page changes` (the whitelist is untouched).
- `test_no_write_outside_the_library`: after create, edit and reset, the only changed paths under the scratch home are
  `skills/**`; nothing under the scratch `user_home`.

## 7.3 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_skills tests.test_server` (the new classes) red.
- [ ] 2. `skills.save`, then the three Handler pieces and the two route registrations. Focused tests green.
- [ ] 3. **CLAUDE.md** (anchored edit: insert a new bullet directly after the bullet that begins `- The Models and tuning
      page writes config.json only through POST /api/config/models`; the other chats edit this file, stage only these
      lines). The exact text:

      - The Skills tab on the Models page (plan 56) writes the skill library only through POST /api/skill
        (`console/skills.py` `save`: one skill's SKILL.md and its `index.json` entry under `~/.claude/console/skills/`,
        validated first, each file replaced atomically); never config.json, never `~/.claude/skills`, never a project
        folder. Task steps carry the library: the chosen skill bodies are inlined whole in the step prompt, masked by
        `redact.mask` and saved as `skills.md`, and a Claude task step runs with `--disable-slash-commands` (a chat step
        and the Hand off lever's turn do not). The window cannot delete a skill.

- [ ] 4. Full suite green; commit with the message above (CLAUDE.md hunk included, staged alone: non-interactive: `git hash-object -w` of HEAD's file plus this hunk, then `git update-index --cacheinfo 100644,<blob>,<path>`; `git add -p` is interactive and not available).
