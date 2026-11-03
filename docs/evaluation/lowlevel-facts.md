# Low-level facts (L1) — measured, not assumed

Scope: read-only, offline, no service touched. Everything below was produced by
`scripts/lowlevel/truncation_check.py` (raw output: `docs/evaluation/truncation_check.json`) or read from code at the cited line.

Command:
```
HF_HUB_OFFLINE=1 python scripts/lowlevel/truncation_check.py \
  DBVECTOR/data/indexes/faiss/metadata.parquet 2000 0
```
Method: read `id,text` one row group at a time (19 groups), sample rows per source kind (seed 0), tokenize with each
model's own tokenizer (tokenization only, no inference) and with tiktoken `cl100k_base`. "Over limit" = model-token length
(with special tokens) > the model's `max_seq_length`.

## V1. Truncation: the index embeds whole documents, and the model reads the first 128–256 tokens

| Model | `max_seq_length` | Source | rows in index | sample n | % over limit | model tokens p50 / p95 | mean % of text actually embedded |
|---|---|---|---|---|---|---|---|
| all-MiniLM-L6-v2 (the live index) | **256** | STJ (hex ids) | 724,375 | 1,651 | **99.4** | 2,172 / 7,649 | **15.2** |
| | | TJDFT | 4,566 | 807 | **99.8** | 4,325 / 16,691 | **7.8** |
| | | Legislation (per article) | 6,135 | 400 | **33.0** | 164 / 449 | 90.1 |
| paraphrase-multilingual-MiniLM-L12-v2 (eval-v1 winner) | **128** | STJ | | 1,651 | 99.8 | 1,688 / 5,782 | 10.1 |
| | | TJDFT | | 807 | 99.8 | 3,186 / 12,219 | 5.3 |
| | | Legislation | | 400 | **47.5** | 124 / 316 | 80.9 |

What this means (each point is a measurement or a code fact):
1. **The 600-token chunker is not in the index path.** `DocumentChunker` is imported only by `DBVECTOR/test_rag_implementation.py`
   (grep over the repo). `tools/append_faiss.py:142` calls `embeddings.encode_texts([doc.text for doc in docs])` on the full
   document text and stores the same `doc.text` (`:162`). So the index holds one vector per document (STJ/TJDFT) or per article (legislation).
   The chunking settings in the code (target 600, overlap 100) describe a chunker that exists but did not build this index.
2. **For case law, a vector represents the first ~8–15% of the text** (median document is thousands of tokens; the model reads 256).
   Anything decided late in an opinion (the holding, the dispositive part) is not in its vector. BM25/FTS sees the whole text. The effect on retrieval was measured afterwards (late-text test, `eval-v2-results.md` step 4): with one vector per ruling, a sentence from the last 40% of the text finds its ruling in the top 10 only 4.5% of the time (64.4% for a sentence from the start); chunking to the window recovers late text (43.5%) but lowers early-text accuracy (47.6%); BM25 finds it 91.6%. Caveat: verbatim fragments, 1,500-document pool.
3. **Legislation is mostly fine for L6 (33% of articles over 256) but the multilingual model that won eval-v1 reads only 128 tokens, so 47.5% of articles were truncated in that eval too** (`scripts/retrieval/evaluate.py:60-61` uses the default `max_seq_length`). The reported dense numbers are therefore for truncated articles. Re-running with `st.max_seq_length = 512` was done afterwards: it made the model **worse** (dense R@5 0.462 to 0.269), and chunking articles to 110 tokens did not rescue it (0.480). A better model did (bge-m3, R@5 0.906).
4. Tokenizer note: the chunker's 4 chars/token estimate is off for this text: measured **~3.2 chars per cl100k token** on all three sources (so a "600-token" chunk by the estimate would be ~750 real tokens), and model tokens run ~1.1× cl100k for L6 and ~0.84× for the multilingual one.

Caveats (say them if asked): sample is capped per kind per row group, not proportional (legislation n=400, not 2,000; STJ/TJDFT ≥ 800);
the parquet has 735,076 rows vs 735,194 vectors in the FAISS file (118 more vectors than metadata rows, unexplained, not investigated); I assume the stored `text` is what was embedded
(true for `append_faiss`, not verified for earlier build scripts).

## V2. Length distribution (model tokens, L6 tokenizer)
See V1: legislation p50 164 / p95 449; STJ p50 2,172 / p95 7,649; TJDFT p50 4,325 / p95 16,691.
Characters p50 / p95: legislation 469 / 1,311; STJ 6,195 / 21,631; TJDFT 12,294 / 47,677.

## V3. Settings actually in code
| Item | Value | Where |
|---|---|---|
| Preprocess | strips control chars, `\r\n`→`\n`, collapses 3+ newlines to 2, collapses spaces, strips line ends. No accent folding, no lowercasing | `DBVECTOR/src/chunking.py:206-229` (`preprocessar_texto_juridico`; also only used by the test script) |
| `NORMALIZE_EMBEDDINGS` | default `true` (env override); so inner product on unit vectors = cosine | `DBVECTOR/src/config.py:18`, used in `embeddings.py:43-47` |
| Embedding model default | `sentence-transformers/all-MiniLM-L6-v2` (English-only, 384-d) | `config.py:16` |

(Defaults m=16, ef_construction=64, ef_search=40 are pgvector's documented defaults; I did not read them back from the running database.)

## What to say in 30 seconds
"When I measured the real index I found the 600-token chunker wasn't in the build path: documents were embedded whole and a 256-token model reads the first 8–15% of a court opinion. For legislation, where one article is one unit, it's mostly fine, except the 128-token multilingual model I benchmarked truncated 47% of articles. So I tested the fixes on the legislation set: a longer window made the small multilingual model worse, chunking did not rescue it, and a retrieval-built model (bge-m3) lifted Recall@5 from 0.64 for BM25 to 0.91. For rulings, the late-text test shows chunking recovers the end of the text but costs accuracy on the start, so the next step would be a document vector plus chunk vectors. I have not rebuilt the 735k index, because re-embedding with bge-m3 is many hours of GPU work."

## V4. Even wiring the existing chunker would not fit the model (one document, `scripts/lowlevel/chunking_demo.py`)
Command: `python scripts/lowlevel/chunking_demo.py --version all --id tjdft:9c171e08-2895-485e-a524-a92242164520` (a typical 12,522-character TJDFT ruling, 4,381 tokens in the L6 tokenizer).

| Version | Chunks | Model tokens per chunk (min / median / max) | Chunks the 256-token model truncates |
|---|---|---|---|
| Index today (one vector for the whole document) | 1 | 4,381 | yes (reads 5.8%) |
| v1 `DocumentChunker` (600 target tokens, sized by a 4-characters-per-token estimate) | 7 | 195 / **843** / 852 | **6 of 7** |
| v2 recursive split packed to the model's window, header repeated (`--version v2`) | 26 | 123 / 225 / 244 | 0 of 26 |

Reading: the repo's chunker sizes chunks with a 4-characters-per-token estimate, which is off for this text (about 3.2 characters per GPT token), and the embedding model counts differently again; for this Portuguese text a "600-token" chunk is about 840 model tokens, so the MiniLM would still cut off most of each chunk. Wiring the existing chunker is not enough; chunk sizes have to be set in the embedding model's tokens (or use a longer-window model). **One document, not a corpus statistic**; the corpus-level truncation figures are in V1, and the retrieval effect is in `eval-v2-results.md` step 4.
