"""Evaluate retrieval configs on a frozen gold set (protocol: docs/evaluation/eval-v1-results.md).

Inputs : a gold JSONL (qid, q, relevant, type, style, source, tenant), legislacao.jsonl and the graph edges.jsonl.
Outputs: per-config metrics (--out, default results.json), per-question ranks (<out>_ranks.json) and tables on stdout.

Configs: bm25, dense:<model>, rrf(bm25+dense), dense+graph(1-hop), rrf+graph.
Scoring: article-level (strip -pN, dedupe in rank order). known_item rows report MRR and Success@10 only.
Cuts: overall, style, type, source, tenant. Never edit labels after seeing results.
Usage: python evaluate.py GOLD.jsonl [--models M ...] [--out results.json]
"""
import argparse, collections, json, math, re
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "legislacao_scraper/data/legislacao.jsonl"
EDGES = ROOT / "docs/evaluation/graph/edges.jsonl"
tok = lambda s: re.findall(r"\w+", s.lower())
# Article id: a long article is stored in parts (-p1, -p2, ...); scoring is article-level, so parts collapse to one id.
art = lambda i: re.sub(r"-p\d+$", "", i)


def rrf(rankings, k=60):
    # Reciprocal rank fusion; k=60 is the usual constant from the original RRF paper.
    sc = {}
    for r in rankings:
        for p, i in enumerate(r):
            sc[i] = sc.get(i, 0) + 1 / (k + p + 1)
    return sorted(sc, key=sc.get, reverse=True)


def score(ranked, rel, typ):
    mrr = next((1 / (p + 1) for p, i in enumerate(ranked) if i in rel), 0.0)
    s10 = float(any(i in rel for i in ranked[:10]))
    if typ == "known_item":
        return {"mrr": mrr, "s10": s10}
    out = {"mrr": mrr, "s10": s10}
    for k in (5, 10):
        hit = sum(i in rel for i in ranked[:k])
        out[f"p{k}"] = hit / k
        out[f"r{k}"] = hit / len(rel)
    dcg = sum(1 / math.log2(p + 2) for p, i in enumerate(ranked[:10]) if i in rel)
    out["ndcg10"] = dcg / sum(1 / math.log2(p + 2) for p in range(min(len(rel), 10)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold")
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--models", nargs="+", default=["sentence-transformers/all-MiniLM-L6-v2",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"])
    ap.add_argument("--max-seq", type=int, default=None, help="override the model's max_seq_length (default: the model's own)")
    a = ap.parse_args()
    try:  # shared GPU: keep to 60% of VRAM (exhausting it crashed the desktop once)
        import torch
        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(0.6)
    except ImportError:
        pass

    # Corpus: one record per article part; ids are collapsed to article level.
    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    ids = [art(r["id"]) for r in recs]
    texts = [r["text"] for r in recs]
    gold = [json.loads(l) for l in open(a.gold, encoding="utf-8")]
    gold = [g for g in gold if all(r in set(ids) for r in g["relevant"])]  # tjdft:* labels need the TJDFT corpus; skipped, not scored as 0

    # Graph edges are used in both directions as a neighbour lookup.
    nbr = collections.defaultdict(list)
    for l in open(EDGES):
        e = json.loads(l)
        nbr[e["src"]].append(e["dst"])
        nbr[e["dst"]].append(e["src"])

    bm = BM25Okapi([tok(t) for t in texts])
    # Dedupe in rank order after collapsing parts to articles; only the top 300 are kept.
    uniq = lambda idx: list(dict.fromkeys(ids[i] for i in idx))
    bm_rank = lambda q: uniq(np.argsort(-bm.get_scores(tok(q)))[:300])

    def graph(rank, seeds=3, keep=5, add=5):
        # keep the top `keep` hits, then splice in up to `add` 1-hop neighbours of the top `seeds` hits,
        # then the rest. (First version appended neighbours after rank 10, so it could not affect @5/@10.)
        extra = [n for s in rank[:seeds] for n in nbr.get(s, []) if n not in rank[:keep]]
        extra = list(dict.fromkeys(extra))[:add]
        return list(dict.fromkeys(rank[:keep] + extra + rank[keep:]))

    configs = {"bm25": bm_rank}
    for m in a.models:
        short = m.split("/")[-1]
        st = SentenceTransformer(m)
        if a.max_seq:
            st.max_seq_length = a.max_seq
            short += f"@{a.max_seq}"
        qp, dp = ("query: ", "passage: ") if "e5" in m.lower() else ("", "")  # e5 models expect these prefixes
        # Normalized vectors, so the dot product below is the cosine similarity.
        emb = st.encode([dp + t for t in texts], normalize_embeddings=True, batch_size=16, show_progress_bar=False)
        d = lambda q, st=st, emb=emb, qp=qp: uniq(np.argsort(-(emb @ st.encode([qp + q], normalize_embeddings=True)[0]))[:300])
        configs[f"dense:{short}"] = d
        configs[f"rrf:{short}"] = lambda q, d=d: rrf([bm_rank(q), d(q)])
        configs[f"dense+graph:{short}"] = lambda q, d=d: graph(d(q))
        configs[f"rrf+graph:{short}"] = lambda q, d=d: graph(rrf([bm_rank(q), d(q)]))

    res = {}
    ranks = {}  # per config: qid -> {"first_rank": 1-based rank of first relevant (None = absent from top 300), "top5": [...]}
    for name, fn in configs.items():
        res[name] = []
        ranks[name] = {}
        for g in gold:
            ranked = fn(g["q"])
            rel = set(g["relevant"])
            res[name].append({**{k: g[k] for k in ("qid", "type", "style", "source", "tenant")}, **score(ranked, rel, g["type"])})
            ranks[name][g["qid"]] = {"first_rank": next((p + 1 for p, i in enumerate(ranked) if i in rel), None), "top5": ranked[:5]}
    Path(a.out).with_name(Path(a.out).stem + "_ranks.json").write_text(json.dumps(ranks, ensure_ascii=False))
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False))

    def table(title, sel, keys):
        print(f"\n## {title}")
        for name, rows in res.items():
            rows = [r for r in rows if sel(r)]
            if rows:
                print(f"{name:52s} n={len(rows):2d} " + "  ".join(f"{k}={np.mean([r[k] for r in rows if k in r]):.3f}" for k in keys))

    table("overall single+multihop", lambda r: r["type"] != "known_item", ["r5", "p5", "r10", "mrr", "ndcg10"])
    table("known_item", lambda r: r["type"] == "known_item", ["mrr", "s10"])
    for cut, vals in (("style", ("keyword", "paraphrase")), ("type", ("single", "multihop")), ("source", ("author-a", "author-b"))):
        for v in vals:
            table(f"{cut}={v}", lambda r, c=cut, v=v: r[c] == v and r["type"] != "known_item", ["r5", "r10", "mrr"])


if __name__ == "__main__":
    main()
