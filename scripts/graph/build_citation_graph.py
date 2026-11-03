"""Build an article-to-article citation graph from legislacao.jsonl.

Edges: article A --cites--> article B, taken from "art. N" mentions in A's body.
A mention is resolved to the same code unless it is followed by an explicit
reference to another code ("da Lei Geral de Proteção de Dados", "do Código Civil", ...).
Unresolved mentions (targets absent from the corpus) are counted, not guessed.

Usage: python scripts/graph/build_citation_graph.py [--out DIR]
"""
import argparse, collections, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "legislacao_scraper/data/legislacao.jsonl"

# phrase after "art. N" that redirects the citation to another code
CODE_HINTS = [
    (r"constitui[çc][ãa]o", "cf-88"), (r"c[óo]digo civil", "cc"),
    (r"c[óo]digo penal\b", "cp"), (r"c[óo]digo de processo civil", "cpc"),
    (r"c[óo]digo de processo penal", "cpp"), (r"c[óo]digo de defesa do consumidor", "cdc"),
    (r"estatuto da crian", "eca"), (r"lei geral de prote[çc][ãa]o de dados|lgpd", "lgpd"),
    (r"lei de execu[çc][ãa]o penal", "lep"), (r"lei n[ºo.]* ?4\.?591", "lei-4-591-64"),
]
# "art. 1.136", "arts. 186 e 187", "arts. 5º, 6º e 7º-A". Thousands dots belong to the number
# ("1.136" is 1136, not art. 1); a list after "arts." yields one citation per number.
NUMTOK = r"\d{1,3}(?:\.\d{3})+|\d+"
ART_HEAD = re.compile(r"\bart(s)?\.?\s*((?:%s)[ºo°]?(?:-[A-Z])?(?:\s*(?:,|e|ou|a)\s*(?:%s)[ºo°]?(?:-[A-Z])?)*)(?![\w])" % (NUMTOK, NUMTOK), re.I)
ITEM = re.compile(r"(%s)[ºo°]?(?:-([A-Z]))?" % NUMTOK)
# a foreign statute named near the citation: do not resolve to the same code
FOREIGN = re.compile(r"^[^.;]{0,80}?\b(lei\s+(?:n[ºo.]*\s*[\d.]+|que|complementar|federal)|decreto|medida provis|regulamento|resolu)", re.I)

def body(rec):
    # drop the heading lines ("<Law> – Art. N", hierarchy) so self-label is not a citation
    lines = rec["text"].split("\n")
    # the hierarchy is ONE line joined with " / " (not one line per level)
    return "\n".join(lines[2 if rec["meta"].get("hierarquia") else 1:])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(ROOT / "docs/evaluation/graph"))
    out = Path(ap.parse_args().out); out.mkdir(parents=True, exist_ok=True)
    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    ids = {r["id"] for r in recs}
    ids_art = {re.sub(r"-p\d+$", "", i) for i in ids}
    edges, unresolved, foreign = collections.Counter(), 0, 0
    for r in recs:
        code = r["id"].split(":")[1]
        text = body(r)
        for m in ART_HEAD.finditer(text):
            tail = text[m.end(): m.end() + 120].lower()
            tcode = code
            for pat, c in CODE_HINTS:
                if re.search(r"^[^.;]{0,80}?(d[aoe]s?|desta|deste)\s+" + pat, tail):
                    tcode = c; break
            else:
                if FOREIGN.search(tail):
                    foreign += 1; continue
            for it in ITEM.finditer(m.group(2)):
                n = it.group(1).replace(".", "") + (f"-{it.group(2).lower()}" if it.group(2) else "")
                tid = f"lei:{tcode}:art-{n}"
                if tid == r["id"].rsplit("-p", 1)[0] or tid == r["id"]: continue
                if tid in ids_art: edges[(r["id"].rsplit("-p", 1)[0], tid)] += 1
                else: unresolved += 1
    with open(out / "edges.jsonl", "w", encoding="utf-8") as f:
        for (a, b), w in sorted(edges.items()):
            f.write(json.dumps({"src": a, "dst": b, "weight": w}) + "\n")
    indeg = collections.Counter(b for _, b in edges)
    stats = {"articles": len(recs), "edges": len(edges), "unresolved_mentions": unresolved, "skipped_foreign_law": foreign,
             "cross_code_edges": sum(1 for a, b in edges if a.split(":")[1] != b.split(":")[1]),
             "top_cited": indeg.most_common(10)}
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
