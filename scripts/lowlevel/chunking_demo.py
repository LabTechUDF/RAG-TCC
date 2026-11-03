"""Chunking demo on one real document, three ways. Run from the repo root:
  python scripts/lowlevel/chunking_demo.py --id tjdft:9c171e08-2895-485e-a524-a92242164520 [--version v1|v2|repo|all]
  python scripts/lowlevel/chunking_demo.py --file some.txt --version v2 --show 3
v1   = what the live index does: ONE vector for the whole document, the model silently reads only its first max_seq_length tokens.
v2   = recursive split (paragraph, line, sentence, word) packed to the model's window in MODEL tokens, with the first line repeated as a header on every chunk after the first.
repo = DBVECTOR/src/chunking.py DocumentChunker (600 target / 800 max tokens; chunks are sized by a 4-characters-per-token estimate, 100 overlap). Exists, NOT used by the index build.
Everything is measured with the model's own tokenizer, so "truncated" means what the embedding model would really cut.

Input: a document id looked up in the index metadata parquet, or a text file. Output: a markdown table on stdout
(chunk counts, model tokens per chunk, truncation, share of the text read) and the first --show v2 chunks.
CPU only (the model is loaded on the CPU just for its tokenizer)."""
import argparse, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "DBVECTOR"))
from src.chunking import DocumentChunker
from src.rag_schemas import DocumentoParaChunking
from sentence_transformers import SentenceTransformer

ap = argparse.ArgumentParser()
ap.add_argument("--id")
ap.add_argument("--file")
ap.add_argument("--version", default="all", choices=["v1", "v2", "repo", "all"])
ap.add_argument("--show", type=int, default=1, help="print this many v2 chunks")
ap.add_argument("--parquet", default=str(ROOT / "DBVECTOR/data/indexes/faiss/metadata.parquet"))
ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
a = ap.parse_args()

if a.file:
    doc_id, text = a.file, Path(a.file).read_text(encoding="utf-8")
else:
    # Scan the parquet one row group at a time, id and text only, and stop at the first hit (the file is large).
    import pyarrow.parquet as pq
    f = pq.ParquetFile(a.parquet)
    doc_id = a.id
    text = None
    for g in range(f.metadata.num_row_groups):
        t = f.read_row_group(g, columns=["id", "text"]).to_pydict()
        if doc_id in t["id"]:
            text = t["text"][t["id"].index(doc_id)]
            break
    if text is None:
        sys.exit(f"id not found: {doc_id}")

st = SentenceTransformer(a.model, device="cpu")
tk = st.tokenizer
msl = st.max_seq_length
# Length in model tokens, special tokens included, never truncated: this is the size the model has to fit.
n = lambda s: len(tk(s, add_special_tokens=True, truncation=False)["input_ids"])


def v2_chunks(text, window):
    # The first line (usually the title) is repeated on every later chunk so each one says what it belongs to;
    # a long first line is cut to 160 characters. `body` is the room left for text in each chunk.
    first = text.strip().split("\n", 1)[0]
    header = first if n(first) <= 40 else first[:160]
    body = window - n(header) - 2

    def split(piece, seps):
        # Recursive split: try the coarsest separator first and fall to finer ones only for pieces still too big.
        if n(piece) <= body or not seps:
            return [piece]
        parts = [p for p in piece.split(seps[0]) if p.strip()]
        if len(parts) == 1:
            return split(piece, seps[1:])
        return [q for p in parts for q in split(p, seps[1:])]

    sep_of = ["\n\n", "\n", ". ", " "]
    out, cur = [], ""

    # Greedy packing: glue consecutive pieces together until the next one would overflow the window.
    for p in split(text, sep_of):
        cand = (cur + " " + p).strip() if cur else p
        if n(cand) <= body:
            cur = cand
        else:
            if cur:
                out.append(cur)
            cur = p
    if cur:
        out.append(cur)
    return [out[0]] + [header + "\n" + c for c in out[1:]]  # chunk 0 already starts with the header

# The v2 window is msl - 8, leaving a margin below the model's max_seq_length.
versions = {
    "v1": [text],
    "v2": v2_chunks(text, msl - 8),
    "repo": [c["texto"] for c in DocumentChunker().chunk_documento(DocumentoParaChunking(id=doc_id, texto=text))],
}
label = {
    "v1": "v1 whole document (live index)",
    "v2": "v2 recursive split to the window + header",
    "repo": "repo DocumentChunker (600 tok, cl100k)",
}
print(f"document {doc_id}: {len(text):,} chars, {n(text):,} model tokens; model window = {msl}\n")
print("| version | chunks | model tokens per chunk (min / median / max) | chunks truncated by the model | share of the text the model reads |\n|---|---|---|---|---|")
for k in (["v1", "v2", "repo"] if a.version == "all" else [a.version]):
    ch = versions[k]
    L = np.array([n(c) for c in ch])
    # Share of the text the model actually reads: tokens inside the window over all tokens.
    read = np.minimum(L, msl).sum() / L.sum()
    print(f"| {label[k]} | {len(ch)} | {L.min()} / {int(np.median(L))} / {L.max()} | {int((L > msl).sum())} of {len(ch)} | {read:.1%} |")
if a.version in ("v2", "all"):
    for i, c in enumerate(versions["v2"][:a.show]):
        print(f"\nv2 chunk {i} ({n(c)} tokens):\n" + c[:400].replace("\n", " | "))
