#!/usr/bin/env python3
"""MLX Whisper (Apple GPU) 全量转录 -> txt / srt / json"""
import json
import sys
import time
from pathlib import Path

import mlx_whisper

AUDIO = Path(sys.argv[1])
OUTDIR = AUDIO.parent
STEM = sys.argv[2] if len(sys.argv) > 2 else AUDIO.stem
MODEL = "mlx-community/whisper-large-v3-turbo"

PROMPT = ("健身房私人教练课录音。教练讲解胸肌训练：杠铃卧推、器械水平推胸、上斜推胸。"
          "术语包括：握距、肩胛骨后缩下沉、离心、向心、顶峰收缩、力竭、组数、次数、"
          "配重片、递增、递减、组间休息、三头肌、三角肌前束、胸部中缝。")


def hms(sec: float) -> str:
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def srt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, r = divmod(ms, 3600000)
    m, r = divmod(r, 60000)
    s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> None:
    t = time.time()
    result = mlx_whisper.transcribe(
        str(AUDIO), path_or_hf_repo=MODEL, language="zh",
        initial_prompt=PROMPT, temperature=0,
        condition_on_previous_text=False, verbose=False,
    )
    segs = [s for s in result["segments"] if s["text"].strip()]
    print(f"[done] {len(segs)} segs, {time.time() - t:.0f}s", flush=True)

    (OUTDIR / f"{STEM}.txt").write_text(
        "\n".join(f"[{hms(s['start'])} - {hms(s['end'])}] {s['text'].strip()}" for s in segs),
        encoding="utf-8")
    (OUTDIR / f"{STEM}.srt").write_text(
        "\n".join(f"{i}\n{srt_ts(s['start'])} --> {srt_ts(s['end'])}\n{s['text'].strip()}\n"
                  for i, s in enumerate(segs, 1)), encoding="utf-8")
    (OUTDIR / f"{STEM}.json").write_text(
        json.dumps([{"start": round(s["start"], 2), "end": round(s["end"], 2),
                     "text": s["text"].strip()} for s in segs], ensure_ascii=False, indent=1),
        encoding="utf-8")
    (OUTDIR / f"{STEM}.plain.txt").write_text(
        "".join(s["text"].strip() for s in segs), encoding="utf-8")


if __name__ == "__main__":
    main()
