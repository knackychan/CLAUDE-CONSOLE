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
    "idle": ("○", "Idle", "info"),
    "stale": ("△", "Stale?", "warning"),
    "interrupted": ("‖", "Interrupted", "warning"),
    "done": ("✓", "Done", "success"),
}
NEEDS_YOU = {"stop", "blocked", "stall", "failed", "interrupted"}
DONE = {"done", "stale"}
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
    start_commit: str = ""
    denials: list = field(default_factory=list)  # a run that still succeeded: shown as a note
    verdict: str = ""          # PASS / FAIL from the last VERDICT: line (verifier or main)
    verdict_detail: str = ""
    escalated: str = ""        # "sonnet/medium -> sonnet/high" once Escalate ran (once per task)
    kind: str = ""             # the last window run: run, continue, verify, handoff, escalate
    handoff: bool = False      # a Handoff run is going
    handed_off: bool = False   # a Handoff run succeeded: Done
    forked_from: str = ""
    forks: list = field(default_factory=list)
    turns: list = field(default_factory=list)  # [start, end or None] per turn, for the Timeline
    rules: dict = field(default_factory=dict)  # file -> {scope, lines, bytes}: CLAUDE.md / rules loaded
    reads: int = 0             # main-chat Read / Grep / Glob / WebFetch / WebSearch steps this turn
    chat_handoff: bool = False  # this turn ran /session-handoff inside the chat: its Stop makes it Done
    run_costs: list = field(default_factory=list)  # [ts, cost] per finished window run: exact spend
    transcript_path: str = ""  # read by usage.Usage for the estimated cost


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
            s.reads = 0
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
                self._verdict(s, rec)
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
                self._verdict(s, rec)
            if s.chat_handoff:  # /session-handoff ran in this turn: Done, like a window Handoff
                s.handed_off, s.chat_handoff = True, False
        elif event == "StopFailure":
            s.in_turn = False
            s.chat_handoff = False
            self._turn_close(s, ts)
            s.failed = {"error": rec.get("error", "unknown"), "details": rec.get("error_details", "")}
        elif event == "InstructionsLoaded" and not agent and rec.get("file"):
            s.rules[rec["file"]] = {"scope": rec.get("scope", ""), "lines": int(rec.get("lines") or 0),
                                    "bytes": int(rec.get("bytes") or 0)}
        elif event == "PostCompact":
            s.ctx_tokens = None
            s.compactions += 1
        elif event == "SessionEnd":
            s.in_turn = False
            self._turn_close(s, ts)
            s.ended = not s.window  # a window run's process ends after every turn; it can resume
        elif event == "run_started":
            s.window, s.run_live, s.source = True, True, "window"
            s.in_turn, s.ended = True, False
            self._turn_open(s, ts)
            s.interrupted = s.stopped = s.handed_off = False
            s.denied = s.failed = None
            s.denials = []
            s.stop_question = ""
            s.kind = rec.get("kind") or "run"
            s.handoff = s.kind == "handoff"
            if rec.get("escalated"):
                s.escalated = rec["escalated"]
            parent = self.sessions.get(rec.get("forked_from") or "")
            if parent and parent is not s:
                s.forked_from = parent.id
                if s.id not in parent.forks:
                    parent.forks.append(s.id)
                if not s.prompts:  # the copy carries the parent's context: same follow-up count
                    s.prompts, s.ctx_tokens = parent.prompts, parent.ctx_tokens
                if s.escalated:
                    parent.escalated = s.escalated  # once per task, whichever copy escalated
                elif parent.escalated:
                    s.escalated = parent.escalated
            if rec.get("title") and not s.title:
                s.title = redact.clip(rec["title"], 60)
            if rec.get("route"):
                s.route, s.route_reason = rec["route"], rec.get("reason", "")
            if rec.get("prep"):
                s.prep = rec["prep"]
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
            if s.handoff and rec.get("subtype") == "success":
                s.handed_off = True
                parent = self.sessions.get(s.forked_from)
                if parent:
                    parent.handed_off = True
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

    def _verdict(self, s, rec):
        s.verdict, s.verdict_detail = rec["verdict"], rec.get("verdict_detail", "")

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
            if age >= self.cfg["stall_after_s"]:
                return "stall"
            if age >= self.cfg["quiet_after_s"]:
                return "quiet"
            return "running"
        if s.stop_question:
            return "stop"
        if age >= self.cfg["stale_after_s"]:
            return "stale"
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

    def snapshot(self, now: float, usage=None) -> dict:
        """`usage` (a usage.Usage) adds the estimated cost; without it every estimate is 0."""
        cost = usage.cost if usage else (lambda files, since=0.0: 0.0)
        writers = self.writers(now)
        writer_ids = {sid for ids in writers.values() for sid in ids}
        rows = []
        for s in sorted(self.sessions.values(), key=lambda x: x.started_ts):
            if now - s.last_ts > SHOW_FOR_S:
                continue
            state = self.state_of(s, now)
            pct, tone = self.gauge(s.ctx_tokens)
            if state in NEEDS_YOU or (tone == "red" and state not in DONE):
                group = "needs"
            elif state in DONE:
                group = "done"
            else:
                group = "working"
            symbol, text, state_tone = STATES[state]
            follow_ups = max(0, s.prompts - 1)
            files = self.files(s)
            exact = s.window and not s.run_live  # a live window run has no result line yet: estimate
            rows.append({
                "id": s.id, "project": s.project, "project_dir": s.project_dir,
                "title": s.title or f"(prompt not seen) {s.id[:8]}", "source": s.source or "?",
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
                "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated,
                "kind": s.kind, "handoff": s.handoff, "forked_from": s.forked_from, "forks": list(s.forks),
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
                "agents": [self._agent_row(a, s, cost) for a in
                           sorted(s.agents.values(), key=lambda a: a.started_ts)],
            })
        shown = [self.sessions[r["id"]] for r in rows]
        return {
            "now": now,
            "sessions": rows,
            "writers": [{"project_dir": p, "sessions": ids} for p, ids in sorted(writers.items())],
            "counts": {g: sum(1 for r in rows if r["group"] == g) for g in ("needs", "working", "done")},
            "spend": self.spend(shown, now, usage),
            "projects": self.projects(shown, now, usage),
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

    def spend(self, sessions: list, now: float, usage=None) -> dict:
        """Today since local midnight: exact = finished window runs (their result line), estimated =
        the other sessions' transcripts; the model shares and the burn rate come from all transcripts."""
        start = midnight(now)
        exact = sum(c for s in sessions for ts, c in s.run_costs if ts >= start)
        runs = sum(1 for s in sessions for ts, _ in s.run_costs if ts >= start)
        every = [f for s in sessions for f in self.files(s)]
        estimated = burn = 0.0
        families = {}
        if usage:
            estimated = sum(self.day_cost(s, start, usage) for s in sessions if not s.window)
            burn = usage.cost(every, now - BURN_S) / (BURN_S / 60)
            families = usage.families(every, start)
        total = sum(families.values())
        rank = {m: i for i, m in enumerate(claude_cli.MODELS[::-1])}  # biggest first
        models = [[m, round(c / total, 3)] for m, c in
                  sorted(families.items(), key=lambda kv: (rank.get(kv[0], len(rank)), kv[0]))]
        return {"today": round(exact + estimated, 4), "exact": round(exact, 4),
                "estimated": round(estimated, 4), "burn": round(burn, 4),
                "budget": self.cfg["daily_budget_usd"], "runs": runs, "models": models}

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

    def _agent_row(self, a: Agent, s: Session, cost=None) -> dict:
        if a.done:
            symbol, text, tone = STATES["done"]
        elif s.in_turn:
            symbol, text, tone = STATES["running"]
        else:
            symbol, text, tone = "…", "No stop seen", "info"
        fill, ctx_tone = self.gauge(a.tokens or None)
        spent = cost([usage_mod.agent_path(s.transcript_path, a.id)]) if cost and s.transcript_path else 0.0
        return {"id": a.id, "type": a.type or "agent", "model": a.model, "effort": a.effort,
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

    def timeline(self, session_id: str, now: float):
        """Bars over time (D7 C): the main thread's turns, then one bar per agent run."""
        s = self.sessions.get(session_id)
        if not s:
            return None
        live = s.in_turn or s.run_live
        end = now if live else s.last_ts
        lanes = [{"label": "main", "tone": "info", "verdict": "",
                  "spans": [[a, end if b is None else b] for a, b in s.turns]}]
        for a in sorted(s.agents.values(), key=lambda x: x.started_ts):
            stop = a.last_ts if a.done or not live else end
            lanes.append({"label": a.type or "agent", "tone": "success" if a.done else "info",
                          "verdict": a.verdict, "spans": [[a.started_ts, stop]]})
        start = min([s.started_ts] + [sp[0] for lane in lanes for sp in lane["spans"]])
        return {"start": start, "end": max(end, start), "lanes": lanes}
