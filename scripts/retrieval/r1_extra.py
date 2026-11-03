"""R1 extras on the legislation gold set: TF-IDF baseline, chunk-to-window dense, cross-encoder reranking.
Usage: python r1_extra.py GOLD.jsonl --out results_extra.json
Configs: tfidf; chunk128:<small model> (article score = best chunk); bm25>rerank; bge-m3>rerank (rerank top 30).

Input: a gold JSONL (qid, q, relevant article ids, type, ...) plus the legislation records that
evaluate.py exposes as SRC. Output: --out JSON with per-question scores for every config, and a
markdown table (R@5, R@10, MRR; known_item questions left out of the means) on stdout.
Needs a GPU only if one is visible; it is capped to 60% of VRAM because the GPU is shared."""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import SRC, tok, art, score
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder
from sklearn.feature_extraction.text import TfidfVectorizer

SMALL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RERANK = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold")
    ap.add_argument("--out", required=True)
    ap.add_argument("--win", type=int, default=110, help="tokens per chunk (model window 128 minus special tokens)")
    ap.add_argument("--stride", type=int, default=90)
    ap.add_argument("--top", type=int, default=30)
    a = ap.parse_args()

    # Cap VRAM because the GPU is shared; torch is optional (CPU runs work without it).
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(0.6)
    except ImportError:
        pass

    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    ids = [art(r["id"]) for r in recs]
    texts = [r["text"] for r in recs]
    gold = [json.loads(l) for l in open(a.gold, encoding="utf-8")]
    # Drop questions whose relevant articles are not in the corpus.
    gold = [g for g in gold if all(r in set(ids) for r in g["relevant"])]

    # Several records can map to one article id: turn record indices into a de-duplicated article ranking.
    uniq = lambda idx: list(dict.fromkeys(ids[i] for i in idx))
    text_of = {}
    for i, t in zip(ids, texts):
        text_of.setdefault(i, t)

    # Lexical baselines: BM25 and TF-IDF over the whole article text.
    bm = BM25Okapi([tok(t) for t in texts])
    bm_rank = lambda q: uniq(np.argsort(-bm.get_scores(tok(q)))[:300])

    tf = TfidfVectorizer(tokenizer=tok, token_pattern=None, sublinear_tf=True)
    X = tf.fit_transform(texts)
    tf_rank = lambda q: uniq(np.argsort(-(X @ tf.transform([q]).T).toarray().ravel())[:300])

    # Chunked dense: the small model only reads 128 tokens, so cut each article into
    # 110-token windows (128 minus special tokens) with stride 90, i.e. 20 tokens of overlap.
    # Offsets map token spans back to the original text so each chunk is a real substring.
    st = SentenceTransformer(SMALL)
    tk = st.tokenizer
    cid, ctext = [], []
    for k, t in enumerate(texts):
        enc = tk(t, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
        starts = list(range(0, max(1, len(enc) - a.win + a.stride), a.stride)) or [0]
        for s0 in starts:
            seg = enc[s0:s0 + a.win]
            if not seg:
                continue
            cid.append(k)
            ctext.append(t[seg[0][0]:seg[-1][1]])
    cemb = st.encode(ctext, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
    cid = np.array(cid)
    print(f"{len(texts)} articles -> {len(cid)} chunks of <= {a.win} tokens")

    def chunk_rank(q):
        # An article scores as its best-matching chunk.
        s = cemb @ st.encode([q], normalize_embeddings=True)[0]
        best = np.full(len(texts), -1.0)
        np.maximum.at(best, cid, s)
        return uniq(np.argsort(-best)[:300])

    # Whole-article dense with bge-m3, truncated at 512 tokens.
    bge = SentenceTransformer("BAAI/bge-m3")
    bge.max_seq_length = 512
    bemb = bge.encode(texts, normalize_embeddings=True, batch_size=16, show_progress_bar=False)
    bge_rank = lambda q: uniq(np.argsort(-(bemb @ bge.encode([q], normalize_embeddings=True)[0]))[:300])

    # Rerank only the first stage's top --top (30) with the cross-encoder; the tail keeps its order.
    ce = CrossEncoder(RERANK, max_length=512)

    def rerank(q, ranked):
        top = ranked[:a.top]
        sc = ce.predict([(q, text_of[i]) for i in top], show_progress_bar=False)
        return [top[j] for j in np.argsort(-sc)] + ranked[a.top:]

    configs = {
        "bm25": bm_rank,
        "tfidf": tf_rank,
        "chunk128:multilingual-L12": chunk_rank,
        "dense:bge-m3@512": bge_rank,
        "bm25>rerank": lambda q: rerank(q, bm_rank(q)),
        "bge-m3>rerank": lambda q: rerank(q, bge_rank(q)),
    }
    res = {n: [] for n in configs}
    for name, fn in configs.items():
        for g in gold:
            res[name].append({
                **{k: g[k] for k in ("qid", "type", "style", "source", "tenant")},
                **score(fn(g["q"]), set(g["relevant"]), g["type"]),
            })
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False))

    # Summary table; known_item questions are excluded from the means.
    print("| config | n | R@5 | R@10 | MRR |\n|---|---|---|---|---|")
    for name, rows in res.items():
        rows = [r for r in rows if r["type"] != "known_item"]
        print(f"| {name} | {len(rows)} | " + " | ".join(f"{np.mean([r[k] for r in rows]):.3f}" for k in ("r5", "r10", "mrr")) + " |")

if __name__ == "__main__":
    main()
