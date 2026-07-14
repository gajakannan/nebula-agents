from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from nebula_agents.domain.enums import ArtifactStatus, GateStatus, ValidatorKey
from nebula_agents.domain.errors import ErrorCode, error
from nebula_agents.domain.models import ArtifactObservation, EvidenceReconciliation, GateSnapshot, RunRecord, ValidatorResult
from nebula_agents.domain.path_contracts import governed_feature_root

from .process import SubprocessRunner


_CONTENT_LIMIT = 1_048_576
_GATE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "G0": ("g0-assembly-plan-validation.md",),
    "G1": ("g1-runtime-preflight.md",),
    "G2": ("g2-self-review.md", "test-execution-report.md", "coverage-report.md", "deployability-check.md"),
    "G3": ("code-review-report.md", "security-review-report.md"),
    "G4": ("gate-decisions.md",),
    "G5": ("signoff-ledger.md",),
    "G6": ("feature-action-execution.md",),
    "G7": ("kg-reconciliation.md",),
    "G8": ("pm-closeout.md",),
}
_LIFECYCLE_PATHS = (
    "commands.log",
    "lifecycle-gates.log",
    "action-context.md",
    "artifact-trace.md",
)


def _descriptor_read(root: Path, relative: str) -> tuple[bytes, os.stat_result]:
    """Read one relative regular file through a no-follow descriptor walk."""
    parts = Path(relative).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise PermissionError("unsafe evidence path")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.open(root, directory_flags)
    try:
        for component in parts[:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        fd = os.open(parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=current_fd)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > _CONTENT_LIMIT:
                raise ValueError("evidence is not a bounded regular file")
            payload = bytearray()
            while len(payload) <= _CONTENT_LIMIT:
                chunk = os.read(fd, min(64 * 1024, _CONTENT_LIMIT + 1 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
            after = os.fstat(fd)
            if (
                len(payload) > _CONTENT_LIMIT
                or before.st_dev != after.st_dev
                or before.st_ino != after.st_ino
                or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                raise ValueError("evidence changed during read")
            return bytes(payload), after
        finally:
            os.close(fd)
    finally:
        os.close(current_fd)


def _balanced_yaml(text: str) -> bool:
    """Conservatively validate the governed, metadata-only YAML subset."""
    if not text.strip() or "\x00" in text or "\t" in text:
        return False
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    pairs = {"]": "[", "}": "{"}
    for char in text:
        if escaped:
            escaped = False
            continue
        if quote is not None:
            if char == "\\" and quote == '"':
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char in "[{":
            stack.append(char)
        elif char in "]}":
            if not stack or stack.pop() != pairs[char]:
                return False
    if quote is not None or stack:
        return False
    meaningful = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return bool(meaningful) and all(
        line.lstrip().startswith(("- ", "---", "...")) or ":" in line
        for line in meaningful
    )


def _valid_governed_content(relative: str, payload: bytes) -> bool:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if "\x00" in text or not text.strip():
        return False
    suffix = Path(relative).suffix.lower()
    if suffix == ".json":
        try:
            json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return False
    elif suffix in (".yaml", ".yml"):
        return _balanced_yaml(text)
    elif suffix in (".md", ".markdown"):
        lines = text.splitlines()
        if lines and lines[0].strip() == "---" and "---" not in (line.strip() for line in lines[1:]):
            return False
        if text.count("```") % 2:
            return False
    return True


class PollingEvidenceWatcher:
    def __init__(self, clock) -> None:
        self._clock = clock
        self._fingerprints: dict[tuple[str, str], tuple[int, int]] = {}

    def observe_once(self, run: RunRecord, paths: Sequence[str]) -> tuple[ArtifactObservation, ...]:
        workspace = Path(run.workspace_root).resolve()
        requested_root = Path(run.evidence_root) if run.evidence_root else workspace
        if requested_root.is_symlink():
            return tuple(ArtifactObservation(relative or "<invalid>", ArtifactStatus.DENIED, self._clock.now(), None) for relative in paths)
        root = requested_root.resolve()
        observations: list[ArtifactObservation] = []
        previous = {item.relative_path: item for item in run.artifacts}
        for relative in paths:
            now = self._clock.now()
            if not relative or Path(relative).is_absolute():
                observations.append(ArtifactObservation(relative or "<invalid>", ArtifactStatus.DENIED, now, None))
                continue
            unresolved = root / relative
            if unresolved.is_symlink() or any(parent.is_symlink() for parent in unresolved.parents if parent != root.parent):
                observations.append(ArtifactObservation(relative, ArtifactStatus.DENIED, now, None))
                continue
            candidate = unresolved.resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                observations.append(ArtifactObservation(relative, ArtifactStatus.DENIED, now, None))
                continue
            details = None
            try:
                # Preserve the existing error taxonomy for inaccessible paths,
                # then bind validation and use to the descriptor read below.
                candidate.stat()
                payload, details = _descriptor_read(root, relative)
                status = ArtifactStatus.AVAILABLE if _valid_governed_content(relative, payload) else ArtifactStatus.MALFORMED
                size = details.st_size
            except FileNotFoundError:
                status, size = ArtifactStatus.MISSING, None
            except PermissionError:
                status, size = ArtifactStatus.DENIED, None
            except OSError:
                status, size = ArtifactStatus.MALFORMED, None
            except ValueError:
                status, size = ArtifactStatus.MALFORMED, None
            prior = previous.get(relative)
            if status is not ArtifactStatus.AVAILABLE and prior is not None and prior.size_bytes is not None:
                size = prior.size_bytes
            fingerprint = (int(getattr(details, "st_mtime_ns", 0)), int(size or 0)) if status is ArtifactStatus.AVAILABLE else (0, int(size or 0))
            cache_key = (run.run_id, relative)
            if prior is not None and prior.status is status and prior.size_bytes == size and self._fingerprints.get(cache_key, fingerprint) == fingerprint:
                observations.append(prior)
            else:
                observations.append(ArtifactObservation(relative, status, now, size))
            self._fingerprints[cache_key] = fingerprint
        return tuple(observations)

    @staticmethod
    def _runs_root(run: RunRecord) -> Path | None:
        workspace = Path(run.workspace_root).expanduser().resolve()
        current = workspace
        for component in ("planning-mds", "operations", "evidence", "runs"):
            current = current / component
            if current.is_symlink():
                return None
        try:
            resolved = current.resolve()
            resolved.relative_to(workspace)
        except (OSError, ValueError):
            return None
        return resolved

    def _discover_root(self, run: RunRecord) -> Path | None:
        runs_root = self._runs_root(run)
        if runs_root is None:
            return None
        if run.evidence_root:
            requested = Path(run.evidence_root).expanduser()
            try:
                existing = requested.resolve()
            except OSError:
                return None
            if (
                requested.is_absolute()
                and not requested.is_symlink()
                and not requested.parent.is_symlink()
                and existing.parent == runs_root
                and existing.is_dir()
            ):
                return existing
            return None
        candidates: list[tuple[int, Path]] = []
        for manifest in runs_root.glob("*/evidence-manifest.json"):
            try:
                details = manifest.stat()
                candidate_root = manifest.parent.resolve()
                if (
                    details.st_size > 1_048_576
                    or manifest.is_symlink()
                    or manifest.parent.is_symlink()
                    or candidate_root.parent != runs_root
                ):
                    continue
                payload, _ = _descriptor_read(candidate_root, "evidence-manifest.json")
                document = json.loads(payload.decode("utf-8"))
                if document.get("feature_id") != run.feature_id or document.get("status") not in {"draft", "in-progress"}:
                    continue
                candidates.append((details.st_mtime_ns, candidate_root))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                continue
        return max(candidates, default=(0, None), key=lambda item: item[0])[1]

    @staticmethod
    def _manifest_document(root: Path | None) -> dict[str, object] | None:
        if root is None:
            return None
        manifest = root / "evidence-manifest.json"
        try:
            details = manifest.stat()
            if manifest.is_symlink() or not manifest.is_file() or details.st_size > 1_048_576:
                return None
            payload, _ = _descriptor_read(root, "evidence-manifest.json")
            document = json.loads(payload.decode("utf-8"))
            return document if isinstance(document, dict) else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _completion_map(document: object) -> dict[int, bool]:
        if not isinstance(document, dict):
            return {number: False for number in range(9)}

        def passed(value: object) -> bool:
            return isinstance(value, dict) and str(value.get("result", "")).upper() in {
                "PASS", "PASSED", "APPROVED", "APPROVED WITH RECOMMENDATIONS", "PASS WITH RECOMMENDATIONS",
            }

        results = document.get("gate_results", {})
        gate_results = results if isinstance(results, dict) else {}
        role_results = document.get("role_results", {})
        roles = role_results if isinstance(role_results, dict) else {}
        required_roles = set(document.get("required_roles", ())) if isinstance(document.get("required_roles", ()), list) else set()

        def required_roles_pass(names: tuple[str, ...]) -> bool:
            applicable = tuple(name for name in names if name in required_roles)
            return bool(applicable) and all(passed(roles.get(name)) for name in applicable)

        return {
            0: passed(gate_results.get("assembly_plan_validation")),
            1: document.get("runtime_bearing") is False or passed(gate_results.get("runtime_preflight")),
            2: passed(gate_results.get("self_review")) and (
                required_roles_pass(("Quality Engineer", "DevOps"))
                or not required_roles.intersection({"Quality Engineer", "DevOps"})
            ),
            3: required_roles_pass(("Code Reviewer", "Security Reviewer"))
                or (
                    passed(gate_results.get("code_review"))
                    and ("Security Reviewer" not in required_roles or passed(gate_results.get("security_review")))
                ),
            4: passed(gate_results.get("approval")),
            5: passed(gate_results.get("signoff")),
            6: passed(gate_results.get("candidate_evidence")),
            7: passed(gate_results.get("kg_reconciliation")),
            8: passed(gate_results.get("pm_closeout")) and passed(gate_results.get("tracker_sync")),
        }

    @staticmethod
    def _gate_for_manifest(root: Path | None, source: object) -> tuple[str, tuple[str, ...]]:
        if root is None:
            return "G0", ("evidence-manifest.json", *_GATE_REQUIREMENTS["G0"])
        document = source if isinstance(source, dict) else PollingEvidenceWatcher._manifest_document(root)
        if document is None:
            return "G0", ("evidence-manifest.json", *_GATE_REQUIREMENTS["G0"])
        completed = PollingEvidenceWatcher._completion_map(document)
        current = next((number for number in range(9) if not completed[number]), 8)
        gate_id = f"G{current}"
        return gate_id, ("evidence-manifest.json", *_GATE_REQUIREMENTS[gate_id])

    @staticmethod
    def _production_paths(current_paths: Sequence[str]) -> tuple[str, ...]:
        all_gate_paths = tuple(path for gate in _GATE_REQUIREMENTS.values() for path in gate)
        return tuple(dict.fromkeys((*current_paths, *_LIFECYCLE_PATHS, *all_gate_paths)))

    @staticmethod
    def _feature_paths(run: RunRecord) -> tuple[str, ...]:
        workspace = Path(run.workspace_root).resolve()
        feature_root = governed_feature_root(workspace, run.feature_id)
        if feature_root is None:
            return ()
        candidates = [feature_root / "STATUS.md"]
        candidates.extend(sorted(feature_root.glob(f"{run.feature_id}-S*.md")))
        stories = feature_root / "stories"
        if stories.is_dir() and not stories.is_symlink():
            candidates.extend(sorted(stories.glob(f"{run.feature_id}-S*.md")))
        return tuple(str(path.relative_to(workspace)) for path in candidates)

    def reconcile_paths(self, run: RunRecord, paths: Sequence[str]) -> EvidenceReconciliation:
        observations = self.observe_once(run, paths)
        malformed = any(item.status in (ArtifactStatus.MALFORMED, ArtifactStatus.DENIED) for item in observations)
        if malformed:
            # Never replace a previously valid registry projection with
            # malformed or boundary-denied metadata.
            gate = replace(run.gate, status=GateStatus.BLOCKED, evidence_ready=False)
            return EvidenceReconciliation(run.evidence_root, run.artifacts, gate, "artifact-malformed")
        ready = bool(observations) and all(item.status is ArtifactStatus.AVAILABLE for item in observations)
        gate = replace(run.gate, status=GateStatus.PENDING if ready else GateStatus.BLOCKED, evidence_ready=ready)
        return EvidenceReconciliation(run.evidence_root, observations, gate, None)

    def reconcile(self, run: RunRecord) -> EvidenceReconciliation:
        root = self._discover_root(run)
        if run.evidence_root is not None and root is None:
            gate = replace(run.gate, status=GateStatus.BLOCKED, evidence_ready=False)
            return EvidenceReconciliation(run.evidence_root, run.artifacts, gate, "evidence-root-denied")
        manifest = self._manifest_document(root)
        if root is not None and manifest is None and run.evidence_root is not None:
            # Preserve the last valid durable evidence projection. The caller
            # exposes this blocked gate only in its read projection; malformed
            # metadata must never replace the last valid registry snapshot.
            gate = replace(run.gate, status=GateStatus.BLOCKED, evidence_ready=False)
            return EvidenceReconciliation(run.evidence_root, run.artifacts, gate, "manifest-unreadable")
        gate_id, paths = self._gate_for_manifest(root, manifest)
        observed_run = run if root is None else replace(run, evidence_root=str(root))
        evidence_observations = self.observe_once(observed_run, self._production_paths(paths))
        if root is not None and evidence_observations and evidence_observations[0].status is not ArtifactStatus.AVAILABLE:
            gate = replace(run.gate, status=GateStatus.BLOCKED, evidence_ready=False)
            return EvidenceReconciliation(run.evidence_root, run.artifacts, gate, "manifest-unreadable")
        feature_paths = self._feature_paths(run)
        feature_observations = self.observe_once(
            replace(run, evidence_root=str(Path(run.workspace_root).resolve())), feature_paths,
        ) if feature_paths else ()
        observations = (*evidence_observations, *feature_observations)
        current_by_path = {item.relative_path: item for item in evidence_observations}
        required_observations = tuple(current_by_path[path] for path in paths if path in current_by_path)
        semantic_ready = self.semantic_gate_ready(observed_run, gate_id)
        ready = semantic_ready and len(required_observations) == len(paths) and all(
            item.status is ArtifactStatus.AVAILABLE for item in required_observations
        )
        decision = run.gate.decision if run.gate.gate_id == gate_id else None
        gate = GateSnapshot(
            gate_id,
            GateStatus.PENDING if ready else GateStatus.BLOCKED,
            ready,
            paths,
            decision,
        )
        return EvidenceReconciliation(str(root) if root else None, observations, gate, None)

    def semantic_gate_ready(self, run: RunRecord, gate_id: str) -> bool:
        if not gate_id.startswith("G") or not gate_id[1:].isdigit():
            return False
        root = self._discover_root(run)
        if root is None:
            return False
        document = self._manifest_document(root)
        if document is None:
            return False
        gate_number = int(gate_id[1:])
        # G4 is the explicit operator approval being evaluated; requiring a
        # pre-existing approval verdict here would be circular.
        return gate_number == 4 or self._completion_map(document).get(gate_number, False)


class AllowlistedValidatorRunner:
    def __init__(self, process: SubprocessRunner, clock) -> None:
        self._process = process
        self._clock = clock

    def run(
        self,
        key: ValidatorKey,
        *,
        workspace_root: Path,
        feature_id: str,
        run_id: str,
        timeout_seconds: float,
    ) -> ValidatorResult:
        feature_path = governed_feature_root(workspace_root, feature_id)
        if feature_path is None:
            raise error(
                ErrorCode.PATH_DENIED,
                "Feature validation path is not a unique governed directory",
                "path-denied",
                "Restore the canonical non-symlink feature and story paths.",
            )
        scripts = {
            ValidatorKey.STORIES: ("agents", "product-manager", "scripts", "validate-stories.py"),
            ValidatorKey.TRACKERS: ("agents", "product-manager", "scripts", "validate-trackers.py"),
            ValidatorKey.TEMPLATES: ("agents", "scripts", "validate_templates.py"),
        }
        templates = {
            ValidatorKey.STORIES: "python3 validate-stories.py --product-root {workspace} {feature}",
            ValidatorKey.TRACKERS: "python3 validate-trackers.py --product-root {workspace} --skip-feature-evidence",
            ValidatorKey.TEMPLATES: "python3 validate_templates.py",
        }
        descriptors: list[int] = []
        try:
            workspace_fd = self._open_workspace(workspace_root)
            descriptors.append(workspace_fd)
            script_fd = self._open_governed(workspace_fd, scripts[key], directory=False)
            descriptors.append(script_fd)
            feature_fd: int | None = None
            if key is ValidatorKey.STORIES:
                feature_parts = feature_path.relative_to(workspace_root.resolve()).parts
                feature_fd = self._open_governed(workspace_fd, feature_parts, directory=True)
                descriptors.append(feature_fd)
            workspace_descriptor = f"/proc/self/fd/{workspace_fd}"
            script_path = f"/proc/self/fd/{script_fd}"
            feature_descriptor = f"/proc/self/fd/{feature_fd}" if feature_fd is not None else None
            if any(not Path(f"/proc/self/fd/{fd}").exists() for fd in descriptors):
                raise error(
                    ErrorCode.PATH_DENIED,
                    "Descriptor-bound validator execution is unavailable",
                    "path-denied",
                    "Run validators on a local platform with stable descriptor paths.",
                )
            argv_by_key = {
                ValidatorKey.STORIES: (
                    "python3",
                    script_path,
                    "--product-root",
                    workspace_descriptor,
                    "--story-root-fd",
                    str(feature_fd),
                    str(feature_descriptor),
                ),
                ValidatorKey.TRACKERS: (
                    "python3", script_path, "--product-root", workspace_descriptor, "--skip-feature-evidence",
                ),
                ValidatorKey.TEMPLATES: ("python3", script_path),
            }
            result = self._process.run(
                argv_by_key[key],
                cwd=Path(workspace_descriptor),
                timeout_seconds=timeout_seconds,
                capture_limit=64_000,
                env_names=("PATH", "LANG", "LC_ALL", "PYTHONPATH"),
                pass_fds=tuple(descriptors),
            )
        finally:
            for fd in reversed(descriptors):
                os.close(fd)
        summary = (result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr).strip()
        if len(summary) > 4_000:
            summary = summary[:3_997] + "..."
        artifact = workspace_root / "planning-mds" / "operations" / "evidence" / "runs" / run_id / "artifacts" / "tests" / f"validator-{key.value}.log"
        artifact_path = str(artifact) if artifact.exists() and not artifact.is_symlink() and artifact.is_file() else None
        return ValidatorResult(
            key, result.exit_code, result.duration_ms, summary, artifact_path, self._clock.now(), templates[key],
        )

    @staticmethod
    def _open_workspace(workspace_root: Path) -> int:
        requested = workspace_root.expanduser()
        if requested.is_symlink():
            raise error(
                ErrorCode.PATH_DENIED,
                "Workspace root cannot be a symlink",
                "path-denied",
                "Use the canonical workspace directory.",
            )
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            return os.open(requested.resolve(strict=True), directory_flags)
        except OSError as exc:
            raise error(
                ErrorCode.PATH_DENIED,
                "Workspace root cannot be opened safely",
                "path-denied",
                "Use the canonical workspace directory.",
            ) from exc

    @staticmethod
    def _open_governed(workspace_fd: int, components: Sequence[str], *, directory: bool) -> int:
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        current_fd = os.dup(workspace_fd)
        try:
            for component in components[:-1]:
                if component in ("", ".", ".."):
                    raise PermissionError("unsafe governed path component")
                next_fd = os.open(component, directory_flags, dir_fd=current_fd)
                os.close(current_fd)
                current_fd = next_fd
            leaf_flags = directory_flags if directory else os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(components[-1], leaf_flags, dir_fd=current_fd)
            details = os.fstat(fd)
            expected_kind = stat.S_ISDIR(details.st_mode) if directory else stat.S_ISREG(details.st_mode)
            if not expected_kind or details.st_uid != os.getuid() or (not directory and stat.S_IMODE(details.st_mode) & 0o022):
                os.close(fd)
                raise PermissionError("unsafe governed path leaf")
            return fd
        except (OSError, ValueError, IndexError) as exc:
            raise error(
                ErrorCode.PATH_DENIED,
                "Validator path is outside the governed workspace",
                "path-denied",
                "Restore the canonical non-symlink validator and feature paths.",
            ) from exc
        finally:
            os.close(current_fd)
