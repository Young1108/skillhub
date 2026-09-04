#!/usr/bin/env python3
"""Wake 日报素材提取：从 wake.db 提取指定日期的活跃会话与摘要骨架。

用法:
    extract_today.py [--date 2026-09-04] [--db ~/Library/Application Support/wake/wake.db] [-o digest.txt]

输出（默认 stdout）:
    每活跃会话一段：会话元数据 + 首个用户目标 + 末条助手结论 + 工具操作特征。
    供智能体阅读后按 references/report-structure.md 模板撰写日报。

已知坑（已内置处理，勿重复踩）:
    1. cursor 会话的 messages.ts 为 NULL —— 会话归属必须用 sessions.updated_at
       判定（不能只靠消息 ts），导出消息时不要按 ts 过滤，否则漏整个会话。
    2. 会话可能跨多日（同一 codex/dsh 会话含历史轮次）—— 本脚本按 ts 窗口
       只取当日消息；ts 为 NULL 的消息整批保留并在头部标注 [ts 未知]，由智能体
       结合会话 updated_at 判断是否当日。
    3. messages.ts / sessions.created_at / updated_at 均为毫秒。
"""
import argparse, datetime, json, os, re, sqlite3, sys
from collections import Counter

DEFAULT_DB = os.path.expanduser("~/Library/Application Support/wake/wake.db")

def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=datetime.date.today().isoformat(), help="YYYY-MM-DD，默认今天")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("-o", "--output", help="写入文件而非 stdout")
    return ap.parse_args()

def clip(s, n):
    s = re.sub(r"\s+", " ", s or "")
    return s[:n]

def main():
    a = parse_args()
    d = datetime.date.fromisoformat(a.date)
    day0 = int(datetime.datetime(d.year, d.month, d.day).timestamp() * 1000)
    day1 = day0 + 86_400_000 - 1
    db = sqlite3.connect(a.db)
    db.row_factory = sqlite3.Row

    sess = db.execute("""
        SELECT DISTINCT s.key, s.agent_id, s.project_name, s.title, s.created_at, s.updated_at
        FROM sessions s LEFT JOIN messages m ON m.session_key = s.key
        WHERE (s.updated_at BETWEEN ? AND ?) OR (m.ts BETWEEN ? AND ?)
        ORDER BY COALESCE(s.updated_at, s.created_at)""",
        (day0, day1, day0, day1)).fetchall()

    out = []
    total_msgs = 0
    out.append(f"# Wake 日报素材 · {a.date}\n")
    out.append(f"活跃会话 {len(sess)} 个（判定：updated_at 或消息 ts 落在当日）\n")
    for i, s in enumerate(sess):
        key, agent, proj = s["key"], s["agent_id"], s["project_name"]
        # 消息：有 ts 的按当日窗口过滤；ts NULL 的整批保留并标注
        rows = db.execute(
            "SELECT role, ts, text FROM messages WHERE session_key=? ORDER BY COALESCE(ts,0), seq",
            (key,)).fetchall()
        win = [r for r in rows if r["ts"] and day0 <= r["ts"] <= day1]
        nullts = [r for r in rows if not r["ts"]]
        msgs = win + nullts
        if not msgs:
            continue
        total_msgs += len(msgs)
        hh = lambda t: datetime.datetime.fromtimestamp(t / 1000).strftime("%H:%M") if t else "--:--"
        t0 = min((r["ts"] for r in msgs if r["ts"]), default=0)
        t1 = max((r["ts"] for r in msgs if r["ts"]), default=0)
        out.append("\n" + "=" * 74)
        out.append(f"[{i+1}] agent={agent}  项目={proj}  时段≈{hh(t0)}-{hh(t1)}")
        out.append(f"    KEY={key}")
        out.append(f"    标题={s['title'] or '(无)'}")
        if nullts:
            out.append(f"    ⚠ {len(nullts)} 条消息无时间戳（cursor 类），已整批纳入，按会话更新归属当日")
        users = [r["text"] for r in msgs if r["role"] == "user"]
        ass = [r["text"] for r in msgs if r["role"] == "assistant"]
        if users:
            out.append(f"    [首个目标] {clip(users[0], 500)}")
        if ass:
            out.append(f"    [末条结论] {clip(ass[-1], 800)}")
            if len(ass) > 1:
                out.append(f"    [前一条]   {clip(ass[-2], 400)}")
        # 工具操作特征（粗粒度，供方向判断）
        ops = re.findall(r"(exec_command|exec const patch|GetMcpTools|run_|Bash|Task |curl |npm |pnpm |cd /Users|\.venv/bin/python|write_stdin|git )",
                         "\n".join(r["text"] for r in msgs))
        top = Counter(ops).most_common(5)
        if top:
            out.append("    [操作特征] " + ", ".join(f"{k}x{v}" for k, v in top))

    out.append("\n" + "=" * 74)
    out.append(f"合计：{len(sess)} 会话 / {total_msgs} 条当日消息。")
    out.append("下一步：对摘要不足的会话可回读原始文件补细节——")
    out.append("  - Claude Code: ~/.claude/projects/*/<uuid>.jsonl")
    out.append("  - Codex: ~/.codex/sessions（state_5.sqlite / jsonl）")
    out.append("  - dsh: $DSH_HOME 或 ~/.dsh/sessions/<ws>/<uuid>/session.jsonl[.zstd]")
    body = "\n".join(out)
    if a.output:
        with open(a.output, "w") as f:
            f.write(body)
        print(f"written: {a.output}")
    else:
        print(body)

if __name__ == "__main__":
    main()
