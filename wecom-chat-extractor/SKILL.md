---
name: wecom-chat-extractor
description: >-
  企业微信 Mac 5.x 本地聊天数据的唯一入口。捕获密钥、解密、查询联系人/会话/客户/群聊消息，
  导出结构化 Markdown 和 HTML 分析报告。用户要解析企业微信本地数据、企微聊天记录、
  WeCom/WXWork contacts、sessions、groups、customers、message history、local database backup、
  structured export，或分析销售沟通群时使用。捕获密钥、读取进程内存或导出明文前需本轮明确授权；
  输出用用户指定的私密目录，不默认写入项目、桌面或云盘。不要安装已归档的 yichen-wecom-local-vault。
---

# wecom-chat-extractor

Mac 企业微信 5.x 本地数据库的唯一 Skill。解密和查询在 `scripts/engine/`（上游 [yichen-wecom-local-vault](https://github.com/mcncarl/yichen-skills/tree/main/yichen-wecom-local-vault)，不改解密实现）。本目录负责统一 CLI、结构化 Markdown 和 HTML 报告。

个人微信用 `yichen-wechat-local-vault`。两套容器和加密不兼容，不要混用。

## 前置条件

- macOS，企业微信 5.x 已安装
- Python 3.10+
- 解密需要 `pycryptodome`；捕获密钥需要 `frida`
- 不要自动安装依赖，先报告缺项

## 工作流

```
status / discover     只检查，不附加进程
    → capture-key     默认 auto：hooks，失败再内存扫描
    → decrypt         明文快照
    → sessions        确认群名
    → analyze         JSON + 结构化 Markdown + HTML
```

已有密钥和快照时跳过前两步。要固定某次快照时，给查询和导出加 `--snapshot`。

没有本轮明确授权时，只运行 `status`、`discover`、`doctor`，以及已有快照上的查询。不要运行 `capture-key` 或 `decrypt`，也不要把明文导出到项目、桌面或云盘。

## 入口

```bash
SKILL_DIR="${HOME}/.agents/skills/wecom-chat-extractor"
python3 "$SKILL_DIR/scripts/wecom_pro.py" <command> [options]
```

装在 `~/.workbuddy/skills/` 或 `~/.codex/skills/` 时，换掉上面的目录即可。引擎在本 Skill 内，不再依赖另一个已安装 Skill。

## 命令

| 命令 | 作用 |
|------|------|
| `status` / `discover` / `doctor` | 检查库、数据集、依赖。不附加进程 |
| `capture-key` | 捕获密钥。方法见下表 |
| `decrypt` | 解密并合并 WAL。`--key-file` `--no-wal` `--data-dir` |
| `sessions` / `contacts` | 列出会话或联系人。`--query` `--snapshot` `--limit` |
| `history "群名"` | 会话历史。`--start` `--end` `--snapshot` |
| `search "关键词"` | 全文搜索。`--chat` `--start` `--end` `--snapshot` |
| `export "群名"` | `structured`（默认）/ `json` / `markdown` / `html` |
| `analyze "群名"` | 一次写出 JSON、结构化 Markdown、HTML |

```bash
python3 "$SKILL_DIR/scripts/wecom_pro.py" capture-key
python3 "$SKILL_DIR/scripts/wecom_pro.py" decrypt
python3 "$SKILL_DIR/scripts/wecom_pro.py" analyze "群名" --output-dir ~/output
```

## 密钥捕获

日常路径和显式路径分开。`auto` 不提权、不重签、不退出原客户端。

| `--method` | 何时用 | 默认会跑吗 |
|---|---|---|
| `auto` | 先 hooks 60 秒，失败再内存扫描 | 是 |
| `hooks` | 企微正在收发，会触发解密 | 只在指定时 |
| `memory-scan` | 企微空闲，hooks 抓不到 | 作为 auto 的第二步，或单独指定 |
| `dbkey-scan` | 上面都失败，且用户同意输入管理员密码 | 否 |
| `signed-copy` | 用户明确允许复制并重签一份企微副本 | 否 |

`--skip-hooks` 只影响 `auto`，让它直接做内存扫描。

`dbkey-scan` 只读 DbKeyManager，不注入代码；脚本会向本机要管理员密码。

`signed-copy` 把副本写到私密 Vault 的 `apps/`，不改 `/Applications/企业微信.app`。若副本被单实例机制拉起后退出，让用户自己退出原客户端再重试。不点击 UI，不代登录。

方法对比、表结构和引用消息格式见 [references/workflow.md](references/workflow.md)。库格式见 [references/database-notes.md](references/database-notes.md)。

## 多数据集

本机可能同时有主库和 Backup。`status`、`capture-key`、`decrypt` 的 `--data-dir` 要传完整目录，不接受数据集 ID。

`sessions`、`contacts`、`history`、`search`、`export`、`analyze` 没有 `--data-dir`。多数据集时先对目标目录 `decrypt`，再把那次快照路径传给 `--snapshot`。

快照默认在 `~/Library/Application Support/wecom-local-vault/snapshots/`，目录名是 `YYYYMMDD-HHMMSS-ffffff-<12位dataset_id>`。`~/.config/wecom-local-vault.json` 的 `vault_dir` 可以改这个根目录。

`wecom_pro.py` 优先用 `~/.workbuddy/binaries/python/envs/default/bin/python3`。不要往系统 Python 里装依赖。

## 安全边界

- 只读源数据库和 WAL，不写回企微容器
- 不发送消息，不点击 UI，不重启客户端，不改原始应用包
- 不关闭 SIP，不放宽系统 `taskport`
- 密钥不打印；密钥、快照、导出权限 0600，拒绝覆盖已有文件
- 回复和日志里不出现 raw key、完整账号目录、联系人内部 ID、整段私聊原文
- 明文不要放进项目、桌面、云盘或 Git

## 布局

```
wecom-chat-extractor/
├── SKILL.md
├── references/
│   ├── workflow.md
│   └── database-notes.md
└── scripts/
    ├── wecom_pro.py
    ├── key_memory_scan.py
    ├── structured_export.py
    ├── html_report.py
    └── engine/                  # 上游引擎，见 scripts/engine/UPSTREAM.md
        ├── vault_cli.py
        ├── capture_key_macos.py
        ├── scan_dbkey_manager_macos.py
        ├── wecom_crypto.py
        ├── wecom_common.py
        └── test_wecom_local_vault.py
```

## 验证

```bash
cd "$SKILL_DIR/scripts"
python3 -m py_compile *.py engine/*.py
python3 engine/test_wecom_local_vault.py
python3 wecom_pro.py --help
python3 wecom_pro.py status
```

`status` 只检查，不附加进程。
