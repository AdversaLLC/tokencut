"""tokencut.archrouter — preference-aligned routing via Arch-Router-1.5B.

Arch-Router (katanemo, arXiv:2506.16655, Qwen2.5-1.5B base) maps a prompt to
a user-defined {domain, action} route and returns JSON {"route": "<name>"}.
This complements route.py: route.py does the COST math over clusters;
ArchRouter does the SEMANTIC decision (which named route fits this prompt),
which you then map to a model. Runs on any OpenAI-compatible endpoint
(llama.cpp / vLLM serving the GGUF on archer's Tesla GPUs). Stdlib-only:
talks HTTP with urllib, parses JSON with json. No model bundled.

LICENSE NOTE: Arch-Router-1.5B is under the katanemo-research license (NOT
Apache/MIT). Fine for research; check terms before commercial redistribution.
tokencut ships NO weights — only this client + the prompt contract.
"""
from __future__ import annotations
import json, re, urllib.request

# The model's provided prompt format (from the model card) — best performance
# requires this exact framing.
TASK_INSTRUCTION = """
You are a helpful assistant designed to find the best suited route.
You are provided with route description within <routes></routes> XML tags:
<routes>

{routes}

</routes>

<conversation>

{conversation}

</conversation>
"""

FORMAT_PROMPT = """
Your task is to decide which route is best suit with user intent on the conversation in <conversation></conversation> XML tags.  Follow the instruction:
1. If the latest intent from user is irrelevant or user intent is full filled, response with other route {"route": "other"}.
2. You must analyze the route descriptions and find the best match route for user latest intent.
3. You only response the name of the route that best matches the user's request, use the exact name in the <routes></routes>.

Based on your analysis, provide your response in the following JSON formats if you decide to match any route:
{"route": "route_name"}
"""


def build_prompt(routes: list[dict], conversation: list[dict]) -> str:
    """routes: [{"name","description"}]; conversation: [{"role","content"}]."""
    return (TASK_INSTRUCTION.format(routes=json.dumps(routes),
                                    conversation=json.dumps(conversation))
            + FORMAT_PROMPT)


def parse_route(text: str, valid: set[str] | None = None) -> str:
    """Extract {"route": name} from model output; fall back to 'other'.
    Tolerant: finds the JSON object even amid extra tokens."""
    m = re.search(r'\{\s*"route"\s*:\s*"([^"]+)"\s*\}', text)
    name = m.group(1) if m else "other"
    if valid is not None and name not in valid:
        return "other"
    return name


class ArchRouter:
    """Client for an OpenAI-compatible endpoint serving Arch-Router."""

    def __init__(self, endpoint: str = "http://localhost:8087/v1/chat/completions",
                 model: str = "arch-router", timeout: float = 30.0):
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout

    def route(self, routes: list[dict], conversation: list[dict]) -> dict:
        """Return {"route": name, "raw": <model text>}. Never raises on a
        well-formed endpoint reply; on transport failure returns route=other
        with an error note so callers fail safe to their default model."""
        prompt = build_prompt(routes, conversation)
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 64,
        }).encode()
        req = urllib.request.Request(self.endpoint, data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read())
            text = body["choices"][0]["message"]["content"]
        except Exception as e:
            return {"route": "other", "raw": None, "error": f"{type(e).__name__}: {e}"}
        valid = {r["name"] for r in routes} | {"other"}
        return {"route": parse_route(text, valid), "raw": text}
