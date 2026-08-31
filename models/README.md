# models/ — local model slots (all EMPTY by design)

Core is stdlib-only and works with every folder empty. Each slot upgrades one
feature. Statuses below were verified against Hugging Face on 2026-08-18.

## embeddings/  → upgrades route.py Stage-1 clustering (embed.py)
- llama.cpp path (archer):
    huggingface-cli download nomic-ai/nomic-embed-text-v1.5-GGUF \
        nomic-embed-text-v1.5.Q8_0.gguf --local-dir models/embeddings
    llama-server -m models/embeddings/*.gguf --embedding --port 8089
- Tiny CPU path: minishlab/potion-base-8M (Model2Vec static, ~30MB).
Verify: python3 -c "from tokencut.embed import EmbeddingClient as E; print(len(E().embed(['hi'])[0]))"

## guard/  → upgrades guard.py heuristics → trained classifier
Resolution order for this dir: $TOKENCUT_MODELS/guard → ./models/guard →
~/.tokencut/models/guard.
- VERIFIED, drop-in-ready path: protectai/deberta-v3-base-prompt-injection-v2
  (Apache-2.0). Needs model.onnx + tokenizer.json here + guard.json
  {"injection_label_index": 1}. Extras: pip install onnxruntime tokenizers.
- VERIFIED, needs one export step: Unplug-AI/unplug-tiny-v1 (Apache-2.0,
  283MB safetensors, tokenizer.json present). Ships NO ONNX and uses a
  custom DebertaV2ForDualHead class — either run it via transformers
  directly, or export the classification head to ONNX before dropping in.
  Its span head (tells you WHERE the injection is) is not yet consumed by
  guard.py; binary head works via guard.json.
- VERIFIED, GGUF/llama.cpp route (not ONNX): inclusionAI/SingGuard-NSFA-0.8B-GGUF
  — serve on llama-server and call it as a second opinion; ~0.8B, heavier.

## phish/  → optional URL screen (no code wired yet; scaffold only)
- VERIFIED: saidutta69/PhishScout (MIT): model.onnx is 135kB LightGBM over
  35 URL features defined in the repo's features.json — integration needs a
  feature extractor implementing that spec, NOT a text tokenizer. Download
  model.onnx + features.json + model_info.json here if/when wired.

## router/  → complexity pre-routing (future workspace.py)
- Candidate: SupraLabs Supra-Router GGUFs (check exact repo on HF).
- VERIFIED adjacent: fdtn-ai/antares-350m (Apache-2.0, Cisco Foundation AI,
  Granite-4.0 base) — NOT a router; it's a terminal-agent vulnerability
  localizer. GATED repo (accept conditions to download); GGUF quants exist
  for llama.cpp. Honest numbers: VLoc Bench File F1 0.135 — beats Gemini 2.5
  Flash / GPT-5 Mini / Qwen3.5-122B at 350M params, but GPT-5.5 (0.229) and
  its own 1B/3B siblings sit above it. Budget: 15 terminal commands/task;
  degrades on repos >10MB; run sandboxed (network=none) per its card.
  Belongs in the /security skill workflow, not the token stack proper.
