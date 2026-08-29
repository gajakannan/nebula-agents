"""Emit the audit stream for a fixed operation sequence, for pre/post-split comparison."""
from __future__ import annotations
import json, re, shutil, sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path.insert(0, str(REPO / "engine" / "src"))

from nebula_agents.bootstrap import build_application            # noqa: E402
from nebula_agents.domain.enums import ProviderKey, PromptAction # noqa: E402
from nebula_agents.domain.models import LaunchRequest            # noqa: E402

import tempfile
tmp = Path(tempfile.mkdtemp(prefix="audit-"))
ws = tmp / "workspace"
(ws / "planning-mds" / "schemas").mkdir(parents=True)
for s in (REPO / "planning-mds" / "schemas").glob("f0001-*.json"):
    shutil.copy2(s, ws / "planning-mds" / "schemas" / s.name)
(ws / "planning-mds" / "features" / "F0001-test").mkdir(parents=True)
pr = ws / "agents" / "templates" / "prompts" / "evidence-contract"
pr.mkdir(parents=True)
prompt = pr / "feature-operator-friendly.md"
prompt.write_text("FEATURE_ID={F####}\n", encoding="utf-8")

runtime = tmp / "runtime"
app = build_application(ws, runtime)
actor = app.current_actor()

class Provider:
    def build_interactive_argv(self, workspace_root, prompt_text):
        return (str(Path(sys.executable).resolve()), "-c", "pass")
class Tmux:
    def __init__(self): self.presence = [False, True]
    def has_session(self, _n): return self.presence.pop(0) if len(self.presence) > 1 else self.presence[0]
    def create_session(self, _n, _d): pass

app.runs._preflight = SimpleNamespace(
    require_ready=lambda *a: SimpleNamespace(prompt_contract_path=str(prompt)))
app.runs._providers = {ProviderKey.CODEX: Provider()}
app.runs._tmux = Tmux()

app.runs.launch(LaunchRequest("F0001", None, ProviderKey.CODEX, PromptAction.FEATURE,
                              None, None, False), actor)
# reads must contribute nothing to the stream
app.queries.sessions()
app.queries.recovery_candidates()

events = sorted(runtime.rglob("events.jsonl"))
lines = []
for f in events:
    for raw in f.read_text(encoding="utf-8").splitlines():
        d = json.loads(raw)
        # normalise the two inherently-variable fields; shape is what must match
        s = json.dumps(d, sort_keys=True)
        s = re.sub(r"\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:\d{2})", "<TS>", s)
        s = re.sub(r"\d{4}-\d{2}-\d{2}-[0-9a-f]{8}", "<RUNID>", s)
        s = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", s)
        s = re.sub(r"nebula-F\d{4}-[0-9a-f]{8}", "<SESSION>", s)
        s = s.replace(str(tmp), "<TMP>").replace(str(REPO), "<REPO>")
        lines.append(s)
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} event(s) -> {OUT}")
shutil.rmtree(tmp, ignore_errors=True)
