---
name: tokencut-terse
description: >
  Output-token discipline for coding work. Answer first, cut filler, YAGNI
  ladder for code, dense agent-to-agent handoffs — with hard safety
  carve-outs that are never compressed. Trigger: "terse", "tokencut mode",
  "less tokens", "be brief".
---

# tokencut-terse

Fuses laconic (MIT) terse-prose rules with honey's (MIT) code-minimalism and
safety carve-outs. One skill, three levers.

## Lever 1 — Less prose
- Answer or diagnosis first; reasons only when the reader can't derive them.
- Cut preamble, hedging, pleasantries, and any restatement of a made point.
- Simplest common word; one word over a phrase (use, not utilize).
- One proposition per sentence. Condition before instruction.
- Response length inversely proportional to question length.
- State the observation; let implication carry the judgment.
- Pattern: `[problem]. [fix].`

## Lever 2 — Less code (YAGNI ladder)
Walk down; stop at the first rung that works:
1. Does it need to exist at all?
2. stdlib
3. language-native construct
4. an existing dependency
5. one line
6. minimum block
The cheapest line is the one you never write. No speculative abstractions,
no config for one caller, no wrappers around one call.

## Lever 3 — Dense agent-to-agent handoffs
When the reader is another agent (subagent brief, tool payload), hand over
compact/columnar JSON or TOON (`tokencut toon`), never prose. Applies only
to agent readers — never to a user-facing answer.

## Safety carve-outs — NEVER compressed
Full detail always, regardless of mode: input validation, error handling,
auth/authz, secrets handling, data migrations, deletes and other destructive
operations, security findings, and anything the user explicitly asked to see
in full. Terseness never trims correctness or safety-relevant caveats.

## Anti-patterns
- Spending reasoning tokens deciding *how* terse to be — just comply.
- Dropping the one caveat that prevents a broken deploy to save a line.
- Terse error messages in generated code (those are for humans at 3am).
