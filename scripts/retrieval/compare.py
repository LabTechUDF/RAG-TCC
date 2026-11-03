"""Compare BM25, dense and RRF retrieval over legislacao.jsonl against a gold set.

Gold set: JSONL, one object per line: {"q": str, "relevant": [article ids, e.g. "lei:lgpd:art-7"]}.
Inputs : the gold JSONL and legislacao.jsonl. Output: a table on stdout, nothing is written to disk.
Prints Recall@K, Precision@K, MRR per method and per embedding model.
Usage: python compare.py GOLD.jsonl [--models M1 M2] [--k 5]
"""
import argparse, json, re
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

SRC = Path(__file__).resolve().parents[2] / "legislacao_scraper/data/legislacao.jsonl"
tok = lambda s: re.findall(r"\w+", s.lower())


def rrf(rankings, k=60):
    # Reciprocal rank fusion; k=60 is the usual constant from the original RRF paper.
    score = {}
    for r in rankings:
        for pos, i in enumerate(r):
            score[i] = score.get(i, 0) + 1 / (k + pos + 1)
    return sorted(score, key=score.get, reverse=True)


def metrics(ranked_ids, relevant, k):
    top = ranked_ids[:k]
    hit = [i for i in top if i in relevant]
    mrr = next((1 / (p + 1) for p, i in enumerate(ranked_ids) if i in relevant), 0.0)
    return len(hit) / len(relevant), len(hit) / k, mrr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold")
    ap.add_argument("--models", nargs="+", default=["sentence-transformers/all-MiniLM-L6-v2",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"])
    ap.add_argument("--k", type=int, default=5)
    a = ap.parse_args()

    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    # Strip the -pN suffix so a split article maps to a single article id.
    ids = [re.sub(r"-p\d+$", "", r["id"]) for r in recs]
    texts = [r["text"] for r in recs]
    gold = [json.loads(l) for l in open(a.gold, encoding="utf-8")]

    bm = BM25Okapi([tok(t) for t in texts])
    rank_bm = lambda q: list(np.argsort(-bm.get_scores(tok(q))))
    rows = {}

    def add(name, fn):
        m = np.array([metrics(list(dict.fromkeys(ids[i] for i in fn(g["q"])[:200])), set(g["relevant"]), a.k) for g in gold])  # article-level: parts collapsed
        rows[name] = m.mean(axis=0)

    add("bm25", rank_bm)
    for model in a.models:
        st = SentenceTransformer(model)
        # Normalized vectors, so the dot product below is the cosine similarity.
        emb = st.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        dense = lambda q, st=st, emb=emb: list(np.argsort(-(emb @ st.encode([q], normalize_embeddings=True)[0])))
        short = model.split("/")[-1]
        add(f"dense:{short}", dense)
        add(f"rrf(bm25+{short})", lambda q, d=dense: rrf([rank_bm(q)[:200], d(q)[:200]]))

    print(f"n_questions={len(gold)} corpus={len(recs)} k={a.k}")
    print(f"{'method':58s} Recall@k  Prec@k   MRR")
    for n, (r, p, m) in rows.items():
        print(f"{n:58s} {r:7.3f}  {p:7.3f}  {m:6.3f}")


if __name__ == "__main__":
    main()
