# Retrieval evaluation of the legal search (legislation and case law)

Reproducible experiments on the legal corpus of this repository: which embedding model, window size, fusion and reranking choices work, with confidence intervals. Everything here is a research result from one machine, one run each unless stated; the numbers are for the 6,135 legislation records (5,545 distinct articles) and for samples of the case-law index.

| File | What it is |
|---|---|
| `eval-v1-results.md`, `eval-v1-ci.md` | the first comparison: keyword search, two small embedding models, fusion; paired bootstrap intervals |
| `eval-v2-results.md` | longer window, open retrieval models (e5, bge-m3), chunking, TF-IDF, reranker, the late-text test, serving cost |
| `graphrag-justice-results.md`, `PROTOCOL-justice-graphrag.md` | GraphRAG on the citation graph, with the protocol written before the run |
| `lowlevel-facts.md` | how much of each document a small embedding model actually reads (truncation measured on the index) |
| `gold_v1.jsonl`, `gold_multihop_justice.jsonl` | the test questions with the article(s) that answer each (see the caveat below) |
| `graph/` | the citation graph (`edges.jsonl`) built from the law texts, and its hand check |
| `*-raw.json`, `truncation_check.json` | raw per-question results behind every table |

Scripts: `scripts/retrieval/` (evaluation, bootstrap intervals, reranking, GraphRAG, serving cost), `scripts/lowlevel/` (truncation, late-text test, chunking demo), `scripts/graph/` (citation graph). Example, from the repository root:

```
python scripts/retrieval/bootstrap_ci.py docs/evaluation/eval-v1-raw.json
python scripts/retrieval/evaluate.py docs/evaluation/gold_v1.jsonl --out /tmp/eval-v1.json
```

The evaluation scripts read `legislacao_scraper/data/legislacao.jsonl`. The truncation, late-text and chunking scripts need the index metadata from the archived data release linked in the main README.

**Caveat on the test questions.** The 63 questions in `gold_v1.jsonl` were written by two AI assistants and labelled with the article that answers each; they have not been independently verified by a human yet. Treat the absolute numbers as indicative and the comparisons between systems (which use the same questions) as the useful part.
