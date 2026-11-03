# scripts/lowlevel: how I found the truncation problem, and how to reproduce each step

Run from the repo root. Sources: `DBVECTOR/data/indexes/faiss/metadata.parquet` (the live index metadata). Measured on 2026-11-01/02; every number is in `docs/evaluation/lowlevel-facts.md` and `eval-v2-results.md`.

## Timeline: how I found it
1. **Read the index build.** The documentation said "600-token chunks, 100 overlap". `grep -rn DocumentChunker` found one importer, a test script. `DBVECTOR/src/tools/append_faiss.py:142` embeds the whole `doc.text`. So the chunker exists and is not used.
2. **Measure the damage.** `truncation_check.py` tokenizes a sample with the model's own tokenizer: 99.4% of STJ rows and 99.8% of TJDFT rows exceed the 256-token window; the model reads about 15% / 8% of the text.
3. **Check it affects retrieval, not just a count.** `late_text_test.py`: a verbatim sentence from the last 40% of a ruling finds its document in the top 10 only 4.5% of the time, against 64% for a sentence from the start. BM25 finds it 91.6% of the time.
4. **Try the obvious fixes and measure each** (`scripts/retrieval/`): a longer window made the old multilingual model worse (R@5 0.462 to 0.269); chunking did not rescue it (0.480); a better model did (bge-m3, 0.906); a reranker helps BM25 but not bge-m3.
5. **Check the repo's own chunker would have fixed it.** `chunking_demo.py`: no. A chunk the repository sizes at "600 tokens" (by a 4-characters-per-token estimate) is about 840 tokens for the MiniLM, so 6 of 7 chunks would still be cut.

## Commands
| Step | Command |
|---|---|
| 1-2 | `HF_HUB_OFFLINE=1 python scripts/lowlevel/truncation_check.py DBVECTOR/data/indexes/faiss/metadata.parquet 2000 0` |
| 3 | `python scripts/lowlevel/late_text_test.py DBVECTOR/data/indexes/faiss/metadata.parquet 750 0 out.json` |
| 5, v1 (what the index does) | `python scripts/lowlevel/chunking_demo.py --version v1 --id tjdft:9c171e08-2895-485e-a524-a92242164520` |
| 5, v2 (split to the window + header) | `python scripts/lowlevel/chunking_demo.py --version v2 --show 3 --id tjdft:9c171e08-2895-485e-a524-a92242164520` |
| 5, the repo chunker | `python scripts/lowlevel/chunking_demo.py --version repo --id tjdft:9c171e08-2895-485e-a524-a92242164520` |
| all three side by side | `python scripts/lowlevel/chunking_demo.py --version all --id ...` |

Needs `sentence-transformers`, `pyarrow`, `tiktoken`, `pydantic`; the demo and truncation check run on CPU. Reading the parquet row group by row group keeps memory low.
