"""tokencut.slop — deterministic prose-slop scorer.

Gleaned from defluff (MIT): 172-entry lexicon + weighted-density formula
  score = clamp01( sum(matched_words * category_weight) / max(n_words, 20) )
The 20-word floor stops single phrases from spiking short texts.
"""
from __future__ import annotations
import json, re
from pathlib import Path

_LEX = None
_MIN_DENOM = 20
_WORD = re.compile(r"\b\w+\b")


def _lex():
    global _LEX
    if _LEX is None:
        d = json.loads((Path(__file__).parent / "lexicon.json").read_text())
        _LEX = {
            "threshold": d["default_threshold"],
            "weights": d["category_weights"],
            "patterns": [
                (re.compile(r"\b" + re.escape(e["pattern"]) + r"\b", re.I), e)
                for e in d["entries"]
            ],
        }
    return _LEX


def detect(text: str) -> dict:
    lex = _lex()
    n_words = len(_WORD.findall(text))
    raw = []
    for rx, e in lex["patterns"]:
        for m in rx.finditer(text):
            raw.append({"text": m.group(0), "category": e["category"],
                        "start": m.start(), "end": m.end()})
    # longest-match wins: drop spans fully contained in another matched span
    raw.sort(key=lambda s: (s["start"], -(s["end"] - s["start"])))
    spans, num = [], 0.0
    for sp in raw:
        if any(k["start"] <= sp["start"] and sp["end"] <= k["end"] and k is not sp
               for k in raw if (k["end"] - k["start"]) > (sp["end"] - sp["start"])):
            continue
        w = len(_WORD.findall(sp["text"])) * lex["weights"].get(sp["category"], 1.0)
        num += w
        spans.append({"text": sp["text"], "category": sp["category"], "start": sp["start"]})
    density = num / max(n_words, _MIN_DENOM)
    return {
        "slop_score": round(min(1.0, density), 4),
        "slop_density": round(density, 4),
        "over_threshold": density > lex["threshold"],
        "n_words": n_words,
        "spans": sorted(spans, key=lambda s: s["start"]),
        "low_confidence": n_words < _MIN_DENOM,
    }


def score(text: str) -> float:
    return detect(text)["slop_score"]
