"""tokencut.guard — layered prompt-injection screening for tool results.

Layer 1 (always on, stdlib): regex heuristics for the classic injection
shapes — imperative overrides, role hijacks, exfil urges, hidden text.
ADVISORY ONLY by default: emits a warning via additionalContext; never
blocks, because heuristics have real false-positive rates.

Layer 2 (optional upgrade): if `onnxruntime` + `tokenizers` are installed
AND a classifier lives in models/guard/, scores with the model instead.
Verified starting model: protectai/deberta-v3-base-prompt-injection-v2
(Apache-2.0, ~86M). Export to ONNX or use their provided onnx/ files.
Layer 2 is NOT stdlib — it is a documented optional extra (see SETUP.md).

Honesty note: Layer 1 catches the obvious; it is nowhere near the ~94%
recall of trained detectors. Treat it as a tripwire, not a wall.
"""
from __future__ import annotations
import json, re
from pathlib import Path

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("override", re.compile(r"ignore (all |any )?(previous|prior|above) (instructions|prompts|rules)", re.I)),
    ("override", re.compile(r"disregard (your|the) (system prompt|instructions|guidelines)", re.I)),
    ("role_hijack", re.compile(r"you are now (a|an|the) |from now on,? you (are|will|must)", re.I)),
    ("role_hijack", re.compile(r"(new|updated) system prompt:", re.I)),
    ("exfil", re.compile(r"(send|post|upload|exfiltrate|forward) (this|the|all|your).{0,40}(to|at) https?://", re.I)),
    ("exfil", re.compile(r"(api[_ ]?key|password|secret|token|credential)s?\b.{0,50}\b(send|reveal|print|echo|include)", re.I)),
    ("tool_abuse", re.compile(r"(run|execute|eval)\s+(this|the following)\s+(command|code|script)\b.{0,60}(silently|without (asking|telling|confirmation))", re.I)),
    ("hidden_text", re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]{2,}")),
    ("hidden_text", re.compile(r"<!--.{0,400}(instruction|ignore|system|prompt).{0,400}-->", re.I | re.S)),
    ("agent_address", re.compile(r"^(attention|dear|hey|note to) (ai|assistant|claude|model|agent)\b", re.I | re.M)),
]

def _models_root() -> Path:
    import os
    for cand in (os.environ.get("TOKENCUT_MODELS"),
                 Path.cwd() / "models",
                 Path.home() / ".tokencut" / "models",
                 Path(__file__).resolve().parent.parent / "models"):
        if cand and Path(cand).is_dir():
            return Path(cand)
    return Path.home() / ".tokencut" / "models"

_MODEL_DIR = _models_root() / "guard"


def scan_heuristic(text: str) -> list[dict]:
    hits = []
    for label, rx in _PATTERNS:
        m = rx.search(text)
        if m:
            hits.append({"kind": label, "span": [m.start(), m.end()],
                         "excerpt": text[m.start():m.end()][:120]})
    return hits


def _onnx_available() -> bool:
    if not any(_MODEL_DIR.glob("*.onnx")):
        return False
    try:
        import onnxruntime  # noqa: F401  (tokenizers optional — see _encode)
        return True
    except ImportError:
        return False


def _encode(text: str, tokp: Path):
    """Prefer the `tokenizers` lib; fall back to a bundled greedy wordpiece
    over tokenizer.json's vocab so Phase 4 needs only onnxruntime."""
    try:
        from tokenizers import Tokenizer
        e = Tokenizer.from_file(str(tokp)).encode(text)
        return e.ids, e.attention_mask
    except ImportError:
        vocab = json.loads(tokp.read_text()).get("model", {}).get("vocab", {})
        unk = vocab.get("[UNK]", 0)
        ids = []
        for w in re.findall(r"\w+|[^\w\s]", text.lower()):
            while w:
                for i in range(len(w), 0, -1):
                    piece = w[:i] if not ids or True else w[:i]
                    cand = piece if piece in vocab else ("##" + piece if ("##" + piece) in vocab else None)
                    if cand:
                        ids.append(vocab[cand]); w = w[i:]; break
                else:
                    ids.append(unk); break
        ids = ids[:512] or [unk]
        return ids, [1] * len(ids)


def scan(text: str) -> dict:
    """Returns {'level': 'clean'|'suspicious'|'model-flagged', 'hits': [...],
    'engine': 'heuristic'|'onnx'}."""
    hits = scan_heuristic(text)
    if _onnx_available():
        try:
            score = _onnx_score(text)
            if score is not None and score > 0.8:
                return {"level": "model-flagged", "score": round(score, 3),
                        "hits": hits, "engine": "onnx"}
            return {"level": "suspicious" if hits else "clean",
                    "score": round(score, 3) if score is not None else None,
                    "hits": hits, "engine": "onnx"}
        except Exception:
            pass  # fall back to heuristics
    return {"level": "suspicious" if hits else "clean", "hits": hits,
            "engine": "heuristic"}


def _onnx_score(text: str) -> float | None:
    import onnxruntime as ort
    cfgp = _MODEL_DIR / "guard.json"
    cfg = json.loads(cfgp.read_text()) if cfgp.exists() else {}
    model = next(_MODEL_DIR.glob("*.onnx"))
    tokp = _MODEL_DIR / cfg.get("tokenizer", "tokenizer.json")
    if not tokp.exists():
        return None
    ids_l, mask_l = _encode(text[:4000], tokp)
    import numpy as np  # onnxruntime pulls numpy in anyway
    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    ids = np.array([ids_l], dtype=np.int64)
    mask = np.array([mask_l], dtype=np.int64)
    feeds = {"input_ids": ids, "attention_mask": mask}
    feeds = {k: v for k, v in feeds.items() if k in {i.name for i in sess.get_inputs()}}
    logits = sess.run(None, feeds)[0][0]
    m = max(logits)
    exps = [pow(2.718281828, x - m) for x in logits]
    probs = [e / sum(exps) for e in exps]
    inj_idx = int(cfg.get("injection_label_index", 1))
    return float(probs[inj_idx]) if inj_idx < len(probs) else None


# --------------------------------------------------------------------------
# Command safety (gleaned from token-ninja, MIT): normalize homoglyphs, deny
# destructive shapes, allow known-deterministic commands. Used by the
# pre-model short-circuit path — a command is only eligible to skip the model
# if it is BOTH on the safe allowlist AND clears the deny grammar.
# --------------------------------------------------------------------------
_HOMOGLYPH = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c",
    "\u0445": "x", "\u0455": "s", "\u0456": "i", "\u0458": "j", "\u04bb": "h",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u039f": "O", "\u03a1": "P",
    "\u0410": "A", "\u0412": "B", "\u0421": "C", "\u041e": "O", "\u0420": "P",
})

_DENY = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b"), "rm -rf"),
    (re.compile(r"\brm\s+-[a-zA-Z]*r.*[*?]"), "rm -r with wildcards"),
    (re.compile(r"\brm\s+-[a-zA-Z]*\s+/(bin|etc|usr|var|boot|lib|sys|dev)\b"), "rm on system path"),
    (re.compile(r"\b(sudo|doas)\b"), "privilege escalation"),
    (re.compile(r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh|python)"), "pipe-to-shell"),
    (re.compile(r"\bbase64\s+(-d|--decode)\b.*\|"), "base64-decode-to-shell"),
    (re.compile(r"\beval\b|\bexec\b"), "eval/exec"),
    (re.compile(r"\bdd\b.*\bof=/dev/"), "dd to device"),
    (re.compile(r"\bmkfs\b|\bfdisk\b|\bwipefs\b"), "filesystem format"),
    (re.compile(r":\(\)\s*\{.*\};:"), "fork bomb"),
    (re.compile(r">\s*/dev/(sd|nvme|hd)"), "write to raw disk"),
    (re.compile(r"\bchmod\s+-R\b.*777"), "recursive world-writable"),
    (re.compile(r"(?<![0-9&])>>?(?![&])"), "output redirection (side effect)"),
    (re.compile(r"\bgit\s+push\b.*(--force|-f)\b"), "force push"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "hard reset"),
]

# commands whose output is deterministic and side-effect-free enough that,
# once deny-cleared, the shell can run them and the model can skip re-deriving.
_SAFE = frozenset(
    "ls pwd cat head tail wc date whoami hostname uname df du stat file "
    "which type env printenv git grep rg find tree sort uniq cut awk sed".split()  # note: echo removed — it is output, and redirection is denied above
)


def command_verdict(cmd: str) -> dict:
    """Return {safe: bool, reason: str, deny: str|None}. `safe` means eligible
    for pre-model short-circuit (allowlisted base AND no deny match)."""
    cands = {cmd, cmd.translate(_HOMOGLYPH),
             __import__("unicodedata").normalize("NFKC", cmd)}
    for c in cands:
        for rx, why in _DENY:
            if rx.search(c):
                return {"safe": False, "reason": f"denied: {why}", "deny": why}
    try:
        import shlex
        toks = shlex.split(cmd)
    except ValueError:
        return {"safe": False, "reason": "unparseable", "deny": None}
    if not toks:
        return {"safe": False, "reason": "empty", "deny": None}
    base = Path(toks[0]).name
    # git write-subcommands are not deterministic reads
    if base == "git" and len(toks) > 1 and toks[1] in {
            "commit", "push", "pull", "merge", "rebase", "reset", "checkout",
            "clean", "add", "rm", "mv", "stash"}:
        return {"safe": False, "reason": "git write subcommand", "deny": None}
    if base in _SAFE:
        return {"safe": True, "reason": "allowlisted deterministic command", "deny": None}
    return {"safe": False, "reason": f"'{base}' not on safe allowlist", "deny": None}
