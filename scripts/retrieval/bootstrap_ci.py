"""Paired bootstrap 95% CI over questions, from the JSON written by evaluate.py.

Input : the results JSON from evaluate.py. Output: a markdown table of mean differences with 95% CIs on stdout.
Usage:
python scripts/retrieval/bootstrap_ci.py docs/evaluation/eval-v1-raw.json   # reproduces docs/evaluation/eval-v1-ci.md
Resamples questions (not documents), 10,000 times, seed 1. Known-item rows are excluded, as in the eval tables."""
import argparse, json
import numpy as np

M = "paraphrase-multilingual-MiniLM-L12-v2"
L6 = "all-MiniLM-L6-v2"
# Comparisons (A, B, metric) reported in eval-v1-ci.md when no --pair is given.
DEFAULT = [(f"rrf:{M}", "bm25", "r5"), (f"rrf:{M}", "bm25", "r10"), (f"rrf:{M}", "bm25", "mrr"),
           (f"dense:{M}", f"dense:{L6}", "r5"), (f"rrf:{M}", f"dense:{M}", "r5")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--pair", nargs=3, action="append", metavar=("A", "B", "METRIC"), help="extra comparison: A minus B")
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    res = json.load(open(a.results, encoding="utf-8"))
    pairs = [tuple(p) for p in a.pair] if a.pair else DEFAULT
    rng = np.random.RandomState(a.seed)  # legacy generator: this is what produced eval-v1-ci.md
    print(f"| Comparison | Metric | Mean diff | 95% CI | Reading |\n|---|---|---|---|---|")
    for A, B, k in pairs:
        # Pair the two configs on the questions they share, so the difference is per question.
        ra = {r["qid"]: r[k] for r in res[A] if r["type"] != "known_item"}
        rb = {r["qid"]: r[k] for r in res[B] if r["type"] != "known_item"}
        q = sorted(set(ra) & set(rb))
        d = np.array([ra[i] - rb[i] for i in q])
        means = d[rng.randint(0, len(d), (a.n, len(d)))].mean(axis=1)
        lo, hi = np.percentile(means, [2.5, 97.5])
        print(f"| {A} minus {B} | {k} | {d.mean():+.3f} | [{lo:+.3f}, {hi:+.3f}] | {'excludes 0' if lo > 0 or hi < 0 else 'includes 0'} |")
    print(f"\nn={len(q)} questions, {a.n} resamples, seed {a.seed}.")


if __name__ == "__main__":
    main()
