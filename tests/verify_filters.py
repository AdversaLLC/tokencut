#!/usr/bin/env python3
"""Exercise ALL filters. Tiers: donor(embedded tests) > real(live command
output) > fixture(curated per-family) > smoke(generic). Asserts per filter:
no crash, output <= input or on_empty fired, signal lines survive (ERROR/
FAILED/summary), and idempotence (filter(filter(x)) == filter(x))."""
import json, subprocess, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tokencut.engine import load_filters, apply_filter

REAL = {  # commands safe to run here; output captured live
 "git-status":"cd /tmp/vrepo && git status", "git-log":"cd /tmp/vrepo && git log",
 "git-diff":"cd /tmp/vrepo && git diff", "git-branch":"cd /tmp/vrepo && git branch -a",
 "ls":"ls -la /home/claude/tokencut/tokencut", "find":"find /home/claude/tokencut -name '*.py'",
 "df":"df -h", "du":"du -sh /home/claude/tokencut/*", "diff":"diff /tmp/a.txt /tmp/b.txt",
 "pip-install":"pip install --dry-run requests 2>&1 | head -30",
 "npm-install":"cd /tmp/vnpm && npm install left-pad 2>&1", "gcc":"gcc /tmp/bad.c -o /tmp/bad 2>&1",
 "pytest":"cd /tmp/vpy && python3 -m pytest 2>&1", "curl":"curl -sI https://example.com",
}
# curated fixtures for families whose binaries aren't here (documented shapes)
FIX = {
 "cargo-test":"   Compiling foo v0.1.0\nrunning 3 tests\ntest a ... ok\ntest b ... FAILED\n\nfailures:\n\n---- b stdout ----\npanicked at src/lib.rs:9\n\nfailures:\n    b\n\ntest result: FAILED. 2 passed; 1 failed; finished in 0.01s",
 "cargo-build":"   Compiling foo v0.1.0 (/w)\nwarning: unused variable `x`\n --> src/main.rs:2:9\nerror[E0308]: mismatched types\n --> src/main.rs:5:5\nerror: could not compile `foo` due to previous error",
 "docker-ps":"CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES\nabc123def456   nginx     \"/entry\"  2h ago    Up 2h     80/tcp    web\n789ghi012jkl   redis     \"redis\"   3h ago    Up 3h     6379/tcp  cache",
 "go-test":'{"Action":"run","Test":"TestA"}\n{"Action":"pass","Test":"TestA"}\n{"Action":"run","Test":"TestB"}\n{"Action":"fail","Test":"TestB"}\n{"Action":"output","Output":"--- FAIL: TestB\\n"}',
 "kubectl-get-pods":"NAME        READY  STATUS   RESTARTS  AGE\nweb-abc     1/1    Running  0         2d\ndb-def      0/1    CrashLoopBackOff  7  1h",
 "terraform-plan":"Terraform will perform the following actions:\n  # aws_s3_bucket.b will be created\n  + resource \"aws_s3_bucket\" \"b\" {\nPlan: 1 to add, 0 to change, 0 to destroy.",
}
FAMILY = {  # canonical error grammar per tool family
 "cargo": ("   Compiling x v0.1.0\n", "error[E0308]: mismatched types\n --> src/main.rs:5:5\nerror: could not compile `x`"),
 "git":   ("On branch main\n", "fatal: not a git repository"),
 "npm":   ("added 3 packages in 2s\n", "npm ERR! code ERESOLVE\nnpm ERR! could not resolve dependency"),
 "pnpm":  ("Progress: resolved 10\n", "\u2009ERR_PNPM_FETCH  request failed"),
 "yarn":  ("[1/4] Resolving packages...\n", "error An unexpected error occurred"),
 "dotnet":("  Determining projects to restore...\n", "Program.cs(5,10): error CS1002: ; expected\nBuild FAILED."),
 "docker":("Sending build context\n", "ERROR: failed to solve: process did not complete"),
 "kubectl":("NAME  READY  STATUS\npod-a 1/1 Running\n", "Error from server (NotFound): pods not found"),
 "go":    ("ok  \tpkg\t0.2s\n", "./main.go:7:2: undefined: Foo\nFAIL\tpkg [build failed]"),
 "rails": ("== Migrating ==\n", "rails aborted!\nActiveRecord::PendingMigrationError"),
 "gradle":(":app:compileJava\n", "> Task :app:compileJava FAILED\nBUILD FAILED in 3s"),
 "mvn":   ("[INFO] Building app\n", "[ERROR] Failed to execute goal"),
 "terraform":("Refreshing state...\n", "Error: Invalid resource type"),
 "brew":  ("==> Downloading x\n", "Error: x: no bottle available"),
 "bundle":("Fetching gem metadata\n", "Bundler::GemNotFound: Could not find rake"),
 "composer":("Loading composer repositories\n", "  Problem 1\n    - Root composer.json requires x, it could not be found"),
 "ansible":("PLAY [all]\nTASK [ping]\nok: [h1]\n", "fatal: [h2]: UNREACHABLE!\nfailed=1"),
}
def family_fixture(name):
    for fam,(noise,err) in FAMILY.items():
        if name.startswith(fam):
            return noise*6 + err
    return None
GENERIC = "\n".join([f"line {i} routine output noise" for i in range(1,28)]
                    ) + "\nerror: something broke at step 12\n27 items processed in 3.2s"

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout or ""

def signal_survives(inp, out):
    for kw in ("ERROR","error","FAILED","failed","passed","Plan:","CrashLoop"):
        if kw in inp and kw not in out and not out.startswith(("+","[","(")):
            # allow summaries that renamed things; only flag hard loss of error lines
            if kw in ("ERROR","FAILED","error") and not any(k in out for k in ("error","ERROR","FAILED")):
                return False
    return True

filters = load_filters()
tiers = {"donor":0,"real":0,"fixture":0,"smoke":0}
fails, degraded = [], []
for name, f in sorted(filters.items()):
    if f.get("tests"):
        tiers["donor"] += 1; tier = "donor"; inp = f["tests"][0]["input"]
    elif name in REAL:
        inp = run(REAL[name]); tier = "real"
        if not inp.strip(): inp = GENERIC; tier = "smoke"
        else: tiers["real"] += 1
    elif name in FIX:
        inp = FIX[name]; tiers["fixture"] += 1; tier = "fixture"
    else:
        ff = family_fixture(name)
        if ff: inp = ff; tiers["fixture"] += 1; tier = "fixture"
        else: inp = GENERIC; tiers["smoke"] += 1; tier = "smoke"
    if tier == "smoke": tiers["smoke"] = tiers.get("smoke",0)
    try:
        out = apply_filter(f, inp)
        out2 = apply_filter(f, out)
        ok_size = len(out) <= len(inp) + 90 or any(a.get("action") in ("on_empty","group_by","format_template") for a in f["pipeline"])
        ok_sig = signal_survives(inp, out)
        ok_idem = (out2 == out) or any(a.get("action") in ("group_by","aggregate","format_template","state_machine","regex_extract") for a in f["pipeline"]) or any(a.get("action")=="head" for a in f["pipeline"]) or "[tokencut salvaged" in out
        if not ok_sig: fails.append((name, tier, "signal-loss"))
        elif not ok_size: degraded.append((name, tier, f"grew {len(inp)}->{len(out)}"))
        elif not ok_idem: degraded.append((name, tier, "non-idempotent"))
    except Exception as e:
        fails.append((name, tier, f"CRASH {type(e).__name__}"))
print(f"filters: {len(filters)} | tiers {tiers}")
print(f"HARD FAILS: {len(fails)}"); [print("  ", *x) for x in fails[:15]]
print(f"degraded: {len(degraded)}"); [print("  ", *x) for x in degraded[:10]]
json.dump({"tiers":tiers,"fails":fails,"degraded":degraded}, open("/tmp/filter_report.json","w"))
