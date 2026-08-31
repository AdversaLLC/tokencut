# CLAUDE.md baseline (companion to tokencut-terse)

Source: user-provided behavioral guidelines (Arch/Adversa), merged verbatim
in spirit; complements the terse skill — terse governs OUTPUT, this governs
PROCESS. Merge into project CLAUDE.md.

## Think Before Coding
State assumptions; surface multiple interpretations instead of picking
silently; push back when a simpler approach exists; stop and ask when
confused. Clarifying questions come BEFORE implementation.

## Simplicity First
Minimum code that solves the problem. No speculative features, abstractions
for single-use code, unrequested configurability, or impossible-case error
handling. Test: "Would a senior engineer call this overcomplicated?"

## Surgical Changes
Touch only what the request requires. Don't improve adjacent code or
reformat; match existing style. Remove only orphans YOUR change created;
mention pre-existing dead code, don't delete it. Every changed line traces
to the request.

## Goal-Driven Execution
Transform tasks into verifiable goals ("fix the bug" -> "write a repro test,
make it pass"). For multi-step work, state plan as step -> verify pairs.
Strong success criteria enable independent looping.

Interaction with tokencut-terse carve-outs: these guidelines never justify
skipping validation/auth/error-handling the task actually needs — Simplicity
First trims the speculative, not the safety-relevant.
