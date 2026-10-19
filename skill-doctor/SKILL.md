---
name: skill-doctor
description: 在用 skill 的复利迭代器——任务收尾时把本次真实使用经验复盘成补丁，安全落盘并记入账本，让同一个 skill 在新场景下越用越准（观察→提炼→判定→落盘→记账）。触发词：skill 复盘、迭代 skill、优化 skill、skill-doctor、沉淀本次经验、把这次经验写进 skill、skill 越用越准、skill 补丁、复盘这个技能、纠错沉淀、skill 迭代账本。不负责：从零创建新 skill（走 skill-creator）、多工具分发与仓库推送的执行细节（走 agent-skill-sync）、专家包（走 expert-manager）、代码库重构（走 code-review / improve-codebase-architecture）。
version: 1.0.3
agent_created: true
metadata:
  short-description: skill 复利迭代（复盘→补丁→账本）
---

# skill-doctor · 让在用的 skill 复利增长

一个 skill 的价值不在写完那天，在于用得越多、覆盖场景越准。本 skill 只做一件事：**把每次真实使用变成对 skill 的最小可验证补丁，并留下可回溯的账本**。

## 与相邻 skill 的边界

| 需求 | 走谁 |
| --- | --- |
| 从零造一个新 skill | `skill-creator` |
| 装到 7 个工具的目录、推私有/公开仓库、合并重叠 skill | `agent-skill-sync` |
| **用完之后迭代在用 skill** | **本 skill** |

## 触发时机

**A. 自动自检（任务收尾时自查，命中任一即触发）**

1. 本次任务实际加载并执行了某个 skill，且工具调用 ≥ 8 次
2. 过程中出现**纠错**：我改过一版、用户纠正过、报错后换路径才成功
3. 出现 **skill 未覆盖的步骤**：临时补了命令/参数/判断，skill 里没有
4. 同一个 skill 在**账本里没记录过的新场景**下被使用

**B. 手动口令**：「skill 复盘」「迭代 xx skill」「把这次经验写进 xx skill」「跑一下 skill-doctor」。

自动触发时**先判断值不值得动**：命中 no-op 就不改、只在账本留一行观察（见判定矩阵）。

## 四步循环

参照 Hermes Agent 的学习闭环（observe → distill → reuse → refine）改造为显式流程——Hermes 靠后台 Review Agent 自动跑，本机没有常驻进程，所以由本 skill 在会话内显式驱动。

### 1. Observe — 只写事实

| 字段 | 内容 |
| --- | --- |
| skill | 名称 + 当前版本 |
| 场景 | 一句话，带可辨识特征（不是"处理数据"，而是"用 xx 查 Prod 表缺列时的口径核对"） |
| 命中 | 走了哪些章节；哪些章节没提但实际需要 |
| 卡点 | 报错原文 / 用户纠正原话 / 我改动的方向 |
| 正确做法 | 最终生效的那条路径 |
| 证据 | 命令输出、文件路径、diff、行号 |

**没有证据的推测不进下一步**，标 `[待验证]` 留在账本观察区。

### 2. Distill — 提炼成可复用断言

把事实压成 1–3 条断言，每条都要能回答：「下次遇到什么信号时，执行什么动作，验收看什么」。

反例（不可用）：「要注意权限问题」。
正例（可用）：「某接口用默认身份读返回 3380004 → 换 `--profile <bot-app-id> --as bot`，验收：正文能读出非空」。

### 3. Decide — 判定动作（防膨胀的核心）

| 观察到的形态 | 动作 | 说明 |
| --- | --- | --- |
| 新增坑位 / 边界条件 / 命令参数 / 报错原文 | **patch** | 并进已有章节，最小改动 |
| 只是措辞不准、触发词缺失导致检索不到 | **patch** | 优先改 `description` |
| 原做法被证伪 | **correct** | 立即改正文，旧做法标「已作废」，不留模糊表述 |
| 同一 skill 出现第二套**约束冲突**的流程 | **split** | 新开 skill，原 skill 顶部加分流指针（日常走 A / 重型走 B） |
| 与另一 skill 职责重叠 | **merge** | 交给 `agent-skill-sync` 的合并流程，被合方进 `~/.agents/skills_archived/`，不直接删 |
| 一次性场景、现有正文已覆盖、只是"这次做对了"无从泛化 | **no-op** | 不写。只在账本「观察未采纳」留一行 |
| 无验证证据的猜测 | **no-op** | 标 `[待验证]`，等第二次复现再动 |

**默认倾向 patch，不是重写。** 同一 skill 连续 no-op ≥ 3 次说明触发阈值太松，收紧条件 A。

### 4. Land — 落盘、同步、记账

落盘闸门（全过才写）：

1. **可执行**：含命令 / 路径 / 参数 / 验收判据，不是感想
2. **有时机**：写清"什么时候走这一步"，而非只写"要注意"
3. **不重复**：现有正文未覆盖；已覆盖则改原句，不新加一段
4. **有证据**：来自本次实测输出或用户明确表述
5. **不越界**：`agent_created: true` 才可直接改；他人的 / 内置的 skill（如 `writing-for-agents`、matt pocock 系列、`skill-creator`）只产出建议 patch 或建本地 override 副本，不改原目录
6. **不膨胀**：`SKILL.md` 主体 ≤ 200 行，细则进 `references/`

落点铁律（本机唯一真改动处，改副本会被同步覆盖）：

```bash
# 1) 改规范源
#    ~/.agents/skills/<name>/          唯一真改动处
# 2) 铺到各工具
~/.agents/scripts/sync-skill.sh <name>
# 3) 校验 frontmatter / 目录结构
python3 ~/.workbuddy/plugins/cache/workbuddy-builtin/skill-skill-creator/*/scripts/quick_validate.py ~/.agents/skills/<name>
```

推仓库时先确认可见性：含内部信息（内部仓路径、表名/DSN、事件名、产品代号）**只进私有仓库**。细节见 `agent-skill-sync` 的泄露闸门，不在此重复。

## 版本号规则

| 改动 | 版本 |
| --- | --- |
| 措辞修正、新增一行坑位、补触发词 | `z+1` |
| 新增章节 / 新流程分支 / 新增 `references/` 文件 | `y+1` |
| 职责或结构重写、split | `x+1` |

## 账本

账本目录：`~/.agents/skill-ledger/<skill-name>.md`（**与 `skills/` 平级**，故意放在 skill 目录外——否则会随 `sync-skill.sh` 铺到 7 个工具目录、跟着推仓库，泄露个人使用痕迹）。

结构、字段、示例见 [`references/ledger-format.md`](references/ledger-format.md)。初始化：

```bash
~/.agents/skills/skill-doctor/scripts/doctor.sh --init <skill-name>
```

任何时候**不写账本 = 没复盘**。账本是复利的本金记录，skill 正文只吸收已固化的结论。

## 体检

```bash
~/.agents/skills/skill-doctor/scripts/doctor.sh            # 全量体检
~/.agents/skills/skill-doctor/scripts/doctor.sh <name>...  # 指定 skill
```

检查项：frontmatter 完整性、`description` 是否带触发词、分发状态、`SKILL.md` 行数、账本缺失 / 长期未迭代 / 未采纳积压、跨 skill 触发词重叠（疑似职责重复）。

对 `agent_created` 非 `true` 的**外部 skill**（`writing-for-agents`、`caveman`、matt pocock 系列等），脚本只给 `ℹ` 提示，不报成缺陷——它们的正文迭代只能产出建议 patch 或建本地 override 副本（见落盘闸门第 5 条）。它们的账本仍值得记（记录的是你的使用经验，不是它们的正文）。

## 反面清单

- 不把"这次做对了"写成 skill 内容——**没被证伪或纠错过的顺利路径，不构成补丁**
- 不在 `no-op` 判定下强行写入换"有产出"的观感
- 不把细则堆进 `SKILL.md` 主体
- 不改各工具目录下的副本，也不改他人/内置 skill 的原目录
- 不同步、不推仓库就结束——落盘没铺开等于没生效
