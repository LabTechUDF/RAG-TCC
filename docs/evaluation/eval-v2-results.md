# Eval v2 (R1), step 1: does a longer window help the multilingual model? No, it got worse

Run 2026-11-02, same code and frozen gold as eval-v1 (`scripts/retrieval/evaluate.py`, new flag `--max-seq`; gold `docs/evaluation/gold_v1.jsonl`, 57 scored questions, 6,135 legislation records (5,545 distinct articles; long articles are stored in paragraph parts and scored per article)).
Command: `python scripts/retrieval/evaluate.py gold_v1.jsonl --models sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 --max-seq 512`. Raw: `eval-v2-seq512-raw.json`. One run, no tuning.
Why: `lowlevel-facts.md` V1 showed 47.5% of articles exceed the model's default 128 tokens, so the eval-v1 dense numbers were on truncated text. The obvious fix was to raise the limit to 512.

| Config (multilingual MiniLM-L12) | R@5 | R@10 | MRR |
|---|---|---|---|
| dense, `max_seq_length` 128 (eval-v1, default) | 0.462 | 0.541 | 0.402 |
| dense, `max_seq_length` 512 | **0.269** | **0.322** | **0.223** |
| RRF with BM25, 128 | 0.667 | 0.781 | 0.586 |
| RRF with BM25, 512 | 0.412 | 0.605 | 0.413 |
| BM25 (unchanged) | 0.640 | 0.711 | 0.585 |

## What it shows
- Raising the limit made dense retrieval clearly **worse** (R@5 0.462 to 0.269), and RRF fell below BM25 alone. That is the opposite of what I expected, and I report it as measured.
- I did not run a confidence interval, but the drop is 19 points on 57 questions; eval-v1 treated a 22-point model difference as significant, so I would not call this noise.
- **I have not established why.** Plausible, untested: this model was trained with short inputs (128), so its positions beyond that are poorly trained, and mean pooling over long text dilutes the article's main idea. Checking would need a model trained for long inputs or chunking each article to 128 and pooling.
- Consequence: "just raise `max_seq_length`" is not a free fix. The proper options are chunk to the model's window, or use a model built for long inputs (bge-m3, multilingual-e5; still to run).
- Still true from L1: the live FAISS index uses all-MiniLM-L6-v2 at 256 tokens on whole documents. This test does not measure that index.

# Step 2: open multilingual models on the same questions (GPU, `max_seq_length` 512)

Run 2026-11-02, one run, models chosen before seeing any number: `intfloat/multilingual-e5-small`, `intfloat/multilingual-e5-base` (with the `query: ` / `passage: ` prefixes they expect), `BAAI/bge-m3`. Same 57 questions, same 6,135 records, same code. Raw: `eval-v2-open-models-raw.json`. ROCm torch (a dedicated virtual environment), VRAM capped at 60%.

| Config | R@5 | R@10 | MRR |
|---|---|---|---|
| BM25 | 0.640 | 0.711 | 0.585 |
| dense multilingual MiniLM-L12 (eval-v1, 128) | 0.462 | 0.541 | 0.402 |
| dense e5-small | 0.789 | 0.851 | 0.706 |
| dense e5-base | 0.836 | 0.871 | 0.708 |
| **dense bge-m3** | **0.906** | **0.924** | **0.817** |
| RRF(BM25 + bge-m3) | 0.833 | 0.868 | 0.696 |
| RRF(BM25 + e5-base) | 0.763 | 0.833 | 0.681 |

By question style (bge-m3 dense): keyword questions R@5 0.976 (BM25 0.905); paraphrase questions R@5 **0.866 vs BM25 0.486**.

Paired bootstrap 95% CI (`bootstrap_ci.py`, 10,000 resamples, seed 1, questions resampled):

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---|---|
| bge-m3 dense minus BM25 | R@5 | +0.266 | [+0.149, +0.389] |
| bge-m3 dense minus BM25 | R@10 | +0.213 | [+0.105, +0.327] |
| bge-m3 dense minus BM25 | MRR | +0.232 | [+0.130, +0.334] |
| bge-m3 dense minus multilingual-L12 (128) | R@5 | +0.444 | [+0.322, +0.573] |
| e5-base dense minus BM25 | R@5 | +0.196 | [+0.091, +0.316] |
| bge-m3 dense minus e5-base dense | R@5 | +0.070 | [-0.018, +0.167] (includes 0) |
| RRF(BM25 + bge-m3) minus bge-m3 dense | R@5 | -0.073 | [-0.178, +0.029] (includes 0) |

## What it shows
- With a model built for retrieval, **dense beats BM25 on this legislation set**, by a margin whose interval excludes 0. The eval-v1 reading "BM25 is the strongest single retriever" was about the weak models I had tried, not about dense retrieval in general.
- The gain is on **paraphrase** questions (the user does not use the statute's words); on keyword questions BM25 and dense are both near the ceiling.
- bge-m3 versus e5-base is not separable with 57 questions. I claim "bge-m3 and e5 beat BM25", not an order between them.
- **Equal-weight RRF with BM25 did not beat the best dense model** (difference not significant, and negative in the mean). Fusion helps when the two lists are comparably good; here one is clearly better.
- Multi-hop questions (n=6): dense models are no better than BM25 there; graph expansion did not help dense either. Too few to say more.

## Caveats (say them)
- Legislation only, 57 questions, labels written by two AI assistants (the two authors in the gold file); a human spot-check of 10 labels is still open. Not the 735k case-law index.
- bge-m3 is a much larger model than MiniLM (about 568M parameters versus 118M for the multilingual MiniLM, from the public model cards, not measured here): the comparison is not size-matched, and it is slower and heavier to serve. Latency and memory were not measured.
- 512 tokens covers about 95% of articles (p95 about 449 on the L6 tokenizer); bge-m3 could read more, I did not test that.
- Whether the same ordering holds on case law (long documents, different vocabulary) is untested. The late-text and chunking experiments below are for that.

# Step 3: chunking, TF-IDF and a cross-encoder reranker (same 57 questions, one run)

Script `scripts/retrieval/r1_extra.py`; raw `eval-v2-extra-raw.json`. Reranker: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` over the top 30 of the first stage, max length 512. Chunk-to-window: each article cut into windows of at most 110 model tokens (stride 90; 6,135 records became 11,522 chunks), article score = its best chunk, model = the same multilingual MiniLM-L12 as eval-v1.

| Config | R@5 | R@10 | MRR |
|---|---|---|---|
| BM25 | 0.640 | 0.711 | 0.585 |
| TF-IDF (sublinear tf) | 0.614 | 0.684 | 0.474 |
| multilingual MiniLM-L12, whole article truncated at 128 (eval-v1) | 0.462 | 0.541 | 0.402 |
| multilingual MiniLM-L12, chunked to 110 tokens, best chunk | 0.480 | 0.594 | 0.429 |
| BM25 then rerank top 30 | 0.784 | 0.825 | 0.778 |
| dense bge-m3 | 0.906 | 0.924 | 0.817 |
| bge-m3 then rerank top 30 | 0.892 | 0.944 | 0.850 |

Paired bootstrap 95% CI (10,000 resamples, seed 1):
| Comparison | Metric | Mean diff | 95% CI |
|---|---|---|---|
| BM25+rerank minus BM25 | R@5 | +0.143 | [+0.056, +0.240] |
| BM25+rerank minus BM25 | MRR | +0.193 | [+0.105, +0.287] |
| bge-m3+rerank minus bge-m3 | R@5 | -0.015 | [-0.085, +0.056] (includes 0) |
| bge-m3+rerank minus bge-m3 | MRR | +0.032 | [-0.035, +0.098] (includes 0) |
| bge-m3+rerank minus BM25+rerank | R@5 | +0.108 | [+0.026, +0.202] |
| chunked L12 minus whole-article L12 | R@5 | +0.018 | [-0.088, +0.123] (includes 0) |
| TF-IDF minus BM25 | R@5 | -0.026 | [-0.088, +0.035] (includes 0) |

## What it shows
- **Reranking helps a weak first stage a lot and a strong one not at all.** On top of BM25 it gives +0.14 R@5 and +0.19 MRR (interval excludes 0), which closes about half of the gap to bge-m3; on top of bge-m3 the change is within noise. The reranker costs one model pass per candidate per query, so on this set it is worth paying for with BM25 and not with bge-m3.
- **Chunking to the 128-token window did not rescue the small multilingual model** (R@5 0.462 to 0.480, interval includes 0). So truncation at 128 was not the main reason that model was weak on legislation; it was the model. I measured this on legislation, where only 47.5% of articles were truncated. It says nothing yet about case law, where 99% of documents are far longer than the window: that is the late-text test, still to do.
- TF-IDF is about as good as BM25 here (no significant difference); BM25's length normalisation is not buying much on short articles.

## Caveats
Same as step 2 (legislation only, labels not independently verified, one run, 57 questions, models of different sizes, no latency or cost measured). Reranker candidates are the top 30 only; an item outside it cannot be rescued.

## Next in R1
Late-text known-item test on TJDFT/STJ (does the verdict, at the end of a long ruling, get found when the vector holds only the first 256 tokens?). Then J-R5.

# Step 4: the late-text test (case law, does the vector see the end of a ruling?)

Script `scripts/lowlevel/late_text_test.py`; raw `late-text-raw.json`. Pool: 1,500 documents sampled from the live index metadata (750 TJDFT + 750 STJ, each longer than 4,500 characters and 1,200 model tokens). For 990 of them I took a verbatim fragment (at most 25 words) from the **early** part (tokens 40-200) and one from the **late** part (the last 40% of the text). The question is whether the system returns the source document among the 1,500. Model: all-MiniLM-L6-v2, the live index's model, 256-token window. "whole256" = one vector per document, as the live index does; "chunked" = windows of 240 tokens (stride 200, 43,806 chunks), document score = best chunk; BM25 on the whole text.

| Query from | System | Success@1 | Success@10 | MRR |
|---|---|---|---|---|
| early | whole256 (live index design) | 0.379 | 0.644 | 0.467 |
| **late** | **whole256 (live index design)** | **0.009** | **0.045** | **0.025** |
| early | chunked | 0.228 | 0.476 | 0.314 |
| late | chunked | 0.196 | 0.435 | 0.277 |
| early | BM25 | 0.782 | 0.941 | 0.841 |
| late | BM25 | 0.646 | 0.916 | 0.744 |

TJDFT and STJ separately show the same shape (late Success@10 for whole256: 0.058 and 0.037).

## What it shows
- **The truncation is real and large for retrieval, not only for the token count.** With one vector per document, a sentence from the last 40% of a ruling finds its document 4.5% of the time in the top 10, against 64% for a sentence from the opening. The vector cannot see the end. This is the measured effect that `lowlevel-facts.md` V1 only inferred.
- **Chunking recovers the late text** (Success@10 0.045 to 0.435) **but costs early-text accuracy** (0.644 to 0.476): with 43,806 chunks competing, a best chunk from another document more often beats the true one. Chunking is a trade, not a free fix; the usual remedies are to keep a document-level vector next to the chunk vectors, or to rerank the candidates.
- **BM25 sees the whole text** and scores 0.916 on late text. That is consistent with lexical retrieval beating the MiniLM index on this corpus, and with hybrid search being worth having for long rulings.

## Caveats (say them)
- The queries are **verbatim fragments**, which is the easiest case for BM25 and for a vector that can see the text. Real users paraphrase. This test measures what the vector can see, not how users will phrase things.
- The pool is 1,500 documents, not 735,194: absolute numbers will be lower at full scale, and the early/late gap is the point.
- Sampled documents are long ones (the filter excludes short rulings); the sample is random within that, not proportional to the index.
- One run, one seed, no confidence intervals (the gap is far larger than any plausible noise at n = 990, but I did not compute it). The model is the live one; bge-m3 and the others were not run on case law.

# Step 5: what each model costs to serve (cost row)

Script `scripts/retrieval/cost_bench.py`; raw `cost-bench-raw.json`. Machine: AMD Radeon Graphics under ROCm, one run, GPU otherwise idle (desktop only), process VRAM cap 30%. Articles = the first 1,000 legislation articles (median about 160 tokens), batch 16. Query latency = single query, 50 repeats after warm-up, p50 (p95 in the raw file). Raw index = n x dims x 4 bytes (arithmetic, no ANN structure).

| Model | Dims | Params (M) | Window used | Encode s per 1,000 articles (GPU) | Query p50 ms GPU / CPU | VRAM peak GiB | Raw index at 735,194 vectors |
|---|---|---|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | 118 | 128 | 4.4 | 3.8 / 8.9 | 0.59 | 1.05 GiB |
| multilingual-e5-small | 384 | 118 | 512 | 9.8 | 4.3 / 8.8 | 0.89 | 1.05 GiB |
| multilingual-e5-base | 768 | 278 | 512 | 23.4 | 5.4 / 29.5 | 1.54 | 2.1 GiB |
| bge-m3 | 1024 | 568 | 512 | 92.3 | 13.6 / 94.6 | 2.76 | 2.8 GiB |

Reranker (`mmarco-mMiniLMv2-L12`, top 30 candidates, 512-token max): **650.1 ms per query on the GPU** (p50 of 20 runs; about 22 ms per candidate).

## Reading it
- bge-m3, the best model on legislation (R@5 0.906), costs about **4x the compute of e5-base** to embed (92 s versus 23 s per 1,000 articles), a **single query takes 14 ms on the GPU and about 95 ms on a CPU**, and its index at 735k vectors is **2.8 GiB** raw (versus 1.05 GiB for the 384-d models). Re-embedding the whole 735k case-law index with it is a job of hours on this GPU, not minutes: 735,194 / 1,000 x 92 s is about 19 hours at the legislation's short length, and case-law documents are far longer, so that figure is a floor, not an estimate.
- e5-base is the middle choice: R@5 0.836, 768 dims, 2.1 GiB, 5 ms a query on the GPU.
- The reranker adds about 0.65 s per query for 30 candidates. It paid off on top of BM25 (R@5 0.640 to 0.784) and not on top of bge-m3, so on this set bge-m3 alone is both faster per query and better than BM25 plus rerank.

## Caveats
One machine, one run, small sample of articles; encode times scale with text length (case-law documents are many times longer than articles). Not a throughput benchmark under concurrency. Parameter counts are read from the loaded models.
