# Task 1: the library, its seeds and the registry

> Contract: [README.md](README.md) 3.2, 3.3, 3.7 (lint), 3.8, section 1 (out of scope). Decisions D1, D2, D3.
> Mirrors `console/kinds.py` (`ensure`, `folder`, `seed_text`, atomic save).

**Files**
- Create: `console/skills.py` (folder, seeds, `ensure`, `check_entry`, `body`, `lint`, `registry`, `vocabulary`)
- Create: `dotclaude/console/skills/index.json`, `dotclaude/console/skills/handoff-quality/SKILL.md`,
  `dotclaude/console/skills/ui-ux-review/SKILL.md`
- Modify: `console/__main__.py` (one line and one import name; other chats edit this file: stage only this hunk,
  non-interactive: `git hash-object -w` of HEAD's file plus this hunk, then `git update-index --cacheinfo 100644,<blob>,<path>`; `git add -p` is interactive and not available)
- Create: `tests/test_skills.py` (`LibraryTest`, `RegistryTest`, `LintTest`)
- Modify: `tests/test_dotclaude.py` (the seed skills)

Commit boundary: `feat: the skill library, its seeds and the validated registry (plan 56 T1)`.

## 1.1 `console/skills.py` (this task's part)

```python
"""The Console's own skill library (plan 56, plan 44 BRAINSTORM 14): <home>/skills/<name>/SKILL.md and a hand-edited
index.json, seeded from dotclaude/console/skills/ like the kind files. The service reads it; a step carries the chosen
bodies in its prompt. Never raises on a read."""
SEED = Path(__file__).resolve().parent.parent / "dotclaude" / "console" / "skills"
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
TAG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
BASE_TAGS = ("backend", "web", "tests", "docs", "data")
KNOWN = ("description", "kinds", "tags", "paths", "always", "source")   # the keys the registry reads; others are kept

def folder(home) -> Path                       # Path(home) / "skills"
def seed_names() -> list                       # sorted folder names under SEED that hold a SKILL.md
def ensure(home) -> list                       # README 3.2: names whose folder was copied in this run
def check_entry(name, entry, user_home) -> str # "" or the exact `index: ...` / `bad name` reason of README 3.3
def body(path) -> tuple                        # (masked body, "") or ("", why): README 3.3, the only reader of a body
def lint(text) -> str                          # "" or "marker line: <m>" (README 3.7)
def registry(home, user_home, cache=None) -> dict   # README 3.3
def vocabulary(reg) -> list
```

Rules the code must follow (all decided; none left to the builder):

- `ensure` copies each missing `<name>/SKILL.md` with `path.parent.mkdir(parents=True, exist_ok=True)` and
  `write_text(..., encoding="utf-8")` as `kinds.ensure` does (an unreadable seed or a write error skips that skill and
  continues). The index is written with `paths.write_text_atomic(path, json.dumps(data, indent=2, ensure_ascii=False)
  + "\n")`. The seed `index.json` is read with `json.loads`; if the repo's own copy is unreadable, `ensure` writes
  nothing for the index and still copies the folders.
- A present, parseable `index.json` that is not an object is "unparseable" for `ensure` (left alone).
- `registry` signature: `(index (mtime_ns, size) or None, tuple(sorted((entry.name, SKILL.md (mtime_ns, size) or None)
  for each child directory of skills/)), user skills pointers' files (mtime_ns, size))`. `cache` is a dict the caller
  owns; keys `sig` and `last`. On an unparseable index the cached `last` rows with `error` set are returned; with no
  `last`, the rows are the unindexed folders only.
- `description` fallback: the frontmatter line `description: <text>` (surrounding quotes removed); a folded or block
  value (`>` or `|`) counts as missing, then the name.
- A pointer's path: `(Path(user_home) / ".claude" / "skills" / name / "SKILL.md")`; `source` is accepted only if the
  text is exactly `~/.claude/skills/<NAME_RE>` (no `..`, no further segment) and the resolved path stays under
  `Path(user_home)/".claude"/"skills"`.
- Rows for index keys come first in the file's key order, then unindexed folders by name; a folder without a SKILL.md
  and without an entry is not listed; an entry without a folder is listed with `no SKILL.md`.
- Child directories that are symlinks or whose resolved path leaves `skills/` are ignored.

## 1.2 The seed files

`dotclaude/console/skills/index.json`:

```json
{
  "handoff-quality": {
    "description": "How to write a six-heading handoff block that passes the brief checks.",
    "kinds": [], "tags": [], "paths": [], "always": true
  },
  "ui-ux-review": {
    "description": "Checks a screen against the Console Cells rules (tokens, 340 px, state never colour alone).",
    "kinds": ["design", "verify", "code"], "tags": ["ui-ux", "web"], "paths": ["web/**"], "always": false
  }
}
```

`dotclaude/console/skills/handoff-quality/SKILL.md` (D1 a; the person is "the user", no template slots, no marker line):

```markdown
---
name: handoff-quality
description: How to write a six-heading handoff block that passes the brief checks.
---

# Handoff quality

The block that ends your final message is checked by code before the next step reads it. These are the points the
checks enforce; the template and the headings are in the rules of your prompt.

- Goal: one line for the task, one line for this step. When an earlier handoff has a Goal, keep its lines as they are
  and add yours. Do not reword them.
- Findings: a few short lines, each with the file path and line number that matters. Say what you did and what you
  learned.
- Files touched: one line per file, the real path as git shows it, and what changed. Name no file that no step
  touched. When you touched nothing, write `- (none)`.
- Troubleshooting: keep every earlier line whole, then add what failed, what fixed it and what does not work. A dead
  end you drop will be tried again by the next step.
- Open questions: keep every earlier question until someone answers it. Write each as one line.
- Next: one line for the next step. Add `Next model:` or `Lesson:` only when the rules of your prompt say to.
- Keep the whole block short. A block over the word limit is compacted by another model, and detail is lost.
```

`dotclaude/console/skills/ui-ux-review/SKILL.md` (D1 a; the text is the user's to edit):

```markdown
---
name: ui-ux-review
description: Checks a screen against the Console Cells rules (tokens, 340 px, state never colour alone).
---

# UI and UX review

Use this when a step adds or changes a screen, a component or a style. Check each point against the diff and the
running page, and say which ones you could not check.

- All styling lives in `web/style.css`, tokens first. A colour, size or radius written inline in a component, or a
  second style sheet, is a defect.
- The window works from 340 px to 900 px wide. Nothing overflows horizontally at 340 px, in both colour schemes.
- State is never carried by colour alone: every state also has a word, a shape or an icon.
- No text under 11 px and no click target under 24 by 24 px.
- Text and controls keep their contrast in the light and the dark scheme.
- Motion follows the system's reduced-motion setting.
- Controls are reachable by keyboard in a sensible order, with a visible focus.
- No emoji and no em-dash in any text.
- Copy says what happens, in plain words.
```

`console/__main__.py`: add `skills` to the `from . import ...` line (alphabetical: `..., server, skills, tasks`) and,
on the line after `kinds.ensure(paths.home())`:
`    skills.ensure(paths.home())  # plan 56: the skill library, seeded once, then the user's to edit`.

## 1.3 Tests first (red before the code)

`tests/test_skills.py` uses a scratch home (`tempfile.mkdtemp`), a scratch `user_home`, and never the real `~/.claude`.

`LibraryTest`
- `test_seeds_are_clean_and_consistent`: the seed `index.json` parses to an object; every key is a `NAME_RE` name with
  a `SKILL.md` folder; every folder is indexed; each SKILL.md starts with a frontmatter whose `name:` equals its folder
  and whose `description:` is one non-empty line equal to the index description; `skills.lint(body)` is `""`; no
  U+2014, no character above U+1F000, no `Fred`, no `$` (bodies are not templates); `handoff-quality` is `always` with
  empty kinds, tags and paths; `ui-ux-review` has kinds design, verify, code.
- `test_ensure_seeds_once_and_keeps_an_edit`: first run returns both names and writes both folders and the index;
  second returns `[]`; an edited `SKILL.md` and an edited index entry survive another `ensure`; the registry on the
  seeded home has two ok rows.
- `test_ensure_adds_an_entry_only_with_its_folder` (D3): delete the `handoff-quality` entry only -> `ensure` -> still
  absent and the row reads `not in index.json`; delete its folder as well -> both return. With `skills.SEED`
  monkeypatched to a temp seed holding a third skill: an existing index gains exactly that entry, the other entries
  are byte-identical.
- `test_ensure_never_raises_and_leaves_a_bad_index_alone`: an unparseable `index.json` keeps its bytes while missing
  folders are still copied; an `index.json` that is a directory, a read-only target (monkeypatch `write_text_atomic`
  to raise `OSError`) and an unreadable seed each return without raising.
- `test_index_is_written_through_write_text_atomic`: monkeypatch `paths.write_text_atomic`, record the calls: the
  index is the only file written that way.
- `test_no_other_module_imports_skills_but_the_allowed`: `tasks.py`, `plan.py`, `kinds.py`, `prep.py` source has no
  `import skills`/`from . import ... skills` (the direction of README 3.1).

`RegistryTest` (a helper writes a library from a dict of name -> (entry or None, body or None))
- `test_why_table`: one case per row of the README 3.3 table, each asserting the exact `why`, `ok` and `hand`: bad key
  `Bad_Name`; entry a list; `kinds: ["reviewer"]`; `kinds: "code"`; `tags: ["Web"]`; `paths: ["../x"]`, `["/abs"]`,
  `["C:/x"]`, `["a\\b"]`, a 201-character glob; `always: "yes"`; `source: "~/.claude/skills/../x"`, `"/etc/passwd"`,
  `"~/.claude/skills/a/b"`; an entry with no folder; a folder whose SKILL.md is a directory (`unreadable`) or invalid
  UTF-8; a SKILL.md with only a frontmatter (`empty SKILL.md`); a body with a line `END HANDOFF`; a folder with no
  entry. An invalid-entry skill with a readable body is `hand` true; `no SKILL.md`, `unreadable`, `empty` and `marker`
  are `hand` false.
- `test_pointer_reads_the_personal_skill`: `source: "~/.claude/skills/my-notes"` with `<user_home>/.claude/skills/
  my-notes/SKILL.md`: ok, `kb` from that file; the library folder of the same name, if any, is ignored; a pointer to a
  missing file is `no SKILL.md`.
- `test_order_description_fallback_kb_and_masking`: index order then unindexed by name; a missing `description` reads
  the frontmatter line, a folded `description: >` falls back to the name; `kb` is the masked body's UTF-8 size in KB to
  one decimal; a body holding a secret-shaped token (`redact` pattern from `tests/test_redact.py`) comes back masked
  from `body()`; a 300 KB body is returned whole (D18).
- `test_cache_reads_a_body_only_when_the_signature_changes`: count `skills.body` calls (monkeypatch): the second
  `registry` call with the same cache reads none; touching one SKILL.md re-reads that skill; editing `index.json`
  re-validates.
- `test_a_bad_index_keeps_the_last_good_rows`: after a good read, write `{`: `error` starts `index.json invalid:`, the
  earlier rows are returned, an unindexed folder added meanwhile is listed; with no earlier read, rows are the unindexed
  folders only; a JSON array is invalid too. A missing `skills/` folder: `{"skills": [], "error": "", "tags": [...base]}`.
- `test_vocabulary`: the base tags plus the tags of ok rows only (a trap row's tags are not offered), sorted.

`LintTest`
- `test_marker_lines`: `HANDOFF`, `END HANDOFF`, `PLAN`, `END PLAN`, `END SUBPLAN`, `SUBPLAN 2 code Title`, and the
  dressed forms `**HANDOFF**`, `` `END HANDOFF` ``, `### PLAN` each return `marker line: <the marker>`; prose such as
  `Write the HANDOFF block last`, a heading `# Plan: x`, `## Goal` and `VERDICT: PASS` return `""` (README 3.7 lints
  structure markers only).

`tests/test_dotclaude.py`: a test `test_seed_skills_are_listed_and_agree_with_the_brief_checks` asserting the seed
`handoff-quality` text names the six headings of `tasks.HEADINGS` by their words (Goal, Findings, Files touched,
Troubleshooting, Open questions, Next) so the skill and the contract cannot drift apart.

## 1.4 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_skills tests.test_dotclaude` red for the missing module.
- [ ] 2. Create the seed files, `console/skills.py` (this task's functions), the `__main__.py` line. Focused tests
      green.
- [ ] 3. Full suite green (report the count). Stage only the two changed lines of `console/__main__.py` (non-interactive: `git hash-object -w` of HEAD's file plus this hunk, then `git update-index --cacheinfo 100644,<blob>,<path>`; `git add -p` is interactive and not available).
      Commit with the message above.
