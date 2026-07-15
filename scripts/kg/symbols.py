#!/usr/bin/env python3
"""Generate symbol-index.yaml from declared code paths in code-index.yaml.

Walks only files declared in code-index.yaml node bindings (no broad repo scans).
Dispatches each file to a per-language extractor:

- Python (.py)  via stdlib ast
- TypeScript (.ts, .tsx) via Node + ts-morph (scripts/kg/ts-symbols/)
- C# (.cs) via .NET + Roslyn (scripts/kg/csharp-symbols/)

Emits planning-mds/knowledge-graph/symbol-index.yaml keyed by canonical node.
Maintains a per-file content-hash cache under .kg-state/ so unchanged files
are not re-parsed on subsequent runs. Cross-file caller/callee edges are
resolved each run by matching called names within the same canonical node.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml

from kg_common import (
    KG_DIR,
    REPO_ROOT,
    collect_referenced_node_ids,
    emit_telemetry,
    estimate_tokens,
    expand_declared_pattern,
    load_bundle,
)


SYMBOL_INDEX_PATH = KG_DIR / "symbol-index.yaml"
UNBOUND_REFS_PATH = KG_DIR / "unbound-but-referenced.yaml"
CACHE_DIR = REPO_ROOT / ".kg-state"
CACHE_PATH = CACHE_DIR / "symbols-cache.json"
# Tracks compilation_roots hash per language between runs. When a language's
# roots change, every cached entry for files of that language is invalidated
# because Roslyn / ts-morph resolution depends on which files are in the
# compilation, not just on the file being parsed.
COMPILATION_ROOTS_PATH = CACHE_DIR / "compilation-roots.json"

LANGUAGE_BY_EXT = {
    ".py": "python",
    ".cs": "csharp",
    ".ts": "typescript",
    ".tsx": "typescript",
}

CS_EXTRACTOR_ROOT = REPO_ROOT / "scripts" / "kg" / "csharp-symbols"
TS_EXTRACTOR_ROOT = REPO_ROOT / "scripts" / "kg" / "ts-symbols"


# ---------------------------------------------------------------------------
# Record + ID helpers
# ---------------------------------------------------------------------------


@dataclass
class SymbolRecord:
    id: str
    node: str
    kind: str
    name: str
    file: str
    line: int
    signature: str
    visibility: str
    language: str
    container: str | None = None
    # 1-based last line of the declaration's syntax span. Consumed by
    # diff-impact.py to map a changed hunk to its enclosing symbol(s).
    # Zero when the extractor didn't emit it (Python/TS pre-Phase-A2);
    # diff-impact.py falls back to "until next symbol's start" in that case.
    end_line: int = 0
    # True when the symbol's file was matched via a code-index.yaml bucket
    # whose path segment is "tests" (e.g. backend.tests, frontend.tests,
    # tests). ANY-rule: if a file matches both a test and non-test bucket
    # it's classified as test, since the worst case is excluding it from
    # --check-untested reports rather than miscategorising production code.
    is_test: bool = False
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    # Calls harvested by the extractor. Each entry is either a bare string
    # (unresolved syntactic name — Python AST and TS extractors) or a dict
    # ``{name, container}`` from the Roslyn-based C# extractor where
    # ``container`` is the resolved declaring type. Resolved into
    # callers/callees by the orchestrator. Persisted in the cache but stripped
    # from the on-disk symbol-index.yaml.
    raw_calls: list[Any] = field(default_factory=list)
    # Interface members and base methods this symbol satisfies. Extractors emit
    # raw ``{name, container}`` dicts; ``resolve_call_edges`` replaces them
    # in-place with resolved symbol ids (list[str]) so the on-disk index can
    # answer ``--implementers`` / ``--overrides`` without re-resolution.
    # Unresolvable entries are dropped during resolution.
    implements: list[Any] = field(default_factory=list)
    # Type instantiations and type references emitted by C# and TS extractors
    # (cheap, high-value extra edges per the §11 measurement: ~0.4x existing
    # edge count combined). Raw lists carry ``{name, container}`` dicts from
    # the semantic extractors; ``resolve_call_edges`` rewrites the resolved
    # ``instantiates`` / ``type_refs`` arrays in-place with target symbol ids.
    # Unidirectional — no back-edge persisted on the target side.
    raw_instantiates: list[Any] = field(default_factory=list)
    raw_type_refs: list[Any] = field(default_factory=list)
    instantiates: list[str] = field(default_factory=list)
    type_refs: list[str] = field(default_factory=list)

    def to_cache_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_index_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("raw_calls", None)
        d.pop("raw_instantiates", None)
        d.pop("raw_type_refs", None)
        if d.get("container") is None:
            d.pop("container", None)
        if not d.get("end_line"):
            d.pop("end_line", None)
        if not d.get("implements"):
            d.pop("implements", None)
        if not d.get("is_test"):
            d.pop("is_test", None)
        if not d.get("instantiates"):
            d.pop("instantiates", None)
        if not d.get("type_refs"):
            d.pop("type_refs", None)
        return d


_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def slug(text: str) -> str:
    if not text:
        return ""
    s = _CAMEL_RE.sub("-", text)
    s = re.sub(r"[_\s]+", "-", s)
    s = re.sub(r"[^A-Za-z0-9.-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s.lower()


def symbol_id(
    node: str, container: str | None, name: str, file_rel: str | None = None
) -> str:
    """Stable symbol ID. Container (class) disambiguates members; file stem
    disambiguates top-level symbols across files bound to the same node."""
    node_slug = node.replace(":", "-")
    member = slug(name) or "anonymous"
    if container:
        member = f"{slug(container)}.{member}"
    elif file_rel:
        stem = Path(file_rel).stem
        if stem:
            member = f"{slug(stem)}.{member}"
    return f"symbol:{node_slug}:{member}"


# ---------------------------------------------------------------------------
# Extractor base + Python AST extractor
# ---------------------------------------------------------------------------


class BaseExtractor:
    language: str = ""

    def extract(
        self, files: list[Path], file_to_node: dict[str, str]
    ) -> list[SymbolRecord]:
        """Return symbol records with `raw_calls` populated.

        Each record's `raw_calls` is a best-effort list of names invoked
        inside the symbol's body. The orchestrator turns those names into
        caller/callee edges via cross-file name matching scoped to the
        symbol's canonical node.
        """
        raise NotImplementedError


def _py_visibility(name: str) -> str:
    return "private" if name.startswith("_") else "public"


def _py_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = ast.unparse(node.args) if hasattr(ast, "unparse") else ""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({args})"


class PythonAstExtractor(BaseExtractor):
    language = "python"
    # Forward-compat seam for product opt-in. Per memo §7 the default is
    # empty — Python is rarely a product's first-class language and the KG
    # pipeline itself lives in scripts/kg/. Products with first-class
    # Python override this on a per-product basis.
    compilation_roots: list[str] = []
    supports_sidecar: bool = True

    def __init__(self) -> None:
        super().__init__()
        self.last_sidecar: list[dict[str, Any]] = []
        # See SubprocessExtractor.last_sidecar_authoritative for semantics.
        self.last_sidecar_authoritative: bool = False

    def extract(
        self, files: list[Path], file_to_node: dict[str, str]
    ) -> list[SymbolRecord]:
        self.last_sidecar = []
        self.last_sidecar_authoritative = False
        records: list[SymbolRecord] = []

        for path in files:
            rel = path.relative_to(REPO_ROOT).as_posix()
            node_id = file_to_node.get(rel)
            if not node_id:
                continue
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, SyntaxError) as exc:
                print(
                    f"[symbols] python parse failed {rel}: {exc}", file=sys.stderr
                )
                continue

            self._walk(tree, rel, node_id, records)

        # Compilation-root walk for the sidecar. Best-effort name-matching
        # only — Python AST has no semantic resolution, so we record every
        # bare-name Call from unbound files; the orchestrator filters at
        # aggregation time to entries that resolve to a bound symbol.
        # Default compilation_roots is empty so this branch is a no-op
        # unless a product opted in.
        if self.compilation_roots and files:
            bound_rels = {p.relative_to(REPO_ROOT).as_posix() for p in files}
            bound_names: set[str] = set()
            for rec in records:
                bound_names.add(rec.name)
            self._collect_sidecar(bound_rels, bound_names)

        self.last_sidecar_authoritative = self.supports_sidecar
        return records

    def _collect_sidecar(
        self, bound_rels: set[str], bound_names: set[str]
    ) -> None:
        # Skip well-known noise directories so a product opting into
        # --compilation-root scripts/ doesn't drown reviewers in
        # site-packages-style entries.
        skip_dirs = {
            "node_modules", "dist", "bin", "obj", ".kg-state",
            "__pycache__", ".venv", "venv", ".tox", ".mypy_cache",
        }
        seen: set[tuple[str, int, str]] = set()
        for root in self.compilation_roots:
            root_path = REPO_ROOT / root
            if not root_path.is_dir():
                print(
                    f"[symbols] python compilation root missing: {root}",
                    file=sys.stderr,
                )
                continue
            for py in root_path.rglob("*.py"):
                if any(part in skip_dirs for part in py.parts):
                    continue
                rel = py.relative_to(REPO_ROOT).as_posix()
                if rel in bound_rels:
                    continue
                try:
                    source = py.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py))
                except (OSError, SyntaxError):
                    continue
                for child in ast.walk(tree):
                    if not isinstance(child, ast.Call):
                        continue
                    func = child.func
                    name: str | None = None
                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr
                    if not name or name not in bound_names:
                        continue
                    line = getattr(child, "lineno", 0) or 0
                    key = (rel, line, name)
                    if key in seen:
                        continue
                    seen.add(key)
                    # container=None since the AST extractor can't resolve
                    # the declaring type without a type checker. The
                    # orchestrator's by_name fallback resolves the entry.
                    self.last_sidecar.append({
                        "source_file": rel,
                        "source_line": line,
                        "target": {"name": name, "container": None},
                    })

    def _walk(
        self,
        tree: ast.Module,
        rel: str,
        node_id: str,
        records: list[SymbolRecord],
    ) -> None:
        def visit(parent_name: str | None, body: list[ast.stmt]) -> None:
            for stmt in body:
                if isinstance(stmt, ast.ClassDef):
                    records.append(SymbolRecord(
                        id=symbol_id(node_id, parent_name, stmt.name, file_rel=rel),
                        node=node_id,
                        kind="class",
                        name=stmt.name,
                        file=rel,
                        line=stmt.lineno,
                        end_line=getattr(stmt, "end_lineno", 0) or 0,
                        signature=f"class {stmt.name}",
                        visibility=_py_visibility(stmt.name),
                        language=self.language,
                        container=parent_name,
                    ))
                    visit(stmt.name, stmt.body)
                elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = "method" if parent_name else "function"
                    referenced: list[str] = []
                    for child in ast.walk(stmt):
                        if isinstance(child, ast.Call):
                            func = child.func
                            if isinstance(func, ast.Name):
                                referenced.append(func.id)
                            elif isinstance(func, ast.Attribute):
                                referenced.append(func.attr)
                    records.append(SymbolRecord(
                        id=symbol_id(node_id, parent_name, stmt.name, file_rel=rel),
                        node=node_id,
                        kind=kind,
                        name=stmt.name,
                        file=rel,
                        line=stmt.lineno,
                        end_line=getattr(stmt, "end_lineno", 0) or 0,
                        signature=_py_signature(stmt),
                        visibility=_py_visibility(stmt.name),
                        language=self.language,
                        container=parent_name,
                        raw_calls=referenced,
                    ))

        visit(None, tree.body)


# ---------------------------------------------------------------------------
# Subprocess extractor base (used by TS + C#)
# ---------------------------------------------------------------------------


class SubprocessExtractor(BaseExtractor):
    command: list[str] = []
    timeout_seconds: int = 600
    # Per-subclass defaults. Subclasses opt into the new C#-extractor CLI:
    #   compilation_roots — directories the extractor walks for files to add
    #     to the semantic compilation (emission stays scoped to the bound-files
    #     list passed via stdin).
    #   supports_sidecar — when True, the orchestrator passes --sidecar
    #     <tempfile> and reads the resulting JSON into self.last_sidecar.
    compilation_roots: list[str] = []
    supports_sidecar: bool = False

    def __init__(self) -> None:
        super().__init__()
        # Populated after each extract() call. Empty list when the extractor
        # does not support sidecar emission or produced no entries.
        self.last_sidecar: list[dict[str, Any]] = []
        # True iff the extractor actually ran the subprocess (i.e., emitted
        # current-truth sidecar data). False when extract() short-circuited
        # because there were no files to parse — in that case last_sidecar
        # carries no information and the previous on-disk sidecar yaml
        # should be preserved rather than overwritten.
        self.last_sidecar_authoritative: bool = False

    def is_available(self) -> bool:
        return bool(self.command)

    def extract(
        self, files: list[Path], file_to_node: dict[str, str]
    ) -> list[SymbolRecord]:
        self.last_sidecar = []
        self.last_sidecar_authoritative = False
        if not files:
            return []
        if not self.is_available():
            print(
                f"[symbols] {self.language} extractor not available; skipping {len(files)} files",
                file=sys.stderr,
            )
            return []

        payload = [p.relative_to(REPO_ROOT).as_posix() for p in files]

        cli = list(self.command)
        for root in self.compilation_roots:
            cli.extend(["--compilation-root", root])
        sidecar_path: Path | None = None
        if self.supports_sidecar:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            sidecar_path = CACHE_DIR / f"sidecar-{self.language}.json"
            if sidecar_path.exists():
                sidecar_path.unlink()
            cli.extend(["--sidecar", str(sidecar_path)])

        try:
            result = subprocess.run(
                cli,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            print(
                f"[symbols] {self.language} extractor timed out", file=sys.stderr
            )
            return []
        except FileNotFoundError as exc:
            print(
                f"[symbols] {self.language} extractor not invokable: {exc}",
                file=sys.stderr,
            )
            return []

        if result.stderr:
            for line in result.stderr.splitlines():
                print(f"[symbols/{self.language}] {line}", file=sys.stderr)
        if result.returncode != 0:
            print(
                f"[symbols] {self.language} extractor exited {result.returncode}",
                file=sys.stderr,
            )
            return []

        try:
            raw_items = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            print(
                f"[symbols] {self.language} extractor produced invalid JSON: {exc}",
                file=sys.stderr,
            )
            return []

        records: list[SymbolRecord] = []
        for item in raw_items:
            rel_file = item.get("file")
            node_id = file_to_node.get(rel_file)
            if not node_id:
                continue
            name = item.get("name")
            if not name:
                continue
            container = item.get("container") or None
            raw_calls = list(item.get("calls") or [])
            implements = [
                dict(impl)
                for impl in (item.get("implements") or [])
                if isinstance(impl, dict) and impl.get("name") and impl.get("container")
            ]
            raw_instantiates = [
                dict(ref)
                for ref in (item.get("instantiates") or [])
                if isinstance(ref, dict) and ref.get("name")
            ]
            raw_type_refs = [
                dict(ref)
                for ref in (item.get("type_refs") or [])
                if isinstance(ref, dict) and ref.get("name")
            ]
            records.append(SymbolRecord(
                id=symbol_id(node_id, container, name, file_rel=rel_file),
                node=node_id,
                kind=item.get("kind", "function"),
                name=name,
                file=rel_file,
                line=int(item.get("line", 0)) or 0,
                end_line=int(item.get("end_line", 0)) or 0,
                signature=item.get("signature", name),
                visibility=item.get("visibility", "public"),
                language=self.language,
                container=container,
                raw_calls=raw_calls,
                implements=implements,
                raw_instantiates=raw_instantiates,
                raw_type_refs=raw_type_refs,
            ))

        if sidecar_path is not None and sidecar_path.exists():
            try:
                loaded = json.loads(sidecar_path.read_text(encoding="utf-8") or "[]")
                if isinstance(loaded, list):
                    self.last_sidecar = loaded
            except json.JSONDecodeError as exc:
                print(
                    f"[symbols] {self.language} sidecar parse failed: {exc}",
                    file=sys.stderr,
                )
            try:
                sidecar_path.unlink()
            except OSError:
                pass
        # Subprocess completed (with or without sidecar entries); the current
        # state is authoritative for this language.
        self.last_sidecar_authoritative = self.supports_sidecar

        return records


class TsExtractor(SubprocessExtractor):
    language = "typescript"
    # Product-specific defaults. The TS extractor walks these roots in
    # addition to the bound-files stdin list so cross-binding callers (test
    # files, helpers outside code-index.yaml) participate in semantic
    # resolution. Symbols are still emitted only for bound files.
    compilation_roots = ["experience/src", "experience/tests"]
    supports_sidecar = True

    def __init__(self) -> None:
        super().__init__()
        node = shutil.which("node")
        entry = TS_EXTRACTOR_ROOT / "extract.js"
        node_modules = TS_EXTRACTOR_ROOT / "node_modules"
        if node and entry.exists() and node_modules.exists():
            self.command = [node, str(entry)]
        else:
            self.command = []


class CsExtractor(SubprocessExtractor):
    language = "csharp"
    # Product-specific defaults. The C# extractor walks these roots in
    # addition to the bound-files stdin list so cross-binding callers (test
    # files, helpers outside code-index.yaml) participate in semantic
    # resolution. Symbols are still emitted only for bound files.
    compilation_roots = ["engine/src", "engine/tests"]
    supports_sidecar = True

    def __init__(self) -> None:
        super().__init__()
        dotnet = shutil.which("dotnet")
        project = CS_EXTRACTOR_ROOT / "CSharpSymbols.csproj"
        if not (dotnet and project.exists()):
            self.command = []
            return
        # Prefer a pre-built DLL for speed; otherwise fall back to `dotnet run`.
        built = list(
            (CS_EXTRACTOR_ROOT / "bin" / "Release").glob("net*/CSharpSymbols.dll")
        )
        if built:
            self.command = [dotnet, str(built[0])]
        else:
            self.command = [
                dotnet,
                "run",
                "--project",
                str(project),
                "--configuration",
                "Release",
                "--",
            ]


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@dataclass
class FileCacheEntry:
    sha256: str
    mtime: float
    symbols: list[dict[str, Any]]  # each dict is SymbolRecord.to_cache_dict()


def load_cache() -> dict[str, FileCacheEntry]:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, FileCacheEntry] = {}
    for rel, value in data.items():
        try:
            out[rel] = FileCacheEntry(
                sha256=value["sha256"],
                mtime=float(value.get("mtime", 0.0)),
                symbols=list(value.get("symbols", [])),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def save_cache(cache: dict[str, FileCacheEntry]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    serial = {
        rel: {
            "sha256": entry.sha256,
            "mtime": entry.mtime,
            "symbols": entry.symbols,
        }
        for rel, entry in cache.items()
    }
    CACHE_PATH.write_text(
        json.dumps(serial, sort_keys=True), encoding="utf-8"
    )


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_compilation_roots(roots: list[str]) -> list[str]:
    """Stable, displayable form of a compilation-root list."""
    return sorted({r.replace("\\", "/").rstrip("/") for r in roots if r})


def compilation_roots_hash(roots: list[str]) -> str:
    """Stable digest of a sorted, normalized root list."""
    normalized = normalized_compilation_roots(roots)
    joined = "\n".join(normalized).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def load_previous_roots_hashes() -> dict[str, str]:
    if not COMPILATION_ROOTS_PATH.exists():
        return {}
    try:
        data = json.loads(COMPILATION_ROOTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: str(v) for k, v in data.items() if isinstance(v, str)}


def save_roots_hashes(hashes: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    COMPILATION_ROOTS_PATH.write_text(
        json.dumps(hashes, sort_keys=True), encoding="utf-8"
    )


def invalidate_cache_by_language(
    cache: dict[str, FileCacheEntry], languages: set[str]
) -> int:
    """Drop cache entries for files of the given languages. Returns drop count."""
    if not languages:
        return 0
    dropped = 0
    for rel in list(cache.keys()):
        ext = Path(rel).suffix.lower()
        if LANGUAGE_BY_EXT.get(ext) in languages:
            cache.pop(rel, None)
            dropped += 1
    return dropped


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def resolve_files_for_binding(binding: dict[str, Any]) -> list[tuple[Path, str]]:
    seen: set[str] = set()
    out: list[tuple[Path, str]] = []
    for entry in binding.get("declared_paths", []):
        for rel in expand_declared_pattern(entry["pattern"]):
            if rel in seen:
                continue
            seen.add(rel)
            abs_path = REPO_ROOT / rel
            if not abs_path.is_file():
                continue
            lang = LANGUAGE_BY_EXT.get(abs_path.suffix.lower())
            if lang:
                out.append((abs_path, lang))
    return out


def collect_test_files(bundle: dict[str, Any]) -> set[str]:
    """Return the set of repo-relative paths matched via test buckets.

    A bucket is a dotted YAML key path (kg_common._collect_patterns) such as
    `backend.tests` or `frontend.tests`. The convention: any bucket whose
    dot-segments include `tests` (case-insensitive) is a test bucket. ANY-rule
    per memo §5 — a file matching both a test and non-test bucket counts as
    test so it's excluded from --check-untested noise.
    """
    test_files: set[str] = set()
    for binding in bundle["bindings"].values():
        for entry in binding.get("declared_paths", []) or []:
            bucket = str(entry.get("bucket", ""))
            if "tests" not in {s.lower() for s in bucket.split(".") if s}:
                continue
            for rel in expand_declared_pattern(entry.get("pattern", "")):
                test_files.add(rel)
    return test_files


def collect_work_items(
    bundle: dict[str, Any],
    node_filter: set[str] | None,
    language_filter: set[str] | None,
) -> dict[str, dict[Path, str]]:
    """Group files by language, mapping each file to its first claiming node."""
    work_by_lang: dict[str, dict[Path, str]] = {}
    for node_id, binding in bundle["bindings"].items():
        if node_filter and node_id not in node_filter:
            continue
        for abs_path, lang in resolve_files_for_binding(binding):
            if language_filter and lang not in language_filter:
                continue
            lang_map = work_by_lang.setdefault(lang, {})
            if abs_path not in lang_map:
                lang_map[abs_path] = node_id
    return work_by_lang


def run_extractor(
    extractor: BaseExtractor,
    files: list[Path],
    file_to_node: dict[str, str],
    cache: dict[str, FileCacheEntry],
    new_cache: dict[str, FileCacheEntry],
    force: bool,
    stats: dict[str, int],
) -> list[SymbolRecord]:
    """Split files into cached vs needs-parse; return merged records.

    Each returned SymbolRecord carries its `raw_calls` list. Records loaded
    from cache reconstruct via SymbolRecord(**dict) since the cache stores
    SymbolRecord.to_cache_dict() output (which preserves raw_calls).
    """
    records: list[SymbolRecord] = []
    to_parse: list[Path] = []
    parse_file_to_node: dict[str, str] = {}

    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        stats["files"] += 1
        mtime = path.stat().st_mtime
        sha = hash_file(path)
        cached = None if force else cache.get(rel)
        if cached and cached.sha256 == sha:
            for sym in cached.symbols:
                records.append(SymbolRecord(**sym))
            new_cache[rel] = cached
            stats["cached"] += 1
            continue
        to_parse.append(path)
        parse_file_to_node[rel] = file_to_node[rel]
        new_cache[rel] = FileCacheEntry(sha256=sha, mtime=mtime, symbols=[])

    if to_parse:
        new_records = extractor.extract(to_parse, parse_file_to_node)
        records.extend(new_records)

        symbols_by_file: dict[str, list[dict[str, Any]]] = {}
        for rec in new_records:
            symbols_by_file.setdefault(rec.file, []).append(rec.to_cache_dict())

        for path in to_parse:
            rel = path.relative_to(REPO_ROOT).as_posix()
            new_cache[rel].symbols = symbols_by_file.get(rel, [])
            stats["parsed"] += 1

    return records


def resolve_call_edges(records: list[SymbolRecord]) -> None:
    """Resolve each record's ``raw_calls`` into callers/callees edges.

    Two-tier resolution:

    1. **Qualified lookup** — when the extractor returns ``{name, container}``
       (Roslyn-resolved C# invocations), match globally on
       ``(container, name)``. This crosses canonical-node boundaries so an
       endpoint on ``entity:order`` correctly reaches a service method on
       ``entity:customer``.
    2. **Same-node name fallback** — when the extractor only gave a bare
       name (Python AST, TS extractor, or an unresolved Roslyn invocation),
       fall back to matching on ``(node, name)``. Same behavior as before.

    Interface dispatch is grown via each record's ``implements`` array: for
    every interface member or base method an impl satisfies, add a synthetic
    edge from the interface member to the impl. A caller of the interface
    member then reaches every implementation through normal callee traversal.

    Over-linking is acceptable for a retrieval aid; raw artifacts remain
    authoritative per ``solution-ontology.yaml.authority.precedence``.
    """
    by_node_name: dict[tuple[str, str], list[SymbolRecord]] = {}
    by_qualified: dict[tuple[str, str], list[SymbolRecord]] = {}
    # Cross-node lookup for top-level types — used by instantiates / type_refs
    # whose target is a class, record, struct, interface, enum, or type alias.
    # Methods/properties stay constrained to (container, name) so call
    # resolution semantics are unchanged.
    TYPE_KINDS = frozenset({"class", "record", "struct", "interface", "enum", "type", "delegate"})
    by_top_level_type_name: dict[str, list[SymbolRecord]] = {}
    for rec in records:
        by_node_name.setdefault((rec.node, rec.name), []).append(rec)
        if rec.container:
            by_qualified.setdefault((rec.container, rec.name), []).append(rec)
        elif rec.kind in TYPE_KINDS:
            by_top_level_type_name.setdefault(rec.name, []).append(rec)

    def add_edge(caller: SymbolRecord, callee: SymbolRecord) -> None:
        if callee.id == caller.id:
            return
        if callee.id not in caller.callees:
            caller.callees.append(callee.id)
        if caller.id not in callee.callers:
            callee.callers.append(caller.id)

    for caller in records:
        for call in caller.raw_calls:
            if isinstance(call, dict):
                name = call.get("name")
                container = call.get("container")
                if not name:
                    continue
                if container:
                    for callee in by_qualified.get((container, name), []):
                        add_edge(caller, callee)
                else:
                    for callee in by_node_name.get((caller.node, name), []):
                        add_edge(caller, callee)
            else:
                name = str(call)
                if not name:
                    continue
                for callee in by_node_name.get((caller.node, name), []):
                    add_edge(caller, callee)

    # Polymorphic dispatch: every interface member reaches its implementations.
    # Also rewrites each impl.implements list from raw {name, container} dicts
    # into resolved symbol ids so the on-disk index can answer --implementers /
    # --overrides without re-resolution. Unresolvable entries are dropped.
    for impl in records:
        resolved_iface_ids: list[str] = []
        for iface_ref in impl.implements:
            iface_name = iface_ref.get("name") if isinstance(iface_ref, dict) else None
            iface_container = iface_ref.get("container") if isinstance(iface_ref, dict) else None
            if not (iface_name and iface_container):
                continue
            for iface_member in by_qualified.get((iface_container, iface_name), []):
                add_edge(iface_member, impl)
                resolved_iface_ids.append(iface_member.id)
        # Sort/dedupe for stable diffs.
        impl.implements = sorted(set(resolved_iface_ids))

    # Resolve raw_instantiates / raw_type_refs into target symbol ids. These
    # are unidirectional — the target does NOT gain a reciprocal edge, so a
    # symbol's `callers` semantics stay unchanged. Consumers that want
    # reverse-scan (e.g. "who instantiates Foo") reverse the array at query
    # time the same way --implementers reverses `implements`.
    #
    # Resolution falls back from (container, name) qualified lookup to
    # cross-node `by_top_level_type_name` so an instantiation on
    # entity:order that targets a class bound to entity:customer resolves
    # correctly. Same-node `by_node_name` is also consulted as a final
    # fallback for languages whose extractor doesn't emit container info.
    def _resolve_refs(refs: list[Any], own_node: str) -> list[str]:
        resolved: set[str] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            name = ref.get("name")
            if not name:
                continue
            container = ref.get("container")
            if container:
                for target in by_qualified.get((container, name), []):
                    resolved.add(target.id)
                continue
            per_ref_hits: set[str] = set()
            for target in by_top_level_type_name.get(name, []):
                per_ref_hits.add(target.id)
            if not per_ref_hits:
                for target in by_node_name.get((own_node, name), []):
                    per_ref_hits.add(target.id)
            resolved.update(per_ref_hits)
        return sorted(resolved)

    for rec in records:
        rec.instantiates = _resolve_refs(rec.raw_instantiates, rec.node)
        # A symbol referencing its own declared type is noise; drop self-edges.
        rec.instantiates = [s for s in rec.instantiates if s != rec.id]
        rec.type_refs = _resolve_refs(rec.raw_type_refs, rec.node)
        rec.type_refs = [s for s in rec.type_refs if s != rec.id]

    for rec in records:
        rec.callers.sort()
        rec.callees.sort()


# ---------------------------------------------------------------------------
# Reachability and dead-code detection
# ---------------------------------------------------------------------------
#
# Reachability is BFS from declared entry points walking the `callees` graph.
# An entry point is any symbol the runtime/framework invokes from outside the
# symbol index — HTTP endpoint handlers, UI route components, hosted services,
# infrastructure callbacks (event handlers, middleware, filters, …).
#
# Reachability is a routing aid for dead-code review, not authority. Raw source
# remains authoritative per `solution-ontology.yaml.authority.precedence`.
# Call-edge resolution is name-matched within the same canonical node
# (`resolve_call_edges`), so cross-node reach is invisible to this layer.
# Confidence weighting compensates by *lowering* confidence when a node has
# feature-mapping refs that could carry an untracked cross-node flow.

DEFAULT_ENTRY_NODE_KINDS: frozenset[str] = frozenset({"endpoint", "ui_route"})

# Framework-pattern name suffixes that mark a symbol as an infrastructure
# entry point. These are invoked by DI containers / message buses / pipeline
# stages — no caller appears in the symbol index because the call site is
# outside the indexed code.
FRAMEWORK_ENTRY_NAME_SUFFIXES: tuple[str, ...] = (
    "Handler",
    "Listener",
    "Subscriber",
    "Consumer",
    "Plugin",
    "Adapter",
    "Middleware",
    "Filter",
    "Interceptor",
)

# File patterns whose symbols are entry points the symbol index cannot see —
# either the runtime invokes them (hosted services, app bootstrappers) or a
# test runner does (xUnit, vitest, pytest, …). Cross-language: .cs, .ts/tsx,
# and .py covered.
FRAMEWORK_ENTRY_FILE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|/)[^/]*HostedService\.[^/]+$"),
    re.compile(r"(^|/)[^/]*BackgroundService\.[^/]+$"),
    re.compile(r"(^|/)[^/]*Worker\.[^/]+$"),
    re.compile(r"(^|/)[^/]*Endpoints?\.cs$"),
    re.compile(r"(^|/)[^/]*Controller\.cs$"),
    re.compile(r"(^|/)Program\.cs$"),
    re.compile(r"(^|/)Startup\.cs$"),
    # EF Core IEntityTypeConfiguration<T>.Configure is invoked via
    # ApplyConfigurationsFromAssembly — reflection again.
    re.compile(r"(^|/)Configurations/"),
    re.compile(r"(^|/)[^/]*Configuration\.cs$"),
    # Seed data and DI registration helpers are invoked from bootstrappers
    # whose call edges are erased by same-node call resolution.
    re.compile(r"(^|/)[^/]*SeedData\.cs$"),
    re.compile(r"(^|/)[^/]*Seeder\.cs$"),
    re.compile(r"(^|/)[^/]*Extensions\.cs$"),
    re.compile(r"(^|/)[^/]*Module\.cs$"),
    re.compile(r"(^|/)[^/]*Registration\.cs$"),
    re.compile(r"(^|/)DependencyInjection\.cs$"),
    re.compile(r"(^|/)Migrations/"),
    # Test files across stacks — test runners invoke methods via reflection,
    # so callers never appear in the symbol index.
    re.compile(r"(^|/)[^/]*Tests?\.cs$"),
    re.compile(r"(^|/)[^/]*\.test\.[tj]sx?$"),
    re.compile(r"(^|/)[^/]*\.spec\.[tj]sx?$"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"(^|/)[^/]+_test\.py$"),
    re.compile(r"(^|/)tests?/"),
)

# Symbol kinds that are declarations rather than callable bodies. Reporting
# them as "dead" would double-count — the body symbols on the same type carry
# the real signal. Classes/records/structs/enums/delegates/interfaces/types
# never have call edges in this graph.
DEAD_CODE_SKIP_KINDS: frozenset[str] = frozenset(
    {
        "constructor",
        "class",
        "record",
        "struct",
        "interface",
        "type",
        "enum",
        "delegate",
        "property",
    }
)


@dataclass
class ReachabilityRecord:
    symbol_id: str
    reachable: bool
    entry_point: bool
    entry_reason: str | None  # e.g. "node-kind:endpoint", "name-suffix:Handler"
    distance: int | None  # 0 for entry points; None for unreached


@dataclass
class DeadCodeCandidate:
    symbol_id: str
    node: str
    file: str
    line: int
    kind: str
    name: str
    visibility: str
    language: str
    confidence: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_framework_entry_name(name: str) -> bool:
    return any(name.endswith(suffix) for suffix in FRAMEWORK_ENTRY_NAME_SUFFIXES)


def _is_framework_entry_file(file_rel: str) -> bool:
    return any(p.search(file_rel) for p in FRAMEWORK_ENTRY_FILE_PATTERNS)


def identify_entry_points(
    records: list[SymbolRecord],
    bundle: dict[str, Any],
    *,
    entry_node_kinds: frozenset[str] = DEFAULT_ENTRY_NODE_KINDS,
) -> dict[str, str]:
    """Return {symbol_id: entry_reason} for every entry-point symbol."""
    canonical_nodes = bundle.get("canonical_nodes", {})
    entries: dict[str, str] = {}
    for rec in records:
        node = canonical_nodes.get(rec.node)
        if node and node.get("_kind") in entry_node_kinds:
            entries[rec.id] = f"node-kind:{node['_kind']}"
            continue
        if _is_framework_entry_name(rec.name):
            entries[rec.id] = f"name-suffix:{rec.name}"
            continue
        if _is_framework_entry_file(rec.file):
            entries[rec.id] = "file-pattern:hosted-service"
            continue
    return entries


def compute_reachability(
    records: list[SymbolRecord],
    bundle: dict[str, Any],
    *,
    entry_node_kinds: frozenset[str] = DEFAULT_ENTRY_NODE_KINDS,
) -> dict[str, ReachabilityRecord]:
    """BFS reachability over the `callees` graph from declared entry points."""
    by_id = {rec.id: rec for rec in records}
    entries = identify_entry_points(records, bundle, entry_node_kinds=entry_node_kinds)
    distance: dict[str, int] = {sid: 0 for sid in entries}

    frontier = list(entries.keys())
    while frontier:
        next_frontier: list[str] = []
        for sid in frontier:
            rec = by_id.get(sid)
            if not rec:
                continue
            d = distance[sid]
            for callee in rec.callees:
                if callee in distance:
                    continue
                distance[callee] = d + 1
                next_frontier.append(callee)
        frontier = next_frontier

    return {
        rec.id: ReachabilityRecord(
            symbol_id=rec.id,
            reachable=rec.id in distance,
            entry_point=rec.id in entries,
            entry_reason=entries.get(rec.id),
            distance=distance.get(rec.id),
        )
        for rec in records
    }


def _score_dead_code(
    rec: SymbolRecord,
    bundle: dict[str, Any],
    referenced_nodes: set[str],
) -> tuple[float, list[str]]:
    """Confidence that an unreached symbol is genuinely dead.

    Baseline 0.6 for "unreached from any entry point". Bumps:
    - +0.2 if the symbol has zero callers anywhere in the index
    - +0.1 if the symbol is publicly visible (any consumer outside its assembly
           should be reachable; broad surface area amplifies the signal)
    Dampers:
    - −0.2 if the symbol's node is not referenced by feature mappings
           (likely already covered by the ontology orphan check; avoid double
           reporting)
    - −0.2 if visibility is private/internal/protected — likely an intentional
           internal helper that the same-node call resolver missed
    """
    score = 0.6
    reasons: list[str] = ["unreached from any entry point"]

    if not rec.callers:
        score += 0.2
        reasons.append("no callers in symbol-index")

    if rec.visibility == "public":
        score += 0.1
        reasons.append("publicly visible (no consumer in indexed code)")
    elif rec.visibility in {"private", "internal", "protected"}:
        score -= 0.2
        reasons.append(
            f"visibility={rec.visibility} (intentional internal scope possible)"
        )

    if rec.node not in referenced_nodes:
        score -= 0.2
        reasons.append(
            "node has no feature-mapping refs (ontology orphan — covered separately)"
        )

    return max(0.0, min(1.0, round(score, 2))), reasons


def find_dead_code_candidates(
    records: list[SymbolRecord],
    bundle: dict[str, Any],
    *,
    min_confidence: float = 0.7,
    entry_node_kinds: frozenset[str] = DEFAULT_ENTRY_NODE_KINDS,
    skip_kinds: frozenset[str] = DEAD_CODE_SKIP_KINDS,
) -> tuple[dict[str, ReachabilityRecord], list[DeadCodeCandidate]]:
    """Return (reachability, candidates with confidence ≥ min_confidence)."""
    reachability = compute_reachability(records, bundle, entry_node_kinds=entry_node_kinds)
    referenced_nodes = collect_referenced_node_ids(bundle)

    candidates: list[DeadCodeCandidate] = []
    for rec in records:
        if rec.kind in skip_kinds:
            continue
        reach = reachability[rec.id]
        if reach.reachable:
            continue
        confidence, reasons = _score_dead_code(rec, bundle, referenced_nodes)
        if confidence < min_confidence:
            continue
        candidates.append(
            DeadCodeCandidate(
                symbol_id=rec.id,
                node=rec.node,
                file=rec.file,
                line=rec.line,
                kind=rec.kind,
                name=rec.name,
                visibility=rec.visibility,
                language=rec.language,
                confidence=confidence,
                reasons=reasons,
            )
        )

    candidates.sort(key=lambda c: (-c.confidence, c.node, c.file, c.line))
    return reachability, candidates


def load_symbol_records() -> list[SymbolRecord]:
    """Re-hydrate SymbolRecord instances from symbol-index.yaml on disk.

    Used by dead-code.py and other downstream tools that should not re-extract
    symbols from source on every invocation.
    """
    if not SYMBOL_INDEX_PATH.exists():
        return []
    doc = yaml.safe_load(SYMBOL_INDEX_PATH.read_text(encoding="utf-8")) or {}
    records: list[SymbolRecord] = []
    for entry in doc.get("symbols", []) or []:
        records.append(SymbolRecord(
            id=entry["id"],
            node=entry["node"],
            kind=entry.get("kind", ""),
            name=entry.get("name", ""),
            file=entry.get("file", ""),
            line=int(entry.get("line", 0) or 0),
            end_line=int(entry.get("end_line", 0) or 0),
            is_test=bool(entry.get("is_test", False)),
            signature=entry.get("signature", ""),
            visibility=entry.get("visibility", "public"),
            language=entry.get("language", "unknown"),
            container=entry.get("container"),
            callers=list(entry.get("callers", []) or []),
            callees=list(entry.get("callees", []) or []),
            implements=list(entry.get("implements", []) or []),
        ))
    return records


def disambiguate_ids(records: list[SymbolRecord]) -> int:
    """Append a -2, -3, … suffix to records whose simple id collides.

    Ordering: stable by (file, line). The first record keeps the simple id;
    subsequent records get the suffix. Returns the count of rewritten ids."""
    records.sort(key=lambda r: (r.id, r.file, r.line))
    groups: dict[str, list[SymbolRecord]] = {}
    for rec in records:
        groups.setdefault(rec.id, []).append(rec)
    rewrites = 0
    for sid, group in groups.items():
        if len(group) <= 1:
            continue
        for idx, rec in enumerate(group[1:], start=2):
            rec.id = f"{sid}-{idx}"
            rewrites += 1
    return rewrites


def build_symbol_bundle(
    bundle: dict[str, Any],
    *,
    node_filter: set[str] | None,
    language_filter: set[str] | None,
    force: bool,
) -> tuple[
    list[SymbolRecord],
    dict[str, Any],
    dict[str, FileCacheEntry],
    dict[str, str],
    dict[str, list[dict[str, Any]]],
]:
    cache = {} if force else load_cache()
    new_cache: dict[str, FileCacheEntry] = {}

    work = collect_work_items(bundle, node_filter, language_filter)

    extractors: dict[str, BaseExtractor] = {
        "python": PythonAstExtractor(),
        "typescript": TsExtractor(),
        "csharp": CsExtractor(),
    }

    # Compilation-roots cache invalidation: if a language's roots changed
    # between runs, drop every cached entry for that language because Roslyn /
    # ts-morph resolution depends on what else is in the compilation.
    current_roots_by_language: dict[str, list[str]] = {
        lang: normalized_compilation_roots(getattr(ext, "compilation_roots", []))
        for lang, ext in extractors.items()
    }
    current_roots_hashes: dict[str, str] = {
        lang: compilation_roots_hash(roots)
        for lang, roots in current_roots_by_language.items()
    }
    if not force:
        previous = load_previous_roots_hashes()
        stale = {
            lang for lang, h in current_roots_hashes.items()
            if previous.get(lang) != h
        }
        if stale:
            dropped = invalidate_cache_by_language(cache, stale)
            if dropped:
                print(
                    f"[symbols] compilation-roots changed for {sorted(stale)}; "
                    f"dropped {dropped} cache entries",
                    file=sys.stderr,
                )

    parse_stats: dict[str, dict[str, int]] = {}
    all_records: list[SymbolRecord] = []
    sidecar_by_language: dict[str, list[dict[str, Any]]] = {}
    sidecar_authoritative: set[str] = set()

    for lang, extractor in extractors.items():
        file_map = work.get(lang) or {}
        if not file_map:
            continue
        files = list(file_map.keys())
        file_to_node = {
            path.relative_to(REPO_ROOT).as_posix(): node_id
            for path, node_id in file_map.items()
        }
        stats = parse_stats.setdefault(
            lang, {"files": 0, "parsed": 0, "cached": 0}
        )
        all_records.extend(
            run_extractor(extractor, files, file_to_node, cache, new_cache, force, stats)
        )
        if getattr(extractor, "last_sidecar_authoritative", False):
            sidecar_authoritative.add(lang)
            sidecar_by_language[lang] = getattr(extractor, "last_sidecar", [])

    rewrites = disambiguate_ids(all_records)
    resolve_call_edges(all_records)

    test_files = collect_test_files(bundle)
    if test_files:
        for rec in all_records:
            if rec.file in test_files:
                rec.is_test = True

    summary = {
        "total_symbols": len(all_records),
        "by_language": parse_stats,
        "disambiguated_ids": rewrites,
        "sidecar_authoritative": sorted(sidecar_authoritative),
        "compilation_roots_by_language": current_roots_by_language,
        "compilation_roots_hash_by_language": current_roots_hashes,
        "test_symbols": sum(1 for r in all_records if r.is_test),
    }
    return all_records, summary, new_cache, current_roots_hashes, sidecar_by_language


def load_existing_unbound_invocations(
    authoritative_languages: set[str],
) -> list[dict[str, Any]]:
    """Return prior sidecar entries for languages not refreshed this run."""
    if not UNBOUND_REFS_PATH.exists():
        return []
    try:
        doc = yaml.safe_load(UNBOUND_REFS_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []

    preserved: list[dict[str, Any]] = []
    for entry in doc.get("invocations", []) or []:
        if not isinstance(entry, dict):
            continue
        language = entry.get("language")
        if language and language not in authoritative_languages:
            preserved.append(entry)
    return preserved


def load_existing_unbound_languages() -> list[str]:
    """Return languages represented in the current unbound sidecar."""
    if not UNBOUND_REFS_PATH.exists():
        return []
    try:
        doc = yaml.safe_load(UNBOUND_REFS_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []

    return sorted(
        {
            entry["language"]
            for entry in doc.get("invocations", []) or []
            if isinstance(entry, dict) and entry.get("language")
        }
    )


def write_unbound_but_referenced(
    sidecar_by_language: dict[str, list[dict[str, Any]]],
    records: list[SymbolRecord],
    authoritative_languages: set[str],
) -> int:
    """Write planning-mds/knowledge-graph/unbound-but-referenced.yaml.

    Resolves each {target.name, target.container} to a bound symbol id using
    the same (container, name) global lookup the orchestrator uses for
    caller/callee edges. When a target is unresolvable, falls back to leaving
    target_symbol absent and emitting target_name / target_container strings.
    Returns the total number of invocation entries written.

    `authoritative_languages` is the set of languages whose extractor actually
    ran this invocation (vs. fully satisfied by cache). The sidecar is a
    language-scoped snapshot: replace entries for refreshed languages, preserve
    existing entries for languages that were not refreshed, and never append
    stale findings indefinitely.
    """
    if not authoritative_languages:
        return 0
    by_qualified: dict[tuple[str, str], list[SymbolRecord]] = {}
    by_name: dict[str, list[SymbolRecord]] = {}
    for rec in records:
        by_name.setdefault(rec.name, []).append(rec)
        if rec.container:
            by_qualified.setdefault((rec.container, rec.name), []).append(rec)

    invocations: list[dict[str, Any]] = load_existing_unbound_invocations(
        authoritative_languages
    )
    source_files: set[str] = set()
    bound_targets: set[str] = set()

    for entry in invocations:
        if entry.get("source_file"):
            source_files.add(entry["source_file"])
        if entry.get("target_symbol"):
            bound_targets.add(entry["target_symbol"])

    for language in sorted(authoritative_languages):
        entries = sidecar_by_language.get(language, [])
        for entry in entries:
            source_file = entry.get("source_file")
            source_line = entry.get("source_line")
            target = entry.get("target") or {}
            name = target.get("name")
            container = target.get("container")
            if not (source_file and name):
                continue
            source_files.add(source_file)

            matches: list[SymbolRecord] = []
            if container:
                matches = by_qualified.get((container, name), [])
            if not matches:
                matches = by_name.get(name, [])

            payload: dict[str, Any] = {
                "source_file": source_file,
                "source_line": int(source_line or 0) or 0,
                "language": language,
            }
            if matches:
                # When multiple symbols share (container, name) — collisions
                # in code-index bindings — pick the first by id for stability.
                target_sym = sorted(matches, key=lambda r: r.id)[0]
                payload["target_symbol"] = target_sym.id
                payload["target_node"] = target_sym.node
                bound_targets.add(target_sym.id)
            else:
                payload["target_name"] = name
                if container:
                    payload["target_container"] = container
            invocations.append(payload)

    if not invocations:
        # Remove a stale file if a prior run wrote one and this run is clean.
        if UNBOUND_REFS_PATH.exists():
            UNBOUND_REFS_PATH.unlink()
        return 0

    invocations.sort(
        key=lambda e: (e.get("language", ""), e["source_file"], e["source_line"])
    )
    by_lang_counts: dict[str, int] = {}
    for e in invocations:
        by_lang_counts[e["language"]] = by_lang_counts.get(e["language"], 0) + 1

    preserved_languages = sorted(
        {
            e["language"]
            for e in invocations
            if e.get("language") not in authoritative_languages
        }
    )
    payload = {
        "version": 0,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": {
            "total_invocations": len(invocations),
            "by_language": by_lang_counts,
            "source_files": len(source_files),
            "bound_targets": len(bound_targets),
            "refreshed_languages": sorted(authoritative_languages),
            "preserved_languages": preserved_languages,
        },
        "invocations": invocations,
    }
    UNBOUND_REFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNBOUND_REFS_PATH.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return len(invocations)


def write_symbol_index(records: list[SymbolRecord], summary: dict[str, Any]) -> None:
    sidecar_languages = summary.get("sidecar_authoritative", [])
    if not sidecar_languages:
        sidecar_languages = load_existing_unbound_languages()

    payload = {
        "version": 0,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": {
            "total_symbols": summary["total_symbols"],
            "by_language": summary["by_language"],
            "disambiguated_ids": summary.get("disambiguated_ids", 0),
            "compilation_roots_by_language": summary.get(
                "compilation_roots_by_language", {}
            ),
            "compilation_roots_hash_by_language": summary.get(
                "compilation_roots_hash_by_language", {}
            ),
            "sidecar_authoritative_languages": sidecar_languages,
        },
        "symbols": [r.to_index_dict() for r in sorted(records, key=lambda x: x.id)],
    }
    SYMBOL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYMBOL_INDEX_PATH.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate symbol-index.yaml from declared code paths in "
            "code-index.yaml. Symbols are retrieval aids; raw source files "
            "remain authoritative."
        )
    )
    parser.add_argument(
        "--node",
        action="append",
        default=[],
        help="Restrict to one or more canonical node IDs.",
    )
    parser.add_argument(
        "--language",
        action="append",
        default=[],
        choices=["python", "csharp", "typescript"],
        help="Restrict to one or more languages.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cache and re-parse every selected file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing symbol-index.yaml or updating the cache.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--telemetry-file", type=Path, default=None)
    args = parser.parse_args()

    bundle = load_bundle()
    node_filter = set(args.node) if args.node else None
    language_filter = set(args.language) if args.language else None

    records, summary, new_cache, roots_hashes, sidecar_by_language = build_symbol_bundle(
        bundle,
        node_filter=node_filter,
        language_filter=language_filter,
        force=args.force,
    )

    unbound_count = 0
    if not args.dry_run:
        write_symbol_index(records, summary)
        save_cache(new_cache)
        save_roots_hashes(roots_hashes)
        if node_filter:
            print(
                "  Unbound-but-referenced sidecar unchanged "
                "(node-scoped run is not a full language snapshot)"
            )
        else:
            unbound_count = write_unbound_but_referenced(
                sidecar_by_language,
                records,
                set(summary.get("sidecar_authoritative", []) or []),
            )

    print(f"Symbol index: {summary['total_symbols']} symbols")
    for lang in ("python", "typescript", "csharp"):
        stats = summary["by_language"].get(lang)
        if not stats:
            continue
        print(
            f"  {lang:11} {stats['files']:>5} files "
            f"({stats['parsed']} parsed, {stats['cached']} cached)"
        )
    if summary.get("disambiguated_ids"):
        print(f"  Disambiguated ids: {summary['disambiguated_ids']}")
    if summary.get("test_symbols"):
        print(f"  Test symbols: {summary['test_symbols']}")
    if unbound_count:
        print(f"  Unbound-but-referenced invocations: {unbound_count}")

    nodes_with_symbols = sorted({r.node for r in records})
    telemetry_payload = {
        "total_symbols": summary["total_symbols"],
        "by_language": summary["by_language"],
    }
    emit_telemetry(
        args.telemetry_file,
        args.run_id,
        "symbols",
        {
            "total_symbols": summary["total_symbols"],
            "by_language": summary["by_language"],
            "nodes_returned": nodes_with_symbols,
            "nodes_count": len(nodes_with_symbols),
            "empty_scope": summary["total_symbols"] == 0,
            "ambiguous_count": summary.get("disambiguated_ids", 0),
            "hint_emitted": False,
            "confidence_band": "high",
            "tokens_estimated": estimate_tokens(telemetry_payload),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
