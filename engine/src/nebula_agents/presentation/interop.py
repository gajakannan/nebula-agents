"""Thin compatibility seam between presentation and the composed application."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from importlib import import_module
from typing import Any


class IntegrationError(RuntimeError):
    """Raised when the application composition does not satisfy its contract."""


def current_actor(application: object) -> object:
    direct = getattr(application, "current_actor", None)
    if callable(direct):
        return direct()
    identity = getattr(application, "identity", None)
    resolver = getattr(identity, "current_actor", None)
    if callable(resolver):
        return resolver()
    for service_name in ("runs", "gates", "queries", "transcripts"):
        service = getattr(application, service_name, None)
        identity = getattr(service, "identity", None) or getattr(service, "_identity", None)
        resolver = getattr(identity, "current_actor", None)
        if callable(resolver):
            return resolver()
    raise IntegrationError("The application composition does not expose the current local actor.")


def invoke(method: Callable[..., Any], /, **available: Any) -> Any:
    """Call a planned service method with the subset of named values it accepts."""

    signature = inspect.signature(method)
    accepts_extra = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())
    values = available if accepts_extra else {key: value for key, value in available.items() if key in signature.parameters}
    missing = [
        name
        for name, parameter in signature.parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and name not in values
    ]
    if missing:
        raise IntegrationError(f"Application method is missing presentation bindings for: {', '.join(missing)}")
    return method(**values)


def enum_member(class_name: str, value: str) -> object:
    module = import_module("nebula_agents.domain.enums")
    enum_class = getattr(module, class_name)
    return enum_class(value)


def launch_request(values: Mapping[str, Any]) -> object:
    module = import_module("nebula_agents.domain.models")
    request_type = getattr(module, "LaunchRequest")
    return request_type(
        feature_id=values["feature"],
        story_id=values.get("story"),
        provider_key=enum_member("ProviderKey", values["provider"]),
        prompt_action=enum_member("PromptAction", values["action"]),
        requested_run_id=values.get("run_id"),
        run_label=values.get("label"),
        transcript_enabled=bool(values.get("transcript")),
        expected_revision=values.get("expected_revision"),
    )
