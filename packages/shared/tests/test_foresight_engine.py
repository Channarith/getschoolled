"""Foresight engine: math primitives + single forward pass + batch inference."""

import numpy as np

from aoep_shared.foresight import (
    ClassificationHead,
    ForesightConfig,
    ForesightEngine,
    ProbabilityHead,
    RankingHead,
    RelationalGraphHead,
    multimodal_fuse,
    pool,
    scaled_dot_product_attention,
    sigmoid,
    softmax,
)


def test_softmax_and_sigmoid():
    p = softmax(np.array([1.0, 2.0, 3.0]))
    assert abs(p.sum() - 1.0) < 1e-9 and np.all(p > 0)
    assert 0 < float(sigmoid(np.array([0.0]))[0]) < 1


def test_attention_shapes_and_weight_rows_sum_to_one():
    rng = np.random.default_rng(0)
    Q, K, V = rng.normal(size=(3, 8)), rng.normal(size=(5, 8)), rng.normal(size=(5, 8))
    out, w = scaled_dot_product_attention(Q, K, V)
    assert out.shape == (3, 8)
    assert np.allclose(w.sum(axis=-1), 1.0)


def test_pool_modes():
    H = np.arange(12.0).reshape(3, 4)
    assert np.allclose(pool(H, "cls"), H[0])
    assert np.allclose(pool(H, "mean"), H.mean(axis=0))
    assert pool(H, "attention", attn_query=np.ones(4)).shape == (4,)


def test_multimodal_fuse_concatenates():
    text = np.zeros((2, 4)); image = np.ones((3, 4))
    X = multimodal_fuse({"text": text, "image": image})
    assert X.shape == (5, 4)


def _engine():
    cfg = ForesightConfig(d=16, taxonomy=["crime", "finance", "medical"], seed=1)
    eng = ForesightEngine(cfg)
    rng = np.random.default_rng(2)
    eng.add_head(ClassificationHead("cause", 16, rng, num_classes=4))
    eng.add_head(ProbabilityHead("money", 16, rng))
    eng.add_head(RankingHead("scenario", 16, rng, top_m=3))
    eng.set_graph_head(RelationalGraphHead("graph", 16, rng, top_k=4))
    return eng


def test_forward_produces_route_heads_and_graph():
    eng = _engine()
    X = np.random.default_rng(3).normal(size=(6, 16))
    cands = np.random.default_rng(4).normal(size=(7, 16))
    out = eng.forward(X, candidates=cands)

    assert abs(sum(out.route.values()) - 1.0) < 1e-9       # router is a distribution
    assert out.route_top in ("crime", "finance", "medical")

    cause = out.heads["cause"]
    assert abs(cause.probs.sum() - 1.0) < 1e-9             # softmax head
    money = out.heads["money"]
    assert 0.0 <= money.value <= 1.0                       # sigmoid head
    scen = out.heads["scenario"]
    assert len(scen.topk) == 3                             # ranking top-m

    assert out.graph and out.graph["nodes"]
    assert all(0.0 <= e["weight"] <= 1.0 for e in out.graph["edges"])  # sigmoid edges
    assert cause.attention is not None and abs(cause.attention.sum() - 1.0) < 1e-9


def test_deterministic_given_seed():
    X = np.random.default_rng(5).normal(size=(4, 16))
    a = _engine().forward(X).route
    b = _engine().forward(X).route
    assert a == b


def test_batch_inference_threaded():
    eng = _engine()
    rng = np.random.default_rng(6)
    inputs = [rng.normal(size=(5, 16)) for _ in range(8)]
    outs = eng.predict_batch(inputs, max_workers=4)
    assert len(outs) == 8
    assert all(abs(sum(o.route.values()) - 1.0) < 1e-9 for o in outs)
