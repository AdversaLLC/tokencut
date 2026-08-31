# tokencut 0.8.1 — verified build (see VERIFICATION.md)

Stdlib-only token-saving toolkit for Claude Code and workspace.py — built by
gleaning the verified mechanisms out of 30 token-optimization repos instead
of installing all of them. No dependencies, no daemons, no network. See
VETTING.md for the full audit and provenance.

## What it does
1. **Output compression** — 132 command filters (git/pytest/cargo/docker/
   npm/go/rails/...) run as declarative pipelines. `tokencut run git status`
   or automatic via PostToolUse hook. Engine passes all 55 tests embedded in
   the donor corpus.
2. **Read guard** — warns on repeated reads of unchanged files, gives symbol
   outlines (name + line range + token estimate) for large Python files so
   the agent reads one function, not the file. Secret files never enter the
   ledger. `tokencut stats` shows tokens wasted on rereads.
3. **Slop scoring** — deterministic 172-pattern lexicon scorer for prose;
   gate your drafts in CI: `tokencut slop draft.md`.
4. **Model routing** — the Cluster/Route/Escalate paper's Stage 1 math for
   workspace.py: Pareto-prune a model pool, compute crossover λ per cluster,
   pick λ* under a cost budget. Reproduces the paper's published tables.

## Hooks (v0.2, contract-verified)
Four hooks, fields verified against the official Claude Code hooks reference:
PreToolUse(Bash) injects quieter flags before execution; PostToolUse(Bash)
replaces verbose output via updatedToolOutput; PreToolUse(Read) warns on
rereads + gives symbol outlines (py/js/ts/go/rs/java); PostToolUse(Read)
collapses byte-identical re-reads to a one-line handle (omni-style dedup).

## New in 0.3.0 — the output-token layer
5. **Terse skill** (`skill/SKILL.md` -> `~/.claude/skills/tokencut-terse/`) —
   answer-first prose, YAGNI code ladder, dense agent handoffs, with safety
   carve-outs that are never compressed. Donor benchmarks: ~90% output cut.
6. **`tokencut digest [budget]`** — deterministic extractive compression of
   long prose/logs under a token budget (TF-IDF + position, stdlib).
7. **`tokencut toon`** — JSON -> TOON for LLM-bound data (~50% on tabular).

## Caveat: server-side context editing (measured, not ours)
Distil measured Anthropic's DEFAULT context-editing (`keep=3`) changing the
agent's next action in 95-100% of cases (vs 2.5% A/A noise). tokencut's own
transforms are reversible/advisory, but the PROVIDER may already be editing
your context server-side before tokencut sees it. `tokencut stats` measures
what tokencut did; it cannot see provider-side edits. Treat any end-to-end
savings number as net of an invisible upstream editor.

## New in 0.8.0
- `tokencut short-circuit "<cmd>"` — decides if a command is safe +
  deterministic enough to run locally and skip the model round-trip (the
  "prompt-agent-loop" waste class). Gated by command safety: allowlisted AND
  deny-clear only; compound commands short-circuit only if every segment is.
  The bash-pre hook now emits this as an advisory. TOON encoder is now fully
  conformant to the official spec v4.1 (12/12 conformance tests).

## New in 0.7.0
- `tokencut cmd-check "<cmd>"` — command safety verdict (homoglyph-normalized
  deny grammar + deterministic-command allowlist). Gates any pre-model
  short-circuit: a command may skip the model only if allowlisted AND
  deny-clear. 12/12 on the test set incl. Cyrillic-homoglyph rm and
  pipe-to-shell.
- `tokencut reap` — dead-skill detector: scans session transcripts, flags
  never-fired skills with per-session token cost (the skill-context waste
  class). Honest default: no transcripts -> everything REAP, run after real
  sessions.

## New in 0.5.0
8. **`tokencut attention [digest]`** — attention-decay map of session files
   (HOT/WARM/COLD with co-activation); `digest` emits a compact session
   brief. Out-of-band levers tokencut does NOT cover, for completeness:
   Anthropic Batch API (~50% on deferrable work) and prompt-cache discipline
   — see claude-cost-optimizer's sourced guides for those.

## Install
```bash
pip install /path/to/tokencut     # or: PYTHONPATH=/path/to/tokencut
python3 -m tokencut.cli selftest  # 55/55 + routing math checks
```
Hooks: merge `hooks/settings-snippet.json` into `~/.claude/settings.json`.

## CLI
```
tokencut run <cmd...>        # execute + compress (with arg injection, e.g. pytest -q --tb=line)
<out> | tokencut filter <cmd># compress piped output
tokencut selftest            # corpus + routing verification
tokencut slop [file]         # slop report (stdin if no file)
tokencut read-check <file>   # what the read hook would say
tokencut stats               # session reread waste
```

## Routing example (workspace.py)
```python
from tokencut.route import Model, Router
pool = [
    Model("qwen3-4b-local",  cost=0.0,  error={"code": 0.18, "chat": 0.09}),
    Model("claude-fable-5",  cost=15.0, error={"code": 0.04, "chat": 0.02}),
]
r = Router(pool)
r.routing_table(lam=0.07)     # {'chat': 'qwen3-4b-local', 'code': 'claude-fable-5'}
r.crossover("code")           # λ where the assignment flips
```
Error rates come from task-correctness labels you already collect; re-run
Router() when the pool changes — Pareto pruning handles new models (paper §4.3).

## Attribution
Filter corpus from snip (MIT). Lexicon from defluff (MIT). Read-guard behavior
after openwolf-enhanced (AGPL — reimplemented, no code copied). Routing math
from Moslem et al. 2026 (arXiv:2606.27457).
