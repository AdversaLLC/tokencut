"""tokencut.embed — local embeddings + stdlib k-means.

Completes route.py's Stage 1 end-to-end (Cluster -> Route): embed queries via
a LOCAL OpenAI-compatible /embeddings endpoint (llama.cpp: `llama-server -m
<model> --embedding --port 8089`), cluster with deterministic k-means, then
hand cluster ids to route.Router. No cloud, no API key, stdlib-only client.

Model files are NOT bundled — see models/embeddings/README section in
models/README.md. Recommended tiny option: minishlab/potion-base-8M via a
Model2Vec-capable server, or any GGUF embedding model under llama.cpp.
"""
from __future__ import annotations
import json, math, random, urllib.request


class EmbeddingClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8089", model: str = "local"):
        self.url = base_url.rstrip("/") + "/v1/embeddings"
        self.model = model

    def embed(self, texts: list[str], timeout: int = 30) -> list[list[float]]:
        req = urllib.request.Request(
            self.url,
            data=json.dumps({"model": self.model, "input": texts}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        out = sorted(data["data"], key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in out]


def _dist2(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def kmeans(vecs: list[list[float]], k: int, iters: int = 50, seed: int = 0
           ) -> tuple[list[list[float]], list[int]]:
    """Deterministic k-means (k-means++ init). Returns (centroids, labels)."""
    rng = random.Random(seed)
    cents = [list(vecs[rng.randrange(len(vecs))])]
    while len(cents) < k:                       # k-means++ seeding
        d2 = [min(_dist2(v, c) for c in cents) for v in vecs]
        total = sum(d2) or 1.0
        r, acc = rng.random() * total, 0.0
        for v, d in zip(vecs, d2):
            acc += d
            if acc >= r:
                cents.append(list(v)); break
    labels = [0] * len(vecs)
    for _ in range(iters):
        new_labels = [min(range(k), key=lambda j: _dist2(v, cents[j])) for v in vecs]
        if new_labels == labels and _ != 0:
            break
        labels = new_labels
        for j in range(k):
            members = [v for v, l in zip(vecs, labels) if l == j]
            if members:
                cents[j] = [sum(col) / len(members) for col in zip(*members)]
    return cents, labels


def assign(vec: list[float], centroids: list[list[float]]) -> int:
    return min(range(len(centroids)), key=lambda j: _dist2(vec, centroids[j]))


def silhouette_k(vecs: list[list[float]], k_range=range(2, 8), seed: int = 0) -> int:
    """Pick k by mean silhouette (paper §4.2). O(n^2) — fine for query corpora."""
    best_k, best_s = 2, -2.0
    for k in k_range:
        if k >= len(vecs):
            break
        _, labels = kmeans(vecs, k, seed=seed)
        s_sum = 0.0
        for i, v in enumerate(vecs):
            same = [w for w, l in zip(vecs, labels) if l == labels[i]]
            a = sum(math.sqrt(_dist2(v, w)) for w in same) / max(len(same) - 1, 1)
            b = min(
                (sum(math.sqrt(_dist2(v, w)) for w, l in zip(vecs, labels) if l == j)
                 / max(labels.count(j), 1))
                for j in set(labels) if j != labels[i]
            ) if len(set(labels)) > 1 else a
            s_sum += 0.0 if max(a, b) == 0 else (b - a) / max(a, b)
        s = s_sum / len(vecs)
        if s > best_s:
            best_s, best_k = s, k
    return best_k
