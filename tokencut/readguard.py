"""tokencut.readguard — repeated-read detection, content dedup, symbol hints.

v0.2: adds content-hash dedup (behavior gleaned from omni, Apache-2.0 —
a file re-read whose bytes are identical to a prior read this session is
already in the model's context; the PostToolUse hook can replace it with a
one-line handle instead of paying for the bytes again) and multi-language
symbol outlines (own regexes; js/ts/go/rust/java + python via ast).

Logic gleaned from openwolf's pre-read hook (behavior reimplemented from
scratch — openwolf is AGPL, no code copied). Three rules that matter:
  1. Warn when a file is re-read in the same session UNLESS its mtime changed
     (an edited file legitimately needs a re-read).
  2. Never track secret-bearing files (.env, *.pem, *.key, id_rsa...) — even
     their PATHS stay out of the ledger.
  3. For large Python files, offer a symbol outline (name + line range +
     ~token estimate) so the agent can read one function with offset/limit
     instead of the whole file.

Ledger lives at .tokencut/session.json in the project root; one per session
(cleared by `tokencut session reset` or a new session id on stdin).
"""
from __future__ import annotations
import ast, hashlib, json, os, re, time
from pathlib import Path

SECRET_RX = re.compile(
    r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx)|id_rsa.*|id_ed25519.*|.*secrets?.*\.(json|ya?ml|toml))$",
    re.I,
)
LARGE_TOKENS = 500  # openwolf's threshold: outline files above this


def _ledger_path(project: Path) -> Path:
    d = project / ".tokencut"
    d.mkdir(exist_ok=True)
    return d / "session.json"


def _load(project: Path) -> dict:
    p = _ledger_path(project)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"started": time.time(), "files_read": {}, "warnings": 0, "hashes": {}}


def est_tokens(path: Path) -> int:
    try:
        return path.stat().st_size // 4
    except OSError:
        return 0


_LANG_RX = {
    ".js": re.compile(r"^(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)|class\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()", re.M),
    ".ts": re.compile(r"^(?:export\s+)?(?:async\s+)?(?:function\s+(\w+)|class\s+(\w+)|interface\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()", re.M),
    ".go": re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)|^type\s+(\w+)\s", re.M),
    ".rs": re.compile(r"^(?:pub\s+)?(?:async\s+)?(?:fn\s+(\w+)|struct\s+(\w+)|impl(?:<[^>]*>)?\s+(\w+)|trait\s+(\w+)|enum\s+(\w+))", re.M),
    ".java": re.compile(r"^\s*(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:class\s+(\w+)|\w[\w<>\[\]]*\s+(\w+)\s*\()", re.M),
}
_LANG_RX[".jsx"] = _LANG_RX[".tsx"] = _LANG_RX[".ts"]


def generic_outline(path: Path) -> list[dict]:
    """Regex symbol outline for non-Python languages (top matches by size)."""
    rx = _LANG_RX.get(path.suffix)
    if not rx:
        return []
    text = path.read_text(errors="replace")
    hits = []
    for m in rx.finditer(text):
        name = next((g for g in m.groups() if g), None)
        if name:
            line = text.count("\n", 0, m.start()) + 1
            hits.append({"kind": "symbol", "name": name, "lines": f"L{line}", "est_tokens": 0})
    return hits[:20]


def py_outline(path: Path) -> list[dict]:
    """Top-level symbols with line ranges + token estimates (Python files)."""
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except SyntaxError:
        return []
    out = []
    src_lines = path.read_text(errors="replace").splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            end = getattr(node, "end_lineno", node.lineno)
            seg_chars = sum(len(l) for l in src_lines[node.lineno - 1 : end])
            out.append(
                {
                    "kind": type(node).__name__.replace("Def", "").lower(),
                    "name": node.name,
                    "lines": f"L{node.lineno}-{end}",
                    "est_tokens": seg_chars // 4,
                }
            )
    return sorted(out, key=lambda s: -s["est_tokens"])


def check_read(file_path: str, project: str = ".") -> dict:
    """Call before a file read. Returns {allow, warning?, hint?}."""
    project_p = Path(project).resolve()
    fp = Path(file_path).resolve()
    rel = str(fp)
    result: dict = {"allow": True}

    if SECRET_RX.search(rel):
        return result  # never track, never hint — path stays out of ledger

    ledger = _load(project_p)
    try:
        mtime = fp.stat().st_mtime
    except OSError:
        return result

    try:
        content_hash = (hashlib.sha256(fp.read_bytes()).hexdigest()[:16]
                        if fp.stat().st_size <= 8_000_000 else None)
    except OSError:
        content_hash = None

    prev = ledger["files_read"].get(rel)
    if prev:
        if prev.get("mtime") == mtime:
            ledger["warnings"] += 1
            result["warning"] = (
                f"REPEATED READ: {fp.name} already read this session "
                f"({prev['count']}x, unchanged since). ~{est_tokens(fp)} tokens. "
                f"Use your earlier context, or read a specific range."
            )
        # omni-gleaned: identical bytes = already in context, flag for dedup
        if content_hash and prev.get("hash") == content_hash:
            result["duplicate_of_read"] = prev["count"]
            result["content_hash"] = content_hash
        prev["count"] += 1
        prev["mtime"] = mtime
        prev["hash"] = content_hash
    else:
        ledger["files_read"][rel] = {"count": 1, "mtime": mtime, "hash": content_hash}
        if est_tokens(fp) > LARGE_TOKENS:
            syms = (py_outline(fp) if fp.suffix == ".py" else generic_outline(fp))[:8]
            if syms:
                result["hint"] = (
                    f"{fp.name} is ~{est_tokens(fp)} tokens. Largest symbols: "
                    + "; ".join(f"{s['kind']} {s['name']} {s['lines']} (~{s['est_tokens']}t)" for s in syms)
                )

    _ledger_path(project_p).write_text(json.dumps(ledger))
    try:
        from .attention import record_read
        record_read(project_p, rel)
    except Exception:
        pass
    return result


def _find_ledger_root(start: str = ".") -> Path:
    p = Path(start).resolve()
    for d in (p, *p.parents):
        if (d / ".tokencut" / "session.json").exists():
            return d
    return p


def session_stats(project: str = ".") -> dict:
    ledger = _load(_find_ledger_root(project))
    reads = ledger["files_read"]
    wasted = sum(
        (v["count"] - 1) * est_tokens(Path(k)) for k, v in reads.items() if v["count"] > 1
    )
    return {
        "files_tracked": len(reads),
        "repeated_reads": sum(v["count"] - 1 for v in reads.values()),
        "warnings_issued": ledger["warnings"],
        "est_tokens_wasted_on_rereads": wasted,
    }
