# GraphRAG on the real citation graph (J-R5): results

Protocol fixed before the run: `PROTOCOL-justice-graphrag.md` (no tuning; dev and held-out run once, together). Code `scripts/retrieval/graphrag_justice.py`; raw `graphrag-justice-raw.json`. Corpus: 6,135 legislation articles. Graph: 1,383 citation edges (regex-extracted, 28/30 hand-checked). Gold: 12 two-article questions J01-J12 (each pair is a direct edge), 2 single-article controls. The first launch crashed on a closure bug before producing any output (a model was freed while a lambda still used it); the fix changed no parameter.

"Full path" = both relevant articles in the top 5. "Path recall@5" = share of the 2 relevant articles in the top 5.

| First stage | Arm | Full paths dev (n=6) | Full paths held-out (n=6) | Both (n=12) | Path recall@5 dev / held-out |
|---|---|---|---|---|---|
| (none) | BM25 | 2 | 2 | 4 | 0.583 / 0.583 |
| multilingual MiniLM-L12 (128) | dense | 1 | 1 | 2 | 0.333 / 0.417 |
| | RRF with BM25 | 1 | 1 | 2 | 0.500 / 0.583 |
| | dense + 1-hop expansion | 1 | 1 | 2 | 0.333 / 0.417 |
| | **dense + GraphRAG** | **3** | **4** | **7** | 0.500 / 0.667 |
| bge-m3 (512, fp16) | dense | 4 | 4 | 8 | 0.750 / 0.833 |
| | RRF with BM25 | 3 | 3 | 6 | 0.750 / 0.750 |
| | dense + 1-hop expansion | 4 | 4 | 8 | 0.750 / 0.833 |
| | **dense + GraphRAG** | **5** | **5** | **10** | 0.833 / 0.917 |

Controls (JC1, JC2): GraphRAG did not lower recall@5 for either first stage (L12: 0.0 to 0.0, the small model misses both controls; bge-m3: 1.0 to 1.0). MRR is unchanged by GraphRAG by construction (the two seeds stay at the top).

## What it shows
- **GraphRAG added full paths on top of every dense first stage, in both the dev and the held-out questions**: +2 and +3 with the weak model (1 to 3, 1 to 4), +1 and +1 with the strong one (4 to 5, 4 to 5). Nothing was tuned between dev and held-out, so the 12 questions can be pooled: 2 to 7 of 12 and 8 to 10 of 12.
- The gain is **larger when the first stage is weaker**. With bge-m3 the base is already 8 of 12 and the graph adds two. This is the same pattern as the reranker (helps a weak first stage, little on a strong one).
- **The old 1-hop expansion added nothing** (same counts as plain dense), so how the neighbours are chosen matters, not only that the graph is used. GraphRAG here ranks neighbours by how many seeds they touch and by their own dense rank; the old splice took the first neighbours it found. I did not isolate which part of the ordering carries the gain.
- Equal-weight RRF with BM25 did not help bge-m3 (6 of 12 versus 8), as in the earlier eval.
- Every article the graph adds carries the edge that brought it in (for example `lei:cp:art-60 -cites/cited_by- lei:cdc:art-77`), so an answer can cite why it was included.

## Caveats (say them)
- n = 6 per split: one question is 17 points. I claim "added full paths in both splits", not a percentage gain, and no ranking between close arms. No confidence intervals.
- The questions are two-article questions whose pair is by construction a direct edge, so they favour a graph that follows direct edges; real multi-hop questions need longer chains, which this graph's regex citations only partly capture.
- Gold written by an AI assistant before the run; the labels have not been independently verified.
- bge-m3 ran in half precision (fp16) to share the GPU; I did not compare fp16 and fp32 on these questions (the fp32 run on `gold_v1` gave R@5 0.906).
- The graph has one edge type ("cites"), so the typed-links-first rule of the ERP demo does not apply. Legislation only; no case-law graph.
