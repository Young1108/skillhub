# skillhub — WorkBuddy Skill 工具集

WorkBuddy 实用 Skill 集合：**账号迁移**（切账号后数据一键恢复）与**微信本地聊天数据提取与分析**（个人微信 Mac 4.x / 企业微信 Mac 5.x）。支持 [WorkBuddy](https://www.codebuddy.cn/)、[Codex](https://openai.com/index/introducing-codex/)、[Claude Code](https://claude.ai/code) 等支持 Skill 机制的 AI Agent 安装使用。

> ⚠️ **微信相关 Skill 仅适用于 macOS**。Windows 用户请阅读 [Windows 用户说明](#windows-用户说明)。

## Skill 列表

### 账号管理

| Skill | 定位 | 来源 |
|-------|------|------|
| **account-migrate** | 账号切换后数据合并：Session 对话记录 / Memory 长期记忆 / Connector 配置一键迁移到当前账号 | 原创（v1.5.0） |

### 个人微信（Mac 4.x）

| Skill | 定位 | 来源 |
|-------|------|------|
| **yichen-wechat-local-vault** | 基础引擎：密钥提取（frida spawn）、全量/增量解密、查询、导出 | ⚠️ 外部开源，源自 [mcncarl/yichen-skills](https://github.com/mcncarl/yichen-skills/tree/main/yichen-wechat-local-vault) |
| **wechat-local-vault-ops** | 运维手册：部署流程、首次抓 key 实战坑、日常运维 | 原创 |
| **wechat-chat-extractor** | 增强工具：结构化 Markdown 导出、HTML 可视化报告、一键分析 | 原创（参照 wecom-chat-extractor 模式） |

## account-migrate — 账号迁移 Skill 详解

> WorkBuddy 切换账号后对话记录不见了？一键恢复。**零依赖**（Python 3.8+），macOS 实测，支持 WorkBuddy / Codex / Claude Code。

### 你是不是遇到了这个问题？

WorkBuddy 切换账号 / 重新登录 / 换了腾讯云身份后，**之前的对话记录全没了**？长期记忆、MCP 连接器配置也看不到了？

**数据其实没丢**——它们还在磁盘上，只是 WorkBuddy 用 `user_id` 做了账号隔离，新账号的 UI 看不到旧账号的数据。本工具一键把旧账号的数据合并到当前登录账号，**对话记录、记忆、连接器全部恢复可见**。

### 功能特性

| 特性 | 说明 |
|---|---|
| ✅ 交互式向导 | 运行即用，先选【目标账号】再选【源账号】，无需知道 user_id，从根本上避免迁移方向搞反 |
| ✅ 跨平台路径适配 | storage.json 路径自动适配 macOS / Windows / Linux |
| ✅ Session 对话记录迁移 | 修改 SQLite 数据库中的 `user_id` 字段，对话记录全部回归 |
| ✅ Memory 长期记忆合并 | 追加式去重合并，不会丢失当前账号已有记忆 |
| ✅ Connector MCP 连接器合并 | JSON 深度合并，目标账号已有配置保留不动 |
| ✅ 自动备份 + 回滚 | 迁移前自动备份数据库、记忆、连接器，支持一键回滚 |
| ✅ WAL 安全处理 | 迁移前后执行 SQLite checkpoint，确保数据持久化 |
| ✅ 迁移方向自检（v1.5） | 手动执行 SQL 时必须核对 target 持有当前会话、source 持有大部分历史，防止方向反了 |
| ✅ 自动化任务归属处理（v1.5） | automations 表有 `owner_user_id`，任务面板的会话记录依赖 session 归属，迁移 sessions 时自动一并修复 |
| ✅ 迁移结果验证 | UPDATE 后验证源 user_id 归零，确认迁移成功 |
| ✅ 零依赖 | 仅需 Python 3.8+，无第三方包 |

### 快速开始

```bash
git clone https://github.com/Young1108/skillhub.git /tmp/skillhub
mkdir -p ~/.workbuddy/skills
cp -r /tmp/skillhub/account-migrate ~/.workbuddy/skills/
# 重启 WorkBuddy 后，对话中说「迁移账号数据」即可触发

# 或命令行直接跑（推荐，最直观）
cd ~/.workbuddy/skills/account-migrate
python3 scripts/migrate.py        # 交互式向导：先选目标账号，再选源账号
python3 scripts/migrate.py --diagnose                       # 仅诊断，查看所有账号数据分布
python3 scripts/migrate.py --source <USER_ID>               # 指定源账号
python3 scripts/migrate.py --source <USER_ID> --target <USER_ID>  # 显式指定目标账号
python3 scripts/migrate.py --rollback <TAG>                 # 回滚到指定备份
```

### 迁移内容

| 数据类型 | 存储位置 | 隔离方式 | 是否迁移 | 迁移策略 |
|---|---|---|---|---|
| Session 对话记录 | `workbuddy.db` sessions 表 | `user_id` 字段 | ✅ | UPDATE user_id |
| 长期记忆 Memory | `~/.workbuddy/memory/{uid}_memory.md` | 按文件名 | ✅ | 追加去重合并 |
| Connector 连接器配置 | `~/.workbuddy/connectors/{uid}/mcp.json` | 按子目录 | ✅ | JSON 深度合并 |
| 自动化任务归属 | `workbuddy.db` automations 表 | `owner_user_id` 字段 | ✅ | UPDATE owner_user_id（如任务归属旧账号） |
| 自动化运行会话 | `workbuddy.db` sessions 表（`is_background_automation=1`） | `user_id` 字段 | ✅ | 随 Session 一并 UPDATE，否则任务面板「会话记录」为空 |
| Skills 技能 | `~/.workbuddy/skills/` | 无隔离 | ❌ | 全局共享，无需迁移 |
| Settings / MCP / Plugins | 全局配置文件 | 无隔离 | ❌ | 全局共享，无需迁移 |

> ⚠️ **易踩坑点（v1.5 已修复）**：`automation_runs` 表的 `conversationId` 指向 sessions 表中的一条记录（`is_background_automation=1`）。任务面板按当前登录账号的 user_id 过滤 session，**如果只迁移普通会话而漏掉自动化会话，会出现「任务在、但任务面板会话记录为空」**。整体 UPDATE sessions 时会自动覆盖，无需单独处理。

### 工作原理

1. **自动诊断** — 从数据库、Memory 文件、Connector 目录三个来源自动发现所有账号。当前登录账号以 **storage.json 的 genie.userId 为权威来源**，DB 作为辅助验证，不一致时发出警告
2. **安全备份** — 迁移前自动备份到 `~/.workbuddy/migrate_backups/{timestamp}_{uid}/`
3. **执行迁移** — Session 用 `UPDATE user_id`，Memory 逐行去重追加，Connector JSON 深度合并
4. **持久化 + 验证** — 迁移后执行 WAL checkpoint 确保数据落盘，验证源 user_id 归零
5. **重启提示** — 提示重启 WorkBuddy 客户端，UI 刷新缓存后数据可见

**迁移方向自检（v1.5 关键新增）**：历史上发生过迁移方向反了的真实事故（源/目标互换，导致历史会话留在旧账号、任务面板会话记录全部消失）。交互式向导强制先选目标、再选源，天然不会搞反；手动执行 SQL 时必须核对 target 持有当前会话、source 持有大部分历史，只允许 `source → target` 方向。

### 致谢

- [xiaoliuzhuan666/workbuddy-account-migrate](https://github.com/xiaoliuzhuan666/workbuddy-account-migrate) — 本文档结构（问题场景、功能特性、迁移内容、工作原理、FAQ 等章节）参考自该项目，交互式向导「先选目标、再选源账号」的设计思路亦受其启发。本 Skill 的 `scripts/migrate.py` 与之功能同源、独立演进，并在 v1.5.0 中补充了迁移方向自检与 automations 归属处理（任务面板会话记录修复）两项实战验证的增强。

> 详细文档（兼容性 / 安全规则 / 回滚 / FAQ / 更新日志）见 [account-migrate/README.md](account-migrate/README.md)。

### 企业微信（Mac 5.x）

| Skill | 定位 | 来源 |
|-------|------|------|
| **yichen-wecom-local-vault** | 基础引擎：数据库发现、解密、查询、导出 | ⚠️ 外部开源，源自 [mcncarl/yichen-skills](https://github.com/mcncarl/yichen-skills/tree/main/yichen-wecom-local-vault) |
| **wecom-chat-extractor** | 增强工具：统一 CLI、内存扫描密钥捕获、结构化导出、HTML 报告 | 原创 |

> **`yichen-*` 系列是外部开源 Skill**，由 [mcncarl](https://github.com/mcncarl) 开发，遵循其原始 LICENSE。本仓库仅做打包分发，不修改其核心逻辑。增强层 Skill 依赖基础引擎提供的能力。

## 架构关系

### 个人微信

```
用户
 │
 ▼
wechat-chat-extractor (增强层)
 │  ├── wechat_pro.py         统一 CLI 入口
 │  ├── structured_export.py  结构化 Markdown 导出（refermsg 解析、日期分组）
 │  └── html_report.py        HTML 分析报告（Chart.js + 通用高频词）
 │
 ▼ 调用 vault_cli.py
 │
yichen-wechat-local-vault (基础层)
 │  ├── extract_keys.py       frida spawn 抓 PBKDF2 密钥
 │  ├── decrypt_all_dbs.py    全量/增量解密
 │  └── vault_cli.py          统一查询/导出
 │
 ▼ 部署/运维指导
 │
wechat-local-vault-ops (运维手册)
    └── SKILL.md              部署流程、macOS SIP 抓 key 坑、日常运维
```

### 企业微信

```
用户
 │
 ▼
wecom-chat-extractor (增强层)
 │  ├── wecom_pro.py          统一 CLI 入口
 │  ├── key_memory_scan.py    Frida 内存扫描（密钥捕获 fallback）
 │  ├── structured_export.py  结构化 Markdown 导出
 │  └── html_report.py        HTML 分析报告
 │
 ▼ 调用
 │
yichen-wecom-local-vault (基础层)
    ├── vault_cli.py          解密/查询/导出
    ├── capture_key_macos.py  标准 Frida hooks 密钥捕获
    ├── wecom_crypto.py       wxSQLite3 AES-128 解密
    └── wecom_common.py       数据库发现/密钥管理
```

## 适用机型与环境

| 项目 | 个人微信 | 企业微信 |
|------|----------|----------|
| 操作系统 | **macOS**（Apple Silicon 或 Intel） | **macOS**（Apple Silicon 或 Intel） |
| 客户端版本 | 微信 Mac **4.x** | 企业微信 Mac **5.x** |
| Python | 3.10+ | 3.10+ |
| 核心依赖 | frida、pycryptodome、zstandard | frida、pycryptodome |
| 密钥捕获 | frida spawn 模式（hook PBKDF2） | frida hooks / 内存扫描 |

> macOS 系统完整性保护（SIP）开启状态下，个人微信必须用 spawn 模式抓 key（attach 会 PermissionDenied）。详见 [wechat-local-vault-ops/SKILL.md](wechat-local-vault-ops/SKILL.md)。

## 安装

### 前置条件

- macOS（Apple Silicon 或 Intel）
- 个人微信 4.x 和/或企业微信 5.x 已安装
- Python 3.10+

### 安装到不同 Agent

本 Skill 遵循通用的 Skill 目录结构（`SKILL.md` + `scripts/` + `references/`），可安装到任何支持该机制的 AI Agent：

#### WorkBuddy

```bash
git clone https://github.com/Young1108/wechat-skills.git /tmp/wechat-skills
mkdir -p ~/.workbuddy/skills
cp -r /tmp/wechat-skills/* ~/.workbuddy/skills/  # 复制全部 skill
# 或按需复制：
# cp -r /tmp/wechat-skills/account-migrate ~/.workbuddy/skills/
# cp -r /tmp/wechat-skills/yichen-wechat-local-vault ~/.workbuddy/skills/
# cp -r /tmp/wechat-skills/wechat-local-vault-ops ~/.workbuddy/skills/
# cp -r /tmp/wechat-skills/wechat-chat-extractor ~/.workbuddy/skills/
```

#### Codex (OpenAI)

```bash
git clone https://github.com/Young1108/wechat-skills.git /tmp/wechat-skills
mkdir -p ~/.codex/skills
cp -r /tmp/wechat-skills/* ~/.codex/skills/
```

#### Claude Code

```bash
git clone https://github.com/Young1108/wechat-skills.git /tmp/wechat-skills
mkdir -p ~/.claude/skills
cp -r /tmp/wechat-skills/* ~/.claude/skills/
```

#### 其他 Agent

将 skill 目录复制到你的 Agent 对应的 skills 目录即可。Skill 通过 `SKILL.md` 中的 `name` 和 `description` 字段被 Agent 识别和加载。

### 安装 Python 依赖

建议在隔离 venv 中安装，避免污染系统 Python 环境：

```bash
# 创建隔离 venv（WorkBuddy 示例）
python3 -m venv ~/.workbuddy/binaries/python/envs/default

# 安装依赖
~/.workbuddy/binaries/python/envs/default/bin/pip install frida pycryptodome zstandard
```

> 个人微信的 `zstandard` 必须预装（脚本不会自动安装）。企业微信只需 `frida` 和 `pycryptodome`。

### 验证安装

```bash
# 个人微信
SKILL_DIR=~/.workbuddy/skills/wechat-chat-extractor
python3 "$SKILL_DIR/scripts/wechat_pro.py" --help
python3 "$SKILL_DIR/scripts/wechat_pro.py" status

# 企业微信
SKILL_DIR=~/.workbuddy/skills/wecom-chat-extractor
python3 "$SKILL_DIR/scripts/wecom_pro.py" --help
python3 "$SKILL_DIR/scripts/wecom_pro.py" status
```

## 使用

### account-migrate — 账号迁移

完整用法见上方 [account-migrate — 账号迁移 Skill 详解](#account-migrate--账号迁移-skill-详解)（功能特性 / 快速开始 / 迁移内容 / 工作原理 / 致谢）与 [account-migrate/README.md](account-migrate/README.md)。一句话触发：对话中直接说 **「迁移账号数据」**，或命令行跑 `python3 ~/.workbuddy/skills/account-migrate/scripts/migrate.py`，**迁移后必须重启 WorkBuddy 客户端生效**。

### 在 AI Agent 中使用

安装到 skills 目录后，在对话中直接说：

> 用 wechat-chat-extractor 分析 XXX 群的聊天记录
>
> 用 wecom-chat-extractor 解析企业微信 XXX 群

Agent 会自动识别 Skill、加载工作流、执行全流程。

### 个人微信 — 命令行使用

```bash
SKILL_DIR=~/.workbuddy/skills/wechat-chat-extractor
PYTHON=~/.workbuddy/binaries/python/envs/default/bin/python

# 首次使用：抓 key → 全量解密 → 分析
# 1. 抓 key（需退出微信，frida spawn 模式，详见 wechat-local-vault-ops/SKILL.md）
$PYTHON ~/.workbuddy/skills/yichen-wechat-local-vault/scripts/extract_keys.py --mode spawn --targets all --duration 240

# 2. 全量解密
$PYTHON ~/.workbuddy/skills/yichen-wechat-local-vault/scripts/decrypt_all_dbs.py --mode full

# 3. 一键分析（JSON + 结构化 MD + HTML 报告）
$PYTHON "$SKILL_DIR/scripts/wechat_pro.py" analyze "群名" --output-dir ~/output

# 后续日常：增量刷新 + 分析
$PYTHON ~/.workbuddy/skills/yichen-wechat-local-vault/scripts/decrypt_all_dbs.py --mode incremental
$PYTHON "$SKILL_DIR/scripts/wechat_pro.py" analyze "群名" --output-dir ~/output
```

### 企业微信 — 命令行使用

```bash
SKILL_DIR=~/.workbuddy/skills/wecom-chat-extractor

# 首次使用：捕获密钥 → 解密 → 分析
python3 "$SKILL_DIR/scripts/wecom_pro.py" capture-key
python3 "$SKILL_DIR/scripts/wecom_pro.py" decrypt
python3 "$SKILL_DIR/scripts/wecom_pro.py" analyze "群聊名称" --output-dir ~/output

# 后续使用（已有密钥和快照）只需最后一步
python3 "$SKILL_DIR/scripts/wecom_pro.py" analyze "群聊名称" --output-dir ~/output
```

### 所有命令

#### 个人微信（wechat-chat-extractor）

| 命令 | 说明 |
|------|------|
| `status` | 检查 vault 状态 |
| `history` | 原始 JSON 历史查询 |
| `export` | 结构化 Markdown 导出 |
| `report` | HTML 分析报告 |
| `analyze` | 一键分析（JSON + 结构化 MD + HTML 报告） |

#### 企业微信（wecom-chat-extractor）

| 命令 | 说明 |
|------|------|
| `status` | 检查数据库状态 |
| `capture-key` | 捕获解密密钥（auto/hooks/memory-scan） |
| `decrypt` | 解密数据库到明文快照 |
| `sessions` | 列出/搜索会话 |
| `contacts` | 列出/搜索联系人 |
| `history` | 查询指定会话历史 |
| `search` | 全文搜索消息 |
| `export` | 导出（json/markdown/structured/html） |
| `analyze` | 一键分析（JSON + 结构化 MD + HTML 报告） |

详细文档见各 Skill 的 `SKILL.md`。

## 输出示例

`analyze` 命令生成三个文件：

| 文件 | 说明 |
|------|------|
| `<群名>_chat_records.json` | 原始 JSON 数据 |
| `<群名>_structured.md` | 结构化 Markdown（解析引用消息、日期分组、类型标签） |
| `<群名>_report.html` | HTML 可视化报告（Chart.js 图表，浏览器直接打开） |

**个人微信 HTML 报告**包含：消息趋势、活跃度分析（小时/星期）、参与者排行、高频关键词（自动提取，通用场景）、消息类型分布。

**企业微信 HTML 报告**包含：消息趋势、活跃度分析、参与者排行、目的国家、物流方式、货物类型、价格关键词等业务维度。

## Windows 用户说明

⚠️ **本仓库所有 Skill 仅适用于 macOS，不支持 Windows。** Windows 用户需自行适配转换，主要差异：

| 维度 | macOS（本仓库） | Windows（需自行适配） |
|------|-----------------|----------------------|
| 客户端 | 微信 Mac 4.x / 企业微信 Mac 5.x | 微信 Windows 版 / 企业微信 Windows 版 |
| 数据库路径 | `~/Library/Containers/com.tencent.xinWeChat/...` | `%APPDATA%\Tencent\WeChat\...`（路径结构完全不同） |
| 密钥提取 | frida spawn hook PBKDF2（macOS SIP 相关） | 需用 Windows 内存读取或其他方法 |
| 数据库加密 | SQLCipher AES-256-CBC（PBKDF2 派生） | 表结构可能因版本不同有差异 |
| frida 用法 | spawn + ad-hoc 重签名 | Windows 无需重签名，但注入方式不同 |

### Windows 替代方案参考

Windows 用户建议参考以下开源项目自行实现等价能力：

- [PyWxDump](https://github.com/xaoyaoo/PyWxDump) — 微信 Windows 版数据库解密与导出（成熟项目）
- [WeChatMsg](https://github.com/LC044/WeChatMsg) — 微信聊天记录导出工具
- [wxdump](https://github.com/xaoyaoo/PyWxDump) — 同上

这些项目针对 Windows 微信，提供密钥获取、数据库解密、消息导出等能力。本仓库的结构化导出与 HTML 报告逻辑（`structured_export.py` / `html_report.py`）可参照复用，但底层数据库访问与密钥提取需替换为 Windows 方案。

> 本仓库**不提供** Windows 适配，也不会计划支持。欢迎社区 fork 后自行适配。

## 安全说明

- 只读操作，不修改微信/企业微信源数据库
- 不发送消息、不点击 UI、不重启客户端（个人微信抓 key 需退出微信，用 SIGTERM 优雅退出）
- 密钥不显示在终端，文件权限 0600
- 明文数据不放进项目/桌面/云盘/Git
- 详见各 Skill 的 `SKILL.md` 安全边界章节

## 致谢

- [mcncarl/yichen-skills](https://github.com/mcncarl/yichen-skills) — `yichen-wechat-local-vault` 与 `yichen-wecom-local-vault` 的原始作者，提供了核心的密钥提取、数据库解密与查询能力
- [frida](https://frida.re/) — 动态代码插桩框架，密钥提取的基础工具
- [Chart.js](https://www.chartjs.org/) — HTML 报告的可视化图表库

## License

MIT License — 详见 [LICENSE](LICENSE)。

> `yichen-*` 系列 Skill 遵循其原始作者 [mcncarl](https://github.com/mcncarl) 的 LICENSE。本仓库的原创 Skill（`wechat-chat-extractor`、`wechat-local-vault-ops`、`wecom-chat-extractor`）遵循 MIT License。
