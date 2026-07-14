from __future__ import annotations

import os
import pwd

from nebula_agents.domain.enums import Role
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import Actor

from .policy_store import LocalPolicyStore


class OsIdentity:
    def __init__(self, policy: LocalPolicyStore) -> None:
        self._policy = policy

    def current_actor(self) -> Actor:
        uid = os.getuid()
        username = pwd.getpwuid(uid).pw_name
        gids = set(os.getgroups()) | {os.getgid()}
        uid_roles: set[Role] = set()
        group_roles: set[Role] = set()
        document = self._policy.load()
        for binding in document.get("bindings", []):
            if not isinstance(binding, dict):
                continue
            subject_type = binding.get("subject_type")
            subject_id = binding.get("subject_id")
            if not (
                (subject_type == "uid" and subject_id == uid)
                or (subject_type == "gid" and subject_id in gids)
            ):
                continue
            try:
                role = Role(binding["role"])
            except (KeyError, TypeError, ValueError) as exc:
                raise error(
                    ErrorCode.FORBIDDEN,
                    "Local identity has an invalid role binding",
                    "forbidden",
                    "Restore an unambiguous schema-valid local policy.",
                ) from exc
            if role is Role.SYSTEM:
                raise error(
                    ErrorCode.FORBIDDEN,
                    "Local identity cannot assume the system role",
                    "forbidden",
                    "Restore an unambiguous schema-valid local policy.",
                )
            if subject_type == "uid":
                uid_roles.add(role)
            else:
                group_roles.add(role)

        # An exact UID binding takes precedence over supplementary groups. When
        # several matching groups agree, their single effective role is stable;
        # contradictory group roles are an identity error and fail closed.
        effective_roles = uid_roles or group_roles
        if len(effective_roles) > 1:
            raise error(
                ErrorCode.FORBIDDEN,
                "Local identity resolves to conflicting roles",
                "forbidden",
                "Remove contradictory UID or group bindings from the local policy.",
            )
        role = next(iter(effective_roles), None)
        # An unbound subject is represented but remains default-denied by AuthorizationService.
        return Actor(uid=uid, username=username, role=role or Role.REVIEWER, display_label=None)


def system_actor(owner_uid: int, username: str = "nebula-system") -> Actor:
    return Actor(owner_uid, username, Role.SYSTEM, None)
