# Protocol: GraphRAG on the real citation graph (J-R5), written before any run

Written 2026-11-02, before `scripts/retrieval/graphrag_justice.py` was run. Gold: `docs/evaluation/gold_multihop_justice.jsonl` (12 two-article questions J01-J12, dev J01-J06, held-out J07-J12, controls JC1-JC2; every relevant pair is a direct edge in the graph). Graph: `docs/evaluation/graph/edges.jsonl` (1,383 edges, regex-extracted citations, 28/30 hand-checked; undirected for expansion).

**No tuning.** Every parameter below is fixed now. Dev and held-out are run together, once, and reported separately. If I change any parameter after seeing a number, the earlier number stays in the report and the change is labelled.

Arms, for each of two first stages (A = multilingual MiniLM-L12 at its default 128 tokens, as in eval-v1; B = bge-m3 at 512):
1. BM25
2. dense (first stage)
3. RRF(BM25 + dense), k = 60
4. dense + 1-hop expansion (the eval-v1 splice: keep top 5, add up to 5 neighbours of the top 3, then the rest)
5. **GraphRAG**: seeds = top 2 of the dense list. Candidates = graph neighbours of the seeds (not already seeds). Order candidates by (number of seeds adjacent, descending; own rank in the dense top 300, ascending; edge weight, descending). Result = 2 seeds, then the top 3 candidates, then the rest of the dense list. Every candidate carries the edge that put it there (its path).

Metrics: path recall@5 (share of the 2 relevant articles in the top 5), full path (both in the top 5), MRR of the first relevant. Controls JC1-JC2 (single article): the graph arms must not lower recall@5 relative to their dense arm.
Counts, not significance: n = 6 per split. No ranking claim between arms that differ by one question.
Known difference from the ERP demo's GraphRAG: this graph has one edge type (cites), so "typed links first" does not apply.
