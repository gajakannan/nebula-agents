"""Keyboard-operable stdlib curses cockpit over application projections."""

from __future__ import annotations

import curses
from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from typing import Any, Callable

from .formatters import MAX_LIST_RECORDS, clean_text, recovery_view_data, status_marker, to_data
from .interop import current_actor, enum_member, invoke, launch_request


class Screen(str, Enum):
    SESSIONS = "sessions"
    DETAIL = "detail"
    GATE = "gate"
    EVIDENCE = "evidence"
    HELP = "help"
    CONFIRM = "confirm"


@dataclass(slots=True)
class PendingAction:
    label: str
    run_id: str
    revision: int | None
    evidence_summary: str
    callback: Callable[[], object]


@dataclass(slots=True)
class CockpitState:
    screen: Screen = Screen.SESSIONS
    previous_screen: Screen = Screen.SESSIONS
    selection: int = 0
    selected_run_id: str | None = None
    sessions: list[dict[str, Any]] | None = None
    detail: dict[str, Any] | None = None
    evidence: dict[str, Any] | list[Any] | None = None
    transcript_preview: dict[str, Any] | None = None
    message: str = ""
    pending: PendingAction | None = None


class CockpitUI:
    """Stateful renderer; all enforcement remains inside called services."""

    def __init__(self, application: object, initial_run_id: str | None = None) -> None:
        self.application = application
        self.state = CockpitState(selected_run_id=initial_run_id)

    def run(self, window: Any) -> int:
        self._configure(window)
        self._refresh_data(open_initial=True)
        while True:
            self._render(window)
            try:
                key = window.getch()
            except KeyboardInterrupt:
                return 130
            if key == -1:
                self._timeout_refresh()
                continue
            if self._handle_key(window, key):
                return 0

    def _configure(self, window: Any) -> None:
        window.keypad(True)
        window.timeout(500)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_CYAN, -1)

    def _refresh_data(self, *, open_initial: bool = False) -> None:
        remembered = self.state.selected_run_id
        try:
            records = invoke(
                self.application.queries.sessions,
                status=None,
                actor=current_actor(self.application),
                limit=MAX_LIST_RECORDS,
            )
            data = to_data(records)
            if isinstance(data, dict):
                data = next((data[key] for key in ("sessions", "runs", "items") if isinstance(data.get(key), list)), [])
            self.state.sessions = [record for record in data if isinstance(record, dict)][:MAX_LIST_RECORDS] if isinstance(data, list) else []
            recovery_candidates = getattr(self.application.queries, "recovery_candidates", None)
            if callable(recovery_candidates):
                candidates = to_data(
                    invoke(
                        recovery_candidates,
                        actor=current_actor(self.application),
                    )
                )
                if isinstance(candidates, dict):
                    candidates = next(
                        (
                            candidates[key]
                            for key in ("candidates", "recoveries", "items")
                            if isinstance(candidates.get(key), list)
                        ),
                        [],
                    )
                if isinstance(candidates, list):
                    self._merge_recovery_candidates(candidates)
            if remembered:
                match = next((index for index, record in enumerate(self.state.sessions) if record.get("run_id") == remembered), None)
                if match is not None:
                    self.state.selection = match
                elif open_initial:
                    self.state.message = f"Run {remembered} was not found."
                    self.state.selected_run_id = None
            self._select_current()
            if open_initial and remembered and self.state.selected_run_id:
                self.state.screen = Screen.DETAIL
            if self.state.screen in {Screen.DETAIL, Screen.GATE, Screen.EVIDENCE, Screen.CONFIRM}:
                self._load_selected()
        except Exception as error:
            self.state.message = _safe_error(error)

    def _merge_recovery_candidates(self, candidates: list[Any]) -> None:
        sessions = self.state.sessions or []
        by_run_id = {record.get("run_id"): record for record in sessions if record.get("run_id")}
        recovery_rows: list[dict[str, Any]] = []
        for candidate in candidates[:MAX_LIST_RECORDS]:
            normalized = recovery_view_data(candidate)
            if not normalized:
                continue
            existing = by_run_id.get(normalized["run_id"])
            if existing is not None:
                existing.update(normalized)
                recovery_rows.append(existing)
                continue
            recovery_rows.append(normalized)
            by_run_id[normalized["run_id"]] = normalized
        recovery_ids = {record["run_id"] for record in recovery_rows}
        self.state.sessions = (
            recovery_rows
            + [record for record in sessions if record.get("run_id") not in recovery_ids]
        )[:MAX_LIST_RECORDS]

    def _select_current(self) -> None:
        sessions = self.state.sessions or []
        if not sessions:
            self.state.selection = 0
            if self.state.screen is Screen.SESSIONS:
                self.state.selected_run_id = None
            return
        self.state.selection = max(0, min(self.state.selection, len(sessions) - 1))
        self.state.selected_run_id = str(sessions[self.state.selection].get("run_id") or "") or None

    def _load_selected(self) -> None:
        run_id = self.state.selected_run_id
        if not run_id:
            self.state.detail = None
            self.state.evidence = None
            self.state.transcript_preview = None
            return
        previous_run_id = (self.state.detail or {}).get("run_id")
        actor = current_actor(self.application)
        selected = next(
            (record for record in self.state.sessions or [] if record.get("run_id") == run_id),
            {},
        )
        if selected.get("is_recovery_candidate") is True:
            recovery_status = getattr(self.application.queries, "recovery_status", None)
            candidate = selected
            if callable(recovery_status):
                candidate_data = to_data(invoke(recovery_status, run_id=run_id, actor=actor))
                if isinstance(candidate_data, dict):
                    candidate = candidate_data
            self.state.detail = recovery_view_data(candidate)
            self.state.evidence = []
            self.state.transcript_preview = None
            return
        detail = invoke(self.application.queries.status, run_id=run_id, actor=actor)
        evidence = invoke(self.application.queries.evidence, run_id=run_id, actor=actor)
        detail_data = to_data(detail)
        evidence_data = to_data(evidence)
        self.state.detail = detail_data if isinstance(detail_data, dict) else {"value": detail_data}
        self.state.evidence = evidence_data if isinstance(evidence_data, (dict, list)) else {"value": evidence_data}
        transcript = self.state.detail.get("transcript", {})
        transcript_status = transcript.get("status") if isinstance(transcript, dict) else None
        if previous_run_id != run_id or str(transcript_status).lower() != "completed":
            self.state.transcript_preview = None

    def _timeout_refresh(self) -> None:
        """Reconcile the selected run on the 500 ms poll without moving selection."""

        if self.state.screen is Screen.CONFIRM:
            # Never advance a revision behind an explicit confirmation screen.
            return
        run_id = self.state.selected_run_id
        if run_id and self._selected_projection().get("is_recovery_candidate") is not True:
            try:
                invoke(
                    self.application.runs.reconcile,
                    run_id=run_id,
                    actor=current_actor(self.application),
                )
            except Exception as error:
                self.state.message = _safe_error(error)
        self._refresh_data()

    def _handle_key(self, window: Any, key: int) -> bool:
        if key in (ord("q"), ord("Q")):
            return True
        if key == curses.KEY_RESIZE:
            return False
        if key == ord("?"):
            self._switch(Screen.HELP)
            return False
        if key in (27, curses.KEY_BACKSPACE, 127, ord("b")):
            self.state.screen = Screen.SESSIONS if self.state.screen in {Screen.DETAIL, Screen.HELP} else Screen.DETAIL
            self.state.pending = None
            return False
        if self.state.screen is Screen.CONFIRM:
            return self._handle_confirmation(window, key)
        if self.state.screen is Screen.GATE:
            self._handle_gate_key(window, key)
            return False
        if key in (curses.KEY_DOWN, ord("j")) and self.state.screen is Screen.SESSIONS:
            self.state.selection += 1
            self._select_current()
        elif key in (curses.KEY_UP, ord("k")) and self.state.screen is Screen.SESSIONS:
            self.state.selection -= 1
            self._select_current()
        elif key in (curses.KEY_ENTER, 10, 13) and self.state.screen is Screen.SESSIONS and self.state.selected_run_id:
            self._switch(Screen.DETAIL)
            self._load_selected_safely()
        elif key == ord("R") and self.state.selected_run_id:
            self._confirm("Reconcile recorded tmux session", self._reconcile)
        elif key == ord("r"):
            self._refresh_data()
            self.state.message = "View refreshed."
        elif key == ord("a") and self.state.selected_run_id and self._can_attach():
            self._confirm("Attach to recorded tmux session", self._attach)
        elif key == ord("x") and self.state.selected_run_id and self._can_recover():
            self._confirm("Recover persisted run state", self._recover)
        elif key == ord("v") and self.state.selected_run_id:
            validator = (self._prompt(window, "Validator [stories]: ") or "stories").lower()
            if validator not in {"stories", "trackers", "templates"}:
                self.state.message = "Validator must be stories, trackers, or templates."
            else:
                self._confirm(f"Run {validator} validator", lambda: self._validate(validator))
        elif key == ord("g") and self.state.selected_run_id:
            self._switch(Screen.GATE)
            self._load_selected_safely()
        elif key == ord("t") and self.state.selected_run_id:
            transcript = (self.state.detail or {}).get("transcript", {})
            status = transcript.get("status") if isinstance(transcript, dict) else None
            if str(status).lower() == "disabled" and self._can_configure_transcript():
                self._confirm("Enable redact-before-write transcript", self._enable_transcript)
            else:
                self._switch(Screen.EVIDENCE)
                self._load_selected_safely()
                if str(status).lower() == "completed":
                    self._load_transcript_preview_safely()
        elif key == ord("c") and self.state.screen is Screen.EVIDENCE and self._transcript_status() == "active" and self._can_configure_transcript():
            self._confirm("Complete and disable transcript capture", self._complete_transcript)
        elif key == ord("e") and self.state.screen is Screen.EVIDENCE and self._transcript_status() in {"disabled", "failed"} and self._can_configure_transcript():
            label = "Retry redact-before-write transcript" if self._transcript_status() == "failed" else "Enable redact-before-write transcript"
            self._confirm(label, self._enable_transcript)
        elif key == ord("p") and self.state.screen is Screen.EVIDENCE and self._transcript_status() == "completed":
            self._load_transcript_preview_safely()
        elif key == ord("l"):
            self._prepare_launch(window)
        return False

    def _handle_confirmation(self, window: Any, key: int) -> bool:
        if key in (ord("n"), ord("N"), 27):
            self.state.screen = self.state.previous_screen
            self.state.pending = None
        elif key in (ord("y"), ord("Y"), curses.KEY_ENTER, 10, 13) and self.state.pending:
            pending = self.state.pending
            try:
                if pending.label.startswith("Attach"):
                    curses.endwin()
                result = pending.callback()
                self.state.message = f"Completed: {pending.label}."
                if isinstance(result, int) and result not in (0,):
                    self.state.message = f"{pending.label} returned {result}."
            except Exception as error:
                self.state.message = _safe_error(error)
            self.state.pending = None
            self.state.screen = Screen.DETAIL if self.state.selected_run_id else Screen.SESSIONS
            self._refresh_data()
            window.refresh()
        return False

    def _handle_gate_key(self, window: Any, key: int) -> None:
        if key == ord("p"):
            if self._gate_approval_available():
                self._confirm("Approve current gate", lambda: self._decide_gate("Approve", None))
            else:
                self.state.message = "Approval is unavailable until evidence and validation are ready."
        elif key == ord("h"):
            if self._can_decide_gate():
                reason = self._prompt(window, "Hold reason: ")
                if reason:
                    self._confirm("Hold current gate", lambda: self._decide_gate("Hold", reason))
        elif key == ord("u"):
            if self._can_decide_gate():
                self._confirm("Resume held gate", self._resume_gate)
        elif key == ord("v"):
            validator = (self._prompt(window, "Validator [stories]: ") or "stories").lower()
            if validator in {"stories", "trackers", "templates"}:
                self._confirm(f"Run {validator} validator", lambda: self._validate(validator))
            else:
                self.state.message = "Validator must be stories, trackers, or templates."

    def _confirm(self, label: str, callback: Callable[[], object]) -> None:
        detail = self.state.detail or {}
        revision = detail.get("revision") if isinstance(detail.get("revision"), int) else None
        artifacts = _artifact_list(self.state.evidence)
        ready = sum(1 for artifact in artifacts if str(artifact.get("status", "")).lower() == "available")
        self.state.pending = PendingAction(
            label=label,
            run_id=self.state.selected_run_id or "new run",
            revision=revision,
            evidence_summary=f"{ready}/{len(artifacts)} observed artifact(s) available",
            callback=callback,
        )
        self.state.previous_screen = self.state.screen
        self.state.screen = Screen.CONFIRM

    def _attach(self) -> object:
        return invoke(
            self.application.runs.attach,
            run_id=self.state.selected_run_id,
            actor=current_actor(self.application),
        )

    def _validate(self, validator: str) -> object:
        return invoke(
            self.application.gates.run_validator,
            run_id=self.state.selected_run_id,
            key=enum_member("ValidatorKey", validator),
            actor=current_actor(self.application),
        )

    def _enable_transcript(self) -> object:
        return invoke(
            self.application.transcripts.enable,
            run_id=self.state.selected_run_id,
            actor=current_actor(self.application),
            expected_revision=self._revision(),
        )

    def _complete_transcript(self) -> object:
        return invoke(
            self.application.transcripts.complete,
            run_id=self.state.selected_run_id,
            actor=current_actor(self.application),
            expected_revision=self._revision(),
        )

    def _preview_transcript(self) -> object:
        projection = invoke(
            self.application.transcripts.preview,
            run_id=self.state.selected_run_id,
            actor=current_actor(self.application),
        )
        data = to_data(projection)
        if not isinstance(data, dict):
            raise RuntimeError("Transcript preview projection is unavailable.")
        self.state.transcript_preview = data
        return projection

    def _load_transcript_preview_safely(self) -> None:
        try:
            self._preview_transcript()
            self.state.message = "Safe redacted transcript preview refreshed."
        except Exception as error:
            self.state.transcript_preview = None
            self.state.message = _safe_error(error)

    def _transcript_status(self) -> str:
        transcript = (self.state.detail or {}).get("transcript", {})
        value = transcript.get("status") if isinstance(transcript, dict) else None
        return str(value or "unknown").lower()

    def _reconcile(self) -> object:
        return invoke(
            self.application.runs.reconcile,
            run_id=self.state.selected_run_id,
            actor=current_actor(self.application),
        )

    def _recover(self) -> object:
        detail = self.state.detail or {}
        revision = detail.get("recoverable_revision", detail.get("revision"))
        return invoke(
            self.application.runs.recover,
            run_id=self.state.selected_run_id,
            actor=current_actor(self.application),
            expected_revision=revision if isinstance(revision, int) else None,
        )

    def _decide_gate(self, decision: str, reason: str | None) -> object:
        models = import_module("nebula_agents.domain.models")
        request_type = getattr(models, "GateDecisionRequest")
        gate = (self.state.detail or {}).get("gate", {})
        gate_id = gate.get("gate_id") if isinstance(gate, dict) else None
        if not gate_id:
            raise RuntimeError("No current gate is available.")
        request = request_type(
            run_id=self.state.selected_run_id,
            gate_id=gate_id,
            decision=enum_member("DecisionKind", decision),
            reason=reason,
            display_label=None,
            expected_revision=self._revision(),
            confirmed=decision == "Approve",
        )
        return invoke(self.application.gates.decide, request=request, actor=current_actor(self.application))

    def _resume_gate(self) -> object:
        return invoke(
            self.application.gates.resume,
            run_id=self.state.selected_run_id,
            actor=current_actor(self.application),
            expected_revision=self._revision(),
        )

    def _revision(self) -> int:
        revision = (self.state.detail or {}).get("revision")
        if not isinstance(revision, int):
            raise RuntimeError("Current run revision is unavailable; refresh before mutating.")
        return revision

    def _gate_approval_available(self) -> bool:
        detail = self.state.detail or {}
        gate = detail.get("gate", {})
        validator = detail.get("latest_validator", {})
        if not self._can_decide_gate() or not isinstance(gate, dict) or str(gate.get("status", "")).lower() != "pending":
            return False
        if not gate.get("evidence_ready") or not isinstance(validator, dict):
            return False
        return validator.get("exit_code") == 0

    def _selected_projection(self) -> dict[str, Any]:
        detail = self.state.detail or {}
        if detail.get("run_id") == self.state.selected_run_id:
            return detail
        for record in self.state.sessions or []:
            if record.get("run_id") == self.state.selected_run_id:
                return record
        return {}

    def _can_attach(self) -> bool:
        projection = self._selected_projection()
        return projection.get("can_attach") is True and isinstance(projection.get("tmux_session"), str)

    def _can_recover(self) -> bool:
        projection = self._selected_projection()
        return projection.get("can_recover") is True and projection.get("recovery_available") is True

    def _can_decide_gate(self) -> bool:
        return self._selected_projection().get("can_decide_gate") is True

    def _can_configure_transcript(self) -> bool:
        return self._selected_projection().get("can_configure_transcript") is True

    def _next_gate_action(self, gate: dict[str, Any], validator: dict[str, Any]) -> str:
        status = str(gate.get("status", "Unknown")).lower()
        if status in {"unknown", "blocked"}:
            return "refresh/reconcile blocked state"
        if status == "held":
            return "resume when hold is resolved"
        if status == "approved":
            return "await next lifecycle stage"
        if not gate.get("evidence_ready"):
            return "provide required evidence"
        if validator.get("exit_code") != 0:
            return "run a required validator"
        return "approve or hold explicitly"

    def _prepare_launch(self, window: Any) -> None:
        feature = self._prompt(window, "Feature [F0001]: ") or "F0001"
        provider = (self._prompt(window, "Provider [codex]: ") or "codex").lower()
        action = (self._prompt(window, "Action [feature]: ") or "feature").lower()
        story = self._prompt(window, "Story (optional): ") or None
        values = {
            "feature": feature,
            "provider": provider,
            "action": action,
            "story": story,
            "run_id": None,
            "label": None,
            "transcript": False,
            "expected_revision": None,
        }

        def perform() -> object:
            return invoke(
                self.application.runs.launch,
                request=launch_request(values),
                actor=current_actor(self.application),
            )

        self.state.selected_run_id = None
        self._confirm(f"Launch {feature} with {provider}/{action}", perform)

    def _prompt(self, window: Any, label: str) -> str:
        height, width = window.getmaxyx()
        row = max(0, height - 2)
        try:
            curses.echo()
            curses.curs_set(1)
            window.move(row, 0)
            window.clrtoeol()
            _safe_add(window, row, 0, label, curses.A_BOLD, max(width - 1, 1))
            window.refresh()
            raw = window.getstr(row, min(len(label), max(width - 1, 0)), 80)
            return clean_text(raw.decode("utf-8", errors="replace"), single_line=True).strip()
        finally:
            curses.noecho()
            try:
                curses.curs_set(0)
            except curses.error:
                pass

    def _switch(self, screen: Screen) -> None:
        self.state.previous_screen = self.state.screen
        self.state.screen = screen

    def _load_selected_safely(self) -> None:
        try:
            self._load_selected()
        except Exception as error:
            self.state.message = _safe_error(error)

    def _render(self, window: Any) -> None:
        window.erase()
        height, width = window.getmaxyx()
        if height < 12 or width < 40:
            _safe_add(window, 0, 0, "Nebula Agents Cockpit", curses.A_BOLD, max(width - 1, 1))
            _safe_add(window, 2, 0, "Terminal is too small; resize to at least 40x12.", 0, max(width - 1, 1))
            _safe_add(window, max(height - 1, 0), 0, "q quit", 0, max(width - 1, 1))
            window.refresh()
            return
        _safe_add(window, 0, 0, "Nebula Agents Cockpit", curses.A_BOLD | _color(3), width - 1)
        _safe_add(window, 1, 0, f"View: {self.state.screen.value}", curses.A_DIM, width - 1)
        if self.state.screen is Screen.SESSIONS:
            self._render_sessions(window, height, width)
        elif self.state.screen is Screen.DETAIL:
            self._render_detail(window, height, width)
        elif self.state.screen is Screen.GATE:
            self._render_gate(window, height, width)
        elif self.state.screen is Screen.EVIDENCE:
            self._render_evidence(window, height, width)
        elif self.state.screen is Screen.HELP:
            self._render_help(window, height, width)
        elif self.state.screen is Screen.CONFIRM:
            self._render_confirm(window, height, width)
        if self.state.message:
            _safe_add(window, height - 2, 0, self.state.message, curses.A_DIM, width - 1)
        if self.state.screen is Screen.EVIDENCE:
            transcript_controls = ""
            if self._can_configure_transcript():
                transcript_controls = "e enable/retry  c complete/disable  "
            footer = f"{transcript_controls}p safe preview  r refresh  R reconcile  Esc back  q quit"
        elif self.state.screen is Screen.GATE:
            decision_controls = "p approve  h hold  u resume  " if self._can_decide_gate() else ""
            footer = f"{decision_controls}v validate  r refresh  R reconcile  Esc back  q quit"
        else:
            attach_control = "a attach  " if self._can_attach() else ""
            recovery_control = "x recover  " if self._can_recover() else ""
            footer = f"j/k move  Enter inspect  l launch  {attach_control}{recovery_control}v validate  g gate  t transcript  r refresh  R reconcile  ? help  q quit"
        _safe_add(window, height - 1, 0, footer, curses.A_REVERSE, width - 1)
        window.refresh()

    def _render_sessions(self, window: Any, height: int, width: int) -> None:
        rows = self.state.sessions or []
        if not rows:
            _safe_add(window, 3, 2, "No recorded sessions.", 0, width - 3)
            return
        _safe_add(window, 3, 1, "RUN ID              PROVIDER  STATUS                 GATE", curses.A_BOLD, width - 2)
        for offset, record in enumerate(rows[: max(height - 7, 1)]):
            selected = offset == self.state.selection
            gate = record.get("gate", {})
            gate_status = gate.get("status", "-") if isinstance(gate, dict) else "-"
            text = (
                f"{str(record.get('run_id', '-')):<20} "
                f"{str(record.get('provider_key', '-')):<9} "
                f"{status_marker(record.get('status', 'Unknown')):<22} "
                f"{gate_status}"
            )
            attribute = curses.A_REVERSE if selected else _status_color(record.get("status"))
            _safe_add(window, 4 + offset, 1, text, attribute, width - 2)

    def _render_detail(self, window: Any, height: int, width: int) -> None:
        detail = self.state.detail or {}
        gate = detail.get("last_gate", detail.get("gate", {}))
        if isinstance(gate, dict):
            last_gate = " / ".join(
                str(value)
                for value in (gate.get("gate_id"), gate.get("status"))
                if value is not None
            ) or "-"
        else:
            last_gate = str(gate) if gate is not None else "-"
        rows = [
            ("Run", detail.get("run_id")),
            ("Feature / story", f"{detail.get('feature_id', '-')} / {detail.get('story_id') or '-'}"),
            ("Provider", detail.get("provider_key")),
            ("Status", status_marker(detail.get("status", "Unknown"))),
            ("Revision", detail.get("revision")),
            ("Recovery status", "Available" if detail.get("recovery_available") is True else "Not available"),
            ("Recovery action", "Press x to recover with confirmation" if self._can_recover() else "Unavailable"),
            ("Last gate", last_gate),
            ("Last audit event", _audit_event_summary(detail.get("last_audit_event"))),
            ("Transcript path", _transcript_path(detail)),
            ("Recovery command", detail.get("recovery_command") or "-"),
            ("Updated", detail.get("updated_at")),
            ("Last seen", detail.get("last_seen_at")),
        ]
        if self._can_attach():
            rows.extend(
                [
                    ("Session", detail.get("tmux_session")),
                    ("Attach", f"nebula-agents attach --run-id {detail.get('run_id')}"),
                ]
            )
        for index, (label, value) in enumerate(rows[: max(height - 8, 1)]):
            _safe_add(window, 3 + index, 2, f"{label:<16} {value if value is not None else '-'}", 0, width - 3)

    def _render_gate(self, window: Any, height: int, width: int) -> None:
        gate = (self.state.detail or {}).get("gate", {})
        if not isinstance(gate, dict):
            gate = {}
        decision = gate.get("decision", {}) if isinstance(gate.get("decision"), dict) else {}
        validator = (self.state.detail or {}).get("latest_validator", {})
        if not isinstance(validator, dict):
            validator = {}
        decision_actor = decision.get("actor", {}) if isinstance(decision.get("actor"), dict) else {}
        rows = [
            ("Gate", gate.get("gate_id") or "No active gate"),
            ("Status", status_marker(gate.get("status", "Unknown"))),
            ("Evidence ready", "yes" if gate.get("evidence_ready") else "no"),
            ("Required", ", ".join(gate.get("required_evidence", [])) or "-"),
            ("Last decision", decision.get("decision") or "-"),
            ("Decision reason", decision.get("reason") or "-"),
            ("Decision by", decision_actor.get("display_label") or decision_actor.get("username") or "-"),
            ("Decision at", decision.get("decided_at") or "-"),
            ("Validator", validator.get("validator_key") or "-"),
            ("Command", validator.get("command_template") or "-"),
            ("Validator exit", validator.get("exit_code") if validator else "-"),
            ("Validator at", validator.get("completed_at") or "-"),
            ("Summary", validator.get("summary") or "-"),
        ]
        if validator.get("artifact_path"):
            rows.append(("Evidence path", validator["artifact_path"]))
        rows.append(("Next action", self._next_gate_action(gate, validator)))
        for index, (label, value) in enumerate(rows[: max(height - 7, 1)]):
            _safe_add(window, 3 + index, 2, f"{label:<16} {value}", 0, width - 3)
        controls = "p approve   h hold   u resume   " if self._can_decide_gate() else ""
        _safe_add(window, height - 3, 2, f"{controls}v validate   Esc back", curses.A_BOLD, width - 3)

    def _render_evidence(self, window: Any, height: int, width: int) -> None:
        artifacts = _artifact_list(self.state.evidence)
        _safe_add(window, 3, 1, "ARTIFACT                                      STATUS", curses.A_BOLD, width - 2)
        artifact_limit = max(height - 15, 0)
        visible_artifacts = artifacts[:artifact_limit]
        for index, artifact in enumerate(visible_artifacts):
            text = f"{str(artifact.get('relative_path', '-')):<45} {status_marker(artifact.get('status', 'Unknown'))}"
            _safe_add(window, 4 + index, 1, text, _status_color(artifact.get("status")), width - 2)
        transcript = (self.state.detail or {}).get("transcript", {})
        if isinstance(transcript, dict):
            row = min(5 + len(visible_artifacts), height - 8)
            status = str(transcript.get("status", "Unknown"))
            findings = transcript.get("redaction_findings", 0)
            summary = (
                f"Transcript: {status_marker(status)}; "
                f"redaction={transcript.get('redaction_status', '-')} findings={findings}"
            )
            _safe_add(window, row, 1, summary, curses.A_BOLD, width - 2)
            can_configure = self._can_configure_transcript()
            failed_guidance = (
                "Capture failed; attach remains available. Remediate, then press e to retry."
                if self._can_attach()
                else "Capture failed; session controls remain policy-gated. Remediate before retry."
            )
            guidance = {
                "active": "Capture is active. Press c to complete/disable safely." if can_configure else "Capture is active; transcript control is unavailable for this policy.",
                "completed": "Capture is complete. Press p to request an authorized safe preview.",
                "failed": failed_guidance if can_configure else "Capture failed; retry is unavailable for this policy.",
                "disabled": "Capture is disabled. Press e to enable with confirmation." if can_configure else "Capture is disabled; transcript control is unavailable for this policy.",
            }.get(status.lower(), "Transcript state is unknown; refresh before acting.")
            _safe_add(window, row + 1, 1, guidance, _status_color(status), width - 2)
            next_row = row + 2
            if transcript.get("path"):
                _safe_add(window, next_row, 1, f"Path: {transcript['path']}", 0, width - 2)
                next_row += 1
            if transcript.get("failure_reason"):
                _safe_add(window, next_row, 1, f"Failure: {transcript['failure_reason']}", _status_color("failed"), width - 2)
                next_row += 1
            preview_projection = self.state.transcript_preview or {}
            preview = preview_projection.get("preview")
            if preview:
                truncated = " [truncated]" if preview_projection.get("truncated") else ""
                _safe_add(window, next_row, 1, f"Authorized redacted preview{truncated}:", curses.A_BOLD, width - 2)
                next_row += 1
                for index, line in enumerate(str(preview).splitlines()[: max(height - next_row - 3, 0)]):
                    _safe_add(window, next_row + index, 3, line, curses.A_DIM, width - 4)

    def _render_help(self, window: Any, height: int, width: int) -> None:
        lines = [
            "j/k or arrows  Move session selection",
            "Enter           Inspect selected run",
            "l               Prepare a native provider launch",
            "v               Confirm the allowlisted stories validator",
            "g               Open gate actions (approve/hold/resume)",
            "t               Open transcript lifecycle and safe review",
            "r               Refresh read-only projections",
            "R               Confirm tmux/evidence reconciliation",
            "Esc             Return to the previous view",
            "q               Quit",
        ]
        if self._can_attach():
            lines.insert(3, "a               Confirm attach to the recorded tmux session")
        if self._can_recover():
            lines.insert(4, "x               Confirm recovery of persisted run state")
        if self._can_configure_transcript():
            lines.insert(-4, "e/c/p           Enable, complete/disable, or safely preview transcript")
        else:
            lines.insert(-4, "p               Request an authorized safe transcript preview")
        for index, line in enumerate(lines[: max(height - 6, 1)]):
            _safe_add(window, 3 + index, 2, line, 0, width - 3)

    def _render_confirm(self, window: Any, height: int, width: int) -> None:
        pending = self.state.pending
        if pending is None:
            return
        lines = [
            "Confirm explicit mutation",
            f"Action:   {pending.label}",
            f"Run:      {pending.run_id}",
            f"Revision: {pending.revision if pending.revision is not None else '-'}",
            f"Evidence: {pending.evidence_summary}",
            "",
            "Press y/Enter to confirm or n/Esc to cancel.",
        ]
        for index, line in enumerate(lines[: max(height - 5, 1)]):
            _safe_add(window, 3 + index, 2, line, curses.A_BOLD if index == 0 else 0, width - 3)


def run_tui(application: object, initial_run_id: str | None = None) -> int:
    return int(curses.wrapper(CockpitUI(application, initial_run_id).run))


def _artifact_list(evidence: object) -> list[dict[str, Any]]:
    if isinstance(evidence, list):
        values = evidence
    elif isinstance(evidence, dict):
        values = next((evidence[key] for key in ("artifacts", "observations", "evidence") if isinstance(evidence.get(key), list)), [])
    else:
        values = []
    return [item for item in values if isinstance(item, dict)]


def _transcript_path(detail: dict[str, Any]) -> object:
    if detail.get("transcript_path"):
        return detail["transcript_path"]
    transcript = detail.get("transcript")
    return transcript.get("path", "-") if isinstance(transcript, dict) else "-"


def _audit_event_summary(value: object) -> str:
    if not isinstance(value, dict):
        return str(value) if value is not None else "-"
    parts = []
    if value.get("sequence") is not None:
        parts.append(f"#{value['sequence']}")
    if value.get("event_type") is not None:
        parts.append(str(value["event_type"]))
    if value.get("occurred_at") is not None:
        parts.append(str(value["occurred_at"]))
    return " ".join(parts) or "-"


def _safe_error(error: Exception) -> str:
    code = getattr(error, "code", "COMMAND_FAILED")
    if isinstance(code, Enum):
        code = code.value
    message = getattr(error, "message", None) or "The operation failed safely."
    return clean_text(f"{code}: {message}", single_line=True)[:240]


def _color(pair: int) -> int:
    return curses.color_pair(pair) if curses.has_colors() else 0


def _status_color(value: object) -> int:
    normalized = str(value).lower()
    if normalized in {"ready", "active", "available", "approved", "passed", "completed"}:
        return _color(1)
    if normalized in {"failed", "blocked", "denied", "missing", "malformed", "stale", "held"}:
        return _color(2)
    return 0


def _safe_add(window: Any, row: int, column: int, text: object, attribute: int, limit: int) -> None:
    if limit <= 0:
        return
    rendered = clean_text(text, single_line=True)
    try:
        window.addnstr(row, column, rendered, limit, attribute)
    except curses.error:
        pass
