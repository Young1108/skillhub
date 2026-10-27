#!/usr/bin/env python3
"""批量拉取飞书 wiki/docx 文档并做「空壳检测」。

用法:
  python3 fetch_lark_docs.py <outdir> <url-or-token> [<url-or-token> ...]
  python3 fetch_lark_docs.py <outdir> --file list.txt     # 每行: 别名<TAB>URL

环境变量:
  LARK_PROFILE   指定 lark-cli 的 profile 名（多租户/企业空间常用）。不设则用默认 profile。

产出:
  <outdir>/<别名>.md          正文（markdown）
  <outdir>/_manifest.json     每个文档的 ok / 空壳 / revision / 字数

为什么要空壳检测：飞书里有大量只建了标题没写正文的占位文档。
直接 fetch 会返回 ok，content 只有 "# 标题"，如果不判定，
会误以为「已读到评审结论」，最后拿录音推断冒充文档事实。
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# 企业 wiki 常挂在独立租户下，默认 profile 会报 3380004；用环境变量传入，不硬编码。
PROFILE = os.environ.get("LARK_PROFILE", "").strip()
FALLBACK_NO_PROFILE = True


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def fetch(target, outdir, alias):
    base = ["lark-cli", "docs", "+fetch", "--doc", target,
            "--doc-format", "markdown", "--as", "user"]
    variants = [base + ["--profile", PROFILE]] if PROFILE else []
    if FALLBACK_NO_PROFILE:
        variants.append(base)

    last_err = ""
    for cmd in variants:
        rc, out, err = run(cmd)
        if rc != 0:
            last_err = (err or out)[:300]
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            last_err = "非 JSON 输出"
            continue
        if not data.get("ok"):
            last_err = json.dumps(data.get("error", {}), ensure_ascii=False)[:300]
            continue

        doc = data["data"]["document"]
        content = doc.get("content", "")
        doc_id = doc.get("document_id", "")
        rev = doc.get("revision_id", 0)

        # 去掉 <title>…</title> 后看剩余正文长度
        body = re.sub(r"<title[^>]*>.*?</title>", "", content, flags=re.S).strip()
        empty = len(body) < 20

        if not empty:
            (outdir / f"{alias}.md").write_text(content, encoding="utf-8")
        return {
            "alias": alias, "target": target, "doc_id": doc_id,
            "revision": rev, "chars": len(body),
            "status": "EMPTY" if empty else "OK",
            "preview": body[:80].replace("\n", " "),
        }
    return {"alias": alias, "target": target, "status": "FAIL", "error": last_err}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)

    pairs = []
    if sys.argv[2] == "--file":
        for line in Path(sys.argv[3]).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) == 2:
                pairs.append((parts[0].strip(), parts[1].strip()))
            else:
                pairs.append((f"doc{len(pairs)+1}", parts[0].strip()))
    else:
        for i, t in enumerate(sys.argv[2:], 1):
            pairs.append((f"doc{i}", t))

    manifest = [fetch(t, outdir, a) for a, t in pairs]
    (outdir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{'alias':<16} {'status':<6} {'rev':>5} {'chars':>7}  preview")
    print("-" * 78)
    for m in manifest:
        if m["status"] == "FAIL":
            print(f"{m['alias']:<16} FAIL   {'-':>5} {'-':>7}  {m.get('error','')}")
        else:
            print(f"{m['alias']:<16} {m['status']:<6} {m['revision']:>5} {m['chars']:>7}  {m['preview']}")

    empty = [m["alias"] for m in manifest if m["status"] == "EMPTY"]
    if empty:
        print(f"\n⚠️  空壳文档（仅标题，无正文）: {', '.join(empty)}")
        print("   -> 必须在交付物中显式标注，不得当作「已读到的结论」。")


if __name__ == "__main__":
    main()
