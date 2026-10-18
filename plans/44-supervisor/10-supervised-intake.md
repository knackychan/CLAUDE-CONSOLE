# Task 10: supervised task intake through the existing Prep route

> Contract: [README.md](README.md) 1, 4.2; brainstorm D7 and section 9. Lands on Task 9.

**Files**
- Modify: `console/server.py` (`Handler._task_new`, `Hub.create_task`, `_prep_files` if manifest text needs it)
- Modify: `tests/test_supervisor_server.py`, `tests/test_server.py`
- No Prep SCHEMA, frontend, step-prompt or skills changes.

## 10.1 API and functions

Extend `Hub.create_task(card, steps, effort, title='', *, supervised=False, supervisor_mode=None) -> str`.
Existing calls with positional/default arguments keep the current automatic chain behavior. Handler._task_new
accepts optional supervised bool and optional supervisor_mode enum only for supervised intake. Unknown mode,
wrong bool type or mode without supervised returns 400. Reject body fields attempting to set counters, bypass
gates or submit supervisor decision JSON. The existing project/Prep/prompt/effort/model validation stays.

When supervised:

1. Reuse current valid Prep-card step parsing/model checks, retain only the first valid worker step as the
   initial task.steps. Do not retain plan_steps' inserted verify. If the card supplies no steps, use one scout
   whose goal is the enhanced prompt cut to STEP_GOAL_MAX, keeping the full enhanced task goal in task.goal.
   A malformed supplied step is rejected; it is not silently replaced with fallback scout.
2. Set progression manual before first save/start, owner service for this first step. Save later validated
   Prep steps in task.supervisor.proposed, preserving their kind/goal/model intent but granting no permission
   to launch them. No proposed step becomes a reservation, queued worker or automatic tail.
3. Snapshot mode from existing project/global policy unless this request explicitly supplies a mode. An
   explicit auto is a human choice and is audited. supervised=true alone preserves the configured suggest
   default. This backend prepares the separate future Run supervised control; no button is added here.
4. Preserve _free_id, Prep folder/prompt/scouting/handoff, allowed-project checks, effort/model validation,
   first-step route/caps, drop_prep and fresh-session behavior. First step starts through ordinary advance.
5. At its successful non-chat manual boundary, the existing Task 9 wake runs; proposed later kinds appear
   in the digest, but actual next work comes from saved evidence and one validated decision.

No changes to `/api/run`, Hub.chat_task's chat semantics, ordinary Run as task, external-session routing or
Prep's router/scouting responsibilities. A live/replied plain chat does not wake simply because a policy is
present. Fred's Add next step converts it through request_next exactly as before; the first later non-chat
manual boundary is eligible. No skill tags or library loading are smuggled into intake.

## Tests first

- `test_supervised_intake_starts_one_manual_step_and_preserves_proposals`: multi-step fake Prep, task has
  exactly one running step, later proposals persisted/reloaded, no verify inserted, one ordinary worker start.
- `test_no_step_prep_gets_one_scout_and_full_goal_is_preserved`: full prompt/00-prep files retained, short
  step goal and no truncation of the canonical task prompt beyond existing GOAL_MAX behavior.
- `test_supervised_mode_precedence_is_explicit`: no mode -> configured project/global/default suggest;
  explicit auto/off stored and audited; unrelated ordinary intake cannot carry hidden override fields.
- `test_supervised_validation_preserves_project_model_and_money_gates`: disabled/gone project, bad effort,
  unknown model, invalid step, pace/Fable first-step hold, limits and pending guidance behavior.
- `test_ordinary_chain_and_chat_intake_are_unchanged`: same steps/routes/Prep ownership as baseline; chat
  turns never supervisor wakes, after explicit Add step a completed non-chat boundary wakes normally.
- `test_supervised_design_does_not_rebuild_a_tail`: saved design plan remains available, next step is one
  validated request_next reservation, not the whole proposed plan chain.

## Steps and acceptance

- [ ] 1. Intake tests red using existing fake Prep and TaskServerTest HTTP helpers.
- [ ] 2. Extend the existing route/function with keyword-only arguments and minimal branch; no new endpoint.
- [ ] 3. `py -m unittest tests.test_supervisor_server tests.test_server tests.test_prep tests.test_task_messages`;
      full suite. Commit: `feat: create manual supervised tasks from Prep (plan 44 backend T10)`.

**Drift guard:** one initial worker plus proposals is the whole intake feature; no parallel graph or extra Prep call.
