#!/usr/bin/env python3
"""wecom_pro — single CLI for local WeCom chat extraction.

Pipeline: key capture → decrypt → query → structured export → analysis.
Decrypt and query delegate to scripts/engine/vault_cli.py. This file selects
the capture method and adds structured markdown plus the HTML report.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = SCRIPTS_DIR / "engine"
sys.path.insert(0, str(SCRIPTS_DIR))


def _python() -> str:
    """Return the managed Python path."""
    managed = Path.home() / ".workbuddy" / "binaries" / "python" / "envs" / "default" / "bin" / "python3"
    return str(managed) if managed.exists() else sys.executable


def _run_engine(script: str, args: list[str]) -> int:
    """Run a script in scripts/engine with that directory on PYTHONPATH."""
    cmd = [_python(), str(ENGINE_DIR / script), *args]
    env = {**os.environ, "PYTHONPATH": str(ENGINE_DIR)}
    return subprocess.run(cmd, env=env).returncode


def _run_vault(args: list[str]) -> int:
    """Run vault_cli.py with the given args, streaming output."""
    return _run_engine("vault_cli.py", args)


def _append_optional(argv: list[str], pairs: list[tuple[str, str | None]]) -> list[str]:
    for flag, value in pairs:
        if value:
            argv.extend([flag, value])
    return argv


# ─── status ──────────────────────────────────────────────────────────────────

def cmd_status(args) -> int:
    """Check WeCom databases and encryption status."""
    vault_args = ["status"]
    if args.data_dir:
        vault_args += ["--data-dir", args.data_dir]
    if args.show_paths:
        vault_args += ["--show-paths"]
    return _run_vault(vault_args)


def cmd_discover(args) -> int:
    """List local WeCom datasets without attaching to a process."""
    vault_args = ["discover"]
    if args.data_dir:
        vault_args += ["--data-dir", args.data_dir]
    if args.show_paths:
        vault_args += ["--show-paths"]
    return _run_vault(vault_args)


def cmd_doctor(args) -> int:
    """Check Python, Frida, and database shape. Does not attach."""
    doctor_args = ["doctor"]
    if args.data_dir:
        doctor_args += ["--data-dir", args.data_dir]
    return _run_engine("capture_key_macos.py", doctor_args)


# ─── capture-key ─────────────────────────────────────────────────────────────

def _run_script(script: Path, args: list[str]) -> int:
    cmd = [_python(), str(script), *args]
    env = {**os.environ, "PYTHONPATH": str(ENGINE_DIR)}
    return subprocess.run(cmd, env=env).returncode


def cmd_capture_key(args) -> int:
    """Capture the WeCom database decryption key.

    auto (default) tries hooks, then the Frida memory scan.
    dbkey-scan and signed-copy run only when explicitly selected.
    """
    if args.method == "dbkey-scan":
        print("=== DbKeyManager 读取（需本机管理员密码，不注入代码）===")
        scan_args = ["scan", "--confirm-sudo"]
        if args.data_dir:
            scan_args += ["--data-dir", args.data_dir]
        return _run_engine("scan_dbkey_manager_macos.py", scan_args)

    if args.method == "signed-copy":
        print("=== 重签副本捕获（不改原始企业微信.app）===")
        copy_args = [
            "capture",
            "--mode", "spawn-signed-copy",
            "--confirm-signed-copy",
            "--duration", str(args.signed_copy_duration),
        ]
        if args.data_dir:
            copy_args += ["--data-dir", args.data_dir]
        return _run_engine("capture_key_macos.py", copy_args)

    if args.method == "hooks" or (args.method == "auto" and not args.skip_hooks):
        print("=== 阶段 1/2: 标准 Frida hooks 捕获 ===")
        hook_args = ["capture", "--confirm-attach", "--duration", str(args.hook_duration)]
        if args.data_dir:
            hook_args += ["--data-dir", args.data_dir]
        result_code = _run_engine("capture_key_macos.py", hook_args)
        if result_code == 0:
            print("✅ hooks 捕获成功")
            return 0
        print(f"⚠️  hooks 捕获未成功 (exit={result_code})")

    if args.method == "hooks":
        return 1

    print("\n=== 阶段 2/2: Frida 内存扫描 ===")
    scan_args = ["--duration", str(args.scan_duration)]
    if args.data_dir:
        scan_args += ["--data-dir", args.data_dir]
    return _run_script(SCRIPTS_DIR / "key_memory_scan.py", scan_args)


# ─── decrypt ─────────────────────────────────────────────────────────────────

def cmd_decrypt(args) -> int:
    """Decrypt all databases into a plaintext snapshot."""
    vault_args = ["decrypt"]
    if args.data_dir:
        vault_args += ["--data-dir", args.data_dir]
    if args.key_file:
        vault_args += ["--key-file", args.key_file]
    if args.no_wal:
        vault_args.append("--no-wal")
    return _run_vault(vault_args)


# ─── sessions / contacts / history / search ──────────────────────────────────

def cmd_sessions(args) -> int:
    vault_args = ["sessions", "--limit", str(args.limit)]
    _append_optional(vault_args, [("--query", args.query), ("--snapshot", args.snapshot)])
    return _run_vault(vault_args)


def cmd_contacts(args) -> int:
    vault_args = ["contacts", "--limit", str(args.limit)]
    _append_optional(vault_args, [("--query", args.query), ("--snapshot", args.snapshot)])
    return _run_vault(vault_args)


def cmd_history(args) -> int:
    vault_args = ["history", args.chat, "--limit", str(args.limit)]
    _append_optional(vault_args, [("--snapshot", args.snapshot), ("--start", args.start), ("--end", args.end)])
    return _run_vault(vault_args)


def cmd_search(args) -> int:
    vault_args = ["search", args.keyword, "--limit", str(args.limit)]
    _append_optional(
        vault_args,
        [("--chat", args.chat), ("--snapshot", args.snapshot), ("--start", args.start), ("--end", args.end)],
    )
    return _run_vault(vault_args)


# ─── export ──────────────────────────────────────────────────────────────────

def cmd_export(args) -> int:
    """Export chat records in the specified format.

    Formats:
      json:       Raw JSON (via vault_cli)
      markdown:   Basic markdown (via vault_cli)
      structured: Structured markdown with parsed replies, date grouping (default)
      html:       HTML analysis report with Chart.js visualizations
    """
    if args.format in ("json", "markdown"):
        vault_args = ["export", args.chat, "--format", args.format, "--limit", str(args.limit)]
        _append_optional(
            vault_args,
            [("--output", args.output), ("--snapshot", args.snapshot), ("--start", args.start), ("--end", args.end)],
        )
        return _run_vault(vault_args)

    # For structured and html, first export JSON, then transform
    import tempfile
    tmp_json = tempfile.mktemp(suffix=".json")
    vault_args = ["export", args.chat, "--format", "json", "--limit", str(args.limit), "--output", tmp_json]
    _append_optional(vault_args, [("--snapshot", args.snapshot), ("--start", args.start), ("--end", args.end)])
    rc = _run_vault(vault_args)
    if rc != 0:
        os.unlink(tmp_json)
        return rc

    if args.format == "structured":
        from structured_export import export_structured_md
        output_path = args.output or args.chat.replace(" ", "_") + "_structured.md"
        export_structured_md(tmp_json, output_path)
        print(f"\n✅ 结构化 Markdown 已导出: {output_path}")
    elif args.format == "html":
        from html_report import generate_html_report
        output_path = args.output or args.chat.replace(" ", "_") + "_report.html"
        generate_html_report(tmp_json, output_path)
        print(f"\n✅ HTML 分析报告已生成: {output_path}")

    os.unlink(tmp_json)
    return 0


# ─── analyze ─────────────────────────────────────────────────────────────────

def cmd_analyze(args) -> int:
    """Full analysis pipeline: export JSON + structured MD + HTML report.

    Produces three files:
      <chat>_chat_records.json       — raw data
      <chat>_chat_records_structured.md — structured markdown
      <chat>_analysis_report.html    — visual analysis report
    """
    chat_slug = args.chat.replace(" ", "_").replace("/", "_")
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{chat_slug}_chat_records.json"
    md_path = output_dir / f"{chat_slug}_chat_records_structured.md"
    html_path = output_dir / f"{chat_slug}_analysis_report.html"

    # Step 1: Export JSON
    print(f"=== 1/3 导出 JSON 原始数据 ===")
    vault_args = ["export", args.chat, "--format", "json", "--limit", str(args.limit), "--output", str(json_path)]
    _append_optional(vault_args, [("--snapshot", args.snapshot), ("--start", args.start), ("--end", args.end)])
    rc = _run_vault(vault_args)
    if rc != 0:
        print(f"❌ JSON 导出失败 (exit={rc})")
        return rc
    print(f"✅ {json_path}")

    # Step 2: Structured markdown
    print(f"\n=== 2/3 生成结构化 Markdown ===")
    from structured_export import export_structured_md
    export_structured_md(str(json_path), str(md_path))
    print(f"✅ {md_path}")

    # Step 3: HTML report
    print(f"\n=== 3/3 生成 HTML 分析报告 ===")
    from html_report import generate_html_report
    generate_html_report(str(json_path), str(html_path))
    print(f"✅ {html_path}")

    print(f"\n🎉 全部完成！三个文件已生成在: {output_dir}")
    return 0


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="wecom_pro",
        description="企业微信本地聊天数据提取与分析工具 (Unified WeCom Local Vault Pro)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status / discover / doctor — read-only, no attach
    p = sub.add_parser("status", help="检查数据库状态和加密格式")
    p.add_argument("--data-dir")
    p.add_argument("--show-paths", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("discover", help="发现本机企业微信数据集，不附加进程")
    p.add_argument("--data-dir")
    p.add_argument("--show-paths", action="store_true")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("doctor", help="检查依赖和数据库格式，不附加进程")
    p.add_argument("--data-dir")
    p.set_defaults(func=cmd_doctor)

    # capture-key
    p = sub.add_parser("capture-key", help="捕获数据库解密密钥")
    p.add_argument("--data-dir")
    p.add_argument(
        "--method",
        choices=["auto", "hooks", "memory-scan", "dbkey-scan", "signed-copy"],
        default="auto",
        help="auto=先hooks后内存扫描(默认); dbkey-scan 与 signed-copy 仅在显式指定时运行",
    )
    p.add_argument("--hook-duration", type=int, default=60, help="hooks 捕获时长(秒)")
    p.add_argument("--scan-duration", type=int, default=300, help="内存扫描时长(秒)")
    p.add_argument("--signed-copy-duration", type=int, default=240, help="重签副本捕获时长(秒)")
    p.add_argument("--skip-hooks", action="store_true", help="auto 模式下跳过 hooks，直接内存扫描")
    p.set_defaults(func=cmd_capture_key)

    # decrypt
    p = sub.add_parser("decrypt", help="解密所有数据库到明文快照")
    p.add_argument("--data-dir")
    p.add_argument("--key-file")
    p.add_argument("--no-wal", action="store_true")
    p.set_defaults(func=cmd_decrypt)

    # sessions
    p = sub.add_parser("sessions", help="列出会话")
    p.add_argument("--query")
    p.add_argument("--snapshot")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_sessions)

    # contacts
    p = sub.add_parser("contacts", help="列出联系人")
    p.add_argument("--query")
    p.add_argument("--snapshot")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_contacts)

    # history
    p = sub.add_parser("history", help="查询指定会话历史")
    p.add_argument("chat")
    p.add_argument("--snapshot")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(func=cmd_history)

    # search
    p = sub.add_parser("search", help="全文搜索已解密消息")
    p.add_argument("keyword")
    p.add_argument("--chat")
    p.add_argument("--snapshot")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(func=cmd_search)

    # export
    p = sub.add_parser("export", help="导出聊天记录")
    p.add_argument("chat")
    p.add_argument("--format", choices=["json", "markdown", "structured", "html"], default="structured",
                   help="json/markdown/structured(默认)/html")
    p.add_argument("--snapshot")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--limit", type=int, default=10000)
    p.add_argument("--output")
    p.set_defaults(func=cmd_export)

    # analyze
    p = sub.add_parser("analyze", help="一键分析: JSON + 结构化MD + HTML报告")
    p.add_argument("chat")
    p.add_argument("--snapshot")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--limit", type=int, default=10000)
    p.add_argument("--output-dir", help="输出目录(默认当前目录)")
    p.set_defaults(func=cmd_analyze)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
