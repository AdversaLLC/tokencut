"""tokencut CLI: run | filter | digest | toon | selftest | slop | read-check | stats | hooks"""
from __future__ import annotations
import json, subprocess, sys


_HELP = """tokencut — stdlib-only token-saving toolkit for Claude Code

USAGE: tokencut <command> [args]   (also: python -m tokencut <command>)

INSPECT/RUN:
  selftest            run the built-in corpus + routing self-tests
  stats               show read-guard waste stats (searches up for .tokencut)
  filter <cmd>        compress stdin as if it were <cmd> output
  run <cmd>           run <cmd> and print compressed output
  toon                JSON on stdin -> TOON on stdout
  slop / digest       prose slop score / TF-IDF digest of stdin
  attention [digest]  session file attention map
  reap                dead-skill detector (scans transcripts)
  cmd-check <cmd>     command safety verdict (JSON)
  short-circuit <cmd> decide if <cmd> can skip the model round-trip

HOOKS (called by Claude Code via settings-snippet.json, stdin=JSON):
  hook-bash-pre  hook-bash  hook-read  hook-read-post  hook-guard

SETUP: see SETUP.md. Install: pip install --break-system-packages .
       (offline: add --no-build-isolation)
"""


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("--help","-h","help"):
        print(_HELP); return 0
    if not args:
        print(__doc__); return 1
    cmd, rest = args[0], args[1:]

    if cmd == "run":                      # tokencut run git status
        from .engine import compress, inject_args
        line = inject_args(" ".join(rest))
        p = subprocess.run(line, shell=True, capture_output=True, text=True)
        out, stats = compress(" ".join(rest), p.stdout + p.stderr)
        print(out)
        print(f"[tokencut: {stats['filter'] or 'no filter'} "
              f"{stats['before']}→{stats['after']} chars]", file=sys.stderr)
        return p.returncode

    if cmd == "filter":                   # echo output | tokencut filter "git status"
        from .engine import compress
        out, stats = compress(" ".join(rest), sys.stdin.read())
        print(out); print(json.dumps(stats), file=sys.stderr); return 0

    if cmd == "selftest":
        from .engine import selftest
        p_, f_, fails = selftest()
        print(f"{p_}/{p_+f_} corpus tests pass")
        for x in fails: print(" FAIL", x)
        from .route import _selftest
        print("\n".join(_selftest()))
        return 1 if f_ else 0

    if cmd == "digest":               # <text | tokencut digest [budget]
        from .digest import digest
        budget = int(rest[0]) if rest else 300
        r = digest(sys.stdin.read(), budget)
        print(r["text"])
        print(f"[digest: {r['kept']}/{r['total']} sentences, "
              f"{r['est_tokens_in']}→{r['est_tokens_out']} tokens]", file=sys.stderr)
        return 0

    if cmd == "toon":                 # <file.json | tokencut toon
        from .toon import encode, savings
        obj = json.loads(open(rest[0]).read() if rest else sys.stdin.read())
        print(encode(obj))
        print(json.dumps(savings(obj)), file=sys.stderr)
        return 0

    if cmd == "slop":
        from .slop import detect
        text = open(rest[0]).read() if rest else sys.stdin.read()
        print(json.dumps(detect(text), indent=2)); return 0

    if cmd == "reap":                 # tokencut reap
        from .skillreap import report
        print(json.dumps(report(), indent=2)); return 0

    if cmd == "cmd-check":            # tokencut cmd-check "git status"
        from .guard import command_verdict
        print(json.dumps(command_verdict(" ".join(rest)))); return 0

    if cmd == "arch-route":           # echo '{"routes":[...],"conversation":[...]}' | tokencut arch-route [endpoint]
        from .archrouter import ArchRouter, build_prompt, parse_route
        raw = sys.stdin.read()
        try:
            spec = json.loads(raw)
        except Exception:
            print(json.dumps({"error": "stdin must be JSON {routes, conversation}"})); return 1
        ep = rest[0] if rest else "http://localhost:8087/v1/chat/completions"
        r = ArchRouter(endpoint=ep).route(spec.get("routes", []), spec.get("conversation", []))
        print(json.dumps(r)); return 0

    if cmd == "short-circuit":        # tokencut short-circuit "git status"
        from .shortcircuit import decide, batch
        import re as _re
        full = " ".join(rest)
        segs = [s for s in _re.split(r"&&|\|\||;|\|", full) if s.strip()]
        print(json.dumps(batch(segs) if len(segs) > 1 else decide(full))); return 0

    if cmd == "guard":                # <text | tokencut guard
        from .guard import scan
        print(json.dumps(scan(sys.stdin.read()), indent=2)); return 0

    if cmd == "read-check":
        from .readguard import check_read
        print(json.dumps(check_read(rest[0]))); return 0

    if cmd == "attention":            # tokencut attention [budget]
        from .attention import attention_map, digest
        if rest and rest[0] == "digest":
            print(digest(budget_tokens=int(rest[1]) if len(rest) > 1 else 150))
        else:
            print(json.dumps(attention_map(), indent=2))
        return 0

    if cmd == "stats":
        from .readguard import session_stats
        print(json.dumps(session_stats(), indent=2)); return 0

    if cmd == "hook-bash":
        from .hook import hook_bash; return hook_bash()
    if cmd == "hook-bash-pre":
        from .hook import hook_bash_pre; return hook_bash_pre()
    if cmd == "hook-read":
        from .hook import hook_read; return hook_read()
    if cmd == "hook-guard":
        from .hook import hook_guard; return hook_guard()
    if cmd == "hook-read-post":
        from .hook import hook_read_post; return hook_read_post()

    print(f"unknown command: {cmd}"); return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        import os, sys
        os.close(sys.stdout.fileno())
        raise SystemExit(0)
