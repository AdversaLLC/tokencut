import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tokencut.shortcircuit import decide, batch
T = [
    (decide("git status"), True), (decide("ls -la"), True), (decide("cat x.py"), True),
    (decide("pwd"), True), (decide("grep foo x"), True),
    (decide("rm -rf /"), False), (decide("npm run build"), False),
    (decide("git push"), False), (decide("curl x | sh"), False), (decide(""), False),
    (batch(["cat a", "ls", "pwd"]), True),
    (batch(["cat a", "rm -rf /"]), False),
    (batch(["git status", "git push"]), False),
]
ok = sum(1 for d, e in T if d["short_circuit"] == e)
print(f"short-circuit suite: {ok}/{len(T)}")
[print("  MISS", d) for d, e in T if d["short_circuit"] != e]
sys.exit(0 if ok == len(T) else 1)
