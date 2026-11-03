# Bootstrap 95% CI on paired per-question differences (n=57, 10,000 resamples, seed 1)

| Comparison | Metric | Mean diff | 95% CI | Reading |
|---|---|---|---|---|
| RRF(BM25+multi) minus BM25 | r5 | +0.026 | [-0.088, +0.140] | includes 0 |
| RRF(BM25+multi) minus BM25 | r10 | +0.070 | [-0.018, +0.167] | includes 0 |
| RRF(BM25+multi) minus BM25 | mrr | +0.001 | [-0.093, +0.097] | includes 0 |
| dense multi minus dense English | r5 | +0.222 | [+0.079, +0.368] | excludes 0 |
| RRF(BM25+multi) minus dense multi | r5 | +0.205 | [+0.073, +0.336] | excludes 0 |

Paired bootstrap over questions (resampling questions, not documents); questions are not independent draws from a population of questions, so treat as indicative.
