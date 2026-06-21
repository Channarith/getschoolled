"""Foresight - a portable multimodal prediction/inference engine.

Reference (CPU/numpy) implementation of the Foresight architecture: multimodal
fusion -> transformer encode + pooled state -> finite query-type router ->
attention over a "liked pattern" library -> parallel multi-head outputs +
a relational graph head -> probability calibration. Designed as a reusable,
backend-swappable engine (a CUDA/CuPy or torch backend can replace numpy without
changing call sites) and to run many inferences concurrently.

Math implemented (verbatim to the Foresight spec):
  Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V
  H = Encoder(X) in R^{T x d},  F = Pool(H) in R^d
  pi(c|F) = softmax(W_route^T F + b_route),  F_tilde = sum_c pi(c|F) A_c F
  K_P = P W_P,  V_P = P U_P
  Q_k = W_k^Q F,  alpha_k = softmax(Q_k K_P^T / sqrt(d)),  G_k = sum_j alpha_{k,j} V_P[j]
  heads: softmax / sigmoid / count / ranking, and a relational graph head
  theta_ij = u_i^T W_g u_j,  w_ij = sigmoid(theta_ij)

Pure/deterministic given a seed; this is the patentable engine, kept dependency-
light (numpy only) so it can be ported and re-used across products.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

FORESIGHT_VERSION = "1.0"


# --------------------------------------------------------------------------- #
# Math primitives
# --------------------------------------------------------------------------- #
def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / np.sum(e, axis=axis, keepdims=True)


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def scaled_dot_product_attention(
    Q: np.ndarray, K: np.ndarray, V: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V. Returns (output, weights)."""
    dk = Q.shape[-1]
    scores = (Q @ np.swapaxes(K, -1, -2)) / np.sqrt(dk)
    weights = softmax(scores, axis=-1)
    return weights @ V, weights


def pool(H: np.ndarray, mode: str = "mean", attn_query: Optional[np.ndarray] = None) -> np.ndarray:
    """Pool H in R^{T x d} -> F in R^d (CLS, mean, or attention pooling)."""
    if mode == "cls":
        return H[0]
    if mode == "attention" and attn_query is not None:
        a = softmax(H @ attn_query)            # (T,)
        return a @ H
    return H.mean(axis=0)


def multimodal_fuse(modalities: Dict[str, np.ndarray]) -> np.ndarray:
    """Concatenate per-modality token matrices (each T_m x d) into X in R^{T x d}."""
    parts = [m for m in modalities.values() if m is not None and len(m)]
    if not parts:
        raise ValueError("no modality tokens provided")
    return np.concatenate(parts, axis=0)


# --------------------------------------------------------------------------- #
# Weights (seeded, so inference is deterministic and reproducible)
# --------------------------------------------------------------------------- #
def _xavier(rng: np.random.Generator, shape: Tuple[int, ...]) -> np.ndarray:
    fan = shape[0] + (shape[1] if len(shape) > 1 else shape[0])
    return rng.normal(0.0, np.sqrt(2.0 / fan), size=shape)


# --------------------------------------------------------------------------- #
# Heads
# --------------------------------------------------------------------------- #
@dataclass
class HeadResult:
    name: str
    kind: str
    probs: Optional[np.ndarray] = None     # softmax / count distribution
    value: Optional[float] = None          # scalar probability (sigmoid)
    topk: Optional[List[int]] = None       # ranking indices
    attention: Optional[np.ndarray] = None  # pattern attention alpha_k (explainability)


class _HeadBase:
    kind = "base"

    def __init__(self, name: str, d: int, rng: np.random.Generator) -> None:
        self.name = name
        self.d = d
        self.Wq = _xavier(rng, (d, d))     # W_k^Q for the grouped summary


class ClassificationHead(_HeadBase):
    kind = "classification"

    def __init__(self, name, d, rng, num_classes: int, temperature: float = 1.0):
        super().__init__(name, d, rng)
        self.W = _xavier(rng, (num_classes, 2 * d))
        self.b = np.zeros(num_classes)
        self.temperature = temperature

    def compute(self, F, Gk, alpha) -> HeadResult:
        z = (self.W @ np.concatenate([F, Gk]) + self.b) / self.temperature
        return HeadResult(self.name, self.kind, probs=softmax(z), attention=alpha)


class ProbabilityHead(_HeadBase):
    kind = "probability"

    def __init__(self, name, d, rng):
        super().__init__(name, d, rng)
        self.w = _xavier(rng, (2 * d,))
        self.b = 0.0

    def compute(self, F, Gk, alpha) -> HeadResult:
        p = float(sigmoid(self.w @ np.concatenate([F, Gk]) + self.b))
        return HeadResult(self.name, self.kind, value=p, attention=alpha)


class CountHead(ClassificationHead):
    kind = "count"

    def __init__(self, name, d, rng, n_max: int):
        super().__init__(name, d, rng, num_classes=n_max)


class RankingHead(_HeadBase):
    """Score external candidate vectors (e.g. course embeddings); return top-m."""
    kind = "ranking"

    def __init__(self, name, d, rng, top_m: int = 5):
        super().__init__(name, d, rng)
        self.Wh = _xavier(rng, (d, 2 * d))
        self.top_m = top_m

    def compute_candidates(self, F, Gk, candidates: np.ndarray, alpha) -> HeadResult:
        query = self.Wh @ np.concatenate([F, Gk])      # (d,)
        scores = candidates @ query                    # (n,)
        order = list(np.argsort(-scores)[: self.top_m])
        return HeadResult(self.name, self.kind, probs=softmax(scores),
                          topk=[int(i) for i in order], attention=alpha)


class RelationalGraphHead(_HeadBase):
    """Relational AI: predict a graph (top-K nodes + weighted edges) from H, Gk.

    U = relu((H || Gk) Wn);  pick top-K nodes;  theta_ij = u_i^T Wg u_j;  w_ij = sigmoid(theta_ij)
    """
    kind = "graph"

    def __init__(self, name, d, rng, d_g: int = 16, top_k: int = 5):
        super().__init__(name, d, rng)
        self.Wn = _xavier(rng, (d_g, 2 * d))
        self.Wg = _xavier(rng, (d_g, d_g))
        self.top_k = top_k

    def compute_graph(self, H, Gk) -> dict:
        T = H.shape[0]
        feats = np.concatenate([H, np.tile(Gk, (T, 1))], axis=1)   # (T, 2d)
        U = np.maximum(0.0, feats @ self.Wn.T)                     # (T, d_g)
        k = min(self.top_k, T)
        node_idx = list(np.argsort(-np.linalg.norm(U, axis=1))[:k])
        nodes = [int(i) for i in node_idx]
        edges = []
        for i in nodes:
            for j in nodes:
                if i == j:
                    continue
                theta = float(U[i] @ self.Wg @ U[j])
                edges.append({"src": int(i), "dst": int(j), "weight": float(sigmoid(theta))})
        return {"nodes": nodes, "edges": edges}


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
@dataclass
class ForesightConfig:
    d: int = 32
    taxonomy: Sequence[str] = field(default_factory=lambda: ["general"])
    pool_mode: str = "mean"
    seed: int = 7


@dataclass
class ForesightOutput:
    route: Dict[str, float]                 # pi(c|F)
    route_top: str
    heads: Dict[str, HeadResult]
    graph: Optional[dict] = None
    F: Optional[np.ndarray] = None


class ForesightEngine:
    """The portable Foresight inference engine (single forward pass, multi-head)."""

    def __init__(self, config: ForesightConfig) -> None:
        self.config = config
        d = config.d
        rng = np.random.default_rng(config.seed)
        self._rng = rng
        # Encoder (one self-attention block) + pooling query.
        self.Wq = _xavier(rng, (d, d))
        self.Wk = _xavier(rng, (d, d))
        self.Wv = _xavier(rng, (d, d))
        self.Wo = _xavier(rng, (d, d))
        self.pool_query = _xavier(rng, (d,))
        # Query-type router + per-class adapters.
        C = list(config.taxonomy)
        self.taxonomy = C
        self.W_route = _xavier(rng, (len(C), d))
        self.b_route = np.zeros(len(C))
        self.adapters = {c: _xavier(rng, (d, d)) for c in C}
        # Pattern library (set via set_pattern_library); defaults to a small random one.
        self.set_pattern_library(_xavier(rng, (8, d)))
        self.heads: Dict[str, _HeadBase] = {}
        self.graph_head: Optional[RelationalGraphHead] = None

    # --- configuration ---------------------------------------------------- #
    def set_pattern_library(self, P: np.ndarray) -> None:
        """K_P = P W_P, V_P = P U_P (project patterns into model dim)."""
        d = self.config.d
        dp = P.shape[1]
        W_P = _xavier(self._rng, (dp, d))
        U_P = _xavier(self._rng, (dp, d))
        self.K_P = P @ W_P
        self.V_P = P @ U_P

    def add_head(self, head: _HeadBase) -> "ForesightEngine":
        self.heads[head.name] = head
        return self

    def set_graph_head(self, head: RelationalGraphHead) -> "ForesightEngine":
        self.graph_head = head
        return self

    # --- forward ---------------------------------------------------------- #
    def encode(self, X: np.ndarray) -> np.ndarray:
        ctx, _ = scaled_dot_product_attention(X @ self.Wq, X @ self.Wk, X @ self.Wv)
        return X + ctx @ self.Wo                       # residual; H in R^{T x d}

    def route(self, F: np.ndarray) -> Tuple[Dict[str, float], np.ndarray]:
        pi = softmax(self.W_route @ F + self.b_route)
        return {c: float(p) for c, p in zip(self.taxonomy, pi)}, pi

    def mixture(self, F: np.ndarray, pi: np.ndarray) -> np.ndarray:
        """F_tilde = sum_c pi(c|F) A_c F."""
        return sum(pi[i] * (self.adapters[c] @ F) for i, c in enumerate(self.taxonomy))

    def grouped_summary(self, F: np.ndarray, head: _HeadBase) -> Tuple[np.ndarray, np.ndarray]:
        Qk = head.Wq @ F
        alpha = softmax((Qk @ self.K_P.T) / np.sqrt(self.config.d))
        return alpha @ self.V_P, alpha

    def forward(self, X: np.ndarray, *, candidates: Optional[np.ndarray] = None) -> ForesightOutput:
        H = self.encode(X)
        F = pool(H, self.config.pool_mode, self.pool_query)
        route, pi = self.route(F)
        F_tilde = self.mixture(F, pi)                  # routed, adapter-mixed state
        results: Dict[str, HeadResult] = {}
        for name, head in self.heads.items():
            Gk, alpha = self.grouped_summary(F_tilde, head)
            if isinstance(head, RankingHead):
                if candidates is None:
                    continue
                results[name] = head.compute_candidates(F_tilde, Gk, candidates, alpha)
            else:
                results[name] = head.compute(F_tilde, Gk, alpha)
        graph = None
        if self.graph_head is not None:
            Gk, _ = self.grouped_summary(F_tilde, self.graph_head)
            graph = self.graph_head.compute_graph(H, Gk)
        top = max(route, key=route.get) if route else "general"
        return ForesightOutput(route=route, route_top=top, heads=results, graph=graph, F=F)

    # --- multi-threaded batch inference ----------------------------------- #
    def predict_batch(self, inputs: Sequence[np.ndarray], *, max_workers: int = 4,
                      candidates: Optional[np.ndarray] = None) -> List[ForesightOutput]:
        """Run many inferences concurrently (threaded; numpy releases the GIL for
        the heavy linear algebra). A CUDA backend batches these on-device."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=max_workers) as pool_exec:
            return list(pool_exec.map(lambda X: self.forward(X, candidates=candidates), inputs))
