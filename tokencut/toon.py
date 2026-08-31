"""tokencut.toon — TOON encoder, conformant to the official spec (v4.1).

TOON (Token-Oriented Object Notation, toonformat.dev) is a lossless, compact
encoding of the JSON data model for LLM input. Four forms:
  inline   : arrays of primitives            tags[3]: a,b,c
  tabular  : uniform arrays of objects        users[2]{id,name}: <rows>
             + nested field groups            orders[2]{id,customer{name,country}}:
  list     : mixed/non-uniform arrays          - item (hyphen markers)
  object   : key: value with 2-space indent

Quoting (spec §quoting): a string is quoted iff it is empty, has leading/
trailing whitespace, equals true/false/null, looks like a number, contains a
structural char (:"\\[]{}), contains the active delimiter, or starts with -/#.
Normalization: NaN/Infinity/None -> null. Lossless round-trip is the contract
the previous ad-hoc encoder violated (it emitted "42" unquoted, decoding back
as an int). Encoder only — decode with any TOON lib.
"""
from __future__ import annotations
import json, math, re

_NUMLIKE = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$|^-?\.\d+$")
_RESERVED = {"true", "false", "null"}
_STRUCTURAL = set(':"\\[]{}')


def _needs_quote(s: str, delim: str = ",") -> bool:
    if s == "" or s != s.strip():
        return True
    if s in _RESERVED or _NUMLIKE.match(s):
        return True
    if s[0] in "-#":
        return True
    if delim in s:
        return True
    return any(c in _STRUCTURAL or ord(c) < 0x20 for c in s)


def _quote(s: str) -> str:
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") \
           .replace("\r", "\\r").replace("\t", "\\t")
    return f'"{out}"'


def _scalar(v, delim: str = ",") -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return "null"
        return repr(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, int):
        return str(v)
    s = str(v)
    return _quote(s) if _needs_quote(s, delim) else s


def _tabular_fields(arr: list) -> list | None:
    """Return the flat field header (with nested groups) if `arr` is a uniform
    array of objects whose values are primitives or uniform sub-objects."""
    if not arr or not all(isinstance(x, dict) for x in arr):
        return None
    keys = list(arr[0].keys())
    if not all(list(x.keys()) == keys for x in arr):
        return None
    header = []
    for k in keys:
        col_vals = [x[k] for x in arr]
        if all(isinstance(cv, dict) for cv in col_vals):
            sub_keys = list(col_vals[0].keys())
            if all(list(cv.keys()) == sub_keys for cv in col_vals) and \
               all(not isinstance(cv[sk], (dict, list)) for cv in col_vals for sk in sub_keys):
                header.append((k, sub_keys))      # nested field group
                continue
            return None                            # non-uniform nested -> not tabular
        if any(isinstance(cv, (dict, list)) for cv in col_vals):
            return None                            # mixed/list column -> not tabular
        header.append((k, None))
    return header


def _tab_header_str(header: list) -> str:
    parts = []
    for k, sub in header:
        parts.append(f"{k}{{{','.join(sub)}}}" if sub else k)
    return "{" + ",".join(parts) + "}"


def _tab_row(obj: dict, header: list, delim: str) -> str:
    cells = []
    for k, sub in header:
        if sub:
            cells.extend(_scalar(obj[k][sk], delim) for sk in sub)
        else:
            cells.append(_scalar(obj[k], delim))
    return delim.join(cells)


def _encode(obj, indent: int, delim: str) -> list[str]:
    pad = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            lines.extend(_encode_kv(k, v, indent, delim))
        return lines
    if isinstance(obj, list):
        return _encode_kv("", obj, indent, delim)  # bare array (rare top-level)
    return [pad + _scalar(obj, delim)]


def _encode_kv(key: str, v, indent: int, delim: str) -> list[str]:
    pad = "  " * indent
    kp = f"{key}: " if key else ""
    kbare = key if key else ""
    if isinstance(v, dict):
        if not v:
            return [f"{pad}{key}: {{}}" if key else f"{pad}{{}}"]
        return [f"{pad}{key}:" if key else f"{pad}"] + _encode(v, indent + 1, delim)
    if isinstance(v, list):
        if not v:
            return [f"{pad}{kbare}[0]:"]
        # inline: all primitives
        if all(not isinstance(x, (dict, list)) for x in v):
            return [f"{pad}{kbare}[{len(v)}]: " + delim.join(_scalar(x, delim) for x in v)]
        # tabular: uniform objects
        header = _tabular_fields(v)
        if header is not None:
            head = f"{pad}{kbare}[{len(v)}]{_tab_header_str(header)}:"
            rows = [pad + "  " + _tab_row(x, header, delim) for x in v]
            return [head] + rows
        # list form: hyphen markers
        out = [f"{pad}{kbare}[{len(v)}]:"]
        for x in v:
            if isinstance(x, (dict, list)):
                sub = _encode(x, indent + 1, delim)
                if sub:
                    sub[0] = pad + "  - " + sub[0].strip()
                    out.extend([sub[0]] + [pad + "    " + s.strip() for s in sub[1:]])
            else:
                out.append(pad + "  - " + _scalar(x, delim))
        return out
    return [f"{pad}{key}: {_scalar(v, delim)}"]


def encode(obj, delim: str = ",") -> str:
    return "\n".join(_encode(obj, 0, delim))


def savings(obj) -> dict:
    j = json.dumps(obj, separators=(",", ":"))
    t = encode(obj)
    return {"json_est_tokens": len(j) // 4, "toon_est_tokens": len(t) // 4,
            "saved_pct": round(100 * (1 - len(t) / max(len(j), 1)), 1)}
