---
name: agent-skill-sync
description: 把一份 skill 同时装到本机所有 AI 编程工具的全局技能目录（WorkBuddy / Codex / Cursor / Claude Code / Kiro / CodeBuddy / Grok / Doubao / Kun），或在改动后把这些工具的 skill 副本重新同步。触发词：全局 skill、全局技能、所有工具都能调用、同步 skill、skill 装到 codex/cursor、agent skills 目录、sync-skill、skill 分发。
version: 1.0.0
agent_created: true
metadata:
  short-description: 本机多工具 skill 全局分发与同步
---

# 多工具 skill 全局分发

## 核心模型

本机用「一个规范源 + 多个镜像」的方式分发 skill：

| 角色 | 路径 | 说明 |
| --- | --- | --- |
| **规范源** | `~/.agents/skills/<name>/` | 唯一真实目录。所有改动都写这里 |
| 符号链接农场 | `~/.claude/skills/`、`~/.kiro/skills/`、`~/.codebuddy/skills/` | 每项都是 `../../.agents/skills/<name>` 的软链，改了规范源自动生效 |
| 目录拷贝 | `~/.codex/skills/`、`~/.cursor/skills/`、`~/.workbuddy/skills/`、`~/.grok/skills/`、`~/Doubao/skills/`、`~/.kun/skills/` | 各自存真实副本，必须跑同步脚本 |

同一份 skill 在拷贝型目录里是独立副本，**不要直接改副本**，否则下次同步被覆盖且各工具口径不一致。

## 用法

```bash
~/.agents/scripts/sync-skill.sh <skill-name>   # 同步指定 skill 到全部目标
~/.agents/scripts/sync-skill.sh                # 列出规范源里的 skill 与各自已铺开的工具
```

脚本行为：对拷贝型目标先删同名子目录再 `cp -R`；对链接型目标重建软链。只会删除 `<目标skills目录>/<skill-name>` 这一个子目录。

脚本随本 skill 一起分发（`scripts/sync-skill.sh`）。新机器上先把脚本落到位：

```bash
mkdir -p ~/.agents/scripts
cp <仓库>/skills/agent-skill-sync/scripts/sync-skill.sh ~/.agents/scripts/
chmod +x ~/.agents/scripts/sync-skill.sh
```

新增一个 skill 的标准姿势：

```bash
mkdir -p ~/.agents/skills/<new-skill>
# 写 ~/.agents/skills/<new-skill>/SKILL.md（frontmatter 必须有 name 与 description）
~/.agents/scripts/sync-skill.sh <new-skill>
```

## 从 GitHub 拉到本机（跨机器）

技能仓库自行替换 `<你的仓库>`（约定 `skills/<name>/SKILL.md` 的私有仓库都适用）。建议克隆到固定位置 `~/Documents/workspace/<repo>`：

```bash
git clone <你的仓库> ~/Documents/workspace/<repo>
cp -r ~/Documents/workspace/<repo>/skills/* ~/.agents/skills/
mkdir -p ~/.agents/scripts
cp ~/.agents/skills/agent-skill-sync/scripts/sync-skill.sh ~/.agents/scripts/
chmod +x ~/.agents/scripts/sync-skill.sh
~/.agents/scripts/sync-skill.sh <skill-name>
```

## 反向：改完推回仓库

1. 改 `~/.agents/skills/<name>/`（规范源，唯一真改动处）
2. `~/.agents/scripts/sync-skill.sh <name>` 铺到各工具
3. `cp -R ~/.agents/skills/<name> ~/Documents/workspace/<repo>/skills/<name>`，同步更新仓库 README 的技能清单表格，再 commit & push

## 不要动的目录

工具自管 / 内置 / 远端，写了会被覆盖或造成混乱：

- `~/.cursor/skills-cursor/`（Cursor 自管，带 `.sync-manifest.json`）
- `~/.codex/skills/.system/`、`~/.codex/vendor_imports/skills/`、`~/.codex/memories/skills/`
- `~/.pi/remote/skills/`、`~/.grok/bundled/skills/`
- `~/.workbuddy/connectors/skills/`（连接器自带）
- `~/.codebuddy/skills-marketplace/skills/`
- `~/.gemini/**`（plugin / antigravity builtin）

## 校验

```bash
for p in ~/.agents/skills ~/.codex/skills ~/.cursor/skills ~/.workbuddy/skills \
         ~/.grok/skills ~/Doubao/skills ~/.kun/skills \
         ~/.claude/skills ~/.kiro/skills ~/.codebuddy/skills; do
  [ -f "$p/<skill-name>/SKILL.md" ] && echo "OK  $p" || echo "FAIL $p"
done
```

## 探测新装的工具

以后装了新的 Agent 工具，用这行找它的用户级技能目录，命中后加进同步脚本的 `COPY_TARGETS` / `LINK_TARGETS`：

```bash
find ~ -maxdepth 3 -type d -name skills 2>/dev/null | grep -v -E "node_modules|\.venv|plugins|bundled|remote|vendor_imports"
```

判断该用哪种目标：`find <dir> -maxdepth 1 -type l | wc -l` 结果等于目录项数 → 是链接农场，走 `LINK_TARGETS`；否则走 `COPY_TARGETS`。

## 生效时机

技能列表一般在进程启动时扫描。装完后各工具需要**重开会话**（部分需要重启进程）才会出现在可用技能列表里；`/` 或技能面板看不到不等于装失败，先按上面「校验」确认文件在位。
