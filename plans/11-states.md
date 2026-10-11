# Plan 11: Attention states (Replied, Verified, Empty)

> Related plans: [../PLAN.md](../PLAN.md) (master), [01-watch.md](01-watch.md) (states), [03-levers.md](03-levers.md) (Verify), [07-cells-drawer.md](07-cells-drawer.md) (the list page)

**Goal:** the list says where each chat stands without a click. Today a chat that just answered, a verified one
and an empty one all read `Idle`, and 39 of 101 sessions seen on 2026-10-11 were `(prompt not seen)` rows.

## Fixed decisions (Fred, 2026-10-11)

1. **Replied**: a turn that ended with a plain reply (no STOP question, no verdict) is `↩ Replied` for
   `replied_for_s` (600 s, config.json), then `Idle`. Its own section between Needs you and Working; not a
   need (the pill count and peek card are untouched).
2. **Verified**: the last turn ended with `VERDICT: PASS` (verifier agent or main) gives `✓ Verified`, listed under
   Done, and it does not decay into Stale?. `VERDICT: FAIL` gives `× Verify failed` under Needs you (red, peek card,
   its detail as the text) until `stale_after_s`. A verdict only counts for the turn it ended (`verdict_ts` against
   the last turn's start), so a new prompt clears it. A Verify copy (`kind` verify, forked) hands its verdict to the
   original chat.
3. **Empty**: a session with no turn, no window run, no agent, no Stop and no compaction (rules loaded, nothing
   sent) is `Empty`, group `empty`, title `Empty chat, nothing sent`; the list folds them behind
   `Show N empty chats` and the pill, the project picker and Needs you ignore them.
4. **Reply line**: the Stop hook logs `reply`, the first 120 characters of Claude's last message (markdown marks
   trimmed, masked); Idle and Replied rows show it as one muted line. Hook-only change, no reinstall.

## Code map

```text
cc_events.py      Stop record + "reply"
console/paths.py  replied_for_s
console/state.py  STATES + replied / verified / verify_failed / empty; Session.reply, replied_ts, verdict_ts;
                  is_empty(); state_of(); _verdict(ts) + Verify-copy hand-over; snapshot group + counts + reply
web/app.js        tone, groups, quietHtml (reply line), Replied section, Empty fold, PEEK + verify_failed
web/style.css     .card.replied, .card .reply
tests/            test_cc_events + 1, test_state + 4 (4 Idle assertions became Replied)
```

## TODO

- [x] Task 1: service and hook (state, config, reply), tests (124 OK)
- [x] Task 2: window (sections, tones, reply line, Empty fold), checked in headless Edge at 420 px on seeded events
- [ ] Task 3: Fred: live check in the real window (restart the window; the reply line needs new Stop events)

## Not done / open

- A chat that was `Idle` before this ships has no reply line until its next Stop.
- `Prep failed` seen in the window could not be reproduced (Prep of the same text succeeded in 31 s through
  `/api/prep`); the red card shows the real message under the title: send it when it appears again.
