# VERIFICATION.md — what was actually run, in this VM, 2026-08-18

## Filters: all 134 exercised, 0 hard fails, 0 degraded
Tiers: 24 donor-test (57 embedded assertions, all pass) · 7 real command
output (git/ls/find/df/du/diff/pytest live in-VM) · 32 grammar-true family
fixtures (cargo/npm/dotnet/docker/kubectl/go/rails/gradle/mvn/terraform/
brew/bundle/composer/ansible error grammars) · 71 generic smoke (no-crash,
size, idempotence-or-exempt). Harness: tests/verify_filters.py.
NEW ENGINE GUARANTEE born from this run: the error-salvage net — if input
carried error-shaped lines (incl. file:line located compiler errors as their
own class) and the pipeline dropped all of them, up to 8 originals are
appended under "[tokencut salvaged errors]". Errors are never eaten silently.
This targets the exact failure mode consistent with JetBrains' measured rtk
regression.

## Hooks: 11/11 contract tests (tests/hook_suite.py)
Garbage-stdin fail-open x5 · bash-pre inject + no-op · bash-post compress
with FAILED lines surviving · read seed→REPEATED-READ warn→byte-identical
dedup chain · guard advisory fires on injected tool result. Fields match the
official reference; 9.5k caps enforced. NOT yet run inside a live Claude
Code session — that remains the Phase 1 field test.

## Guard ONNX path: fully exercised
Dir resolution ($TOKENCUT_MODELS), guard.json config, NEW bundled wordpiece
fallback (tokenizers lib now optional — Phase 4 needs only onnxruntime),
feeds filtered to session inputs, softmax, injection_label_index, 0.8
threshold, engine flip heuristic→onnx, and removal→fallback. Real
onnxruntime import; InferenceSession stubbed content-sensitively (flagged
0.953 on injection text, 0.047 clean). Real-model detection quality is the
Phase 4 field test, by design.

## Theory tests (donor code / published numbers vs ours)
- defluff parity: donor library executed in-VM (ahocorasick+filelock shimmed,
  scoring math untouched). FOUND AND FIXED A PORT BUG: slop.py double-counted
  overlapping lexicon entries (0.929 vs donor 0.696 on the fluff text).
  Longest-match-wins suppression added; post-fix max delta 0.033 across the
  4-text set (residual: word-boundary edge on one hyphenated phrase).
- omni dedup claim 97.2%: ours measured 98.4% on a real repeat-read of
  engine.py. Mechanism confirmed.
- Routing paper: crossovers, both routing tables, AND the eta efficiency
  metric (0.36 at lambda=0.06) all reproduce exactly.
- TOON: FULL SPEC CONFORMANCE CLOSED (spec v4.1 fetched from
  deepwiki/toon-format 2026-08-18). Rewrote toon.py to the real grammar and
  added tests/toon_conformance.py — 12/12 spec cases: 4 array forms, inline
  key[N]{fields}: headers (prev version wrongly hoisted them to own line),
  minimal-quoting rules (empty/whitespace/reserved-word/number-like/
  structural-char/leading-dash-hash), null/NaN/Infinity normalization, and
  nested field groups (orders[2]{id,customer{name,country}}:). Losslessness
  fixed — the old encoder emitted "42" unquoted so it round-tripped to int 42;
  now quoted. Measured 56.2% on tabular data (was ad-hoc 47.1%).
- Attention: ordered+bounded+decay-cools invariants pass. Constants remain
  untuned heuristics.
- laconic 90% output cut: UNTESTABLE here (needs model inference). Stays
  vendor-reported.

## Environment limits hit honestly
PyPI allowlist blocked tokenizers/pyahocorasick/filelock (shimmed for tests;
wordpiece fallback removes the tokenizers runtime dep). onnxruntime installs
fine. No Claude Code binary (leak declined); no model inference.
