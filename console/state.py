"""Sessions -> agents -> steps, built from event records; states computed at snapshot time."""
import re
import time
from dataclasses import dataclass, field

from . import claude_cli, redact, usage as usage_mod

# state -> (symbol, text, tone). Colour never carries a state alone.
STATES = {
    "running": ("▶", "Running", "info"),
    "quiet": ("…", "Quiet", "info"),
    "stall": ("◷", "Stall?", "warning"),
    "stop": ("?", "STOP", "warning"),
    "blocked": ("■", "Blocked", "danger"),
    "failed": ("×", "Failed", "danger"),
    "replied": ("↩", "Replied", "info"),  # the turn ended with a plain reply: read it (replied_for_s, then Idle)
    "idle": ("○", "Idle", "info"),
    "stale": ("△", "Stale?", "warning"),
    "interrupted": ("‖", "Interrupted", "warning"),
    "done": ("✓", "Done", "success"),
    "verified": ("✓", "Verified", "success"),  # the last turn ended with VERDICT: PASS
    "verify_failed": ("×", "Verify failed", "danger"),
    "empty": ("◌", "Empty", "info"),  # opened, nothing sent: rules loaded and no prompt or step ever
    "lost": ("⊘", "Lost?", "info"),  # mid-turn, no event for stale_after_s: the chat was closed without a Stop
}
NEEDS_YOU = {"stop", "blocked", "stall", "failed", "interrupted", "verify_failed"}
DONE = {"done", "stale", "lost", "verified"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob", "WebFetch", "WebSearch"}  # main-chat reads: "should delegate"
HANDOFF_SKILL = "session-handoff"
SOURCES = {"claude-vscode": "vscode", "cli": "terminal", "claude-desktop": "desktop"}
MAX_STEPS = 500
MAX_TURNS = 200
SHOW_FOR_S = 86400
ACTIVITY_MIN = 30               # activity cells: one per minute, the last 30 minutes
ACTIVITY_STEPS = (1, 3, 6, 10)  # steps in a minute for levels 1-4 (Fred: 1-2, 3-5, 6-9, 10+)
BURN_S = 300                    # "$ / min now" is the estimated cost of the last 5 minutes / 5
_PASTED = re.compile(r"</?pasted_content[^>]*>")
_TAGGED = re.compile(r"<[A-Za-z]")  # an injected block the hook clipped before it closed: not a title
_FULL = re.compile(r"claude-(fable|opus|sonnet|haiku)-(\d+)(?:-(\d{1,2}))?(?:[-\[]|$)")  # a date or [1m] may follow


def norm_dir(path: str) -> str:
    """One spelling per folder: VS Code reports the drive as d:, terminals as D:."""
    if len(path) > 1 and path[1] == ":":
        return path[0].upper() + path[1:]
    return path


@dataclass
class Agent:
    id: str
    type: str = ""
    started_ts: float = 0.0
    last_ts: float = 0.0
    effort: str = ""
    model: str = ""
    tokens: int = 0
    steps: int = 0
    doing: str = ""
    done: bool = False
    verdict: str = ""


@dataclass
class Session:
    id: str
    started_ts: float = 0.0
    last_ts: float = 0.0
    project: str = ""
    project_dir: str = ""
    cwd: str = ""
    first_cwd: str = ""  # where the chat started: Claude Code files it under this folder (resume / fork)
    title: str = ""
    source: str = ""
    model: str = ""
    effort: str = ""
    route: str = ""
    prompts: int = 0
    in_turn: bool = False
    ended: bool = False
    doing: str = ""
    ctx_tokens: int = None
    compactions: int = 0
    stop_question: str = ""
    denied: dict = None
    failed: dict = None
    last_write_ts: float = 0.0
    agents: dict = field(default_factory=dict)
    steps: list = field(default_factory=list)
    window: bool = False
    run_live: bool = False
    interrupted: bool = False
    stopped: bool = False
    cost: float = 0.0
    route_reason: str = ""
    prep: str = ""
    prep_model: str = ""       # the Prep that wrote the prompt: its model, cost and turns (Route block)
    prep_cost: float = None
    prep_turns: int = 0
    start_commit: str = ""
    denials: list = field(default_factory=list)  # a run that still succeeded: shown as a note
    verdict: str = ""          # PASS / FAIL from the last VERDICT: line (verifier or main)
    verdict_detail: str = ""
    verdict_ts: float = 0.0    # when it arrived: a verdict older than the last turn's start is not about this turn
    reply: str = ""            # the start of the last reply (Stop hook), shown under Idle / Replied rows
    replied_ts: float = 0.0    # the last turn ended with a reply at this time (0: a turn is going or none ended)
    escalated: str = ""        # "sonnet/medium -> sonnet/high" once Escalate ran (once per task)
    escalated_ts: float = 0.0
    kind: str = ""             # the last window run: run, continue, verify, handoff, escalate
    handoff: bool = False      # a Handoff run is going
    handed_off: bool = False   # a Handoff run succeeded: Done
    handoff_by: str = ""       # the session whose last message is the handoff note (itself or its Handoff copy)
    forked_from: str = ""
    forks: list = field(default_factory=list)
    turns: list = field(default_factory=list)  # [start, end or None] per turn; the last start is turn_ts
    rules: dict = field(default_factory=dict)  # file -> {scope, lines, bytes}: CLAUDE.md / rules loaded
    reads: int = 0             # main-chat Read / Grep / Glob / WebFetch / WebSearch steps this turn
    chat_handoff: bool = False  # this turn ran /session-handoff inside the chat: its Stop makes it Done
    run_costs: list = field(default_factory=list)  # [ts, cost] per finished window run: exact spend
    transcript_path: str = ""  # read by usage.Usage for the estimated cost
    task: str = ""             # the task a step session belongs to (plan 17), for good
    step: int = 0              # its step number in that task


def is_empty(s: Session) -> bool:
    """A chat that loaded its rules and never got a prompt, a step, an agent or a Stop."""
    return not (s.turns or s.window or s.agents or s.failed or s.compactions or s.replied_ts
                or s.ctx_tokens is not None)


def shares(families: dict) -> list:
    """[[family, share of the cost]], biggest model first: the spend line and a session's Route block."""
    total = sum(families.values())
    if not total:
        return []
    rank = {m: i for i, m in enumerate(claude_cli.MODELS[::-1])}
    return [[m, round(c / total, 3)] for m, c in
            sorted(families.items(), key=lambda kv: (rank.get(kv[0], len(rank)), kv[0]))]


def midnight(now: float) -> float:
    """Local midnight before `now`: "today" for the spend figures."""
    t = time.localtime(now)
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


class State:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.sessions = {}

    def apply(self, rec: dict) -> None:
        sid = rec.get("session_id")
        if not sid:
            return
        ts = float(rec.get("ts") or 0)
        s = self.sessions.get(sid)
        if s is None:
            s = self.sessions[sid] = Session(id=sid, started_ts=ts)
        s.last_ts = max(s.last_ts, ts)
        for key in ("project", "project_dir", "cwd"):
            if rec.get(key):
                setattr(s, key, norm_dir(rec[key]) if key == "project_dir" else rec[key])
        if rec.get("cwd") and not s.first_cwd:
            s.first_cwd = rec["cwd"]
        if rec.get("transcript_path"):
            s.transcript_path = rec["transcript_path"]
        agent = None
        aid = rec.get("agent_id")
        if aid:
            agent = s.agents.get(aid)
            if agent is None:
                agent = s.agents[aid] = Agent(id=aid, started_ts=ts)
            agent.last_ts = ts
            if rec.get("agent_type"):
                agent.type = rec["agent_type"]
            if rec.get("effort"):
                agent.effort = rec["effort"]
        elif rec.get("effort"):
            s.effort = rec["effort"]

        event = rec.get("event")
        if event == "SessionStart":
            s.ended = False
            if rec.get("model"):
                s.model = rec["model"]
        elif event == "UserPromptSubmit":
            s.in_turn, s.ended = True, False
            s.prompts += 1
            text = redact.clip(_PASTED.sub(" ", rec.get("prompt", "")), 60)
            if not s.title and not _TAGGED.match(text):
                s.title = text
            s.denied = s.failed = None
            s.stop_question = ""
            s.interrupted = s.stopped = s.handed_off = False
            s.handoff_by = ""
            s.reads = 0
            s.reply, s.replied_ts = "", 0.0
            words = rec.get("prompt", "").split()
            s.chat_handoff = bool(words) and words[0] == "/" + HANDOFF_SKILL  # typed: no Skill step
            self._turn_open(s, ts)
        elif event == "PreToolUse":
            s.in_turn = True
            self._turn_open(s, ts)
            tool, what = rec.get("tool", ""), rec.get("what", "")
            self._step(s, ts, aid, tool, what)
            doing = f"{tool} {what}".strip()
            if agent:
                agent.doing = doing
                agent.steps += 1
            else:
                s.doing = doing
                s.reads += tool in READ_TOOLS
                if tool == "Skill" and what.split(":")[-1] == HANDOFF_SKILL:  # Claude ran the skill itself
                    s.chat_handoff = True
            if tool in WRITE_TOOLS:
                s.last_write_ts = ts
        elif event == "SubagentStop" and agent:
            agent.done = True
            agent.doing = ""
            agent.model = rec.get("model") or agent.model
            agent.tokens = rec.get("context_tokens") or agent.tokens
            if rec.get("verdict"):
                agent.verdict = rec["verdict"]
                self._verdict(s, rec, ts)
        elif event == "PermissionDenied":
            s.denied = {"tool": rec.get("tool", ""), "what": rec.get("what", ""),
                        "reason": rec.get("reason", ""), "ts": ts}
            self._step(s, ts, aid, rec.get("tool", ""), rec.get("what", ""), denied=True)
        elif event == "Stop":
            s.in_turn = False
            s.doing = ""
            self._turn_close(s, ts)
            s.model = rec.get("model") or s.model
            if rec.get("context_tokens") is not None:
                s.ctx_tokens = rec["context_tokens"]
            if rec.get("entrypoint") and not s.window:
                s.source = SOURCES.get(rec["entrypoint"], rec["entrypoint"])
            if rec.get("route"):
                s.route = rec["route"]
            s.stop_question = rec.get("stop_question", "")
            if rec.get("verdict"):
                self._verdict(s, rec, ts)
            s.reply, s.replied_ts = rec.get("reply", ""), ts
            if s.chat_handoff:  # /session-handoff ran in this turn: Done, like a window Handoff
                s.handed_off, s.chat_handoff, s.handoff_by = True, False, s.id
        elif event == "StopFailure":
            s.in_turn = False
            s.chat_handoff = False
            s.replied_ts = 0.0
            self._turn_close(s, ts)
            s.failed = {"error": rec.get("error", "unknown"), "details": rec.get("error_details", "")}
        elif event == "InstructionsLoaded" and not agent and rec.get("file"):
            s.rules[rec["file"]] = {"scope": rec.get("scope", ""), "lines": int(rec.get("lines") or 0),
                                    "bytes": int(rec.get("bytes") or 0)}
        elif event == "PostCompact":
            s.ctx_tokens = None
            s.compactions += 1
        elif event == "marked_done":  # Fred's Mark done; the chat's next prompt brings it back
            s.in_turn, s.ended, s.doing = False, True, ""
            self._turn_close(s, ts)
        elif event == "SessionEnd":
            s.in_turn = False
            self._turn_close(s, ts)
            s.ended = not s.window  # a window run's process ends after every turn; it can resume
        elif event == "run_started":
            s.window, s.run_live, s.source = True, True, "window"
            s.in_turn, s.ended = True, False
            self._turn_open(s, ts)
            s.interrupted = s.stopped = s.handed_off = False
            s.handoff_by = ""
            s.reply, s.replied_ts = "", 0.0
            s.denied = s.failed = None
            s.denials = []
            s.stop_question = ""
            s.kind = rec.get("kind") or "run"
            s.handoff = s.kind == "handoff"
            if rec.get("task"):
                s.task, s.step = rec["task"], int(rec.get("step") or 0)
            if rec.get("escalated"):
                s.escalated, s.escalated_ts = rec["escalated"], ts
            parent = self.sessions.get(rec.get("forked_from") or "")
            if parent and parent is not s:
                s.forked_from = parent.id
                if s.id not in parent.forks:
                    parent.forks.append(s.id)
                if not s.prompts:  # the copy carries the parent's context: same follow-up count
                    s.prompts, s.ctx_tokens = parent.prompts, parent.ctx_tokens
                if s.escalated:  # once per task, whichever copy escalated
                    parent.escalated, parent.escalated_ts = s.escalated, s.escalated_ts
                elif parent.escalated:
                    s.escalated, s.escalated_ts = parent.escalated, parent.escalated_ts
            if rec.get("title") and not s.title:
                s.title = redact.clip(rec["title"], 60)
            if rec.get("route"):
                s.route, s.route_reason = rec["route"], rec.get("reason", "")
            if rec.get("prep"):
                s.prep = rec["prep"]
                s.prep_model = rec.get("prep_model") or ""
                s.prep_cost = rec.get("prep_cost")
                s.prep_turns = int(rec.get("prep_turns") or 0)
            if rec.get("start_commit") and not s.start_commit:
                s.start_commit = rec["start_commit"]
            if rec.get("model") and not s.model:
                s.model = rec["model"]
        elif event == "run_ended":
            s.window, s.run_live, s.in_turn = True, False, False
            s.doing = ""
            self._turn_close(s, ts)
            s.cost += float(rec.get("cost") or 0)
            s.run_costs.append([ts, float(rec.get("cost") or 0)])
            s.stopped = bool(rec.get("stopped"))
            s.interrupted = bool(rec.get("interrupted"))
            if rec.get("subtype") == "success" and not (s.stopped or s.interrupted):
                s.replied_ts = ts
            if s.handoff and rec.get("subtype") == "success":
                s.handed_off, s.handoff_by = True, s.id
                parent = self.sessions.get(s.forked_from)
                if parent:
                    parent.handed_off, parent.handoff_by = True, s.id
            s.handoff = False
            if rec.get("denials") and rec.get("subtype") == "success":
                s.denials = [{"tool": d.get("tool", ""), "what": d.get("what", "")} for d in rec["denials"]]
            elif rec.get("denials") and not s.denied:
                first = rec["denials"][0]
                s.denied = {"tool": first.get("tool", ""), "what": first.get("what", ""),
                            "reason": "window runs cannot ask: open in terminal", "ts": ts}

    def _step(self, s, ts, aid, tool, what, denied=False):
        s.steps.append({"ts": ts, "agent": aid or "", "tool": tool, "what": what, "denied": denied})
        if len(s.steps) > MAX_STEPS:
            del s.steps[: len(s.steps) - MAX_STEPS]

    def _verdict(self, s, rec, ts):
        s.verdict, s.verdict_detail, s.verdict_ts = rec["verdict"], rec.get("verdict_detail", ""), ts
        parent = self.sessions.get(s.forked_from) if s.kind == "verify" else None
        if parent:  # a Verify copy judged the original chat: the original carries the verdict too
            parent.verdict, parent.verdict_detail, parent.verdict_ts = s.verdict, s.verdict_detail, ts

    def _turn_open(self, s, ts):
        if not s.turns or s.turns[-1][1] is not None:
            s.turns.append([ts, None])
            if len(s.turns) > MAX_TURNS:
                del s.turns[0]

    def _turn_close(self, s, ts):
        if s.turns and s.turns[-1][1] is None:
            s.turns[-1][1] = ts

    # -- snapshot -----------------------------------------------------------------
    def state_of(self, s: Session, now: float) -> str:
        if is_empty(s):
            return "empty"
        if s.ended or s.handed_off:
            return "done"
        if s.failed:
            return "failed"
        if s.denied:
            return "blocked"
        if s.interrupted:
            return "interrupted"
        age = now - s.last_ts
        if s.in_turn:
            if age >= self.cfg["stale_after_s"] and not s.run_live:  # a window run has its own process
                return "lost"
            if age >= self.cfg["stall_after_s"]:
                return "stall"
            if age >= self.cfg["quiet_after_s"]:
                return "quiet"
            return "running"
        if s.stop_question:
            return "stop"
        verdict = s.verdict if s.verdict_ts >= (s.turns[-1][0] if s.turns else 0.0) else ""  # about the last turn
        if verdict == "PASS":
            return "verified"
        if age >= self.cfg["stale_after_s"]:
            return "stale"
        if verdict == "FAIL":
            return "verify_failed"
        if s.replied_ts and now - s.replied_ts < self.cfg["replied_for_s"]:
            return "replied"
        return "idle"

    def gauge(self, tokens):
        """(fill, tone): fill is tokens / gauge_red_tokens, capped at 1.0.

        Token thresholds, not % of the window: the 5.x models have a 1M window, and a chat
        degrades long before it is full (Context Playbook)."""
        if tokens is None:
            return None, None
        red, yellow = self.cfg["gauge_red_tokens"], self.cfg["gauge_yellow_tokens"]
        fill = min(tokens / red, 1.0)
        if tokens >= red:
            return fill, "red"
        if tokens >= yellow:
            return fill, "yellow"
        return fill, "green"

    def writers(self, now: float) -> dict:
        """project -> session ids that wrote files in the last writers_window_s."""
        cutoff = now - self.cfg["writers_window_s"]
        by_project = {}
        for s in self.sessions.values():
            if not s.ended and s.last_write_ts >= cutoff and s.project_dir:
                by_project.setdefault(s.project_dir, []).append(s.id)
        return {p: ids for p, ids in by_project.items() if len(ids) >= 2}

    def files(self, s: Session) -> list:
        """The session's transcript and its agents' transcripts ([] until a hook line names it)."""
        if not s.transcript_path:
            return []
        return [s.transcript_path] + [usage_mod.agent_path(s.transcript_path, a) for a in s.agents]

    def transcripts(self, now: float) -> list:
        """Every transcript of the shown sessions: the hub reads them for the estimated cost."""
        return [f for s in self.sessions.values() if now - s.last_ts <= SHOW_FOR_S for f in self.files(s)]

    def activity(self, s: Session, now: float) -> list:
        """Tool steps (main + agents) per minute over the last ACTIVITY_MIN minutes, oldest first,
        as levels 0-4."""
        counts = [0] * ACTIVITY_MIN
        end = int(now // 60)
        for step in s.steps:
            back = end - int(step["ts"] // 60)
            if 0 <= back < ACTIVITY_MIN:
                counts[ACTIVITY_MIN - 1 - back] += 1
        return [sum(c >= t for t in ACTIVITY_STEPS) for c in counts]

    def versions(self) -> dict:
        """family -> the newest version seen in a full model id ("5.5"), from every session in memory; an alias
        alone says nothing, a family never seen is left out."""
        best = {}
        for s in self.sessions.values():
            m = _FULL.match(s.model or "")
            if m:
                v = (int(m.group(2)), int(m.group(3) or 0))
                best[m.group(1)] = max(best.get(m.group(1), v), v)
        return {fam: f"{a}.{b}" for fam, (a, b) in best.items()}

    def snapshot(self, now: float, usage=None, day=None) -> dict:
        """`usage` (a usage.Usage) adds the estimated cost; without it every estimate is 0. `day` is today's
        usage.History row ({cost, models}), the spend figure; without it the spend is 0."""
        cost = usage.cost if usage else (lambda files, since=0.0: 0.0)
        fams = usage.families if usage else (lambda files, since=0.0: {})
        writers = self.writers(now)
        writer_ids = {sid for ids in writers.values() for sid in ids}
        rows = []
        for s in sorted(self.sessions.values(), key=lambda x: x.started_ts):
            if now - s.last_ts > SHOW_FOR_S:
                continue
            state = self.state_of(s, now)
            pct, tone = self.gauge(s.ctx_tokens)
            if state == "empty":
                group = "empty"
            elif state in NEEDS_YOU or (tone == "red" and state not in DONE):
                group = "needs"
            elif state in DONE:
                group = "done"
            elif state == "replied":
                group = "replied"
            else:
                group = "working"
            symbol, text, state_tone = STATES[state]
            follow_ups = max(0, s.prompts - 1)
            files = self.files(s)
            exact = s.window and not s.run_live  # a live window run has no result line yet: estimate
            rows.append({
                "id": s.id, "project": s.project, "project_dir": s.project_dir,
                "title": s.title or ("Empty chat, nothing sent" if state == "empty" else f"(prompt not seen) {s.id[:8]}"), "source": s.source or "?",
                "model": s.model, "effort": s.effort, "route": s.route or "unrouted",
                "state": state, "symbol": symbol, "text": text, "tone": state_tone,
                "group": group, "doing": s.doing, "prompts": s.prompts,
                "ctx_tokens": s.ctx_tokens, "ctx_fill": None if pct is None else round(pct, 3),
                "ctx_tone": tone, "compactions": s.compactions,
                "stop_question": s.stop_question, "denied": s.denied, "failed": s.failed,
                "denials": s.denials,
                "two_writers": s.id in writer_ids,
                "window": s.window, "run_live": s.run_live, "stopped": s.stopped,
                "cost": round(s.cost, 4), "route_reason": s.route_reason, "prep": s.prep,
                "start_commit": s.start_commit, "cwd": s.cwd,
                "started_ts": s.started_ts, "last_ts": s.last_ts,
                "turn_ts": s.turns[-1][0] if s.turns else s.started_ts,
                "verdict": s.verdict, "verdict_detail": s.verdict_detail, "reply": s.reply, "escalated": s.escalated,
                "escalated_ts": s.escalated_ts,
                "prep_model": s.prep_model, "prep_cost": s.prep_cost, "prep_turns": s.prep_turns,
                "models": shares(fams(files)),
                "task": s.task, "step": s.step,
                "kind": s.kind, "handoff": s.handoff, "handoff_by": s.handoff_by if s.handed_off else "", "forked_from": s.forked_from, "forks": list(s.forks),
                "follow_ups": follow_ups,
                "handoff_hint": state not in DONE and (
                    tone == "red" or follow_ups >= self.cfg["handoff_after_followups"]),
                "rules": [dict(r, file=f) for f, r in s.rules.items()],
                "rules_bytes": sum(r["bytes"] for r in s.rules.values()),
                "rules_warn": self.rules_warn(s.rules),
                "reads": s.reads,
                "delegate_hint": state not in DONE and s.reads >= self.cfg["delegate_after_reads"],
                "spent": round(s.cost if exact else cost(files), 4) if exact or files else None,
                "spent_exact": exact,
                "burn": round(cost(files, now - BURN_S) / (BURN_S / 60), 4),
                "activity": self.activity(s, now),
                "main_steps": sum(1 for st in s.steps if not st["agent"]),
                "agents": [self._agent_row(a, s, cost, fams) for a in
                           sorted(s.agents.values(), key=lambda a: a.started_ts)],
            })
        shown = [self.sessions[r["id"]] for r in rows]
        return {
            "now": now,
            "sessions": rows,
            "writers": [{"project_dir": p, "sessions": ids} for p, ids in sorted(writers.items())],
            "counts": {g: sum(1 for r in rows if r["group"] == g) for g in ("needs", "replied", "working", "done", "empty")},
            "spend": self.spend(shown, now, usage, day),
            "projects": self.projects(shown, now, usage),
            "versions": self.versions(),
        }

    def rules_warn(self, rules: dict) -> str:
        """Why the loaded rules are too big ("" = fine): a file over rules_max_lines, or all of
        them together over rules_max_kb (docs: "target under 200 lines per CLAUDE.md file")."""
        max_lines, max_kb = self.cfg["rules_max_lines"], self.cfg["rules_max_kb"]
        out = [f"{name} {r['lines']} lines (over {max_lines})"
               for name, r in rules.items() if r["lines"] > max_lines]
        total = sum(r["bytes"] for r in rules.values()) / 1000
        if total > max_kb:
            out.append(f"{total:.1f} KB in all (over {max_kb} KB)")
        return "; ".join(out)

    def spend(self, sessions: list, now: float, usage=None, day=None) -> dict:
        """Today since local midnight: the Usage calendar's figure for today (`day`, list prices from every
        transcript, window runs included), so the main screen and the calendar always agree. The burn rate
        comes from the shown sessions' transcripts."""
        day = day or {}
        runs = sum(1 for s in sessions for ts, _ in s.run_costs if ts >= midnight(now))
        burn = 0.0
        if usage:
            burn = usage.cost([f for s in sessions for f in self.files(s)], now - BURN_S) / (BURN_S / 60)
        return {"today": round(float(day.get("cost") or 0), 4), "burn": round(burn, 4),
                "budget": self.cfg["daily_budget_usd"], "runs": runs, "models": shares(day.get("models") or {})}

    def day_cost(self, s: Session, start: float, usage=None) -> float:
        """What one session cost since `start`: a window session's finished runs (exact), else the
        transcript estimate (0 without a reader)."""
        if s.window:
            return sum(c for ts, c in s.run_costs if ts >= start)
        return usage.cost(self.files(s), start) if usage else 0.0

    def projects(self, shown: list, now: float, usage=None) -> list:
        """Every project a session ran in (also one older than SHOW_FOR_S): when it was last active and
        what today's shown sessions cost there. The window's project picker reads this."""
        start, today, found = midnight(now), {}, {}
        for s in shown:
            if s.project_dir:
                today[s.project_dir] = today.get(s.project_dir, 0.0) + self.day_cost(s, start, usage)
        for s in self.sessions.values():
            if s.project_dir:
                p = found.setdefault(s.project_dir, {"dir": s.project_dir, "name": s.project, "last_ts": 0.0})
                p["last_ts"] = max(p["last_ts"], s.last_ts)
                p["name"] = s.project or p["name"]
        return [dict(p, today=round(today.get(d, 0.0), 4)) for d, p in sorted(found.items())]

    def _agent_row(self, a: Agent, s: Session, cost=None, fams=None) -> dict:
        if a.done:
            symbol, text, tone = STATES["done"]
        elif s.in_turn:
            symbol, text, tone = STATES["running"]
        else:
            symbol, text, tone = "…", "No stop seen", "info"
        fill, ctx_tone = self.gauge(a.tokens or None)
        files = [usage_mod.agent_path(s.transcript_path, a.id)] if s.transcript_path else []
        spent = cost(files) if cost and files else 0.0
        seen = fams(files) if fams and files else {}  # a running agent: the model its transcript names
        model = a.model or (max(seen, key=seen.get) if seen else "")
        return {"id": a.id, "type": a.type or "agent", "model": model, "effort": a.effort,
                "tokens": a.tokens, "steps": a.steps, "doing": a.doing, "verdict": a.verdict,
                "cost": round(spent, 4),
                "symbol": symbol, "text": text, "tone": tone,
                "ctx_fill": None if fill is None else round(fill, 3), "ctx_tone": ctx_tone}

    def steps(self, session_id: str, limit: int = 200) -> list:
        s = self.sessions.get(session_id)
        if not s:
            return []
        types = {a.id: a.type for a in s.agents.values()}
        return [dict(step, agent_type=types.get(step["agent"], "") if step["agent"] else "main")
                for step in s.steps[-limit:]]
