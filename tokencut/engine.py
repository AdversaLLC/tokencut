"""tokencut.engine — declarative output-compression pipeline engine.

Executes the filter corpus in filters.json (ported from snip, MIT) against
command output. Stdlib-only. Every action is implemented; filters whose
semantics can't be honored fall back to passthrough (never mangle output).

Filter schema (per filter):
  match:    command, subcommand?, flags?, exclude_flags?
  pipeline: list of {action, ...params}
  on_error: "passthrough" (always honored)
  tests:    embedded input/expected pairs (used by selftest())
"""
from __future__ import annotations
import json, re, shlex
from pathlib import Path

_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07")
_FILTERS = None


def load_filters() -> dict:
    global _FILTERS
    if _FILTERS is None:
        _FILTERS = json.loads((Path(__file__).parent / "filters.json").read_text())
    return _FILTERS


# ------------------------------------------------------------------ matching
def match_command(cmdline: str) -> dict | None:
    """Return the filter dict matching a shell command line, or None."""
    try:
        toks = shlex.split(cmdline)
    except ValueError:
        return None
    if not toks:
        return None
    base = Path(toks[0]).name
    # unwrap launchers: python -m pytest / npx vitest / uv run pytest ...
    _LAUNCH = {"python", "python3", "npx", "bunx", "uvx"}
    if base in _LAUNCH or (base == "uv" and toks[1:2] == ["run"]):
        rest = toks[1:]
        if rest[:1] == ["run"]:
            rest = rest[1:]
        if rest[:1] == ["-m"]:
            rest = rest[1:]
        if rest:
            toks = rest
            base = Path(toks[0]).name
    sub = next((t for t in toks[1:] if not t.startswith("-")), None)
    flags = [t for t in toks[1:] if t.startswith("-")]
    best = None
    for f in load_filters().values():
        m = f.get("match", {})
        if m.get("command") != base:
            continue
        if m.get("subcommand") and m["subcommand"] != sub:
            continue
        ex = m.get("exclude_flags") or []
        if any(any(fl == e or fl.startswith(e) for e in ex) for fl in flags):
            continue
        # prefer the most specific match (subcommand beats bare command)
        if best is None or (m.get("subcommand") and not best.get("match", {}).get("subcommand")):
            best = f
    return best


# ------------------------------------------------------------------ actions
def _cond(cond: str, ctx: dict) -> bool:
    """Evaluate the condition shapes the corpus uses: .key (truthy),
    eq .k V, ne .k V, and (...) (...)."""
    cond = cond.strip()
    if cond.startswith("and"):
        return all(_cond(p, ctx) for p in re.findall(r"\(([^()]+)\)", cond))
    m = re.match(r"(eq|ne) \.(\w+) (\S+)", cond)
    if m:
        op, k, v = m.groups()
        same = str(ctx.get(k, "")) == v
        return same if op == "eq" else not same
    m = re.match(r"\.(\w+)$", cond)
    if m:
        v = ctx.get(m.group(1))
        return bool(v) and v != 0
    return False


def _tmpl(fmt: str, ctx: dict) -> str:
    """Minimal Go-template subset covering the shapes in the ported corpus:
    {{.key}}, {{if COND}}..{{else}}..{{end}} (nestable), {{with .stats}}..{{end}}."""
    # {{with .X}}...{{end}} (balanced against nested if/end) -> merged scope
    m = re.search(r"\{\{with \.(\w+)\}\}", fmt)
    if m:
        depth, i = 1, m.end()
        for tok in re.finditer(r"\{\{(if [^{}]+|with [^{}]+|end)\}\}", fmt[m.end():]):
            depth += 1 if not tok.group(1) == "end" else -1
            if depth == 0:
                i = m.end() + tok.start(); close_end = m.end() + tok.end(); break
        else:
            close_end = i = len(fmt)
        inner_ctx = dict(ctx); inner_ctx.update(ctx.get(m.group(1), {}) or {})
        fmt = fmt[: m.start()] + _tmpl(fmt[m.end(): i], inner_ctx) + fmt[close_end:]
    # innermost-first {{if}} resolution (loop handles nesting)
    if_rx = re.compile(r"\{\{if ([^{}]+?)\}\}((?:(?!\{\{if ).)*?)\{\{end\}\}", re.S)
    while True:
        m = if_rx.search(fmt)
        if not m:
            break
        body = m.group(2)
        then, _, els = body.partition("{{else}}")
        fmt = fmt[: m.start()] + (then if _cond(m.group(1), ctx) else els) + fmt[m.end():]
    return re.sub(r"\{\{\.(\w+)\}\}", lambda m: str(ctx.get(m.group(1), "")), fmt)


def _run_action(lines: list[str], a: dict, ctx: dict) -> list[str]:
    act = a["action"]
    if act == "strip_ansi":
        return [_ANSI.sub("", l) for l in lines]
    if act == "keep_lines":
        rx = re.compile(a["pattern"])
        return [l for l in lines if rx.search(l)]
    if act == "remove_lines":
        rx = re.compile(a["pattern"])
        return [l for l in lines if not rx.search(l)]
    if act == "truncate_lines":
        mx = int(a["max"])
        return [l if len(l) <= mx else l[: mx - 1] + "…" for l in lines]
    if act == "head":
        n = int(a["n"])
        if len(lines) > n:
            over = len(lines) - n
            out = lines[:n]
            msg = a.get("overflow_msg") or a.get("overflow_format") or "+{overflow} more lines"
            out.append(msg.replace("{{.overflow}}", str(over)).replace("{overflow}", str(over)))
            return out
        return lines
    if act == "tail":
        return lines[-int(a["n"]):]
    if act == "replace":
        rx = re.compile(a["pattern"])
        rep = re.sub(r"\$(\d+)", r"\\\1", a.get("replacement", ""))  # Go $1 -> Python \1
        return [rx.sub(rep, l) for l in lines]
    if act == "dedup":
        seen, out = set(), []
        for l in lines:
            if l not in seen:
                seen.add(l); out.append(l)
        return out
    if act == "on_empty":
        return lines if any(l.strip() for l in lines) else [a.get("message", a.get("text", ""))]
    if act == "aggregate":
        counts = {k: 0 for k in a["patterns"]}
        regs = {k: re.compile(p) for k, p in a["patterns"].items()}
        for l in lines:
            for k, rx in regs.items():
                if rx.search(l):
                    counts[k] += 1
        if a.get("append"):           # stash for a later format_template
            ctx.setdefault("stats", {}).update(counts)
            return lines
        c = dict(counts); c.update(ctx)
        return [_tmpl(a["format"], c)]
    if act == "group_by":
        rx = re.compile(a["pattern"])
        counts: dict[str, int] = {}
        rest = []
        for l in lines:
            m = rx.search(l)
            if m:
                key = m.group(1) if rx.groups else m.group(0)
                counts[key] = counts.get(key, 0) + 1
            else:
                rest.append(l)
        items = sorted(counts.items(), key=lambda kv: -kv[1])
        if a.get("top"):
            items = items[: int(a["top"])]
        summary = [_tmpl(a["format"], {"Key": k, "Count": c}) for k, c in items]
        return (lines + summary) if a.get("append") else summary
    if act == "state_machine":
        states = a["states"]
        cur, out = "start", []
        for l in lines:
            st = states.get(cur, {})
            keep = st.get("keep")
            if keep and re.search(keep, l):
                out.append(l)
            until = st.get("until")
            if until and re.search(until, l):
                cur = st.get("next", cur)   # transition line is consumed, not emitted
        return out
    if act == "regex_extract":
        rx = re.compile(a["pattern"])
        fmt = a.get("format")
        out = []
        for l in lines:
            m = rx.search(l)
            if m:
                if fmt:
                    out.append(re.sub(r"\$(\d+)", lambda g: m.group(int(g.group(1))) or "", fmt))
                else:
                    out.append(m.group(1) if rx.groups else m.group(0))
        return out
    if act == "format_template":
        c = {"lines": "\n".join(lines), "count": len(lines)}
        c.update(ctx)
        return _tmpl(a.get("template", ""), c).split("\n")
    raise KeyError(f"unknown action: {act}")


# ------------------------------------------------------------------ run
_ERROR_RX = re.compile(
    r"\b(error|fatal|panic(?:ked)?|traceback|exception|FAILED|failure)\b"
    r"|\berror\[?[A-Z]{1,4}\d{2,5}"
    r"|npm ERR!|BUILD FAILED|CS\d{4}|E\d{4}:", re.I)


def apply_filter(filt: dict, text: str) -> str:
    """Run one filter's pipeline. on_error: passthrough — always.

    Salvage net: if the INPUT carried error-shaped lines and the pipeline
    dropped every one of them (out-of-grammar output), append up to 8 of
    the originals under a marker. Errors must never be eaten silently —
    this is the failure mode behind independently measured filter
    regressions (JetBrains rtk A/B)."""
    lines = text.splitlines()
    ctx: dict = {}
    try:
        for a in filt.get("pipeline", []):
            lines = _run_action(lines, a, ctx)
        out = "\n".join(lines)
        _LOC_RX = re.compile(r"[\w./-]+[:(]\d+[,:)]?\d*\)?:?\s*(error|fatal)", re.I)
        in_errs = [l for l in text.splitlines() if _ERROR_RX.search(l)]
        in_locs = [l for l in in_errs if _LOC_RX.search(l)]
        out_has_err = any(_ERROR_RX.search(l) for l in lines)
        out_has_loc = any(_LOC_RX.search(l) for l in lines)
        if in_locs and not out_has_loc:          # located compiler errors lost
            in_errs, out_has_err = in_locs, False
        if in_errs and not out_has_err:
            keep = in_errs[:8]
            more = len(in_errs) - len(keep)
            out += "\n[tokencut salvaged errors]\n" + "\n".join(keep)
            if more > 0:
                out += f"\n(+{more} more error lines in raw output)"
        return out
    except Exception:
        return text  # passthrough, per on_error


def compress(cmdline: str, output: str) -> tuple[str, dict]:
    """Compress `output` of `cmdline`. Returns (text, stats)."""
    filt = match_command(cmdline)
    if not filt:
        return output, {"filter": None, "before": len(output), "after": len(output)}
    out = apply_filter(filt, output)
    return out, {
        "filter": filt.get("name"),
        "before": len(output),
        "after": len(out),
        "saved_pct": round(100 * (1 - len(out) / max(len(output), 1)), 1),
        "est_tokens_saved": max(0, (len(output) - len(out)) // 4),
    }


def inject_args(cmdline: str) -> str:
    """Apply a filter's arg-injection (e.g. pytest -> pytest --tb=line -q)."""
    filt = match_command(cmdline)
    if not filt or "inject" not in filt:
        return cmdline
    inj = filt["inject"]
    skip = inj.get("skip_if_present", [])
    if any(s in cmdline for s in skip):
        return cmdline
    return cmdline + " " + " ".join(inj.get("args", []))


# ------------------------------------------------------------------ selftest
def selftest(verbose: bool = False) -> tuple[int, int, list[str]]:
    """Run every embedded test from the ported corpus against this engine."""
    passed = failed = 0
    failures = []
    for name, f in load_filters().items():
        for t in f.get("tests", []):
            got = apply_filter(f, t["input"].rstrip("\n"))
            want = t["expected"].rstrip("\n")
            if got.strip() == want.strip():
                passed += 1
            else:
                failed += 1
                failures.append(f"{name}::{t.get('name','?')}")
                if verbose:
                    failures.append(f"  want: {want!r}\n  got:  {got!r}")
    return passed, failed, failures
