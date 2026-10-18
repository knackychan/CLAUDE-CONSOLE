# Plan 45 - Usage limits: model scope, date, Clear

Status: code done 2026-10-19; Fred's live check open. Decisions by Fred 2026-10-19 ("all four"). Amends plan 40 D3 and D6.

## 1. Finding

On 2026-10-17 a Fable 5.1 run (session 14763dcd) got a `rate_limit_event` with `status: rejected`,
`errorCode: credits_required`, `overageDisabledReason: org_level_disabled`, `resetsAt` Sun 1 Nov 08:00.
`claude.summary` read it as a provider limit, so `limits.json` kept every Claude rung (Opus too) out of routing for
13 days, and the Tiers page showed "claude: usage limit, until 08:00" (the clock had no date). The 5 hour and
weekly limits were not reached.

## 2. Decisions (Fred, 2026-10-19)

- D1 Scope: a `rejected` event with `errorCode: credits_required` limits that rung only (key = the rung, e.g.
  `fable`), why `credits required`. Every other limit keeps plan 40 D3 (the provider). `limits.key(rung, hit)`.
- D2 Date: `limits.clock` shows `HH:MM` when the reset is today, else `Sun 01 Nov 08:00`.
- D3 Clear (replaces plan 40 D6 "No Clear button"): POST /api/limits/clear `{"key"}` drops that entry from
  `Hub.limits` and `limits.json` and answers the config (404 when no such entry). GET /api/config `tiers` rows carry
  `limit` (the entry's key, "" when none). The Tiers page puts a `clear` link on the hidden line and on each hidden
  row that has a limit. A real limit is found again by the next run.
- D4 No health check at start or on reload: a probe run spends tokens on each provider and a limited account only
  refuses it; the next real run shows the same.

## 3. Changes

- `console/limits.py`: `key(rung, hit)`, `clock(ts, now=None)`.
- `console/harness/claude.py`: `credits_required` gives `{"why": "credits required", ..., "model": True}`.
- `console/server.py`: `Hub.limit_key(rung)`, `Hub.limited` via it, `Hub.clear_limit(key)`, `_ended` keys the hit
  with `limits.key`, `tier_view` rows get `limit`, route `/api/limits/clear`.
- `web/app.js`: `tierCard` clear links, `clearLimit(key)` (keeps unsaved edits: only `cfg` is replaced).

Tests: test_limits +2, test_harness +1, test_server +3, test_web +1.

## 4. Live check (Fred)

Restart the service, open Models and tuning, Tiers: the think card says `1 hidden`-style line with
`claude: usage limit, until Sun 01 Nov 08:00 · clear`; clear it and Fable / Opus come back.
