"""Serving cost per embedding model: dims, encode time per 1k legislation articles (GPU), single-query latency p50/p95 (GPU and CPU),
peak VRAM, raw index size at 735,194 vectors (n*d*4 bytes), and cross-encoder ms per query for top 30.
Usage: python cost_bench.py out.json   (run when nothing else uses the GPU; timings are one machine, one run)

Input: the first 1000 records of legislacao_scraper/data/legislacao.jsonl and a fixed list of 4 Portuguese
questions repeated to 52. Output: the JSON file given as argument (one entry per model, plus the rerank
timing); each model's numbers are also printed as it finishes. VRAM is capped to 30% (shared GPU)."""
import json, statistics, sys, time
import numpy as np, torch
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder

ROOT = Path(__file__).resolve().parents[2]
texts = [json.loads(l)["text"] for l in open(ROOT / "legislacao_scraper/data/legislacao.jsonl", encoding="utf-8")][:1000]
queries = [
    "Em quais hipóteses a empresa pode tratar dados pessoais sem pedir consentimento?",
    "Quais direitos o titular dos dados pode exigir do controlador?",
    "O operador responde pelos danos causados pelo tratamento irregular de dados?",
    "Quando é preciso avisar a autoridade e o titular?",
] * 13
torch.cuda.set_per_process_memory_fraction(0.3)
pct = lambda xs, p: float(np.percentile(xs, p))


def qlat(st, pre=""):
    # Single-query latency in ms (p50, p95): 5 warm-up calls first, then 50 timed one-at-a-time.
    # `pre` is the model's own query prefix.
    for q in queries[:5]:
        st.encode([pre + q])
    ts = []
    for q in queries[:50]:
        t = time.perf_counter()
        st.encode([pre + q], normalize_embeddings=True)
        ts.append((time.perf_counter() - t) * 1000)
    return pct(ts, 50), pct(ts, 95)


# (model, max_seq_length override or None, query prefix). The e5 models expect "query: " in front of queries.
MODELS = [
    ("paraphrase-multilingual-MiniLM-L12-v2", None, ""),
    ("intfloat/multilingual-e5-small", 512, "query: "),
    ("intfloat/multilingual-e5-base", 512, "query: "),
    ("BAAI/bge-m3", 512, ""),
]
out = {"gpu": torch.cuda.get_device_name(0), "n_articles": len(texts), "models": {}}
for name, msl, pre in MODELS:
    full = name if "/" in name else "sentence-transformers/" + name
    st = SentenceTransformer(full, device="cuda")
    if msl:
        st.max_seq_length = msl

    # Small warm-up encode, then time the full 1000-article encode on the GPU.
    torch.cuda.reset_peak_memory_stats()
    st.encode(texts[:32], batch_size=16)
    t = time.perf_counter()
    st.encode(texts, batch_size=16, normalize_embeddings=True)
    enc = time.perf_counter() - t
    g50, g95 = qlat(st, pre)
    peak = torch.cuda.max_memory_allocated() / 2**30
    d = st.get_sentence_embedding_dimension()

    # Same query timing again with the model moved to the CPU.
    st.to("cpu")
    c50, c95 = qlat(st, pre)
    out["models"][name] = dict(
        dims=d,
        max_seq=st.max_seq_length,
        params_M=round(sum(p.numel() for p in st.parameters()) / 1e6),
        encode_s_per_1k_articles_gpu=round(enc, 1),
        query_ms_gpu_p50=round(g50, 1),
        query_ms_gpu_p95=round(g95, 1),
        query_ms_cpu_p50=round(c50, 1),
        query_ms_cpu_p95=round(c95, 1),
        vram_peak_gib=round(peak, 2),
        # Raw float32 index: vectors x dims x 4 bytes, no compression.
        index_gib_at_735194=round(735194 * d * 4 / 2**30, 2),
    )
    del st
    torch.cuda.empty_cache()
    print(name, out["models"][name], flush=True)

# Cross-encoder: time scoring 30 (query, article) pairs, the rerank depth used elsewhere.
ce = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", max_length=512, device="cuda")
pairs = [(queries[0], t) for t in texts[:30]]
ce.predict(pairs)
ts = []
for _ in range(20):
    t = time.perf_counter()
    ce.predict(pairs, show_progress_bar=False)
    ts.append((time.perf_counter() - t) * 1000)
out["rerank_top30_ms_gpu_p50"] = round(pct(ts, 50), 1)
print("rerank top30 ms p50", out["rerank_top30_ms_gpu_p50"])
json.dump(out, open(sys.argv[1], "w"), indent=1)
