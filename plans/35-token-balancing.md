# Plan 35: tracked token bars and balancing without allowances

Fred, 2026-10-15: restore the model rows and segmented bars from the earlier Usage mockup. A model that
has processed many tokens should give way to another eligible model. This measures workload, not provider
quotas or model quality. No subscription limits or monetary allowances are invented.

## Scope

- Keep per-model processed tokens (input, output, cache write and cache read) in the existing daily history.
  Keep old history readable; rescan available transcripts to add token counts without lowering saved costs.
- Keep configured USD pace balancing. When no candidate has a usable pace, balance by today's measured
  tokens instead, preferring idle models before those already working. The margin/cache preference continues
  to apply to USD pace; token balancing selects the least-used idle model. Missing measurements are unknown,
  not zero.
- Restore all configured model rows on Usage. Without an allowance, the bar shows the model's share of
  today's tracked tokens. Show the totals for day/week/month and distinguish unknown measurements.
- Expose those rows from the board's existing usage breakdown. New single chats can select Auto and use
  the same balance function. Explicit picks and existing chat continuations retain their model.
  Auto keeps attachments on Claude, the only adapter that accepts their content; Fable remains an explicit
  choice for a new chat because its credit confirmation is tied to that choice.
- Resolve Command Code's known npm launcher through Node directly so rotation cannot select a launcher
  that passes its version probe but rejects every prompt. Never pass prompts through a shell.

## Files and checks

`console/usage.py`, `console/fills.py`, `console/server.py`, `console/harness/cmd.py`, `web/app.js`,
`web/style.css`, and their existing tests. Check history deduplication/persistence, missing token data,
cross-CLI rotation after heavy Opus use, pins/picks, configured pace, new-chat Auto and safe npm launching.
Run relevant Python tests, Node syntax/render checks, and inspect the existing UI at narrow and wide sizes.

Deployment: do not restart the service while it owns running tasks. No real model calls are required.

## Validation, 2026-10-15

- 89 focused tests pass across history, fills, routes, rendering, adapters, Auto, attachments and Fable confirmation.
- Full suite: 631 tests, 629 pass. The two existing failures are `HarnessServerTest.test_harness_switch` and
  `test_probe_never_raises`: they assume OpenCode/Codex are absent from PATH. Both pass with discovery isolated;
  persistent test isolation belongs to plan 34. Node syntax check passes.
- Headless Edge: 340, 400 and 900 px, all 11 model rows present, no horizontal overflow or page errors; dark
  mode at 340 and 400 px, plus the board's model-usage disclosure. The mechanical UI scan flags one existing
  unrelated border at style.css's `.v-subs` rule; the usage changes add no flagged pattern.
- Read-only scan of actual transcripts: about 40.3M Opus processed tokens today. The new balance function picks
  `codex:gpt-6-astra` for the next think run. No request was sent to that model.
- The installed Command Code entry point runs through Node directly and reports version 1.81.0. Prompt
  metacharacters stay within one argv entry in the adapter test. No paid model execution was tested.

Activation is pending a service restart after the active task finishes. No allowances, prices, provider settings
or active task files were changed by this work. Preview screenshots are under `~/.claude/console/checks/token-balancing/`.
