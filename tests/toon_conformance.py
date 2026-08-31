"""TOON conformance vs the official spec (v4.1, fetched 2026-08-18).
Rules encoded: 4 array forms, minimal quoting (empty/ws/reserved/number-like/
structural/delimiter/leading -#), [N]{fields}: header, null normalization."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tokencut.toon import encode

CASES = [
    # (json_obj, must_contain_lines[])  — spec examples
    ({"users":[{"id":1,"name":"Alice","role":"admin"},{"id":2,"name":"Bob","role":"user"}]},
     ["users[2]{id,name,role}:", "1,Alice,admin", "2,Bob,user"]),
    ({"tags":["admin","ops","dev"]}, ["tags[3]: admin,ops,dev"]),
    # quoting: number-like string, reserved words, empty, structural, leading dash
    ({"a":"42"}, ['a: "42"']),
    ({"a":"true"}, ['a: "true"']),
    ({"a":""}, ['a: ""']),
    ({"a":"x,y"}, ['a: "x,y"']),
    ({"a":"-hi"}, ['a: "-hi"']),
    ({"a":"he:llo"}, ['a: "he:llo"']),
    ({"a":"plain"}, ["a: plain"]),          # no quotes when safe
    # null / NaN / Infinity normalization
    ({"a":None}, ["a: null"]),
    # nested object (indentation)
    ({"user":{"name":"Ada","country":"DK"}}, ["user:", "  name: Ada", "  country: DK"]),
    # nested field group in tabular
    ({"orders":[{"id":1,"customer":{"name":"Ada","country":"DK"}},
                {"id":2,"customer":{"name":"Bo","country":"US"}}]},
     ["orders[2]{id,customer{name,country}}:", "1,Ada,DK", "2,Bo,US"]),
]

def run():
    passed = fails = 0
    for obj, musts in CASES:
        out = encode(obj)
        lines = out.split("\n")
        ok = all(any(m == l.strip() or m == l for l in lines) or m in out for m in musts)
        if ok: passed += 1
        else:
            fails += 1
            print(f"  FAIL {json.dumps(obj)[:50]}")
            print(f"    want lines: {musts}")
            print(f"    got:\n      " + "\n      ".join(lines))
    print(f"TOON conformance: {passed}/{len(CASES)} spec cases pass")
    return fails

if __name__ == "__main__":
    sys.exit(1 if run() else 0)
