# Task 8: Fred's live check

> Claude never starts a run, never POSTs `/api/run`, `/api/task` or `/api/prep`. Fred runs this in a real project
> (CONTENT MANAGER, or this repo on a scratch branch) after Task 7 is placed and the tray's service restarted.

## 8.1 Widen and return

1. The list at its compact size: `⇔ Board` in the header. Click: the window widens to 900 x 680 (the first time) and
   shows the Board on the newest task. Drag the grip to 1000 x 720, Esc: the compact size comes back; Board again:
   1000 x 720 (window.json `board`). Fold to the pill from the Board and unfold: compact size, the list.
2. From a Task page: `⇔ Board` opens on that task, Esc returns to the Task page. Enter on a step opens its session;
   Esc comes back to the Board, Esc again to the Task page.

## 8.2 A task with four or more steps (scout, code, test, verify), effort auto

3. While it runs: the current step full with its 30 cells moving, the done steps two lines with 15 cells, the
   connector after the running step `writing`, the dotted ones after the planned steps; the footer keys work.
4. After each step: the connector `handoff`, its chip title with the words; pick it: what the next step received,
   the raw note's six headings, Checks closed `5 of 5 pass ...`. Note one connector with `cut N w` if the pass cut:
   the struck lines in place, in ink.
5. Pick a step: Chat first (Prompt row folded, tool rows, the HANDOFF chip and Next), Received and Handoff with
   their figures, Route with the rule notes, the Facts fold with the test line. Close Files touched open on one
   handoff, restart the window: it is still open.
6. The task head: Now line, open questions (if a brief carried one), prompt.md's Done when, the chain log.
7. Esc to the Measure table after two or three tasks: the medians match what the steps showed; the reading names the
   kind with the most context per word received (D3), or nothing.

## 8.3 A failure and a fix

8. A task whose verify fails (a request with a test that cannot pass, or the fake word on a scratch branch): the
   verify `Fail` with its detail in red, the fix bracket with `fix` and the second `verify` numbered as the folder is
   (D1); the count `step N of M` reads the folder's numbers.

## 8.4 Other harnesses (when plan 5 is placed)

9. A Codex or OpenCode step: `ctx unknown` with the harness title, `cost unknown` where the harness reports none, the rung
   `codex · gpt-6.1-sol · medium`, the chat labelled `Codex`.

## 8.5 Record

- Each item: what was expected, what was seen, the task id. Note D1 to D4 as seen: is `06 fix` / `07 verify` clear
  enough (D1), did a question close when it should (D2), did the reading name the right kind (D3), did `△ scout
  first` show where a scout would have helped (D4).
- Findings become fixes in a later plan or small commits on this branch when they are one-liners.
