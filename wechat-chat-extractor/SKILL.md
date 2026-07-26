---
name: wechat-chat-extractor
description: |
  个人微信 Mac 4.x 本地聊天数据结构化导出与分析工具。在 yichen-wechat-local-vault 解密
  能力基础上，增加结构化 Markdown 导出（引用回复解析、日期分组、消息类型标签）和
  可视化 HTML 分析报告（Chart.js 图表：消息趋势、活跃度、发言排行、高频关键词、消息类型）。
  当用户要导出个人微信聊天记录、分析微信群聊、生成群聊报告、可视化聊天统计、
  解析微信引用回复、wechat-chat-extractor 时使用。依赖 yichen-wechat-local-vault 提供核心解密与查询。
agent_created: true
---

# wechat-chat-extractor

个人微信 4.x 本地数据结构化导出与分析工具。在 `yichen-wechat-local-vault` 的 `vault_cli.py` 之上，增加三项能力：

1. **结构化 Markdown 导出** — 引用回复 `<refermsg>` XML 解析为引用块、按日期分组带星期与计数、消息类型 emoji 标签、图片 hash/截图文件名清理
2. **HTML 可视化分析报告** — 自包含单文件，Chart.js 图表（每日趋势、小时/星期活跃度、Top 15 发言者、高频关键词 Top 20、消息类型分布）
3. **一键 analyze** — 同时生成 JSON 原始数据 + 结构化 MD + HTML 报告三件套

## 前置条件

- macOS，微信 4.x 已安装
- `yichen-wechat-local-vault` skill 已部署且 vault 已解密（运行过 `decrypt_all_dbs.py`）
- Python 隔离 venv（`~/.workbuddy/binaries/python/envs/default`）含 pycryptodome / zstandard
- 零额外依赖：structured_export 与 html_report 仅用标准库 + Chart.js CDN（HTML 内嵌）

## 入口

```bash
SKILL_DIR="${HOME}/.workbuddy/skills/wechat-chat-extractor"
~/.workbuddy/binaries/python/envs/default/bin/python "$SKILL_DIR/scripts/wechat_pro.py" <command> [options]
```

## 命令

### analyze — 一键分析（最常用）

```bash
python3 wechat_pro.py analyze "群名或联系人" \
  [--start-time 2026-05-26] [--end-time 2026-07-26] \
  [--limit 10000] [--output-dir DIR]
```

自动生成三个文件到 `--output-dir`（默认当前目录）：

| 文件 | 内容 |
|------|------|
| `<群名>_chat_records.json` | 原始 JSON（vault_cli history 格式） |
| `<群名>_structured.md` | 结构化 Markdown（日期分组 + 引用解析 + 类型标签） |
| `<群名>_report.html` | 可视化 HTML 报告（浏览器直接打开） |

### export — 结构化 Markdown 导出

```bash
python3 wechat_pro.py export "群名" \
  [--start-time DATE] [--end-time DATE] \
  [--limit 10000] [--output PATH.md] [--output-dir DIR]
```

输出结构化 Markdown，相比 `vault_cli.py export --format markdown` 的原始时间线，增加：
- 按日期分组（`## 📅 2026-07-24 周五（12 条）`）
- 引用回复 `<refermsg>` 解析为 blockquote
- 系统消息（撤回等）斜体渲染
- 图片 hash / 截图文件名清理为 `[图片]` / `[截图]`

### report — HTML 分析报告

```bash
python3 wechat_pro.py report "群名" \
  [--start-time DATE] [--end-time DATE] \
  [--limit 10000] [--output PATH.html] [--output-dir DIR]
```

生成自包含 HTML（单文件，浏览器直接打开，无需服务器），含 Chart.js 图表：

- 每日消息量趋势（折线图）
- 按小时 / 按星期活跃度（柱状图，周末标红）
- 参与者 Top 15 横向柱状图
- **高频关键词 Top 20**（基于文本消息自动提取 2-4 字中文词，内置停用词过滤，无需 jieba）
- 消息类型分布（环形图 + 明细表）

### history — 原始 JSON 查询

```bash
python3 wechat_pro.py history "群名" [--limit N] [--output PATH.json]
```

委托 `vault_cli.py history`，输出原始 JSON。适合被其他脚本消费。

### status — vault 状态

```bash
python3 wechat_pro.py status
```

委托 `vault_cli.py status --format text`，检查明文库是否齐全。

## ⚠️ 关键参数说明

| 参数 | 默认 | 说明 |
|------|------|------|
| `--limit` | **10000** | 本 skill 默认调大以避免截断大群（vault_cli 原始默认 500 会截断） |
| `--start-time` / `--end-time` | 无 | 格式 `YYYY-MM-DD`，时间范围过滤 |
| `--output-dir` | 当前目录 | analyze/export/report 输出目录 |

## 工作流

```
vault 已解密（yichen-wechat-local-vault + wechat-local-vault-ops）
    │
    ① status          确认 vault 可用
    │
    ② analyze "群名"   一键三件套（JSON + MD + HTML）
    │
    ③ 浏览器打开 HTML  查看可视化报告
```

日常使用直接 ②→③。需要单独格式时用 `export`（仅 MD）或 `report`（仅 HTML）。

## 结构化导出示例

个人微信引用回复原始 content（`<refermsg>` XML）：

```xml
<refermsg><sourcename>Yang</sourcename><sourcecontent>Midjourney新副业曝光</sourcecontent></refermsg>这个方向有意思
```

结构化后：

```markdown
#### 2026-06-19 00:42:00 · 张祎

> **Yang：**
> Midjourney新副业曝光
>
> *（被引用消息）*

这个方向有意思
```

## 高频关键词提取

`html_report.py` 内置无依赖中文关键词提取（不依赖 jieba）：

1. 从 `type="文本"` 的消息提取 content
2. 正则匹配 2-4 字中文连续序列
3. 过滤内置停用词表（虚词、代词、语气词、常见无意义词）
4. 过滤全同字词（如"哈哈"）
5. 频次排序取 Top 20

适用通用场景；如需行业特定关键词分析，可修改 `html_report.py` 的 `STOPWORDS` 或在 `_extract_keywords` 后追加自定义词表。

## 与其他 skill 的关系

| Skill | 定位 | 关系 |
|-------|------|------|
| `yichen-wechat-local-vault` | 工具本体（解密 + vault_cli 查询） | 本 skill 的基础，提供 vault_cli.py |
| `wechat-local-vault-ops` | 运维手册（部署 + 抓 key + 坑） | 部署/运维指导 |
| `wechat-chat-extractor`（本 skill） | 结构化导出 + HTML 报告 | 在 vault_cli 之上增加分析导出 |
| `wecom-chat-extractor` | 企业微信版（同模式） | 参照对象，本 skill 是个人微信对应版 |

## 安全边界

继承 `yichen-wechat-local-vault` 的全部边界：

- 只读已解密 vault，不碰源数据库，不操作微信 UI
- 导出文件默认含明文聊天内容，不要放到云盘 / Git / 项目目录（除非用户明确要求）
- HTML 报告内嵌 Chart.js CDN，打开需联网；离线环境可替换为本地 chart.js

## 架构

```
wechat-chat-extractor/
├── SKILL.md                      # 本文档
└── scripts/
    ├── wechat_pro.py             # 统一 CLI（history/export/report/analyze/status）
    ├── structured_export.py      # 结构化 Markdown 导出（适配个人微信 JSON）
    └── html_report.py            # HTML 分析报告（Chart.js + 通用高频词）
```

核心查询委托 `yichen-wechat-local-vault` 的 `vault_cli.py`，本 skill 增加结构化导出与可视化报告两项能力。

## 验证

```bash
SKILL_DIR="${HOME}/.workbuddy/skills/wechat-chat-extractor"
cd "$SKILL_DIR/scripts"
python3 -m py_compile *.py
python3 wechat_pro.py --help
python3 wechat_pro.py status
python3 wechat_pro.py analyze "测试群名" --limit 50 --output-dir /tmp/wechat-test
```
