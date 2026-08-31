"""tokencut.shortcircuit — pre-model command short-circuit.

The "prompt-agent-loop" waste class (awesome-ai-tokenomics): when an agent
asks to run a deterministic, side-effect-free command (git status, ls, cat),
the model does not need to re-derive the output — the shell already knows it.
token-ninja's insight. tokencut adds the SAFE version: a command is eligible
to short-circuit ONLY if guard.command_verdict says it's allowlisted AND
deny-clear. This module produces the UserPromptSubmit/PreToolUse decision;
it never executes anything itself (the harness runs the command) — it only
answers "is this safe to run locally and skip the model round-trip?".

Returns a decision dict the hook layer serializes. Fail-closed: anything not
provably safe returns short_circuit=False (model handles it normally).
"""
from __future__ import annotations
from .guard import command_verdict


def decide(command: str) -> dict:
    """Decision for a single command string."""
    if not command or not command.strip():
        return {"short_circuit": False, "reason": "empty command"}
    v = command_verdict(command)
    if v["safe"]:
        return {"short_circuit": True, "command": command.strip(),
                "reason": v["reason"],
                "hint": "deterministic + deny-clear: run locally, skip model derivation"}
    return {"short_circuit": False, "reason": v["reason"], "deny": v.get("deny")}


def batch(commands: list[str]) -> dict:
    """Decision over several commands (e.g. a && b && c). Short-circuits only
    if EVERY segment is independently safe — one unsafe part disqualifies all,
    since the model needs the whole result."""
    parts = [c.strip() for c in commands if c.strip()]
    if not parts:
        return {"short_circuit": False, "reason": "no commands"}
    decisions = [decide(c) for c in parts]
    if all(d["short_circuit"] for d in decisions):
        return {"short_circuit": True, "commands": parts,
                "reason": "all segments deterministic + deny-clear"}
    blocked = next(d for d in decisions if not d["short_circuit"])
    return {"short_circuit": False, "reason": f"segment blocked: {blocked['reason']}"}
