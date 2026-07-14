from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import JsonValue


class JsonSchemaRegistry:
    def __init__(self, schema_root: Path) -> None:
        self._root = schema_root.expanduser().resolve()
        self._validators: dict[str, Draft202012Validator] = {}

    def _load(self, name: str) -> Draft202012Validator:
        if Path(name).name != name or not name.startswith("f0001-") or not name.endswith(".schema.json"):
            raise error(ErrorCode.SCHEMA_INVALID, "Schema name is not allowlisted", "state-io", "Use a committed F0001 schema.")
        if name in self._validators:
            return self._validators[name]
        path = (self._root / name).resolve()
        try:
            path.relative_to(self._root)
            document = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(document)
        except (OSError, json.JSONDecodeError, SchemaError, ValueError) as exc:
            raise error(ErrorCode.SCHEMA_INVALID, "Schema cannot be loaded", "state-io", "Restore the committed schema.", schema=name) from exc
        validator = Draft202012Validator(document, format_checker=FormatChecker())
        self._validators[name] = validator
        return validator

    def validate(self, schema_name: str, document: Mapping[str, JsonValue]) -> None:
        errors = sorted(self._load(schema_name).iter_errors(document), key=lambda item: tuple(str(part) for part in item.path))
        if errors:
            first = errors[0]
            location = "/".join(str(part) for part in first.absolute_path) or "$"
            raise error(ErrorCode.SCHEMA_INVALID, "Document does not satisfy its contract", "state-io", "Repair the local state or restore the committed contract.", schema=schema_name, location=location)
