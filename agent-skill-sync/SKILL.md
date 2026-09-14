---
name: agent-skill-sync
description: 把一份 skill 同时装到本机所有 AI 编程工具的全局技能目录（WorkBuddy / Codex / Cursor / Claude Code / Kiro / CodeBuddy / Grok / Doubao / Kun），或在改动后把这些工具的 skill 副本重新同步；含新建/校验、合并重叠 skill、批量改写（组件替换）、公开仓库泄露闸门与跨机器拉取推回。触发词：全局 skill、全局技能、所有工具都能调用、同步 skill、skill 装到 codex/cursor、agent skills 目录、sync-skill、skill 分发、新建 skill、校验 skill、合并 skill、skill 改名换组件、skill 推公开仓库、skill 泄露复核。
version: 1.1.0
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

### 写完必须过校验脚本

**别只靠肉眼检查 frontmatter 和目录结构**，用内置 skill-creator 的校验脚本过一遍（合格输出 `Skill is valid!`）：

```bash
# Codex 侧（推荐，路径稳定）
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.agents/skills/<name>

# WorkBuddy 侧（版本目录会变，用通配）
python3 ~/.workbuddy/plugins/cache/workbuddy-builtin/skill-skill-creator/*/scripts/quick_validate.py ~/.agents/skills/<name>
```

同目录还有两个能用的：

- `init_skill.py` — 生成 skill 骨架，省得手写目录与 frontmatter
- `package_skill.py` — 打包成可分发产物

要完整流程（理解用例 → 规划可复用内容 → 初始化 → 编写 → 打包 → 迭代）时，直接加载内置 skill `skill-creator` 按它的六步走。

> 说明：`SkillManage` 工具只在部分宿主会话里可用。它不可用时不要停在「没法创建 skill」，直接写文件 + 本 skill 的同步脚本即可，但**校验这一步不能省**。

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

> 目标仓库的目录约定不一样（有的用 `skills/<name>/`，有的把 skill 目录直接放仓库根），拷回去前先 `ls` 一眼，别按习惯硬套。
>
> **两个必踩的坑**：
>
> 1. `cp -R <源> <目标>` 在目标已存在时会**把源目录塞进目标里面**，变成 `<目标>/<name>/SKILL.md`。先 `rm -rf <目标>` 再拷，拷完 `find <仓库> -maxdepth 4 -name '<name>' -type d` 确认没有嵌套层。
> 2. 提交时用 `git -C <仓库根>` 显式指定仓库根，**不要 `cd $(dirname <skill目录>)`** —— skill 目录就在仓库根时 dirname 会落到仓库外面，`git add` 报 `not a repository`，而复制已经发生，形成「文件改了但没提交」的静默漏推。
>
> 推完逐仓库核验：`git -C <仓库根> status -sb` 应为 `## main...origin/main`（无领先提交），并 `shasum -a 256` 比对规范源与仓库副本一致。

## 推送到公开仓库前的闸门（必做）

**先确认目标仓库可见性，再决定推哪些 skill**：

```bash
gh repo view <org>/<repo> --json visibility --jq .visibility
```

- 含**内部信息**的 skill（内部仓库路径、内部表名 / DSN、事件名、内部产品代号、内部文档路径）**只能进私有仓库**。推到公开仓库不可逆，属于数据外泄。
- 推送前跑一遍泄露面复核，命中就先停下来问用户，不要自己判断「应该没事」：

```bash
cd ~/.agents/skills/<name>
# 按项目补内部标识词：公司名、内部仓名、内部产品代号、核心表名
for kw in <内部标识1> <内部标识2>; do
  n=$(grep -ro "$kw" . | wc -l); [ "$n" != "0" ] && echo "⚠ $kw 命中 $n 次"
done
# 内部代码路径引用密度
grep -rhoE "(app|agent|scripts|docs|tests)/[a-zA-Z0-9_/.-]+\.(py|md|sql)" . | sort -u | wc -l
```

判不准时的默认动作：**只推通用 skill，把含内部信息的留在私有仓库**，并向用户说明原因，由用户决定是否做脱敏版。

## 合并重叠 skill

发现两个 skill 职责重叠时收口为一个，**不要直接删掉被合并的**：

1. 把被合并方的独有内容折进保留方，通常落成新的一节 + 一份 `references/<topic>.md`
2. 保留方的 `description` 并入被合并方的触发词，否则以后搜不到
3. 用「使用路径」式的分叉开头（如「日常场景走 A 节 / 重型场景走 B 节」）隔离两套约束，避免被合并方的门禁规则误伤日常用法
4. 被合并方**移动到归档目录**而不是删除：`~/.agents/skills_archived/<name>.merged-<YYYYMMDD>/`；先 `cp -R` 备份、`diff -r` 校验一致，再 `mv` 原始目录进去
5. 同步保留方到各工具目录，逐个确认被合并方已从所有 skills 目录消失

## frontmatter 约定

```yaml
---
name: <kebab-case，与目录名一致>
description: <能力一句 + `触发词：…` + `不负责：…`>
version: 1.0.0
agent_created: true
---
```

`description` 是各工具**唯一**用来判断「要不要加载」的字段，必须把触发词写全（中英文、同义词、错误信息原文都算），否则技能装了也检索不到。写完后用本文「写完必须过校验脚本」那节复验。

## 批量改写 skill 内容（组件替换）

场景：skill 里某块内容整体过时或换方案（例：观测后端从 A 换成 B、鉴权方式变更、依赖库换代），需要系统性替换而不是零星改词。

1. **先 grep 定影响面，别凭印象改**：

   ```bash
   cd ~/.agents/skills/<name>
   grep -rn -i "<旧组件词>" .        # 命中明细
   grep -rln -i "<旧组件词>" .       # 涉及哪些文件，重点查 SKILL.md / references/ / agents/*.yaml
   ```

2. **把命中分三类再动手**，不分类就会改错或改漏：
   - 必须改：实现口径、配置项、模块路径、排查步骤
   - 保留但改措辞：术语、历史说明（显式标注「已废弃」）
   - 不动：同名误伤（如 `-i "arize"` 会命中 `summarize`）
3. **细则落 `references/<新组件>.md`，不要往 SKILL.md 主体堆**：配置表、映射表、排查提示放参考文件，SKILL.md 只留指针 + 硬约束，控制主文件长度。
4. **旧内容降级、不抹掉**：仓库里仍存在但已作废的文档（ADR、旧方案章节）在参考列表中保留指针并标注「口径已作废」——直接删指针会让后来看到旧文档的人无法反查。
5. **留一份迁移差异对照表**（旧 → 新：客户端 / 抽象 / 分级 / 开关 / 地址 / 凭据 / 落库字段）。排障时这张表最省时间，也是唯一值得保留旧名词的地方。
6. **改完复查**：再跑一次 `grep -rn -i "<旧组件词>" .`，确认剩余命中都属于「有意保留」（迁移对照表、废弃标注、无法改的历史字段名）。
7. **目标组件尚未落地时**，在文件顶部显式标注「模块名 / 配置项为约定命名，落地后以代码为准」，别把推测当事实传下去。

两个容易踩的坑：

- **改名会波及落库字段名（列名）**。列名属 DDL，改它要单独走迁移 —— 默认**保留列名，只改语义说明**，并在文档里写清「该列名不变、语义现由新组件产生」。
- **只改了 SKILL.md，漏掉 `references/` 与 `agents/*.yaml` 里的简述字段**（后者的 short_description 常被忽略，但它是宿主界面直接展示的文案）。

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
