#!/usr/bin/env python3
"""wechat_pro.py — unified CLI for personal WeChat structured export & analysis.

Wraps yichen-wechat-local-vault's vault_cli.py and adds:
- structured Markdown export (date grouping, refermsg parsing, type labels)
- self-contained HTML analysis report (Chart.js visualizations)
- one-shot `analyze` producing JSON + structured MD + HTML

Commands:
  history <chat>   Fetch raw JSON history from vault (delegates to vault_cli.py)
  export <chat>    Structured Markdown export
  report <chat>    HTML analysis report
  analyze <chat>   One-shot: JSON + structured MD + HTML (three files)
  status           Vault status (delegates to vault_cli.py)

Common options: --limit, --start-time, --end-time, --output-dir
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Locate sibling modules and the vault_cli of yichen-wechat-local-vault
SELF_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = SELF_DIR.parent.parent  # ~/.workbuddy/skills
VAULT_CLI = SKILLS_ROOT / "yichen-wechat-local-vault" / "scripts" / "vault_cli.py"

if str(SELF_DIR) not in sys.path:
    sys.path.insert(0, str(SELF_DIR))

import structured_export  # noqa: E402
import html_report  # noqa: E402


def _run_vault_cli(args: list[str]) -> str:
    """Run vault_cli.py with the same interpreter, return stdout."""
    if not VAULT_CLI.exists():
        sys.exit(f"vault_cli.py not found: {VAULT_CLI}. Is yichen-wechat-local-vault installed?")
    cmd = [sys.executable, str(VAULT_CLI)] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"vault_cli.py failed: {result.stderr or result.stdout}")
    return result.stdout


def _safe_filename(name: str) -> str:
    """Make a chat name safe for filenames."""
    return re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', name).strip('_') or "chat"


def _fetch_history_json(chat: str, limit: int, start: str | None, end: str | None) -> dict:
    """Fetch history as JSON dict from vault_cli.py."""
    args = ["history", chat, "--limit", str(limit)]
    if start:
        args += ["--start-time", start]
    if end:
        args += ["--end-time", end]
    out = _run_vault_cli(args)
    return json.loads(out)


def cmd_history(args: argparse.Namespace) -> None:
    data = _fetch_history_json(args.chat, args.limit, args.start_time, args.end_time)
    if args.output:
        Path(args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Done: {args.output} ({data.get('count', 0)} messages)")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_export(args: argparse.Namespace) -> None:
    data = _fetch_history_json(args.chat, args.limit, args.start_time, args.end_time)
    out_dir = Path(args.output_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_md = args.output or str(out_dir / f"{_safe_filename(args.chat)}_structured.md")
    summary = _export_from_dict(data, out_md)
    print(f"Done: {out_md} ({summary['total']} messages)")


def _export_from_dict(data: dict, out_md: str) -> dict:
    """Write dict to temp json then call structured_export on file (compat helper)."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        tmp = f.name
    try:
        return structured_export.export_structured_md(tmp, out_md)
    finally:
        os.unlink(tmp)


def cmd_report(args: argparse.Namespace) -> None:
    data = _fetch_history_json(args.chat, args.limit, args.start_time, args.end_time)
    out_dir = Path(args.output_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_html = args.output or str(out_dir / f"{_safe_filename(args.chat)}_report.html")
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        tmp = f.name
    try:
        summary = html_report.generate_html_report(tmp, out_html)
    finally:
        os.unlink(tmp)
    print(f"Done: {out_html} ({summary['total']} messages)")


def cmd_analyze(args: argparse.Namespace) -> None:
    """One-shot: JSON + structured MD + HTML."""
    data = _fetch_history_json(args.chat, args.limit, args.start_time, args.end_time)
    out_dir = Path(args.output_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = _safe_filename(args.chat)

    json_path = out_dir / f"{base}_chat_records.json"
    md_path = out_dir / f"{base}_structured.md"
    html_path = out_dir / f"{base}_report.html"

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    structured_export.export_structured_md(str(json_path), str(md_path))
    html_report.generate_html_report(str(json_path), str(html_path))

    print(f"分析完成 · {data.get('count', 0)} 条消息:")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    print(f"  HTML: {html_path}")


def cmd_status(args: argparse.Namespace) -> None:
    out = _run_vault_cli(["status", "--format", "text"])
    print(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wechat_pro.py",
        description="Personal WeChat structured export & analysis (on top of yichen-wechat-local-vault).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("chat", help="chat name or group name")
        sp.add_argument("--limit", type=int, default=10000, help="max messages (default 10000; vault_cli default 500 truncates large chats)")
        sp.add_argument("--start-time", default=None, help="YYYY-MM-DD")
        sp.add_argument("--end-time", default=None, help="YYYY-MM-DD")
        sp.add_argument("--output-dir", default=None, help="output directory (default cwd)")

    sp = sub.add_parser("history", help="raw JSON history from vault")
    add_common(sp)
    sp.add_argument("--output", default=None, help="output json path")
    sp.set_defaults(func=cmd_history)

    sp = sub.add_parser("export", help="structured Markdown export")
    add_common(sp)
    sp.add_argument("--output", default=None, help="output md path")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("report", help="HTML analysis report")
    add_common(sp)
    sp.add_argument("--output", default=None, help="output html path")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("analyze", help="one-shot JSON + structured MD + HTML")
    add_common(sp)
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("status", help="vault status")
    sp.set_defaults(func=cmd_status)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
