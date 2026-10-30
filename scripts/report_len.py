#!/usr/bin/env python
"""Daily-brief length gate (binding since 2026-10-31).

Usage: python scripts/report_len.py data/reports/daily/<DATE>-<kind>.md [...]
Exit 0 = every file within budget, 1 = at least one over.

The reading text is what is measured: from the title down to (not including)
`## 주석` / `## 출처` / `## 부록` in the Korean half and `## Notes` / `## Sources` /
`## Appendix` in the English half. Footnotes, sources and the appendix are
unlimited by design — they are reference, not reading.
"""
import re
import sys

MARK = "<!-- ===== ENGLISH EDITION ===== -->"
KO_STOP = re.compile(r"^## (주석|출처|부록)", re.M)
EN_STOP = re.compile(r"^## (Notes|Sources|Appendix)", re.M)
# Korean reading text in characters (spaces included), English in words.
BUDGET = {
    "gucci-business-review": (2600, 480),
    "index-interpretation": (2600, 480),
    "luxury-brief": (2900, 540),
}


def body(text, stop):
    m = stop.search(text)
    return text[: m.start()] if m else text


def measure(path):
    t = open(path, encoding="utf-8").read()
    ko, en = (t.split(MARK) + [""])[:2]
    ko_b = re.sub(r"\[\d+\]", "", body(ko, KO_STOP))
    en_b = re.sub(r"\[\d+\]", "", body(en, EN_STOP))
    return len(ko_b.strip()), len(en_b.split())


def main():
    bad = 0
    for path in sys.argv[1:]:
        kind = next((k for k in BUDGET if k in path.replace("\\", "/")), None)
        ko_n, en_n = measure(path)
        if not kind:
            print(f"{path}: KO {ko_n} chars / EN {en_n} words (no budget for this kind)")
            continue
        ko_max, en_max = BUDGET[kind]
        ok = ko_n <= ko_max and en_n <= en_max
        bad += not ok
        print(f"{path}: KO {ko_n}/{ko_max} chars, EN {en_n}/{en_max} words -> {'OK' if ok else 'OVER'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
