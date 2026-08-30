"""F0003 `evidence index|list|show` CLI contract, and F0001's `evidence` left intact.

Contract 1.1 is additive. The subcommands are added to the *existing* `evidence` parser,
so the risk this file covers is that adding them silently changed the F0001 form.
"""

from __future__ import annotations

import json

import pytest

from nebula_agents.presentation.cli import build_parser


def parse(argv: list[str]):
    return build_parser().parse_args(argv)


RUN = "2026-08-29-16075bda"


def test_the_f0001_form_still_parses_unchanged() -> None:
    namespace = parse(["evidence", "--run-id", RUN, "--format", "json"])
    assert namespace.command == "evidence"
    assert namespace.run_id == RUN
    assert namespace.format == "json"
    assert getattr(namespace, "evidence_command", None) is None


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["evidence", "index", "--run-id", RUN, "--path", "a.log"], "index"),
        (["evidence", "list", "--run-id", RUN], "list"),
        (["evidence", "show", f"{RUN}/transcript/rt-0123456789ab"], "show"),
    ],
)
def test_the_f0003_subcommands_parse(argv: list[str], expected: str) -> None:
    assert parse(argv).evidence_command == expected


def test_a_subcommand_format_does_not_clobber_the_parent_and_vice_versa() -> None:
    """argparse applies subparser defaults after the parent parses.

    A plain `default="table"` on the subparser would silently downgrade
    `evidence --format json list` to a table; SUPPRESS is why it does not.
    """
    assert parse(["evidence", "--format", "json", "list", "--run-id", RUN]).format == "json"
    assert parse(["evidence", "list", "--run-id", RUN, "--format", "json"]).format == "json"
    assert parse(["evidence", "list", "--run-id", RUN]).format == "table"


def test_evidence_index_rejects_an_unknown_artifact_kind() -> None:
    with pytest.raises(Exception):
        parse(["evidence", "index", "--run-id", RUN, "--kind", "not-a-kind"])


def test_bare_evidence_without_a_run_id_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """The F0001 behaviour, preserved after `--run-id` moved off `required=True`.

    The parser can no longer enforce it — the subcommands carry their own — so dispatch
    does, and this asserts the exit class and envelope did not drift.
    """
    from nebula_agents.presentation import cli

    monkeypatch.setattr(cli, "_build_application", lambda _root: object())
    assert cli.main(["evidence", "--format", "json"]) == 2
    document = json.loads(capfd.readouterr().err)   # errors go to stderr
    assert document["error"]["code"] == "USAGE_ERROR"
    assert "--run-id" in document["error"]["message"]


# --------------------------------------------------------------------------- #
# F0003 Step 4 surfaces
# --------------------------------------------------------------------------- #
def test_wrap_takes_the_same_arguments_as_launch() -> None:
    """A divergent argument set would imply `wrap` is something other than a guarded
    `launch`, which is exactly the confusion the runtime contract avoids."""
    wrapped = parse(["wrap", "codex", "--feature", "F0001", "--action", "feature"])
    assert wrapped.command == "wrap"
    assert (wrapped.provider, wrapped.feature, wrapped.action) == ("codex", "F0001", "feature")

    launch = build_parser().parse_args(
        ["launch", "--provider", "codex", "--feature", "F0001", "--action", "feature"]
    )
    optional = {"story", "run_id", "label", "transcript", "format"}
    assert optional <= set(vars(wrapped)) and optional <= set(vars(launch))


def test_wrap_rejects_an_unsupported_provider() -> None:
    with pytest.raises(Exception):
        parse(["wrap", "gemini", "--feature", "F0001", "--action", "feature"])


def test_providers_requires_a_subcommand() -> None:
    with pytest.raises(Exception):
        parse(["providers"])


def test_providers_doctor_parses_with_and_without_a_provider() -> None:
    assert parse(["providers", "doctor"]).providers_command == "doctor"
    assert parse(["providers", "doctor", "--provider", "claude"]).provider == "claude"


# --------------------------------------------------------------------------- #
# F0003 Step 6 surfaces
# --------------------------------------------------------------------------- #
def test_metrics_and_learn_subcommands_parse() -> None:
    assert parse(["metrics", "--run-id", RUN]).command == "metrics"
    assert parse(["learn", "review", "--run-id", RUN]).learn_command == "review"
    assert parse(["learn", "list", "--run-id", RUN, "--status", "Draft"]).status == "Draft"
    assert parse(["learn", "show", "p-abc", "--run-id", RUN]).proposal_id == "p-abc"


def test_learn_requires_a_subcommand() -> None:
    with pytest.raises(Exception):
        parse(["learn"])


def test_learn_scope_is_a_bounded_enumeration_not_free_text() -> None:
    """Runtime contract §3: `--scope` is an enumeration."""
    assert parse(["learn", "review", "--run-id", RUN, "--scope", "validators"]).scope == "validators"
    with pytest.raises(Exception):
        parse(["learn", "review", "--run-id", RUN, "--scope", "anything-goes"])


def test_decide_offers_exactly_the_four_contract_decisions() -> None:
    """`Draft` is a status, never a decision, so it is unreachable from the CLI."""
    for decision in ("accept", "edit", "reject", "archive"):
        parse(["learn", "decide", "p-abc", "--run-id", RUN, "--decision", decision,
               "--reason", "r"])
    with pytest.raises(Exception):
        parse(["learn", "decide", "p-abc", "--run-id", RUN, "--decision", "draft"])


@pytest.mark.parametrize("decision", ["reject", "archive"])
def test_reject_and_archive_require_a_reason_as_a_usage_error(
    decision: str, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """Enforced in the CLI as well as the domain, so the operator gets exit 2 rather
    than a state-io error surfacing from deeper in the stack."""
    from nebula_agents.presentation import cli

    monkeypatch.setattr(cli, "_build_application", lambda _root: object())
    code = cli.main(["learn", "decide", "p-abc", "--run-id", RUN,
                     "--decision", decision, "--format", "json"])
    assert code == 2
    document = json.loads(capfd.readouterr().err)
    assert document["error"]["code"] == "USAGE_ERROR"
    assert "--reason" in document["error"]["message"]


def test_learn_decide_has_no_role_flag() -> None:
    """A role the caller can name is a role the caller can claim.

    `--role` was removed after review found that a LocalOperator could pass
    `--role architect` and decide an architecture proposal: the check compared the
    declared role to the required one and never asked whether the actor held it. The role
    is now derived from the target document and verified against policy.json.
    """
    with pytest.raises(Exception):
        parse(["learn", "decide", "p-abc", "--run-id", RUN, "--decision", "accept",
               "--role", "architect"])
