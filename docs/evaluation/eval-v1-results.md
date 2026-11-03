# Retrieval eval v1 — legislacao.jsonl (6,135 records (5,545 distinct articles)), gold_v1 (57 scored questions)

Run 2026-10-28 with `scripts/retrieval/evaluate.py`, protocol described in this file (article-level, frozen labels).
Raw table: `eval-v1-raw.txt`. BM25 = rank_bm25 on `\w+` tokens, no stemming. Dense = sentence-transformers, exact cosine over all 6,135 vectors (not the FAISS 735k index). RRF k=60.

## Headline (single + multihop, n=57)
| Method | Recall@5 | Recall@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| BM25 | 0.640 | 0.711 | 0.585 | 0.602 |
| dense all-MiniLM-L6-v2 (English-only) | 0.240 | 0.336 | 0.190 | 0.208 |
| dense paraphrase-multilingual-MiniLM-L12-v2 | 0.462 | 0.541 | 0.402 | 0.415 |
| RRF(BM25 + English model) | 0.570 | 0.667 | 0.482 | 0.503 |
| **RRF(BM25 + multilingual)** | **0.667** | **0.781** | **0.586** | **0.619** |

## What this does and does not support
1. **Model choice is a real, large effect.** The English-only default (what the old index uses) gets Recall@5 0.24 on Portuguese legal text; the multilingual model gets 0.46 (about 2x). This is the strongest, cleanest finding.
2. **Hybrid helps recall, barely helps ranking.** RRF+multilingual vs BM25 alone: Recall@10 0.781 vs 0.711, MRR equal (0.586 vs 0.585). With 57 questions a difference under ~5 points is noise (see gold_v1.md). Say "fusion recovered some misses BM25 had", not "hybrid is much better".
3. **My prior did not hold.** I expected BM25 to win on keyword questions and dense on paraphrases. Here BM25 beat dense on both styles (paraphrase Recall@5: 0.486 vs 0.412). Probable reason: statute text shares vocabulary with the question; a small multilingual MiniLM is weak on legal paraphrase. A stronger embedding model or a reranker is the next experiment, not a claim.
4. **Graph 1-hop expansion did not help.** Multi-hop (n=6): Recall@5 unchanged (0.222 dense, 0.500 RRF); Recall@10 moved 0.306 -> 0.528 for dense only, nothing for RRF, and single-hop Recall@10 dropped slightly (0.569 -> 0.549). n=6 is far too small to claim a GraphRAG payoff. Honest Q2 answer: built the graph, tested it, no demonstrated gain yet.
5. **Confound:** `source` and `style` are perfectly aligned (all `author-a` questions are keyword style, all `author-b` ones paraphrase), so the "two authors = bias check" cannot be read separately from the style cut.

## Bugs found while running (Q5 material)
- First graph-expansion version appended neighbours after rank 10, so it could not change any @5/@10 metric by construction; results looked identical to plain dense. Noticed because dense and dense+graph matched to 3 decimals; fixed by splicing neighbours in after rank 5.
- The 6 `known_item` questions point to `tjdft:*` documents, which are not in the legislation corpus; the first run scored them 0.000 for every method. That was a harness artifact, not retrieval failure. They are now skipped here and need the TJDFT corpus to be scored.

## Not measured
Latency, the 735k FAISS index, tenant-leak test, reranker, TJDFT questions.
