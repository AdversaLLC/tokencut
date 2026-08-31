# VETTING.md — 30-repo audit behind tokencut

## Method
Automated sweep across all 30 uploaded repos: package.json lifecycle scripts
(postinstall/preinstall), base64-decode call sites, and outbound URLs in
source (allowlist-filtered). Manual code reading where mechanisms were
gleaned or flags needed resolution. Depth is stated per repo — spot-checked
means indicators reviewed, not every line read.

## Sweep results
| Repo | Verdict | Basis |
|---|---|---|
| tokenWise-Optimizer | **MALWARE — do not run** | Bundled `Wise_Optimizer_token_v1.2.zip` contains `Activate.cmd` + `lua.exe` + 300KB `package.txt` (lua-loader payload pattern); README funnels users to it. Python code is decoy. |
| snip | Clean (code-read: engine actions, 132 filters, licenses) | MIT. Filters are pure data with embedded tests. **Gleaned: filter corpus + pipeline semantics.** |
| defluff | Clean (code-read: api/report/lexicon, 12 files) | MIT. No network, no exec. **Gleaned: lexicon data + scoring formula.** |
| openwolf-enhanced | Clean (code-read: pre-read hook, package.json) | postinstall = `chmod +x` only. `evil.tld`/`169.254.169.254` hits are in tests (SSRF guards). AGPL-3.0 → **logic reimplemented from scratch, zero code copied.** |
| openwolf (upstream) | Clean (spot-checked) | Unmaintained since Mar 2026; superseded by fork. |
| rtk | Clean (spot-checked: hook scripts, install.sh) | Odd URLs are vendored C++ lib comments. |
| lean-ctx | Clean (spot-checked) | `10.0.0.5` etc. are docs/examples. Rust core not line-audited (2,318 files — out of scope). |
| sdl-mcp | Clean (spot-checked: postinstall.mjs = build asset copy) | `extension.ladybugdb.com` is its DB extension host — declared, not hidden. |
| repo-forensics | Clean (code-read: scanners) | 16 base64 hits are its own detector signatures; odd URLs are IOC lists. |
| mcptoon, tokf, tura, token-optimizer-mcp | Clean (spot-checked) | "evil.com/evil.test" hits are test fixtures. token-optimizer-mcp postinstall reviewed: local setup script, no network. |
| worldmonitor | Not audited deeply | postinstall runs `npm ci` in subdir (normal monorepo). Irrelevant to task. |
| RouteLLM, scip-io, semble_rs, senior-fable, sqz, tokenfold, tokenix, tokless, vs-token-safer, token-optimizer, token_saver, spec-kit-token-budget, jdocmunch, pxpipe, aikill, cca-f, claude-code-research | Clean on sweep (indicators only) | No lifecycle scripts, no suspicious decode/network patterns. Not line-audited. |

## What was gleaned into tokencut, and provenance
| Module | Mechanism | Source | License handling |
|---|---|---|---|
| engine.py + filters.json | 132 declarative output filters, 14-action pipeline vocabulary, arg-injection, embedded tests | snip (MIT) | Data bundled with attribution; engine written from scratch in Python, **validated 55/55 against snip's own embedded test expectations** |
| slop.py + lexicon.json | 172-entry slop lexicon, weighted-density score with 20-word floor | defluff (MIT) | Data bundled with attribution; scorer reimplemented (~50 lines) |
| readguard.py | mtime-aware repeated-read warning, secret-file ledger exclusion, symbol-outline hints for large files | openwolf-enhanced (AGPL-3.0) | **Behavior only** — clean-room Python reimplementation, no code copied (ideas are not copyrightable; expression is) |
| route.py | Eq.1–4: cost-normalized routing score, closed-form crossover, Pareto pruning, budgeted λ* | Moslem et al. 2026, arXiv:2606.27457 | Math from the paper; **unit-tested against its published AIME tables (crossovers 0.067/0.052/0.099 and both routing regions reproduce exactly)** |
| hook.py | PostToolUse output rewrite + PreToolUse context injection pattern | RTK / openwolf hook architecture | Pattern only; trivial glue |

## What was evaluated and deliberately NOT gleaned
- **RTK's Rust parsers** — richer than snip's filters for some commands, but
  non-portable without a Rust toolchain dependency; snip's corpus covers the
  same commands declaratively. If a specific RTK parser outperforms a snip
  filter, port it as a new filters.json entry — the schema supports it.
- **LeanCTX wire proxy / tokenfold** — request-level compression requires
  sitting on the API path; out of scope for a stdlib package, and cache-safety
  claims were not independently verified.
- **SDL-MCP symbol graph** — 1,408 TS files; readguard's outline hints cover
  the 80% case (avoid whole-file reads) at 1% of the complexity.
- **senior-fable delegation** — it's prompt/plugin config, not mechanism;
  install it directly if wanted (12KB, clean on sweep).
- **jdocmunch** — commercial license required for LLC use; section-retrieval
  idea noted for a future workspace.py feature instead.

## Honest limits
- 55/55 corpus tests pass, but the corpus tests cover ~40 of 132 filters;
  the rest are ported verbatim and structurally valid but not output-verified.
- Sweep detects known-bad patterns; it is not a proof of absence. Deep audits
  were done only where code was gleaned or flags fired.
- Token estimates use bytes/4 everywhere (same approximation RTK documents).

## v0.2.0 additions (batch 4, 20 zips: 16 unique + 3 duplicates + 1 declined)
Sweep: all clean (lifecycle scripts absent or build glue; b64/curlpipe hits are
installers, lockfiles, and outsourcerer's own repo-forensics integration).

**Declined: claude-code-main** — leaked Claude Code source. Not used; the hook
contract was verified against the official reference (code.claude.com/docs/en/hooks)
instead, which is both the legitimate path and the current one (the leak is a
stale v2.1 snapshot).

| Gleaned | From | Into | Notes |
|---|---|---|---|
| Correct hook fields: hookSpecificOutput.updatedToolOutput (PostToolUse), updatedInput (PreToolUse), 10k output cap | Official docs + cross-checked against pith (MIT) and omni (Apache-2.0) shipping hooks | hook.py rewrite | **v0.1 bug fixed**: field name updatedOutput was wrong and would have no-oped |
| Pre-execution arg injection via PreToolUse updatedInput | Official docs capability + filter corpus inject blocks | hook-bash-pre | pytest -> pytest --tb=line -q before it runs |
| Content-hash dedup: byte-identical re-read collapses to a handle | omni (Apache-2.0), behavior gleaned | readguard + hook-read-post | omni claims 97.2% on repeat reads; ours saves len/4 tokens per dup |
| tool_response shape normalization (string / stdout / file.content) | pith (MIT) post-tool-use.js | hook.py _tool_text | |
| Min-lines threshold before compressing | pith (MIT) | hook.py MIN_LINES=12 | |
| Multi-language symbol outlines (js/ts/go/rs/java) | own regexes (mnemosyne is AGPL — not read beyond README) | readguard.generic_outline | |

Not absorbed: paritok (needs its 4B model), octave-mcp (doc canonicalization,
different problem), paper7/notebooklm/promptlean/punderstruck/redesign-skill/
openworker (out of scope), outsourcerer (PolyForm Noncommercial — LLC conflict),
ratel (tool pruning — mcptoon already covers the category in the stack).

## v0.3.0 additions (batch 5: 20 zips = 16 unique + 4 duplicates/repeats)
Sweep: clean. neura (11 b64 hits) not deep-audited — nothing gleaned from it.
invisible_playwright is bot-detection evasion tooling — flagged out of scope
and out of character for this stack; not gleaned, not recommended.

| Gleaned | From | Into | Notes |
|---|---|---|---|
| Output-token discipline skill: terse-prose rules + YAGNI ladder + safety carve-outs | laconic (MIT, benchmarked 90% avg output cut) + honey (MIT) | skill/SKILL.md | New layer: model verbosity. Carve-outs (auth/secrets/migrations/deletes) are honey's key insight — terseness never trims safety |
| Extractive text compression under token budget (TF-IDF salience + position + length, deterministic) | llmslim (MIT), behavior; math is textbook, own implementation | digest.py + `tokencut digest` | Verified: keeps the salient sentence against 30 repeated fillers at 60-token budget |
| TOON encoding for LLM-bound JSON (tabular uniform arrays) | TOON open spec via laravel-toon (MIT) | toon.py + `tokencut toon` | Measured 47.1% on a 3-row tabular case, matching the ~50% claim; feeds Lever 3 of the skill |

Evaluated, not absorbed: lowfat (Apache-2.0; filter set is a subset of the
snip corpus already bundled), jcodemunch (Dual-Use license — commercial use
paid, same conflict as jdocmunch), mcp-server-code-execution-mode (canonical
Anthropic code-execution pattern — stack-level alternative to mcptoon, note
for the stack not the package), LMCache (KV-cache serving layer for the GPU
boxes — workspace.py/vLLM territory, not tokencut), mcp-slim-guard (MCP call
validation, different problem), log-file-genius (methodology, workspace
already covers), LAP / laravel-toon-the-package / llama-agents / lsp-io /
llmtrim (out of scope or superseded by absorbed equivalents).

## v0.4.0 — claims-honesty pass + local-model scaffolding + self-audit

### Claims honesty (prompted by awesome-ai-tokenomics, CC-BY-4.0)
Independent measurements contradict several donor headlines this package
previously repeated at face value:
- JetBrains A/B: **rtk measured +7.6% MORE expensive** at low effort vs its
  60-90% claim; **Caveman measured ~8.5%** vs its 65% claim. laconic (our
  skill's donor) is caveman-family and benchmarked itself — treat its 90%
  as vendor-reported, unreplicated. The skill remains shipped because its
  carve-outs bound the downside, but the README no longer cites 90% as fact.
- ICPC 2026 minification study: 42% input cut cost 12pp accuracy — context
  compression is not free. ECIR 2026: compression helps only in a narrow
  window. Consequence: tokencut's filters stay surgical (structured command
  output with embedded tests), never generic code minification, and digest()
  is opt-in per call, never a hook.
- Earlier stack advice (v1-v3 install scripts) repeated RTK/LeanCTX vendor
  numbers uncritically. Corrected stance: the only numbers to trust are the
  ones your own `tokencut stats` / `lean-ctx gain` show on your workload.

### Local-model scaffolding (this release)
- embed.py: OpenAI-compatible /embeddings client (urllib) + deterministic
  k-means++ and silhouette k-selection. Tested: 3-cluster purity, k=3
  recovered, assignment correct. Completes paper Stage 1 end-to-end.
- guard.py: layered injection screen. Heuristic layer (stdlib, advisory)
  verified firing on override/exfil/hidden-text and staying quiet on clean
  prose. ONNX layer is an OPTIONAL extra (onnxruntime+tokenizers) and only
  activates when models/guard/ is populated. Verified model recommendation:
  protectai/deberta-v3-base-prompt-injection-v2. Names from the user's
  research doc that could not be verified are marked UNVERIFIED in
  models/README.md and nothing depends on them.
- models/ tree ships EMPTY with per-slot download notes; SETUP.md is the
  hand-to-Claude-Code runbook with per-phase verification.

### Self-audit findings and fixes
- FIXED: py_outline re-read the file once per symbol (O(n*m) I/O).
- FIXED (0.2.0, restated): PostToolUse field name updatedOutput -> updatedToolOutput.
- Verified: all CLI commands execute; hooks parse the documented stdin
  shapes; zip contains skill/, models/, SETUP.md; no secrets in ledger paths.
- Known limits (unchanged, restated): 40/132 filters output-verified via
  embedded tests; bytes/4 token estimates; guard heuristics are a tripwire,
  not a wall.

## v0.4.1 — verification correction + red-team fixes

### Correction (I was wrong)
v0.4.0 marked unplug-tiny-v1, PhishScout, SingGuard, and Antares as
"UNVERIFIED, possibly confabulated" without searching. All four exist on
Hugging Face (fetched 2026-08-18). The right protocol — search before
labeling — is now applied; models/README.md carries verified statuses with
integration-relevant facts from the actual repos:
- unplug-tiny-v1: real, Apache-2.0, but safetensors + custom dual-head class,
  NOT drop-in ONNX (my earlier integration note was wrong in the other
  direction).
- PhishScout: real, MIT, 135kB ONNX — but LightGBM over 35 URL features
  (features.json), needs a feature extractor, not a tokenizer.
- Antares-350M: real, Apache-2.0, org is fdtn-ai = Cisco Foundation AI. The
  research doc's "beats GPT-5.5-class" is overstated: it beats GPT-5 Mini /
  Gemini 2.5 Flash / Qwen3.5-122B on VLoc Bench (F1 0.135) but trails
  GPT-5.5 (0.229). Repo is gated. GGUF quants exist.
- SingGuard-NSFA-0.8B-GGUF: real; llama.cpp route, not ONNX.

### Red-team findings on tokencut itself (all fixed)
1. guard.py resolved models/ relative to the package — broken under pip
   install. Now: $TOKENCUT_MODELS → ./models → ~/.tokencut/models → pkg-adjacent.
2. readguard hashed entire file bytes on every read — pathological on huge
   files. Now capped at 8MB (dedup disabled above; warning still works).
3. engine.match_command missed launcher forms (python -m pytest, npx vitest,
   uv run pytest) — launchers now unwrapped before matching.
Accepted risks, documented: guard heuristic "Dear AI" pattern can false-
positive on legit prose (advisory-only by design); dedup requires the
PreToolUse read hook to have recorded the hash (ordering dependency).

## v0.5.0 (batch 6: 18 items = 13 unique repos + CLAUDE.md doc + 4 repeats/dups)
Repeats: claude-code leak (3rd upload — still declined), claude-code-research,
cca-f, memory-setup x2 (byte-identical pair). Sweep clean; curlpipe hits are
bootstrap installers (catalyst, claude-reimagined, cost-optimizer).

| Gleaned | From | Into |
|---|---|---|
| Attention-decay file ranking (HOT/WARM/COLD, decay, co-activation) | claude-cognitive (MIT), behavior clean-room | attention.py + readguard wiring + `tokencut attention [digest]` |
| gh run/pr filter coverage (corpus gap) | chop (MIT) category map; rules authored here with embedded tests | filters.json (57 tests now) |
| Process guidelines: think-first, simplicity, surgical changes, goal-driven loops | user-provided CLAUDE.md | skill/claude-baseline.md (companion to terse) |
| Batch API as an out-of-band ~50% lever + typical-vs-ceiling framing | claude-cost-optimizer (its sourced 30-60% typical / 90% ceiling framing matches our claims-honesty stance) | README note |

Flagged, not absorbed: claude-skills-swarm ("98 patents", "93% of Fable 5 at
1/125th cost") — unreplicated vendor math, no mechanism worth the license
read. Noted for the stack, not the package: claude-reimagined and catalyst
(workstation wirers — validate the category tokencut's SETUP.md occupies),
burnless (capsule/prefix-cache session layer), brick-SR1 (MoM routing
gateway — Layer-0 alternative to senior-fable), claudeclaw (orchestrator
plugin), boost (same layer as rtk/chop, JFrog-sponsored),
claude-code-memory-setup (Obsidian+Graphify recipe — pairs with the user's
existing vault workflow; guide, not code), claude-context-optimizer and
claude-modular (prompt/workflow frameworks, overlap with shipped skills).

## v0.6.0 — full in-VM verification release
Everything runnable was run; see VERIFICATION.md for the complete record.
Code changes this release: (1) engine error-salvage net (errors can no
longer be silently eaten by out-of-grammar filtering — located compiler
errors tracked as their own class), (2) guard.py bundled wordpiece fallback
(tokenizers pip dep now optional), (3) tests/ shipped: verify_filters.py
(134/134, tiered) and hook_suite.py (11/11), (4) slop.py overlap
double-counting bug found by donor-parity testing and fixed
(longest-match-wins, matching defluff semantics).
Remaining field tests (need archer, not this VM): live Claude Code session,
real guard model, attention-constant tuning, laconic output-cut measurement.

## v0.7.0 (batch 7: 19 repos, my priority picks)
Sweep clean; engram/token-ninja postinstall = build glue, headroom/entroly/
distil b64 hits = test fixtures + config. New code, all in-VM tested:

| Gleaned | From | Into | Test |
|---|---|---|---|
| Command safety: homoglyph-normalized deny grammar + deterministic allowlist | token-ninja (MIT), clean-room | guard.command_verdict + `cmd-check` | 12/12 incl. Cyrillic-homoglyph rm, pipe-to-shell, fork bomb |
| Dead-skill waste detector (scan transcripts, flag never-fired skills) | skillreaper (MIT), clean-room | skillreap.py + `reap` | empty-path exercised; real run needs ~/.claude transcripts |
| Server-side context-editing caveat (keep=3 changed action 95-100%) | distil (measured finding) | README caveat | documents a limit tokencut cannot see |

Verified head-to-head, NOT absorbed:
- attention-span: Claude Code OUTPUT STYLES (markdown drop-ins), not a
  mechanism — complements tokencut-terse; different artifact type. My
  attention.py (decay ranking) is unrelated despite the name; no conflict.
- headroom (65k stars): SmartCrusher = static "first-3+last-2" array
  preservation, Rust, moving toward dynamic. Same LAYER as our digest/toon
  but heavier and provider-proxy-shaped; digest covers the prose case at
  stdlib cost. Noted, not merged (would need the Rust runtime).
- toon-main: Laravel/PHP, identical to laravel-toon already seen — still no
  runnable spec vectors for the python encoder; TOON full-conformance
  remains the one open validation item.
Noted for stack not package: deepseek-as-subagent (matches your DeepSeek
delegation pattern — real subagent wiring, install directly), governor/
guardian-runtime/claude-warden (spend+PII enforcement — genuine gap, but
they're proxies/daemons not stdlib), MemOS/engram (memory layer — engram's
bi-temporal git-revert mistake capture is clever), entroly (content-addressed
recoverable compression w/ receipts — closest to a superset, Apache-2.0,
worth watching), ctxlint (lints CLAUDE.md against codebase — pairs with the
baseline skill), hush/whittle/distil/thedistillery/Few-Word (same
compressor/proxy layer as shipped mechanisms).

## v0.8.0 — TOON conformance + short-circuit (from the master map)
Processed the awesome-ai-tokenomics master list (QuesmaOrg, CC-BY-4.0; the
taxonomy behind every uploaded batch) by web-fetch. IMPORTANT SCOPE NOTE:
web_fetch renders repo pages/READMEs but cannot clone repos or pull HF
weights, so entries reachable only by URL are read as DOCUMENTED-MECHANISM,
never code-verified. Nothing in this release is gleaned from unverifiable
fetched source — both additions are either spec-validated or built here.

Coverage cross-check against the 190-entry taxonomy (5 areas): tokencut
already spans the compression (engine/digest), read-guard (readguard),
routing-math (route), and local-model-wiring (embed) layers at stdlib tier.
Confirmed OUT OF SCOPE (daemons/services, not stdlib): semantic caches
(GPTCache/khazad/prompt-cache), spend-cap gateways (LiteLLM/Helicone/
governor/guardian), full memory platforms (Mem0/Letta/Zep/MemOS), and
provider-log dashboards (ccusage-class). These are correctly NOT reimplemented.

Two things closed this release:
| What | Source | Status |
|---|---|---|
| TOON encoder full spec conformance | official spec v4.1 (fetched) | REWRITTEN + tests/toon_conformance.py 12/12; 47.1%->56.2%; losslessness fixed |
| Pre-model short-circuit (the "prompt-agent-loop" waste class) | token-ninja mechanism (map-confirmed as its own category) | NEW shortcircuit.py + `short-circuit` CLI + bash-pre hook advisory; 13/13, gated by command_verdict (safe AND deny-clear only) |

SECURITY FIX during v0.8 build (found by self-testing the new module): the
safe-command allowlist included `echo` and did not catch output redirection,
so `echo x > f` and `cat a > b` — both side-effecting — were wrongly judged
safe to short-circuit. Fixed: `echo` removed from the deterministic-read
allowlist (it is output, not a read), and `>`/`>>` redirection added to the
deny grammar (stderr dup `2>&1` and `>&2` still allowed). command_verdict
holds 12/12; short-circuit correctly refuses all redirecting commands.

The short-circuit closes the loop token-ninja opened: v0.7 added the SAFETY
verdict; v0.8 adds the ACTION — a safe, deterministic command emits an
advisory that its shell output is authoritative so the model needn't re-derive
it. Fail-closed: anything not provably safe is left to the model.


## v0.8.1 — deployment findings (installed + tested from the zip)
Installing the 0.8.0 zip clean and driving it through the public CC hook
contract surfaced defects unit tests had hidden. Fixed in 0.8.1:
- PACKAGING: pyproject declared no package -> `pip install` failed with
  "Multiple top-level packages discovered". Added [tool.setuptools] packages
  and __main__.py. pip install now builds a wheel and imports from
  site-packages. (offline: needs --no-build-isolation; no PyPI for build deps)
- `--help`/`-h`/`help` printed "unknown command" -> now prints usage.
- `tokencut stats` only read ./.tokencut and showed 0 from any other dir ->
  now searches upward for the session ledger. Verified: 812 tokens-wasted
  reported from both the session dir and a nested subdir.
- TEST HARNESS: hook_suite.py hardcoded a dev path (cwd=/home/claude/tokencut)
  so it couldn't validate an install -> repointed.

Filter effectiveness (measured on install, on donor test inputs):
- STRONG compressors (ship as-is): rails-migrate 90%, pip-install 86%,
  pytest 82%, npm-install 82%, pnpm/yarn 75%, docker-build 52%, +8 more >5%.
- INTENTIONAL small growth (kept — the summary is worth more than the bytes):
  git-diff emits "diffstat only, patch not produced" advisory; eslint/git-add
  emit "ok" on clean input. These GROW tiny inputs but give the model a
  clearer signal; not a bug.
- WEAK on human-format input: git-status/git-log/git-show append a tally that
  can slightly inflate small outputs. They target --porcelain shape (arg
  injection rewrites `git status`->`git status --porcelain`). HONEST NOTE:
  the git-* family is the least effective in the set; its value is
  normalization, not compression. Documented rather than over-forced, because
  a blanket "never grow" rule broke 53 donor tests whose contract is to add a
  summary.

DEDUP verified live through the full two-hook sequence (PreToolUse hook-read
bumps the count, PostToolUse hook-read-post collapses on match): 94% saved on
an identical re-read (3249B -> 182B handle). A single post-hook call alone
does NOT dedup (needs count>=2 from the pre-hook) — by design.


## v0.8.2 — preference-aligned router backend (Arch-Router-1.5B)
Added archrouter.py: a stdlib-only client for katanemo/Arch-Router-1.5B
(VERIFIED on HF: Qwen2.5-1.5B base, arXiv:2506.16655, SOTA preference routing,
GGUF quants, powers katanemo's `arch` proxy). Fills the previously-empty
router/ slot with a REAL model contract, complementing route.py's cost math:
Arch-Router makes the semantic {domain,action}->route decision, route.py makes
the cost decision, and they compose.

LICENSE FLAG (recorded, not buried): Arch-Router-1.5B is katanemo-research
licensed, NOT permissive. Fine for Adversa research use; verify before any
commercial redistribution. A permissive <40MB alternative
(SupraLabs/Supra-Router-51M-gguf, Apache-2.0) is documented in
models/router/README.md but not wired (different pipe-schema contract).

Tested in-VM (tests/archrouter_suite.py, 3/3): prompt framing matches the
model card's required format; JSON {"route":name} parser is tolerant of extra
tokens and rejects invalid names -> 'other'; full HTTP round-trip against a
stub OpenAI-compatible endpoint routes correctly; transport failure fails safe
to 'other' so callers fall back to their default model. Routing QUALITY (does
the real 1.5B pick well) is a field test on archer with the served GGUF —
tokencut's job (framing/transport/parse/failsafe) is proven; the model's job
is not something this VM can measure. NOTE: these are all DOCUMENTED-CONTRACT
+ in-VM plumbing proofs; the model card was fetched, not the weights.

New CLI: `tokencut arch-route [endpoint]` (reads {routes, conversation} JSON
on stdin). settings-snippet.json unchanged (routing is not a hook).
