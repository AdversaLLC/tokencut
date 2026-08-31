"""tokencut.route — cost-aware model routing (Stage 1 of Moslem et al. 2026,
"Cluster, Route, Escalate", arXiv:2606.27457).

Implements the paper's exact math, stdlib-only:
  Score(m, c)   = Error(m, c) + lambda * Cost_norm(m)          (Eq. 1)
  Cost_norm(m)  = (cost - cost_min) / (cost_max - cost_min)    (Eq. 2)
  lambda_c      = Error(fast, c) - Error(strong, c)   [K=2]    (Eq. 3)
  Pareto prune  : drop models dominated on cost AND every cluster's error.

Intended use in workspace.py: define your pool (local llama.cpp models +
Claude), measure per-cluster error rates once from task-correctness labels,
then route() each query's cluster. Embeddings/k-means for cluster assignment
are left to your local endpoint — this module takes cluster ids and gives
routing decisions. Verified against the paper's published AIME tables.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Model:
    name: str
    cost: float                      # TPOT ms, $/Mtok — any consistent unit
    error: dict[str, float]          # cluster_id -> empirical error rate
    cost_norm: float = field(default=0.0)


class Router:
    def __init__(self, models: list[Model]):
        if len(models) < 2:
            raise ValueError("need >= 2 models")
        self.models = self._pareto_prune(models)
        lo = min(m.cost for m in self.models)
        hi = max(m.cost for m in self.models)
        for m in self.models:
            m.cost_norm = 0.0 if hi == lo else (m.cost - lo) / (hi - lo)

    @staticmethod
    def _pareto_prune(models: list[Model]) -> list[Model]:
        keep = []
        for m in models:
            dominated = any(
                o is not m
                and o.cost <= m.cost
                and all(o.error.get(c, 1) <= e for c, e in m.error.items())
                and (o.cost < m.cost or any(o.error.get(c, 1) < e for c, e in m.error.items()))
                for o in models
            )
            if not dominated:
                keep.append(m)
        return keep

    def score(self, m: Model, cluster: str, lam: float) -> float:
        return m.error.get(cluster, 1.0) + lam * m.cost_norm       # Eq. 1

    def route(self, cluster: str, lam: float) -> Model:
        # ties break toward the cheaper model (paper section 4.1)
        return min(self.models, key=lambda m: (self.score(m, cluster, lam), m.cost))

    def crossover(self, cluster: str) -> float:
        """Closed-form lambda where the assignment flips (K=2 only, Eq. 3)."""
        if len(self.models) != 2:
            raise ValueError("closed form requires exactly 2 models")
        fast = min(self.models, key=lambda m: m.cost)
        strong = max(self.models, key=lambda m: m.cost)
        return fast.error.get(cluster, 1.0) - strong.error.get(cluster, 1.0)

    def routing_table(self, lam: float) -> dict[str, str]:
        clusters = sorted({c for m in self.models for c in m.error})
        return {c: self.route(c, lam).name for c in clusters}

    def select_lambda(self, budget: float, cluster_weights: dict[str, float],
                      grid: int = 400) -> float:
        """lambda* = max-accuracy lambda whose expected cost <= budget (Eq. 4).
        cluster_weights: fraction of traffic per cluster (sums to 1)."""
        best_lam, best_acc = 0.0, -1.0
        hi = max(0.001, max(m.error.get(c, 1) for m in self.models for c in m.error) + 0.01)
        for i in range(grid + 1):
            lam = hi * i / grid
            cost = acc = 0.0
            for c, w in cluster_weights.items():
                m = self.route(c, lam)
                cost += w * m.cost
                acc += w * (1 - m.error.get(c, 1.0))
            if cost <= budget and acc > best_acc:
                best_acc, best_lam = acc, lam
        return round(best_lam, 4)


def _selftest() -> list[str]:
    """Verify against the paper's AIME tables (Table 1 errors -> Fig 2 / Table 2)."""
    v = Model("V", cost=9.15, error={"C0": 0.130, "C1": 0.083, "C2": 0.182})
    q = Model("Q3-30B", cost=24.7, error={"C0": 0.063, "C1": 0.031, "C2": 0.083})
    r = Router([v, q])
    out = []
    # Eq.3 crossovers: paper reports 0.067 / 0.052 / 0.099
    for c, want in [("C0", 0.067), ("C1", 0.052), ("C2", 0.099)]:
        got = round(r.crossover(c), 3)
        out.append(f"crossover {c}: got {got}, paper {want} -> {'OK' if got == want else 'FAIL'}")
    # Table 2: lambda=0.06 routes C1 to V, C0/C2 to Q3-30B
    t = r.routing_table(0.06)
    ok = t == {"C0": "Q3-30B", "C1": "V", "C2": "Q3-30B"}
    out.append(f"lambda=0.06 table: {t} -> {'OK' if ok else 'FAIL'}")
    # lambda=0.10: all V (region R4)
    t2 = r.routing_table(0.10)
    ok2 = set(t2.values()) == {"V"}
    out.append(f"lambda=0.10 table: {t2} -> {'OK' if ok2 else 'FAIL'}")
    return out


if __name__ == "__main__":
    print("\n".join(_selftest()))
