#!/usr/bin/env python3
"""HTML analysis report generator for personal WeChat (yichen-wechat-local-vault).

Creates a self-contained HTML report with Chart.js visualizations from a
vault_cli.py history JSON export. Adapted from wecom-chat-extractor's html_report
with personal-WeChat field names and generic high-frequency word analysis (no
logistics-industry keywords baked in).

Input JSON shape:
  {"chat": "...", "username": "...", "messages": [
    {"type": "文本", "sender": "...", "time": "YYYY-MM-DD HH:MM:SS", "content": "...", ...}
  ]}
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Common Chinese stopwords for keyword extraction (lightweight, no jieba needed)
STOPWORDS = {
    "我们", "你们", "他们", "这个", "那个", "一个", "什么", "怎么", "可以", "没有",
    "现在", "因为", "所以", "但是", "如果", "已经", "还是", "就是", "这样", "那样",
    "觉得", "知道", "感觉", "其实", "应该", "可能", "或者", "一下", "一直", "一些",
    "这些", "那些", "自己", "他们", "不是", "不要", "不会", "不能", "的话", "然后",
    "不过", "只是", "只有", "还有", "的话", "好像", "真的", "确实", "当然", "比如",
    "这是", "那是", "都是", "就有", "就有", "说到", "起来", "出来", "回来", "过来",
    "下去", "下去", "这是", "是的", "好的", "好的", "好吧", "哦哦", "嗯嗯", "哈哈",
    "哈哈哈", "哈哈哈哈", "谢谢", "感谢", "不错", "厉害", "加油", "辛苦", "麻烦",
    "可能", "大概", "也许", "应该", "必须", "需要", "希望", "想要", "觉得", "认为",
    "开始", "结束", "问题", "时候", "地方", "东西", "事情", "办法", "方式", "原因",
    "今天", "明天", "昨天", "现在", "以前", "以后", "最近", "马上", "突然", "终于",
    "他们", "她们", "你们", "我们", "咱们", "别人", "大家", "自己", "哪个", "哪些",
    "的话", "的话", "那么", "这么", "多少", "几条", "几个", "有些", "任何", "所有",
    "的话", "虽然", "尽管", "即使", "除非", "除了", "无论", "不管", "只要", "只有",
    "的话", "比如", "例如", "譬如", "好比", "好像", "似乎", "也许", "或许", "大概",
    "可以", "能够", "应该", "必须", "可能", "会能", "要会", "想要", "需要", "希望",
    "这是", "那是", "说是", "算是", "成了", "到了", "看了", "想了", "做了", "说了",
    "的不", "了的", "是在", "会有", "能做", "要做", "想做", "在看", "在说", "在想",
    "一下", "一些", "一直", "一样", "一般", "一起", "一切", "所有", "有些", "任何",
    "或者", "还是", "或者", "并且", "而且", "然而", "另外", "此外", "其实", "反而",
    "而且", "不仅", "不但", "不过", "只是", "只有", "只要", "一旦", "一直", "一向",
    "只是", "只有", "只是", "只", "都", "也", "还", "又", "再", "更", "最", "很",
    "太", "能", "会", "可", "需", "应", "该", "并", "且", "但", "而", "如", "若",
    "因", "所", "之", "其", "此", "的", "了", "是", "我", "你", "他", "她", "它",
    "这", "那", "在", "有", "就", "和", "与", "为", "要", "不", "没", "一", "个",
    "上", "下", "中", "人", "说", "做", "来", "去", "到", "对", "从", "着", "把",
    "被", "给", "让", "向", "里", "外", "后", "前", "已", "将", "只", "又", "更",
    "吗", "呢", "吧", "啊", "哦", "嗯", "哈", "呵", "哎", "呀", "哇", "哟", "啦",
    "得", "地", "么", "多", "少", "好", "看", "想", "说", "做", "来", "去", "给",
}


def _extract_keywords(texts: list[str], top_n: int = 20) -> list[tuple[str, int]]:
    """Extract Chinese 2-4 char keywords by frequency (no jieba, regex-based)."""
    counter = Counter()
    for text in texts:
        # Extract 2-4 char Chinese sequences
        for m in re.finditer(r'[\u4e00-\u9fa5]{2,4}', text):
            word = m.group()
            if word in STOPWORDS:
                continue
            # Skip if all chars identical (e.g. 哈哈)
            if len(set(word)) == 1 and len(word) >= 2:
                continue
            counter[word] += 1
    return counter.most_common(top_n)


def _prepare_chart_data(data: dict) -> dict:
    msgs = data["messages"]

    # Top participants
    senders = Counter(m["sender"] for m in msgs if m.get("sender") and m["sender"] != "")
    top_senders = senders.most_common(15)

    # Daily trend
    days = Counter()
    for m in msgs:
        t = m.get("time", "")
        if t:
            days[t[:10]] += 1
    daily = sorted(days.items())

    # Message types
    types = Counter(m.get("type", "未知") for m in msgs)
    type_data = types.most_common()

    # Hourly activity
    hours = Counter()
    for m in msgs:
        t = m.get("time", "")
        if t and len(t) >= 13:
            hours[int(t[11:13])] += 1
    hourly = [(h, hours.get(h, 0)) for h in range(24)]

    # Weekday activity
    weekdays = Counter()
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for m in msgs:
        t = m.get("time", "")
        if t:
            try:
                dt = datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
                weekdays[dt.weekday()] += 1
            except (ValueError, TypeError):
                pass
    weekday_data = [(weekday_names[i], weekdays.get(i, 0)) for i in range(7)]

    # High-frequency keywords from text messages
    text_contents = [m["content"] for m in msgs if m.get("type") == "文本" and m.get("content")]
    keywords = _extract_keywords(text_contents, top_n=20)

    return {
        "top_senders": top_senders,
        "daily": daily,
        "types": type_data,
        "hourly": hourly,
        "weekdays": weekday_data,
        "keywords": keywords,
        "total_msgs": len(msgs),
        "participants": len(senders),
        "date_range": [daily[0][0] if daily else "", daily[-1][0] if daily else ""],
        "active_days": len(days),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - 聊天记录分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{ --bg:#f5f7fa; --card:#fff; --text:#1a1a2e; --muted:#6b7280; --border:#e5e7eb; --blue:#2563eb; --blue-l:#dbeafe; --red:#dc2626; --green:#16a34a; --orange:#ea580c; --purple:#7c3aed; --teal:#0d9488; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); line-height:1.6; }}
  .container {{ max-width:1200px; margin:0 auto; padding:24px 16px; }}
  .header {{ background:linear-gradient(135deg,#07c160 0%,#0d9488 100%); color:#fff; border-radius:16px; padding:32px; margin-bottom:24px; box-shadow:0 4px 20px rgba(7,193,96,0.15); }}
  .header h1 {{ font-size:24px; margin-bottom:8px; }}
  .header .sub {{ font-size:14px; opacity:0.85; }}
  .header .meta {{ display:flex; gap:24px; margin-top:16px; flex-wrap:wrap; }}
  .header .meta-item {{ background:rgba(255,255,255,0.15); border-radius:8px; padding:8px 16px; font-size:13px; }}
  .header .meta-item strong {{ font-size:20px; display:block; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-bottom:24px; }}
  .stat {{ background:var(--card); border-radius:12px; padding:20px; border:1px solid var(--border); box-shadow:0 1px 3px rgba(0,0,0,0.05); }}
  .stat .l {{ font-size:13px; color:var(--muted); margin-bottom:4px; }}
  .stat .v {{ font-size:28px; font-weight:700; color:var(--green); }}
  .stat .s {{ font-size:12px; color:var(--muted); margin-top:4px; }}
  .section {{ background:var(--card); border-radius:12px; padding:24px; margin-bottom:20px; border:1px solid var(--border); box-shadow:0 1px 3px rgba(0,0,0,0.05); }}
  .section-title {{ font-size:17px; font-weight:700; margin-bottom:16px; display:flex; align-items:center; gap:8px; }}
  .section-title::before {{ content:""; width:4px; height:18px; background:var(--green); border-radius:2px; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .grid.full {{ grid-template-columns:1fr; }}
  .box {{ position:relative; }}
  .box h3 {{ font-size:14px; color:var(--muted); margin-bottom:8px; }}
  .table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  .table th {{ text-align:left; padding:8px 12px; background:var(--bg); color:var(--muted); font-weight:600; border-bottom:2px solid var(--border); }}
  .table td {{ padding:8px 12px; border-bottom:1px solid var(--border); }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
  .footer {{ text-align:center; padding:20px; color:var(--muted); font-size:12px; }}
  @media (max-width:768px) {{ .grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{title} · 聊天记录分析</h1>
    <div class="sub">个人微信本地数据库解密分析报告 · 数据范围 {date_start} ~ {date_end}</div>
    <div class="meta">
      <div class="meta-item"><strong>{total}</strong>条消息</div>
      <div class="meta-item"><strong>{participants}</strong>位参与者</div>
      <div class="meta-item"><strong>{active_days}</strong>个活跃天</div>
    </div>
  </div>
  <div class="stats">
    <div class="stat"><div class="l">消息总量</div><div class="v">{total}</div><div class="s">已导出</div></div>
    <div class="stat"><div class="l">参与人数</div><div class="v">{participants}</div><div class="s">发过消息的成员</div></div>
    <div class="stat"><div class="l">日均消息</div><div class="v">{avg_daily}</div><div class="s">条/活跃天</div></div>
    <div class="stat"><div class="l">活跃天数</div><div class="v">{active_days}</div><div class="s">天</div></div>
  </div>
  <div class="section"><div class="section-title">消息趋势</div><div class="grid full"><div class="box"><h3>每日消息量</h3><canvas id="c1" height="60"></canvas></div></div></div>
  <div class="section"><div class="section-title">活跃度</div><div class="grid"><div class="box"><h3>按小时</h3><canvas id="c2" height="160"></canvas></div><div class="box"><h3>按星期</h3><canvas id="c3" height="160"></canvas></div></div></div>
  <div class="section"><div class="section-title">参与者 Top 15</div><div class="grid full"><div class="box"><canvas id="c4" height="100"></canvas></div></div></div>
  <div class="section"><div class="section-title">高频关键词 Top 20</div><div class="grid"><div class="box"><canvas id="c5" height="220"></canvas></div><div class="box"><h3>明细</h3><table class="table"><thead><tr><th>关键词</th><th>出现次数</th></tr></thead><tbody>{keyword_rows}</tbody></table></div></div></div>
  <div class="section"><div class="section-title">消息类型</div><div class="grid"><div class="box"><canvas id="c6" height="200"></canvas></div><div class="box"><h3>明细</h3><table class="table"><thead><tr><th>类型</th><th>数量</th><th>占比</th></tr></thead><tbody>{type_rows}</tbody></table></div></div></div>
  <div class="footer">报告生成于 {generated_at} · 数据来源：个人微信本地数据库解密快照（yichen-wechat-local-vault）</div>
</div>
<script>
const D={chart_json};
const P=['#07c160','#2563eb','#dc2626','#ea580c','#7c3aed','#0d9488','#db2777','#ca8a04','#0891b2','#4f46e5','#059669','#b91c1c','#9333ea','#0284c7','#65a30d','#c2410c','#1d4ed8','#be185d'];
new Chart(document.getElementById('c1'),{{type:'line',data:{{labels:D.daily.map(d=>d[0]),datasets:[{{data:D.daily.map(d=>d[1]),borderColor:'#07c160',backgroundColor:'rgba(7,193,96,0.1)',fill:true,tension:0.3,pointRadius:0,borderWidth:2}}]}},options:{{plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{maxTicksLimit:12,font:{{size:10}}}}}},y:{{beginAtZero:true}}}}}});
new Chart(document.getElementById('c2'),{{type:'bar',data:{{labels:D.hourly.map(h=>h[0]+':00'),datasets:[{{data:D.hourly.map(h=>h[1]),backgroundColor:'#07c160',borderRadius:4}}]}},options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true}}}}}}}});
new Chart(document.getElementById('c3'),{{type:'bar',data:{{labels:D.weekdays.map(w=>w[0]),datasets:[{{data:D.weekdays.map(w=>w[1]),backgroundColor:['#07c160','#07c160','#07c160','#07c160','#07c160','#dc2626','#dc2626'],borderRadius:4}}]}},options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true}}}}}}}});
new Chart(document.getElementById('c4'),{{type:'bar',data:{{labels:D.top_senders.map(s=>s[0]),datasets:[{{data:D.top_senders.map(s=>s[1]),backgroundColor:P,borderRadius:4}}]}},options:{{indexAxis:'y',plugins:{{legend:{{display:false}}}},scales:{{x:{{beginAtZero:true}}}}}}}});
new Chart(document.getElementById('c5'),{{type:'bar',data:{{labels:D.keywords.map(k=>k[0]),datasets:[{{data:D.keywords.map(k=>k[1]),backgroundColor:'#7c3aed',borderRadius:4}}]}},options:{{indexAxis:'y',plugins:{{legend:{{display:false}}}},scales:{{x:{{beginAtZero:true}}}}}}}});
new Chart(document.getElementById('c6'),{{type:'doughnut',data:{{labels:D.types.map(t=>t[0]),datasets:[{{data:D.types.map(t=>t[1]),backgroundColor:P}}]}},options:{{plugins:{{legend:{{position:'right',labels:{{font:{{size:11}},padding:8}}}}}}}}}});
</script>
</body>
</html>"""


def generate_html_report(input_json: str, output_html: str) -> dict:
    """Generate a self-contained HTML analysis report from a vault_cli JSON export."""
    with Path(input_json).open(encoding="utf-8") as f:
        data = json.load(f)

    cd = _prepare_chart_data(data)
    title = data.get("chat", "未知会话")
    total = cd["total_msgs"]

    type_rows = "".join(
        f'<tr><td>{t}</td><td>{c:,}</td><td><span class="badge" style="background:#dcfce7;color:#16a34a">{c/total*100:.1f}%</span></td></tr>'
        for t, c in cd["types"]
    )
    keyword_rows = "".join(
        f'<tr><td>{k}</td><td>{c}</td></tr>'
        for k, c in cd["keywords"]
    )

    html = HTML_TEMPLATE.format(
        title=title,
        date_start=cd["date_range"][0],
        date_end=cd["date_range"][1],
        total=f"{total:,}",
        participants=cd["participants"],
        active_days=cd["active_days"],
        avg_daily=total // max(cd["active_days"], 1),
        type_rows=type_rows,
        keyword_rows=keyword_rows,
        chart_json=json.dumps(cd, ensure_ascii=False),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    Path(output_html).write_text(html, encoding="utf-8")
    return {"title": title, "total": total, "output": output_html}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 html_report.py <input.json> <output.html>")
        sys.exit(1)
    summary = generate_html_report(sys.argv[1], sys.argv[2])
    print(f"Done: {summary['output']} ({summary['total']} messages)")
