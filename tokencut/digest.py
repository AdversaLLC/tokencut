"""tokencut.digest — extractive text compression under a token budget.

Behavior gleaned from llmslim (MIT): rank sentences by TF-IDF salience +
position + length signals, keep the top set that fits the budget, preserve
original order. Own implementation, stdlib-only. Deterministic: same input,
same output. For prose/logs/docs — code goes through readguard outlines.
"""
from __future__ import annotations
import math, re

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n{2,}")
_WORD = re.compile(r"[a-z][a-z0-9_\-]{1,}")
_STOP = frozenset(
    "the a an and or but if then else of to in on for with as at by is are was "
    "were be been it its this that these those from into over under not no you "
    "we they he she i our your their have has had do does did can could will "
    "would should may might must".split()
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s.strip()]


def digest(text: str, budget_tokens: int = 300) -> dict:
    """Return {'text', 'kept', 'total', 'est_tokens_in', 'est_tokens_out'}."""
    sents = _sentences(text)
    if len(sents) <= 2:
        return {"text": text, "kept": len(sents), "total": len(sents),
                "est_tokens_in": len(text) // 4, "est_tokens_out": len(text) // 4}
    # document frequencies
    docs = [set(w for w in _WORD.findall(s.lower()) if w not in _STOP) for s in sents]
    df: dict[str, int] = {}
    for d in docs:
        for w in d:
            df[w] = df.get(w, 0) + 1
    n = len(sents)
    scores = []
    for i, s in enumerate(sents):
        words = [w for w in _WORD.findall(s.lower()) if w not in _STOP]
        if not words:
            scores.append((0.0, i)); continue
        tfidf = sum(math.log(1 + n / df[w]) for w in set(words)) / math.sqrt(len(words))
        pos = 1.15 if i == 0 else (1.05 if i < 3 or i >= n - 2 else 1.0)   # edges matter
        length = 0.6 if len(words) < 4 else 1.0                             # fragments demoted
        scores.append((tfidf * pos * length, i))
    ranked = sorted(scores, reverse=True)
    kept, used = [], 0
    for _, i in ranked:
        cost = len(sents[i]) // 4 + 1
        if used + cost > budget_tokens:
            continue
        kept.append(i); used += cost
    kept.sort()
    out = "\n".join(sents[i] for i in kept)
    return {"text": out, "kept": len(kept), "total": n,
            "est_tokens_in": len(text) // 4, "est_tokens_out": len(out) // 4}
