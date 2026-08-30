"""Argparse command surface for the tmux-native agent cockpit."""

from __future__ import annotations

import argparse
import os
import re
import sys
import traceback
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, NoReturn, TextIO
from uuid import uuid4

from nebula_agents.domain.enums import (
    ArtifactKind,
    ProposalDecisionKind,
    ProposalStatus,
    ReviewerRole,
)

from .formatters import (
    MAX_LIST_RECORDS,
    clean_text,
    error_envelope,
    recovery_view_data,
    render_error_table,
    render_json,
    render_success_table,
    success_envelope,
    to_data,
)
from .interop import IntegrationError, current_actor, enum_member, invoke, launch_request

_FEATURE = re.compile(r"^F\d{4}$")
_STORY = re.compile(r"^(F\d{4})-S\d{4}$")
_RUN_ID = re.compile(r"^(\d{4}-\d{2}-\d{2})-[0-9a-f]{8}$")
_FORMATS = ("table", "json")
_PROVIDERS = ("codex", "claude")
_ACTIONS = ("plan", "feature", "build", "review", "validate")
_VALIDATORS = ("stories", "trackers", "templates")
_ARTIFACT_KINDS = tuple(kind.value for kind in ArtifactKind)
_DECISIONS = ("accept", "edit", "reject", "archive")
_REVIEWER_ROLES = tuple(role.value for role in ReviewerRole)
_PROPOSAL_STATUSES = tuple(status.value for status in ProposalStatus)
#: A bounded enumeration, never free text (runtime contract, section 3).
_LEARN_SCOPES = ("run", "validators", "commands", "transcript")
#: `learn decide --decision` values map to the recorded status. `Draft` is a status, not
#: a decision, so it is deliberately unreachable from the CLI.
_DECISION_KIND = {
    "accept": "Accepted", "edit": "Edited", "reject": "Rejected", "archive": "Archived",
}
_RUN_STATUSES = (
    "PreflightPending",
    "Launching",
    "Active",
    "DetachedOrExited",
    "Failed",
    "Exited",
    "Unknown",
)


class UsageFault(ValueError):
    def __init__(self, message: str, usage: str) -> None:
        super().__init__(message)
        self.message = message
        self.usage = usage


class ParserExit(RuntimeError):
    def __init__(self, status: int) -> None:
        self.status = status


class ContractParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise UsageFault(clean_text(message, single_line=True), self.format_usage())

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            self._print_message(message, sys.stdout if status == 0 else sys.stderr)
        raise ParserExit(status)


def build_parser() -> ContractParser:
    parser = ContractParser(
        prog="nebula-agents",
        description="Launch and govern native provider sessions in tmux.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    doctor = subcommands.add_parser("doctor", help="Check tmux, providers, workspace, prompts, and runtime state.")
    doctor.add_argument("--provider", choices=_PROVIDERS)
    doctor.add_argument("--action", choices=_ACTIONS)
    _format_argument(doctor)

    launch = subcommands.add_parser("launch", help="Launch exactly one provider in a new recorded tmux session.")
    launch.add_argument("--feature", required=True, type=_feature_id)
    launch.add_argument("--provider", required=True, choices=_PROVIDERS)
    launch.add_argument("--action", required=True, choices=_ACTIONS)
    launch.add_argument("--story", type=_story_id)
    launch.add_argument("--run-id", type=_run_id)
    launch.add_argument("--label", type=_label)
    launch.add_argument("--transcript", action="store_true")
    _format_argument(launch)

    # F0003. `wrap` takes the same arguments as `launch` because it IS `launch` plus a
    # preflight and capability guard -- a divergent argument set would imply otherwise.
    wrap = subcommands.add_parser("wrap", help="Guarded launch: preflight, capability guard, then launch.")
    wrap.add_argument("provider", choices=_PROVIDERS)
    wrap.add_argument("--feature", required=True, type=_feature_id)
    wrap.add_argument("--action", required=True, choices=_ACTIONS)
    wrap.add_argument("--story", type=_story_id)
    wrap.add_argument("--run-id", type=_run_id)
    wrap.add_argument("--label", type=_label)
    wrap.add_argument("--transcript", action="store_true")
    _format_argument(wrap)

    providers = subcommands.add_parser("providers", help="Inspect provider capability reports.")
    providers_commands = providers.add_subparsers(dest="providers_command", metavar="SUBCOMMAND", required=True)
    providers_doctor = providers_commands.add_parser("doctor", help="Probe providers and write capability reports.")
    providers_doctor.add_argument("--provider", choices=_PROVIDERS)
    _format_argument(providers_doctor)

    attach = subcommands.add_parser("attach", help="Attach to the exact tmux session recorded for a run.")
    attach.add_argument("--run-id", required=True, type=_run_id)

    recover = subcommands.add_parser("recover", help="Recover a preserved run from its last valid local state.")
    recover.add_argument("--run-id", required=True, type=_run_id)
    recover.add_argument("--expected-revision", type=_nonnegative_int)
    _format_argument(recover)

    sessions = subcommands.add_parser("sessions", help="List up to 100 recorded runs.")
    sessions.add_argument("--status", type=_run_status)
    _format_argument(sessions)

    status = subcommands.add_parser("status", help="Show the current immutable run projection.")
    status.add_argument("--run-id", required=True, type=_run_id)
    _format_argument(status)

    # F0001's `evidence --run-id X` is preserved exactly. F0003 adds `index`, `list`,
    # and `show` as OPTIONAL subcommands (contract 1.1 is additive), so `--run-id` moves
    # off `required=True` here and the bare form's usage error is raised in `_dispatch`
    # instead -- same message, same exit 2.
    evidence = subcommands.add_parser("evidence", help="Show expected paths and artifact observations.")
    evidence.add_argument("--run-id", type=_run_id)
    _format_argument(evidence)
    evidence_commands = evidence.add_subparsers(dest="evidence_command", metavar="SUBCOMMAND")

    evidence_index = evidence_commands.add_parser("index", help="Index run artifacts into the retrieval index.")
    evidence_index.add_argument("--run-id", required=True, type=_run_id, dest="sub_run_id")
    evidence_index.add_argument("--path", action="append", default=[], dest="paths")
    evidence_index.add_argument("--kind", choices=_ARTIFACT_KINDS)
    _sub_format_argument(evidence_index)

    evidence_list = evidence_commands.add_parser("list", help="List indexed artifacts for a run.")
    evidence_list.add_argument("--run-id", required=True, type=_run_id, dest="sub_run_id")
    evidence_list.add_argument("--kind", choices=_ARTIFACT_KINDS)
    _sub_format_argument(evidence_list)

    evidence_show = evidence_commands.add_parser("show", help="Show one artifact by its stable id.")
    evidence_show.add_argument("artifact_id")
    _sub_format_argument(evidence_show)

    evidence_summarize = evidence_commands.add_parser("summarize", help="Summarize indexed artifacts deterministically.")
    evidence_summarize.add_argument("--run-id", required=True, type=_run_id, dest="sub_run_id")
    evidence_summarize.add_argument("--artifact-id")
    _sub_format_argument(evidence_summarize)

    metrics = subcommands.add_parser("metrics", help="Report derived runtime metrics for a run.")
    metrics.add_argument("--run-id", required=True, type=_run_id)
    _format_argument(metrics)

    learn = subcommands.add_parser("learn", help="Draft and decide failure-learning proposals.")
    learn_commands = learn.add_subparsers(dest="learn_command", metavar="SUBCOMMAND", required=True)

    learn_review = learn_commands.add_parser("review", help="Draft proposals from failed run evidence.")
    learn_review.add_argument("--run-id", required=True, type=_run_id)
    learn_review.add_argument("--scope", choices=_LEARN_SCOPES)
    _format_argument(learn_review)

    learn_list = learn_commands.add_parser("list", help="List recorded proposals.")
    learn_list.add_argument("--run-id", required=True, type=_run_id)
    learn_list.add_argument("--status", choices=_PROPOSAL_STATUSES)
    _format_argument(learn_list)

    learn_show = learn_commands.add_parser("show", help="Show one proposal with its decision history.")
    learn_show.add_argument("proposal_id")
    learn_show.add_argument("--run-id", required=True, type=_run_id)
    _format_argument(learn_show)

    learn_decide = learn_commands.add_parser("decide", help="Record accept, edit, reject, or archive.")
    learn_decide.add_argument("proposal_id")
    learn_decide.add_argument("--run-id", required=True, type=_run_id)
    learn_decide.add_argument("--decision", required=True, choices=_DECISIONS)
    learn_decide.add_argument("--role", required=True, choices=_REVIEWER_ROLES)
    learn_decide.add_argument("--reason")
    learn_decide.add_argument("--patch-plan")
    _format_argument(learn_decide)

    validate = subcommands.add_parser("validate", help="Run one committed allowlisted validator.")
    validate.add_argument("--run-id", required=True, type=_run_id)
    validate.add_argument("--validator", required=True, choices=_VALIDATORS)
    _format_argument(validate)

    # `mcp serve` only. Host configuration is documented, not installed: see M1 in the
    # F0003 STATUS and `docs/mcp-host-configuration.md`. There is deliberately no
    # `mcp install` subcommand -- writing another tool's config file from here would put
    # Nebula inside a trust boundary it does not own.
    mcp = subcommands.add_parser("mcp", help="Serve the read-only MCP surface over stdio.")
    mcp_commands = mcp.add_subparsers(dest="mcp_command", metavar="SUBCOMMAND", required=True)
    mcp_commands.add_parser("serve", help="Serve MCP over stdio until the host closes it.")

    tui = subcommands.add_parser("tui", help="Open the keyboard-operated terminal cockpit.")
    tui.add_argument("--run-id", type=_run_id)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    product_root: str | Path | None = None,
) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if arguments and arguments[0] == "session-entry":
        from .session_entry import main as session_entry_main

        return session_entry_main(arguments[1:])
    if arguments and arguments[0] == "transcript-filter":
        from .transcript_filter import main as transcript_filter_main

        return transcript_filter_main(arguments[1:])

    parser = build_parser()
    output_format = _requested_format(arguments)
    command = _command_name(arguments)
    try:
        namespace = parser.parse_args(arguments)
        command = namespace.command
        output_format = getattr(namespace, "format", "table")
        _validate_usage(namespace)
        resolved_product_root = _resolve_product_root(product_root)
        application = _build_application(resolved_product_root)
        return _dispatch(application, namespace, output_format, product_root=resolved_product_root)
    except ParserExit as result:
        return result.status
    except UsageFault as error:
        document = error_envelope(
            command,
            code="USAGE_ERROR",
            message=error.message,
            category="usage",
            details=[{"usage": clean_text(error.usage, single_line=True)}],
            remediation=f"Run nebula-agents {command} --help for command syntax." if command else "Run nebula-agents --help for command syntax.",
            correlation_id=uuid4(),
        )
        _emit_error(document, output_format)
        return 2
    except KeyboardInterrupt:
        document = error_envelope(
            command,
            code="INTERRUPTED",
            message="The operation was cancelled safely.",
            category="interrupted",
            details=[],
            remediation="Rerun the command when ready.",
            correlation_id=uuid4(),
        )
        _emit_error(document, output_format)
        return 130
    except BrokenPipeError:
        return 0
    except Exception as error:
        if _is_nebula_error(error):
            document = error_envelope(
                command,
                code=getattr(error, "code"),
                message=getattr(error, "message", "The operation failed."),
                category=getattr(error, "category", "command-failed"),
                details=getattr(error, "details", ()),
                remediation=getattr(error, "remediation", "Review the command inputs and retry."),
                correlation_id=getattr(error, "correlation_id", uuid4()),
            )
            _emit_error(document, output_format)
            return _error_exit(error)
        correlation_id = uuid4()
        document = error_envelope(
            command,
            code="INTERNAL_ERROR",
            message="The command failed without exposing internal state.",
            category="command-failed",
            details=[],
            remediation=f"Retry the command. If it fails again, report correlation {correlation_id}.",
            correlation_id=correlation_id,
        )
        _emit_error(document, output_format)
        if output_format != "json" and os.environ.get("NEBULA_AGENTS_DEBUG_TRACEBACK") == "1":
            traceback.print_exc(file=sys.stderr)
        return 8


def _dispatch(
    application: object,
    namespace: argparse.Namespace,
    output_format: str,
    *,
    product_root: Path | None = None,
) -> int:
    command = namespace.command
    if command == "tui":
        from .tui import run_tui

        return run_tui(application, namespace.run_id)
    if command == "doctor":
        runtime_override = os.environ.get("NEBULA_AGENTS_RUNTIME_DIR")
        result = invoke(
            application.preflight.run,
            workspace_root=product_root or _resolve_product_root(),
            runtime_dir_override=Path(runtime_override) if runtime_override else None,
            provider_hint=enum_member("ProviderKey", namespace.provider) if namespace.provider else None,
            prompt_action=enum_member("PromptAction", namespace.action) if namespace.action else None,
        )
        _emit_success(command, result, output_format)
        status = str(to_data(result).get("overall_status", "unknown")).lower() if isinstance(to_data(result), dict) else "unknown"
        return 0 if status in {"ready", "ok", "passed"} else 3

    actor = current_actor(application)
    if command == "providers":
        result = invoke(
            application.capabilities.doctor,
            actor=actor,
            provider_key=enum_member("ProviderKey", namespace.provider) if namespace.provider else None,
        )
        _emit_success("providers doctor", to_data(result), output_format)
        # A blocked provider is reported, not raised: `providers doctor` is a diagnostic
        # and must describe an unusable environment rather than refuse to run in one.
        blocked = any(
            str(item.get("launch_decision")) == "blocked"
            for item in (to_data(result) if isinstance(to_data(result), list) else [])
            if isinstance(item, dict)
        )
        return 3 if blocked else 0
    if command == "wrap":
        launched = invoke(
            application.commands.wrap,
            request=launch_request({**vars(namespace), "provider": namespace.provider}),
            actor=actor,
        )
        result = invoke(
            application.queries.status,
            run_id=_result_run_id(launched),
            actor=actor,
        )
        _emit_success("wrap", result, output_format)
        return 0
    if command == "launch":
        if namespace.story and not namespace.story.startswith(f"{namespace.feature}-"):
            raise UsageFault("--story must belong to --feature.", "nebula-agents launch --help")
        launched = invoke(
            application.runs.launch,
            request=launch_request(vars(namespace)),
            actor=actor,
        )
        result = invoke(
            application.queries.status,
            run_id=_result_run_id(launched),
            actor=actor,
        )
        _emit_success(command, result, output_format)
        return 0
    if command == "attach":
        result = invoke(application.runs.attach, run_id=namespace.run_id, actor=actor)
        return int(result) if isinstance(result, int) else 0
    if command == "recover":
        result = invoke(
            application.runs.recover,
            run_id=namespace.run_id,
            actor=actor,
            expected_revision=namespace.expected_revision,
        )
        _emit_success(command, result, output_format)
        return 0
    if command == "sessions":
        result = invoke(
            application.queries.sessions,
            status=enum_member("RunStatus", namespace.status) if namespace.status else None,
            actor=actor,
            limit=100,
        )
        if namespace.status is None:
            recovery_candidates = getattr(application.queries, "recovery_candidates", None)
            if callable(recovery_candidates):
                recoveries = invoke(recovery_candidates, actor=actor)
                result = _merge_recovery_sessions(result, recoveries)
        _emit_success(command, result, output_format)
        return 0
    if command == "status":
        result = invoke(application.queries.status, run_id=namespace.run_id, actor=actor)
        _emit_success(command, result, output_format)
        return 0
    if command == "mcp":
        from .mcp_server import McpServer, serve

        # Constructed with the QUERY facade only. Passing `application.commands` here is
        # the visible architectural edit ADR-007 requires for a mutating tool to exist.
        return serve(McpServer(application.queries, _SystemClock()))
    if command == "metrics":
        result = invoke(application.queries.metrics, run_id=namespace.run_id, actor=actor)
        _emit_success(command, to_data(result), output_format)
        return 0
    if command == "learn":
        subcommand = namespace.learn_command
        if subcommand == "review":
            result = invoke(
                application.learning.review,
                run_id=namespace.run_id, actor=actor, scope=namespace.scope,
            )
            _emit_success("learn review", to_data(result), output_format)
            return 0
        if subcommand == "list":
            result = invoke(
                application.queries.proposals,
                run_id=namespace.run_id, actor=actor, status=namespace.status,
            )
            _emit_success("learn list", to_data(result), output_format)
            return 0
        if subcommand == "show":
            result = invoke(
                application.queries.proposal,
                run_id=namespace.run_id, proposal_id=namespace.proposal_id, actor=actor,
            )
            _emit_success("learn show", to_data(result), output_format)
            return 0
        if subcommand == "decide":
            result = invoke(
                application.learning.decide,
                run_id=namespace.run_id,
                proposal_id=namespace.proposal_id,
                decision=enum_member("ProposalDecisionKind", _DECISION_KIND[namespace.decision]),
                actor=actor,
                reviewer_role=enum_member("ReviewerRole", namespace.role),
                reason=namespace.reason,
                patch_plan=namespace.patch_plan,
            )
            _emit_success("learn decide", to_data(result), output_format)
            return 0
    if command == "evidence":
        subcommand = getattr(namespace, "evidence_command", None)
        if subcommand is None:
            # F0001's form, unchanged. `--run-id` is validated in `main` before the
            # application is built -- see `_require_evidence_run_id`.
            result = invoke(application.queries.evidence, run_id=namespace.run_id, actor=actor)
            _emit_success(command, result, output_format)
            return 0
        if subcommand == "index":
            result = invoke(
                application.evidence.index_artifacts,
                run_id=namespace.sub_run_id,
                paths=[Path(item) for item in namespace.paths],
                actor=actor,
                kinds=None,
            )
            _emit_success("evidence index", to_data(result), output_format)
            return 0
        if subcommand == "list":
            result = invoke(
                application.queries.artifacts,
                run_id=namespace.sub_run_id,
                actor=actor,
                kind=namespace.kind,
            )
            _emit_success("evidence list", to_data(result), output_format)
            return 0
        if subcommand == "summarize":
            result = invoke(
                application.evidence.summarize,
                run_id=namespace.sub_run_id,
                actor=actor,
                artifact_id=namespace.artifact_id,
            )
            _emit_success("evidence summarize", to_data(result), output_format)
            return 0
        if subcommand == "show":
            result = invoke(
                application.queries.artifact,
                artifact_id=namespace.artifact_id,
                actor=actor,
            )
            _emit_success("evidence show", to_data(result), output_format)
            return 0
    if command == "validate":
        validated = invoke(
            application.gates.run_validator,
            run_id=namespace.run_id,
            key=enum_member("ValidatorKey", namespace.validator),
            actor=actor,
        )
        validator_exit = _validator_exit(validated)
        result = invoke(application.queries.status, run_id=namespace.run_id, actor=actor)
        _emit_success(command, result, output_format)
        return validator_exit if 1 <= validator_exit <= 125 else 0
    raise IntegrationError(f"No dispatcher exists for command {command!r}.")


def _resolve_product_root(explicit: str | Path | None = None) -> Path:
    """Resolve composition root precedence without mutating process state."""

    if explicit is not None:
        candidate = Path(explicit)
    else:
        configured = os.environ.get("NEBULA_AGENTS_PRODUCT_ROOT")
        candidate = Path(configured) if configured and configured.strip() else Path.cwd()
    return candidate.expanduser().resolve()


def _build_application(product_root: str | Path | None = None) -> object:
    from nebula_agents.bootstrap import build_application

    workspace = _resolve_product_root(product_root)
    return invoke(build_application, workspace_root=workspace, runtime_override=None)


def _emit_success(command: str, result: object, output_format: str, *, stream: TextIO | None = None) -> None:
    destination = stream if stream is not None else sys.stdout
    if output_format == "json":
        destination.write(render_json(success_envelope(command, result)))
    else:
        destination.write(render_success_table(command, result))
    destination.flush()


def _emit_error(document: dict[str, Any], output_format: str, *, stream: TextIO | None = None) -> None:
    destination = stream if stream is not None else sys.stderr
    destination.write(render_json(document) if output_format == "json" else render_error_table(document))
    destination.flush()


def _format_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=_FORMATS, default="table")


class _SystemClock:
    """The MCP envelope needs a timestamp; presentation does not own a clock."""

    @staticmethod
    def now():
        from datetime import datetime

        return datetime.now().astimezone()


def _validate_usage(namespace: argparse.Namespace) -> None:
    """Argument rules argparse cannot express, checked before anything is built.

    Deliberately ahead of the application: a usage error must not depend on a workspace
    being resolvable, which is how F0001 behaved when argparse enforced these.
    """
    command = getattr(namespace, "command", None)

    # `evidence` without a subcommand still requires `--run-id`. The parser cannot say
    # "required unless a subcommand is given", and the F0003 subcommands carry their own.
    if (
        command == "evidence"
        and getattr(namespace, "evidence_command", None) is None
        and getattr(namespace, "run_id", None) is None
    ):
        raise UsageFault(
            "the following arguments are required: --run-id",
            "nebula-agents evidence --run-id RUN_ID [--format {table,json}]",
        )

    # `--reason` is required for reject and archive (runtime contract, section 1).
    # Enforced here as well as in the domain so the operator gets a usage error rather
    # than a state-io one surfacing from deeper in the stack.
    if (
        command == "learn"
        and getattr(namespace, "learn_command", None) == "decide"
        and namespace.decision in ("reject", "archive")
        and not namespace.reason
    ):
        raise UsageFault(
            f"--reason is required for {namespace.decision}.",
            "nebula-agents learn decide PROPOSAL_ID --run-id RUN_ID "
            "--decision {accept,edit,reject,archive} --role ROLE [--reason REASON]",
        )


def _sub_format_argument(parser: argparse.ArgumentParser) -> None:
    """`--format` on a subparser, without clobbering the parent's value.

    argparse applies a subparser's defaults *after* the parent has parsed, so a plain
    `default="table"` here would silently override `evidence --format json list`.
    SUPPRESS leaves the parent's value in place when the flag is absent.
    """
    parser.add_argument("--format", choices=_FORMATS, default=argparse.SUPPRESS)


def _feature_id(value: str) -> str:
    if _FEATURE.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("feature must match F####")
    return value


def _story_id(value: str) -> str:
    if _STORY.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("story must match F####-S####")
    return value


def _run_id(value: str) -> str:
    match = _RUN_ID.fullmatch(value)
    if match is None:
        raise argparse.ArgumentTypeError("run ID must match YYYY-MM-DD-8hex")
    try:
        date.fromisoformat(match.group(1))
    except ValueError as error:
        raise argparse.ArgumentTypeError("run ID contains an invalid calendar date") from error
    return value


def _label(value: str) -> str:
    label = clean_text(value, single_line=True).strip()
    if not label:
        raise argparse.ArgumentTypeError("label must contain visible text")
    if len(label) > 80:
        raise argparse.ArgumentTypeError("label must not exceed 80 Unicode characters")
    return label


def _run_status(value: str) -> str:
    lookup = {status.lower(): status for status in _RUN_STATUSES}
    try:
        return lookup[value.lower()]
    except KeyError as error:
        raise argparse.ArgumentTypeError(f"status must be one of: {', '.join(_RUN_STATUSES)}") from error


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a nonnegative integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be a nonnegative integer")
    return parsed


def _requested_format(arguments: Sequence[str]) -> str:
    for index, argument in enumerate(arguments):
        if argument == "--format" and index + 1 < len(arguments) and arguments[index + 1] in _FORMATS:
            return arguments[index + 1]
        if argument.startswith("--format=") and argument.partition("=")[2] in _FORMATS:
            return argument.partition("=")[2]
    return "table"


def _command_name(arguments: Sequence[str]) -> str:
    for argument in arguments:
        if not argument.startswith("-"):
            return clean_text(argument, single_line=True)
    return ""


def _is_nebula_error(error: Exception) -> bool:
    return all(hasattr(error, field) for field in ("code", "category", "remediation", "correlation_id"))


def _error_exit(error: Exception) -> int:
    exit_code = getattr(error, "exit_code", None)
    if isinstance(exit_code, int):
        return exit_code
    category = str(getattr(error, "category", "command-failed")).lower().replace("_", "-")
    return {
        "usage": 2,
        "preflight": 3,
        "not-found": 4,
        "forbidden": 5,
        "conflict": 6,
        "gate-blocked": 7,
        "command-failed": 8,
        "state-io": 9,
        "timeout": 10,
        "interrupted": 130,
    }.get(category, 8)


def _validator_exit(result: object) -> int:
    data = to_data(result)
    if not isinstance(data, dict):
        return 0
    latest = data.get("latest_validator")
    if isinstance(latest, dict) and isinstance(latest.get("exit_code"), int):
        return latest["exit_code"]
    return data.get("exit_code", 0) if isinstance(data.get("exit_code"), int) else 0


def _result_run_id(result: object) -> str:
    data = to_data(result)
    if isinstance(data, dict) and isinstance(data.get("run_id"), str):
        return data["run_id"]
    raise IntegrationError("Application mutation did not return a run identifier.")


def _merge_recovery_sessions(sessions: object, candidates: object) -> list[dict[str, Any]]:
    session_data = to_data(sessions)
    if isinstance(session_data, dict):
        session_data = next(
            (
                session_data[key]
                for key in ("sessions", "runs", "items", "records")
                if isinstance(session_data.get(key), list)
            ),
            [],
        )
    records = [dict(item) for item in session_data if isinstance(item, dict)] if isinstance(session_data, list) else []
    candidate_data = to_data(candidates)
    if isinstance(candidate_data, dict):
        candidate_data = next(
            (
                candidate_data[key]
                for key in ("candidates", "recoveries", "items")
                if isinstance(candidate_data.get(key), list)
            ),
            [],
        )
    recovery_records = (
        [recovery_view_data(item) for item in candidate_data]
        if isinstance(candidate_data, list)
        else []
    )
    recovery_records = [item for item in recovery_records if item]
    recovery_ids = {item["run_id"] for item in recovery_records}
    return (recovery_records + [item for item in records if item.get("run_id") not in recovery_ids])[:MAX_LIST_RECORDS]
