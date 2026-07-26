#!/usr/bin/env python3
"""Structured markdown export for personal WeChat (yichen-wechat-local-vault).

Reads a vault_cli.py history JSON export and produces a structured Markdown file:
- date grouping with weekday and per-day count
- message type emoji labels (based on Chinese `type` field)
- refermsg XML parsing for reply messages → blockquote
- image-hash / screenshot-filename cleanup
- system messages (revoke etc.) rendered as italic

Input JSON shape (personal WeChat):
  {"chat": "...", "username": "...", "count": N, "messages": [
    {"type": "文本", "local_type": 1, "sender": "...", "time": "YYYY-MM-DD HH:MM:SS",
     "content": "...", ...}
  ]}
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Emoji mapping by Chinese type name (personal WeChat already provides Chinese type)
TYPE_EMOJI = {
    "文本": "💬",
    "图片": "🖼️",
    "视频": "🎬",
    "表情": "😄",
    "语音": "🎙️",
    "链接/文件": "🔗",
    "文件": "📎",
    "系统": "⚙️",
    "位置": "📍",
    "名片": "📋",
    "通话": "📞",
    "引用": "💬",
    "转账": "💰",
    "红包": "🧧",
    "小程序": "🤖",
    "视频号": "📺",
}

# Patterns to clean up raw content
IMG_HASH_PATTERN = re.compile(r'[0-9a-f]{32}\.(?:jpg|jpeg|png|gif|bmp|webp)', re.IGNORECASE)
SCREENSHOT_PATTERN = re.compile(r'(?:微信|企业微信)截图_\d+\.png')
MULTI_NEWLINE = re.compile(r'\n{3,}')

# Personal WeChat refermsg XML: <refermsg><sourcename>..</sourcename><sourcecontent>..</sourcecontent></refermsg>reply
REFERMSG_PATTERN = re.compile(
    r'<refermsg>.*?<sourcename>(.*?)</sourcename>.*?<sourcecontent>(.*?)</sourcecontent>.*?</refermsg>(.*)',
    re.DOTALL,
)
# Fallback: some versions use <title>/<desc>
REFERMSG_PATTERN2 = re.compile(
    r'<refermsg>.*?<title>(.*?)</title>.*?<desc>(.*?)</desc>.*?</refermsg>(.*)',
    re.DOTALL,
)


def clean_content(text: str) -> str:
    """Clean image hashes, screenshot filenames, excess newlines."""
    text = IMG_HASH_PATTERN.sub("[图片]", text)
    text = SCREENSHOT_PATTERN.sub("[截图]", text)
    text = MULTI_NEWLINE.sub('\n\n', text)
    return text.strip()


def parse_refermsg(content: str) -> dict | None:
    """Parse personal WeChat refermsg XML into quoted sender/text + reply text.

    Returns None if content is not a refermsg reply.
    """
    for pat in (REFERMSG_PATTERN, REFERMSG_PATTERN2):
        m = pat.search(content)
        if m:
            quoted_sender = clean_content(m.group(1).strip())
            quoted_text = clean_content(m.group(2).strip())
            reply_text = clean_content(m.group(3).strip())
            if not quoted_text and not reply_text:
                continue
            return {
                "quoted_sender": quoted_sender,
                "quoted_text": quoted_text,
                "reply_text": reply_text,
            }
    return None


def format_message(msg: dict) -> str:
    """Format a single message into structured markdown."""
    time_str = msg.get("time", "")
    sender = msg.get("sender", "") or "未知"
    type_name = msg.get("type", "未知")
    raw_content = msg.get("content", "")

    emoji = TYPE_EMOJI.get(type_name, "❓")

    # System messages (revoke, join, etc.) — render as italic, no sender emphasis
    if type_name == "系统":
        # Try to extract human-readable text from revoke XML
        revoke_match = re.search(r'<content>(.*?)</content>', raw_content)
        text = revoke_match.group(1) if revoke_match else clean_content(raw_content)
        return f"> *{time_str} · ⚙️ {text}*"

    # Refermsg reply → blockquote
    if type_name in ("文本", "引用"):
        reply = parse_refermsg(raw_content)
        if reply:
            lines = [f"#### {time_str} · {sender}", ""]
            if reply["quoted_text"]:
                lines.append(f"> **{reply['quoted_sender']}：**")
                for ql in reply["quoted_text"].split("\n"):
                    lines.append(f"> {ql}")
                lines.append(">")
                lines.append("> *（被引用消息）*")
                lines.append("")
            if reply["reply_text"]:
                for rl in reply["reply_text"].split("\n"):
                    lines.append(rl)
            else:
                lines.append("*（仅引用，无回复内容）*")
            lines.append("")
            return "\n".join(lines)

    content = clean_content(raw_content)

    # Media-only messages often have placeholder content like [图片]
    lines = [f"#### {time_str} · {sender} `{emoji} {type_name}`", ""]
    for cl in content.split("\n"):
        lines.append(cl)
    lines.append("")
    return "\n".join(lines)


def export_structured_md(input_json: str, output_md: str) -> dict:
    """Convert a vault_cli JSON history export into structured Markdown.

    Returns a small summary dict (for logging / chaining).
    """
    with Path(input_json).open(encoding="utf-8") as f:
        data = json.load(f)

    chat_name = data.get("chat", "未知会话")
    username = data.get("username", "")
    messages = data.get("messages", [])

    output = [
        f"# {chat_name}",
        "",
        f"> 个人微信聊天记录结构化导出 · 共 {len(messages):,} 条消息",
        f"> 会话 ID: `{username}`" if username else "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    current_date = None
    # Pre-compute per-day counts for the day headers
    day_counts = {}
    for m in messages:
        d = (m.get("time") or "")[:10]
        if d:
            day_counts[d] = day_counts.get(d, 0) + 1

    for msg in messages:
        msg_date = (msg.get("time") or "")[:10] or "未知日期"
        if msg_date != current_date:
            current_date = msg_date
            try:
                dt = datetime.strptime(msg_date, "%Y-%m-%d")
                weekday = "周" + "一二三四五六日"[dt.weekday()]
            except (ValueError, TypeError):
                weekday = ""
            cnt = day_counts.get(msg_date, 0)
            output.append("\n---\n")
            output.append(f"## 📅 {msg_date} {weekday}（{cnt} 条）\n")
        output.append(format_message(msg))

    md_text = "\n".join(output)
    Path(output_md).write_text(md_text, encoding="utf-8")

    return {
        "chat": chat_name,
        "username": username,
        "total": len(messages),
        "output": output_md,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 structured_export.py <input.json> <output.md>")
        sys.exit(1)
    summary = export_structured_md(sys.argv[1], sys.argv[2])
    print(f"Done: {summary['output']} ({summary['total']} messages)")
