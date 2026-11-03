"""V1/V2: do real indexed chunks exceed the embedding model's max_seq_length?

Reads metadata.parquet one row group at a time (id, text only), samples N rows per
source kind, tokenizes with the model tokenizers (no inference) and with cl100k_base.
Usage: python truncation_check.py <metadata.parquet> [n_per_kind] [seed]

Input: the index metadata parquet (columns id, text). Output: a per-model, per-kind summary
(share over the limit, token and character percentiles, share of the text actually embedded)
printed as JSON and written to truncation_check.json in the current directory.
CPU only: the models are loaded just for their tokenizer and max_seq_length.
"""
import json, random, sys
from collections import defaultdict
import numpy as np
import pyarrow.parquet as pq
import tiktoken
from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer

path = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 0)

MODELS = ["sentence-transformers/all-MiniLM-L6-v2",
          "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"]


def kind(i):
    return "lei" if i.startswith("lei:") else "tjdft" if i.startswith("tjdft:") else "stj(hex id)"

# The parquet is 3.4 GB: read one row group at a time and load only id and text, to keep RAM low.
f = pq.ParquetFile(path)
per_rg = {}
pool = defaultdict(list)
for g in range(f.metadata.num_row_groups):
    t = f.read_row_group(g, columns=["id", "text"]).to_pydict()
    k_idx = defaultdict(list)
    for j, i in enumerate(t["id"]):
        k_idx[kind(i)].append(j)

    # Sample per row group so the pool stays small: lei and tjdft are capped at 400 per group,
    # stj gets its share of N (N / number of groups, plus 5).
    for k, idx in k_idx.items():
        take = rng.sample(idx, min(len(idx), 400 if k != 'stj(hex id)' else N // f.metadata.num_row_groups + 5))
        pool[k] += [(t["id"][j], t["text"][j] or "") for j in take]
    per_rg[g] = {k: len(v) for k, v in k_idx.items()}

# Row counts per kind over the whole file (not just the sample).
tot = defaultdict(int)
for d in per_rg.values():
    for k, v in d.items():
        tot[k] += v
print("rows by kind (all):", dict(tot))


# Both tokenizers on purpose: the model's own tokenizer decides what is truncated;
# cl100k (the OpenAI tokenizer) is the yardstick the chunker in the repo counts with, so the ratio between them is reported.
enc = tiktoken.get_encoding("cl100k_base")
out = {"rows_by_kind": dict(tot), "models": {}}
for m in MODELS:
    st = SentenceTransformer(m, device="cpu")
    tok = st.tokenizer
    msl = st.max_seq_length
    res = {"max_seq_length": msl, "kinds": {}}
    for k, rows in pool.items():
        rows = rng.sample(rows, min(len(rows), N))
        # mt = model tokens (with special tokens, as the model would see them), ct = cl100k tokens, ch = characters.
        mt = np.array([len(tok(x[1], add_special_tokens=True, truncation=False)["input_ids"]) for x in rows])
        ct = np.array([len(enc.encode(x[1])) for x in rows])
        ch = np.array([len(x[1]) for x in rows])
        # Fraction of each text that fits in the model's window, averaged over the sample.
        kept = np.minimum(mt, msl) / np.maximum(mt, 1)
        res["kinds"][k] = dict(
            n=len(rows),
            pct_over_limit=round(float((mt > msl).mean() * 100), 1),
            model_tok_p50=int(np.percentile(mt, 50)), model_tok_p95=int(np.percentile(mt, 95)),
            cl100k_p50=int(np.percentile(ct, 50)), cl100k_p95=int(np.percentile(ct, 95)),
            chars_p50=int(np.percentile(ch, 50)), chars_p95=int(np.percentile(ch, 95)),
            mean_pct_of_text_embedded=round(float(kept.mean() * 100), 1),
            model_per_cl100k=round(float(mt.sum() / max(ct.sum(), 1)), 2),
            chars_per_cl100k=round(float(ch.sum() / max(ct.sum(), 1)), 2),
        )
    out["models"][m] = res
print(json.dumps(out, indent=1))
json.dump(out, open("truncation_check.json", "w"), indent=1)
