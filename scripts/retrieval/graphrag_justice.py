"""J-R5: GraphRAG on the real citation graph. Protocol (fixed before running): docs/evaluation/PROTOCOL-justice-graphrag.md
Usage: python graphrag_justice.py GOLD.jsonl --out results.json
Two first stages: A = multilingual MiniLM-L12 (128 tokens), B = bge-m3 (512 tokens, fp16 to fit the shared-GPU budget).

Input: a gold JSONL of two-article questions (qid, q, relevant, type, optional split) and the
legislation records and citation edges that evaluate.py exposes (SRC, EDGES).
Output: --out JSON with per-question rows (one per arm) and the graph path behind each added article,
the bge-m3 fp16 article embeddings next to it as <out>_bge-m3_fp16.npy, and a markdown table on stdout.
Needs a GPU, so it is capped to 30% of VRAM (shared GPU)."""
import argparse, collections, json, sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import SRC, EDGES, tok, art, rrf
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

def graphrag(ranked, nbr, seeds=2, add=3):
    # seeds=2 and add=3 were fixed before the run, see docs/evaluation/PROTOCOL-justice-graphrag.md.
    # Seeds = top of the dense list; candidates = their graph neighbours, each remembering which seed
    # brought it (the path shown to the reader).
    S = ranked[:seeds]
    pos = {d: p for p, d in enumerate(ranked)}
    cand = {}
    for s in S:
        for n, w in nbr.get(s, {}).items():
            if n in S:
                continue
            c = cand.setdefault(n, {"adj": 0, "w": 0, "via": []})
            c["adj"] += 1
            c["w"] += w
            c["via"].append(s)

    # Order: most seeds adjacent, then own dense rank, then edge weight (as in the protocol).
    order = sorted(cand, key=lambda n: (-cand[n]["adj"], pos.get(n, 10**6), -cand[n]["w"]))[:add]
    paths = {n: f"{cand[n]['via'][0]} -cites/cited_by- {n}" for n in order}
    return list(dict.fromkeys(S + order + ranked)), paths

def onehop(rank, nbr, seeds=3, keep=5, add=5):
    # Plain 1-hop splice: keep the top 5, add up to 5 neighbours of the top 3, then the rest.
    extra = list(dict.fromkeys(n for s in rank[:seeds] for n in nbr.get(s, {}) if n not in rank[:keep]))[:add]
    return list(dict.fromkeys(rank[:keep] + extra + rank[keep:]))

def metrics(ranked, rel):
    # r5 = share of the relevant articles in the top 5; full = 1 if the whole pair is there.
    top = ranked[:5]
    hit = sum(r in top for r in rel)
    return {
        "r5": hit / len(rel),
        "full": float(hit == len(rel)),
        "mrr": next((1 / (p + 1) for p, i in enumerate(ranked) if i in rel), 0.0),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    torch.cuda.set_per_process_memory_fraction(0.3)

    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    ids = [art(r["id"]) for r in recs]
    texts = [r["text"] for r in recs]
    # Record indices -> de-duplicated article ranking (top 300).
    uniq = lambda idx: list(dict.fromkeys(ids[i] for i in idx))

    # The citation graph is used undirected: each edge is added in both directions, weights summed.
    nbr = collections.defaultdict(dict)
    for l in open(EDGES):
        e = json.loads(l)
        w = e.get("weight", 1)
        nbr[e["src"]][e["dst"]] = nbr[e["src"]].get(e["dst"], 0) + w
        nbr[e["dst"]][e["src"]] = nbr[e["dst"]].get(e["src"], 0) + w

    gold = [json.loads(l) for l in open(a.gold, encoding="utf-8")]
    bm = BM25Okapi([tok(t) for t in texts])
    bm_rank = lambda q: uniq(np.argsort(-bm.get_scores(tok(q)))[:300])

    # First stages for the dense arms. fp16 for bge-m3 keeps it inside the VRAM cap.
    stages = {}
    A = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cuda")
    ea = A.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    stages["L12"] = lambda q: uniq(np.argsort(-(ea @ A.encode([q], normalize_embeddings=True)[0]))[:300])
    # keep A loaded: the query lambda needs it (small model)
    B = SentenceTransformer("BAAI/bge-m3", device="cuda", model_kwargs={"torch_dtype": torch.float16})
    B.max_seq_length = 512
    eb = B.encode(texts, normalize_embeddings=True, batch_size=8, show_progress_bar=False).astype(np.float32)
    np.save(str(Path(a.out).with_suffix("")) + "_bge-m3_fp16.npy", eb)
    stages["bge-m3"] = lambda q: uniq(np.argsort(-(eb @ B.encode([q], normalize_embeddings=True).astype(np.float32)[0]))[:300])

    # Every question runs through every arm: bm25, then per stage dense / RRF with bm25 / 1-hop / GraphRAG.
    rows = []
    paths_log = {}
    for g in gold:
        rel = g["relevant"]
        base = {"qid": g["qid"], "split": g.get("split", g["type"]), "type": g["type"]}
        arms = {"bm25": bm_rank(g["q"])}
        for sname, st in stages.items():
            d = st(g["q"]); arms[f"{sname}:dense"] = d
            arms[f"{sname}:rrf"] = rrf([arms["bm25"], d])
            arms[f"{sname}:1hop"] = onehop(d, nbr)
            arms[f"{sname}:graphrag"], p = graphrag(d, nbr)
            paths_log[f"{g['qid']}/{sname}"] = p
        for arm, ranked in arms.items():
            rows.append({**base, "arm": arm, **metrics(ranked, rel), "top5": ranked[:5]})
    json.dump({"rows": rows, "paths": paths_log}, open(a.out, "w"), ensure_ascii=False)

    # Summary table: dev and held-out are reported separately, as the protocol requires.
    print("| arm | split | n | path recall@5 | full paths | MRR |\n|---|---|---|---|---|---|")
    for arm in dict.fromkeys(r["arm"] for r in rows):
        for sp in ("dev", "heldout", "control"):
            rr = [r for r in rows if r["arm"] == arm and r["split"] == sp]
            if rr:
                print(f"| {arm} | {sp} | {len(rr)} | {np.mean([r['r5'] for r in rr]):.3f} | {int(sum(r['full'] for r in rr))} of {len(rr)} | {np.mean([r['mrr'] for r in rr]):.3f} |")

if __name__ == "__main__":
    main()
