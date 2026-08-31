"""tokencut.skillreap — dead-skill / dead-context waste detector.

Behavior gleaned from skillreaper (MIT): scan Claude Code session transcripts,
count how often each installed skill actually fired, and flag never-used ones
as REAP candidates with an estimated per-session token cost. This is a waste
class nothing else in tokencut touches (skills sit in context every session
whether used or not). Stdlib-only; reads local skill dirs + transcript JSONL.

Token cost per skill = its SKILL.md size / 4 (the standard estimate).
Utilization = sessions_where_fired / sessions_scanned.
"""
from __future__ import annotations
import json, re
from pathlib import Path

SKILL_DIRS = [
    Path.home() / ".claude" / "skills",
    Path.cwd() / ".claude" / "skills",
]
TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"


def _installed_skills() -> dict[str, int]:
    """name -> est_tokens (from SKILL.md size)."""
    out = {}
    for d in SKILL_DIRS:
        if not d.is_dir():
            continue
        for skill_md in d.glob("*/SKILL.md"):
            out[skill_md.parent.name] = skill_md.stat().st_size // 4
    return out


def _skill_fires(transcript_root: Path, limit_sessions: int = 200) -> tuple[dict, int]:
    """Count sessions in which each skill name appears. Returns (fires, n_sessions)."""
    fires: dict[str, int] = {}
    n = 0
    files = sorted(transcript_root.rglob("*.jsonl"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:limit_sessions]
    for f in files:
        n += 1
        seen = set()
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        for name in re.findall(r'"skill"\s*:\s*"([^"]+)"|Skill\(([^)]+)\)', text):
            s = name[0] or name[1]
            if s:
                seen.add(s.strip())
        for s in seen:
            fires[s] = fires.get(s, 0) + 1
    return fires, n


def report(transcript_root: Path | None = None) -> dict:
    skills = _installed_skills()
    root = transcript_root or TRANSCRIPT_ROOT
    fires, n_sessions = _skill_fires(root) if root.is_dir() else ({}, 0)
    rows = []
    dead_tokens = 0
    for name, toks in sorted(skills.items(), key=lambda kv: -kv[1]):
        used = fires.get(name, 0)
        util = used / n_sessions if n_sessions else 0.0
        verdict = "KEEP" if used else "REAP"
        if verdict == "REAP":
            dead_tokens += toks
        rows.append({"skill": name, "est_tokens": toks, "sessions_fired": used,
                     "utilization": round(util, 3), "verdict": verdict})
    return {"skills_installed": len(skills), "sessions_scanned": n_sessions,
            "dead_tokens_per_session": dead_tokens, "rows": rows,
            "note": ("no transcripts found — verdicts default to REAP; run after real sessions"
                     if n_sessions == 0 else None)}
