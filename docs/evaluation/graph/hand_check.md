# Citation-graph hand check (2026-10-28)

Method: 30 random edges (seed 11) from `edges.jsonl`, each compared by eye with the sentence that cites the target article.
Result: **28 of 30 correct (93%)**. Small sample: the 95% interval is roughly 78–99%, so say "about 9 in 10 on a 30-edge hand check".

| Verdict | Count | Notes |
|---|---|---|
| Correct | 28 | includes cross-code edges (ADCT->CF-88, CDC->CP) |
| Wrong | 1 | `eca:art-264 -> eca:art-102`: sentence says "art. 102 da Lei n.º 6.015" (another statute); foreign-law filter did not catch this mention |
| Unverifiable | 1 | `cc:art-1271 -> cc:art-1270`: my snippet search found no context |

Known limits (not fixed): ranges "arts. 406 a 497" cite only the two endpoints, not the interior; mentions of other statutes are skipped or counted as unresolved, never guessed.

Bugs found and fixed from review (earlier version: 316 edges, 39 landing on art-1/art-2):
1. plural lists ("arts. 186 e 187") produced no edge -> now one citation per number;
2. thousands dots ("art. 1.136" was read as art. 1) -> number pattern keeps "1.136";
3. other-statute mentions ("art. 2º da lei que institui...") resolved to the same code -> skipped and counted;
4. article body cut: hierarchy is ONE line joined by " / ", but the code dropped one line per level, so many bodies were empty (cc:art-927 had no edges) -> fixed.
Effect: 316 -> 1,383 edges; edges landing on art-1/art-2 fell from 39 to a handful.
