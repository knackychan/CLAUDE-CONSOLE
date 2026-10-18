# Task 4: one bounded, tool-free pass

> Contract: [README.md](README.md) 4.1, 4.5. Lands on Task 3.

**Files**
- Modify: `console/supervisor.py` (`build_prompt`, `prompt_hash`, `run`)
- Modify: `console/compact.py` (`_ask` only; preserve existing callers)
- Modify: `console/kinds.py` (`NAMES`)
- Create: `dotclaude/console/kinds/supervisor.md`
- Modify: `tests/fake_claude.py` (`prep` structured-output branch)
- Modify: `tests/test_supervisor.py`, `tests/test_compact.py`, `tests/test_kinds.py`, `tests/test_claude_cli.py`

## 4.1 Shared runner change

Read all `_ask` callers before editing: run_brief, replan.run_replan, handoff.run and their tests. Extend the
signature by optional keyword-only `max_cost: float = 0.0, safe_mode: bool = False`. Existing model/schema/info arguments and
defaults remain compatible. A positive max_cost appends the documented max-budget-usd argument to the
existing brief_command; format without rounding a tiny remaining allowance upwards. Zero means the existing
callers' behavior, but supervisor admission must never pass zero to mean an unlimited supervisor call.

For the supervisor only, safe_mode adds --safe-mode and --disallowedTools mcp__* to the existing bounded
command. Empty tools alone does not prevent automatic CLAUDE.md/memory/plugin loading; digest-only must
also suppress ambient context. The current CLI reference documents safe-mode retaining normal authentication
while disabling customizations; do not use bare mode as an unverified authentication change. Keep existing
no-tools/strict-MCP/hooks-off constraints. Unsupported isolation is a terminal no-decision, never a retry with
isolation removed. No new setting or change to other pass callers is needed.

When info is supplied, set `info['cost']` as soon as a valid result envelope exposes finite nonnegative
total_cost_usd, before checking is_error/structured_output/returncode. An absent/malformed cost is None;
definite failure to spawn costs zero, timeout is unknown. Keep turns reporting and BriefError behavior.
Reject a nonzero subprocess exit even if stdout contains a plausible decision. This allows supervisor.run
to retain paid cost when the decision is unusable, without changing brief/replan/handoff return shapes.
Do not move other passes into a new abstraction or change their models/timeouts.

## 4.2 Signatures, prompt and kind

- `build_prompt(raw: str, task: dict, digest_text: str) -> str`: kinds.body_of, Template substitution for
  $you/$You, fixed schema reminder, digest last. The seed starts '# supervisor'; body starts with
  'You supervise one Claude Console task'. Keep the English seed below 600 words and 4500 UTF-8 bytes,
  a conservative check for its under-1500-token target without a tokenizer dependency. Preserve edited
  kind files; no hard new size policy for Kinds.
- `prompt_hash(prompt: str) -> str`: SHA256 of prompt.encode('utf-8'), no normalization or file reads.
- `run(cfg: dict, exe: list, task: dict, prompt: str, model: str, max_cost: float) -> dict`:
  blocking, no writes/mutation; returns {decision: dict|null, cost: number|null, model, turns, error: str}.
  R3: caller builds prompt once with build_prompt, hashes it for the claim and passes the same string here.
  run sends it unchanged to _ask; it does not reload the kind or rebuild the digest. Update live/replay
  callers and fake runner fixtures to this signature, not the superseded digest_text/raw signature.
  Adapt cfg locally with brief_timeout_s=supervisor_timeout_s; call compact._ask once with SCHEMA, model
  and safe_mode=True.
  Validate shape; dynamic gate validation remains in Hub on completion. Every error returns no decision;
  no brief-style fallback action. Unexpected exceptions are caught by the Hub worker in Task 5.
- Add supervisor after prep in kinds.NAMES; leave tasks.KINDS/PREP_KINDS/RULES unchanged. Update the exact
  NAMES test and exclude supervisor from worker-only HANDOFF heading assertions, like prep/replan/design.
  Existing kinds.ensure in main already seeds it; do not add a second seeding mechanism.

Seed prompt: one task, saved digest only, select one allowed move, no tools/files/commands/model ids, never
answer human questions or release Fable/pace holds. A saved design suggests its first implementation step;
a completed code step suggests Verify against Acceptance; verify PASS with no remaining work can Finish;
concrete FAIL can propose one repair, otherwise escalate. Stuck can propose one Retry with a concrete note.
Stall only suggests Stop for Fred. Missing/omitted evidence must be acknowledged, never invented. Confidence
does not override gates. Keep the schema as the source of enums instead of duplicating it in a long prompt.

## Tests first

- `RunnerTest.test_one_call_has_project_cwd_timeout_and_tool_free_flags`: inspect subprocess.run arguments,
  schema JSON, empty tools, dontAsk, disabled commands, strict MCP, disabled hooks, no persistence, six turns,
  budget, safe-mode and explicit MCP denial; child_env/NO_WINDOW reused. No resume/session-id/add-dir/
  Agent/background options or RunManager call. Other callers' default _ask command remains unchanged.
- `test_prompt_order_and_seed_override`: edited kinds.text wins, personal $you substitution, schema before
  digest and no lost dollar signs in evidence; model haiku normally/sonnet on supplied stuck context only.
- `test_prompt_fingerprint_matches_executed_bytes`: hash equals SHA256 of captured subprocess stdin,
  including CJK/dollar signs; a kind-only edit changes the hash while Task 3's evidence revision stays equal.
  Editing the kind after snapshot cannot change the prompt executed by that already claimed pass.
- `test_failures_have_no_decision_and_no_retry`: subtests missing executable, OSError, timeout, non-JSON,
  non-object, nonzero exit, is_error, no structured_output, malformed fields and unexpected runner exception.
- `test_invalid_decision_keeps_reported_cost`: paid bad JSON shape/schema and error envelope retain cost;
  negative/NaN cost is unknown and cannot replenish allowance. Budget overrun retained in full.
- Extend fake_claude.prep by inspecting schema's decision property before the existing prompt branches.
  Recognize SUP-VERIFY/CODE/FINISH/ESCALATE/BAD, plus test-local timeout/error envelopes. Existing BROKEN/SLOW
  modes keep working; a fake supervisor answer is never confused with brief/replan/Prep.
- `tests/test_compact.py`: existing calls without max_cost have unchanged command/default timeout; info
  preserves reported cost on failures. Replan and handoff fake suites still green.

## Steps and acceptance

- [ ] 1. Runner/shared-helper tests red. Recheck [CLI reference](https://code.claude.com/docs/en/cli-reference)
      flags against the existing command. No new hook fields are needed.
- [ ] 2. Implement the optional _ask extension, kind and one-call runner; make focused tests green.
- [ ] 3. Run `py -m unittest tests.test_supervisor tests.test_compact tests.test_replan tests.test_handoff tests.test_kinds tests.test_claude_cli`.
      Full suite; commit: `feat: run one bounded supervisor pass per wake (plan 44 backend T4)`.

**Risk retained:** max-budget-usd uses CLI estimates; one call may overshoot. Record full actual reported
cost and refuse another call at the cap. A timeout cannot establish that a paid request cost zero.
