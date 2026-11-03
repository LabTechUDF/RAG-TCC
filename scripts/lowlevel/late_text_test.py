"""Late-text known-item test: can a vector built from the first 256 tokens find a document from a sentence that sits late in it?
Usage: python late_text_test.py <metadata.parquet> [n_per_kind=750] [seed=0] [out.json]
Pool = sampled TJDFT + STJ documents (>= 1,200 model tokens). For each, one query from the early part (tokens 40-200) and one
from the late part (>= 60% of the document). Systems: all-MiniLM-L6-v2 on the whole document (what the live index does, 256-token
limit), the same model chunked to 240-token windows (best chunk), BM25 on the whole text. Query = a verbatim 12-25 word fragment,
so this is an easy test for lexical systems and a pure visibility test for the vector: it measures what the vector can see, not user realism.

Input: the index metadata parquet (id, text). Output: a markdown table on stdout (Success@1, Success@10, MRR
per kind, query part and system) and the same numbers plus per-query ranks in the JSON file."""
import bisect, json, random, re, sys
from collections import defaultdict
import numpy as np
import pyarrow.parquet as pq
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

path = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 750
rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 0)
OUT = sys.argv[4] if len(sys.argv) > 4 else "late_text.json"
kind = lambda i: "tjdft" if i.startswith("tjdft:") else "stj" if not i.startswith("lei:") else "lei"

# Same model as the live index (all-MiniLM-L6-v2); its tokenizer is also used to cut chunks.
st = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
tk = st.tokenizer

# Cap VRAM because the GPU is shared; torch is optional.
try:
    import torch
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(0.6)
except ImportError:
    pass

# Read the 3.4 GB parquet one row group at a time, id and text only, to keep RAM low.
# Keep only long documents (> 4500 characters) and subsample while reading: the pool is
# drawn at random (TJDFT kept with probability 0.5, STJ with 0.004), lei excluded.
f = pq.ParquetFile(path)
pool = defaultdict(list)
for g in range(f.metadata.num_row_groups):
    t = f.read_row_group(g, columns=["id", "text"]).to_pydict()
    for i, x in zip(t["id"], t["text"]):
        k = kind(i)
        if k != "lei" and x and len(x) > 4500 and rng.random() < (0.5 if k == "tjdft" else 0.004):
            pool[k].append((i, x))

# At most N documents per source kind.
docs = []
for k, rows in pool.items():
    docs += rng.sample(rows, min(len(rows), N))
print({k: len(v) for k, v in pool.items()}, "->", len(docs), "docs")


def sentences(text):
    # Candidate query sentences: 12 to 40 words, split on sentence-ending '.' or ';'.
    return [s.strip() for s in re.split(r"(?<=[.;])\s+", text) if 12 <= len(s.split()) <= 40]

# One early query (tokens 40-200, inside what the 256-token vector sees) and one late query
# (>= 60% into the document) per document; documents lacking either are skipped.
queries = []
for d, (i, x) in enumerate(docs):
    off = tk(x, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
    n_tok = len(off)
    if n_tok < 1200:
        continue
    starts = [o[0] for o in off]
    pos = lambda c: bisect.bisect_left(starts, c)  # token index of character offset c
    cand = [(m.start(), m.group()) for s in sentences(x) for m in [re.search(re.escape(s), x)] if m]
    early = [s for c, s in cand if 40 <= pos(c) <= 200]
    late = [s for c, s in cand if pos(c) >= 0.6 * n_tok]
    if early and late:
        # Verbatim fragment of at most 25 words.
        trim = lambda s: " ".join(s.split()[:25])
        queries.append((d, "early", trim(rng.choice(early))))
        queries.append((d, "late", trim(rng.choice(late))))
print(len(queries) // 2, "docs with both an early and a late sentence")


texts = [x for _, x in docs]

# System 1: one vector per whole document, as the live index does (the model reads only the first 256 tokens).
whole = st.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)  # truncated to 256 by the model

# System 2: the same model on 240-token windows every 200 tokens (40 tokens of overlap);
# a document scores as its best chunk. cd maps each chunk back to its document.
cd, ct = [], []
for d, x in enumerate(texts):
    off = tk(x, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
    for s0 in range(0, len(off), 200):
        seg = off[s0:s0 + 240]
        if seg:
            cd.append(d)
            ct.append(x[seg[0][0]:seg[-1][1]])
cemb = st.encode(ct, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
cd = np.array(cd)
print(len(ct), "chunks")

# System 3: BM25 on the whole text with a plain lowercase word tokenizer.
tokz = lambda s: re.findall(r"\w+", s.lower())
bm = BM25Okapi([tokz(t) for t in texts])


def rank_of(scores, d):
    # 1-based rank of the right document: number of documents scoring strictly higher, plus one.
    return int((scores > scores[d]).sum()) + 1


rows = []
for d, part, q in queries:
    qv = st.encode([q], normalize_embeddings=True)[0]
    s_whole = whole @ qv
    sc = cemb @ qv
    s_chunk = np.full(len(texts), -1.0)
    np.maximum.at(s_chunk, cd, sc)
    rows.append({
        "kind": kind(docs[d][0]),
        "part": part,
        "whole256": rank_of(s_whole, d),
        "chunked": rank_of(s_chunk, d),
        "bm25": rank_of(bm.get_scores(tokz(q)), d),
    })

# Summary per kind (and all together), query part and system.
out = {}
print("| kind | query from | n | system | Success@1 | Success@10 | MRR |\n|---|---|---|---|---|---|---|")
for k in ("tjdft", "stj", "all"):
    for part in ("early", "late"):
        rr = [r for r in rows if r["part"] == part and (k == "all" or r["kind"] == k)]
        if not rr:
            continue
        for sysn in ("whole256", "chunked", "bm25"):
            ranks = np.array([r[sysn] for r in rr])
            res = dict(
                n=len(rr),
                s1=float((ranks == 1).mean()),
                s10=float((ranks <= 10).mean()),
                mrr=float((1 / ranks).mean()),
            )
            out[f"{k}/{part}/{sysn}"] = res
            print(f"| {k} | {part} | {len(rr)} | {sysn} | {res['s1']:.3f} | {res['s10']:.3f} | {res['mrr']:.3f} |")
json.dump({"pool": len(docs), "rows": rows, "summary": out}, open(OUT, "w"))
