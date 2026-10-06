#!/usr/bin/env python3
"""交叉验证两版转录，剔除幻觉，输出高置信片段。

用法:
    python crosscheck.py v1.json v2.json [-o verified.txt]
"""
import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

PUNCT = re.compile(r"[，。？！、,.?!\s]")


def norm(t: str) -> str:
    return PUNCT.sub("", t)


def overlap(a, b) -> float:
    return min(a["end"], b["end"]) - max(a["start"], b["start"])


def hms(x: float) -> str:
    h, r = divmod(int(x), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("v1", help="第一版转录 json")
    ap.add_argument("v2", help="第二版转录 json")
    ap.add_argument("-o", "--out", default="verified.txt")
    ap.add_argument("--high", type=float, default=0.6)
    ap.add_argument("--mid", type=float, default=0.35)
    a = ap.parse_args()

    v1 = json.loads(Path(a.v1).read_text(encoding="utf-8"))
    v2 = json.loads(Path(a.v2).read_text(encoding="utf-8"))

    high, mid = [], []
    for s in v1:
        n1 = norm(s["text"])
        if len(n1) < 3:
            continue
        best, alt = 0.0, ""
        for t in v2:
            if overlap(s, t) > 0.5:
                r = SequenceMatcher(None, n1, norm(t["text"])).ratio()
                if r > best:
                    best, alt = r, t["text"]
        row = (hms(s["start"]), s["text"], alt)
        if best >= a.high and len(n1) >= 4:
            high.append(row)
        elif a.mid <= best < a.high and len(n1) >= 6:
            mid.append(row)

    lines = [f"=== A 双版本高置信（相似度>={a.high}）==="]
    lines += [f"[{t}] {txt}   <-- alt: {alt}" for t, txt, alt in high]
    lines += ["", f"=== B 单版本中等置信（{a.mid}-{a.high}）==="]
    lines += [f"[{t}] {txt}   <-- alt: {alt}" for t, txt, alt in mid]
    Path(a.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"high={len(high)} mid={len(mid)} -> {a.out}")


if __name__ == "__main__":
    main()
