# router/ — preference-aligned routing model slot (EMPTY by design)

route.py does the COST math (Cluster/Route/Escalate). archrouter.py does the
SEMANTIC decision (which named route fits a prompt). This slot holds the model
for the latter. tokencut ships NO weights.

## VERIFIED option (recommended): katanemo/Arch-Router-1.5B
- Real (fetched 2026-08-18): Qwen2.5-1.5B base, arXiv:2506.16655, SOTA on
  preference-aligned routing, powers katanemo's `arch` proxy. GGUF quants exist.
- LICENSE: katanemo-research (NOT Apache/MIT). Fine for research; verify terms
  before commercial redistribution. This is the one non-permissive model
  tokencut points at — flagged deliberately.
- Serve on archer's Tesla GPUs:
    llama-server -hf katanemo/Arch-Router-1.5B:Q4_K_M --port 8087
  (or vLLM: vllm serve katanemo/Arch-Router-1.5B)
- Contract (from the model card, implemented in archrouter.py):
    define routes [{name, description}], pass conversation [{role, content}],
    model returns {"route": "<name>"} or {"route": "other"}.
- Wire test:
    echo '{"routes":[{"name":"code_gen","description":"write code"},
      {"name":"bug_fix","description":"fix errors"}],
      "conversation":[{"role":"user","content":"fix my torch error"}]}' \
      | tokencut arch-route http://localhost:8087/v1/chat/completions
    EXPECT: {"route":"bug_fix", ...}

## VERIFIED alternative (permissive, tiny): SupraLabs/Supra-Router-51M-gguf
- Real (fetched 2026-08-18): 51.8M params, Apache-2.0, GGUF from 19.6MB.
- Different contract: emits a pipe schema
  `Domain:.. | Complexity:1-5 | Math:T/F | Code:T/F | Route:small/big | ...`
  with framing `Task: <prompt>\nAnalysis:`. NOT wired in archrouter.py (which
  targets Arch-Router's JSON scheme). Use if you want Apache licensing and a
  <40MB footprint and are willing to add a pipe-schema parser.

## How this plugs into route.py
Arch-Router picks the NAMED route; you map each route name -> a Model in your
route.py pool, then route.py's cost math picks among models tied to that route.
Semantic decision (Arch) + cost decision (route.py) compose.

STATUS: archrouter.py client is code-complete and plumbing-tested in-VM
(framing, transport, JSON parse, fail-safe to 'other'). Routing QUALITY needs
the real GGUF on archer — that's the field test.
