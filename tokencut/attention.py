"""tokencut.attention — attention-decay ranking over session files.

Behavior gleaned from claude-cognitive (license checked at absorption):
files carry an attention score that ACTIVATES on read, DECAYS as other
reads happen, and CO-ACTIVATES with files read close together. Buckets:
HOT (>0.8) full attention, WARM (0.25-0.8) headers-only awareness,
COLD (<0.25) evicted. Clean-room stdlib reimplementation on top of the
existing readguard ledger — no new state files, no daemon.

Use: `tokencut attention` prints the ranked map; the SessionStart-style
digest is the top slice, cheap enough to inject by hand or hook.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from .readguard import _load, _ledger_path, est_tokens

DECAY = 0.92          # per subsequent read event
ACTIVATE = 1.0
CO_WINDOW = 3         # reads within this distance co-activate
CO_BOOST = 0.15


def record_read(project: Path, rel: str) -> None:
    """Called by readguard hook path: bump attention, decay others."""
    led = _load(project)
    att = led.setdefault("attention", {})
    order = led.setdefault("read_order", [])
    for k in att:
        att[k] = round(att[k] * DECAY, 4)
    att[rel] = ACTIVATE
    # co-activation with recent distinct reads
    for prev in [p for p in order[-CO_WINDOW:] if p != rel]:
        att[prev] = round(min(1.0, att.get(prev, 0) + CO_BOOST), 4)
    order.append(rel)
    if len(order) > 200:
        del order[: len(order) - 200]
    _ledger_path(project).write_text(json.dumps(led))


def attention_map(project: str = ".") -> dict:
    led = _load(Path(project).resolve())
    att = led.get("attention", {})
    hot, warm, cold = [], [], []
    for path, score in sorted(att.items(), key=lambda kv: -kv[1]):
        name = Path(path).name
        entry = {"file": name, "score": score, "est_tokens": est_tokens(Path(path))}
        (hot if score > 0.8 else warm if score >= 0.25 else cold).append(entry)
    return {"hot": hot, "warm": warm, "cold_count": len(cold)}


def digest(project: str = ".", budget_tokens: int = 150) -> str:
    """Compact session brief: hot files verbatim-worthy, warm as names."""
    m = attention_map(project)
    lines, used = [], 0
    for e in m["hot"]:
        line = f"HOT {e['file']} (~{e['est_tokens']}t)"
        if used + len(line) // 4 > budget_tokens:
            break
        lines.append(line); used += len(line) // 4
    if m["warm"]:
        lines.append("WARM " + ", ".join(e["file"] for e in m["warm"][:10]))
    if m["cold_count"]:
        lines.append(f"({m['cold_count']} files gone cold)")
    return "\n".join(lines) or "(no session reads yet)"
