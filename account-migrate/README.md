# account-migrate — WorkBuddy 账号迁移 Skill

> **项目定位**：WorkBuddy 切换账号后对话记录不见了？一键恢复。同平台账号切换后的数据合并工具，支持 Session 对话记录、Memory 长期记忆、Connector 连接器一键迁移。

**v1.5.0** · macOS 实测 · 零依赖（Python 3.8+） · MIT License

> **来源**：基于 [xiaoliuzhuan666/workbuddy-account-migrate](https://github.com/xiaoliuzhuan666/workbuddy-account-migrate) 演进（功能同源、独立维护，详见文末[致谢](#致谢)）。

---

## 你是不是遇到了这个问题？

WorkBuddy 切换账号 / 重新登录 / 换了腾讯云身份后，**之前的对话记录全没了**？长期记忆、MCP 连接器配置也看不到了？

**数据其实没丢**——它们还在磁盘上，只是 WorkBuddy 用 `user_id` 做了账号隔离，新账号的 UI 看不到旧账号的数据。

本工具一键把旧账号的数据合并到当前登录账号，**对话记录、记忆、连接器全部恢复可见**。

```
切换账号前：                       切换账号后：
┌──────────────────┐              ┌──────────────────┐
│  账号 A           │              │  账号 B           │
│  27 个对话 ✅     │    ──→      │  27 个对话 ❌     │ ← UI 看不到了
│  长期记忆 ✅      │              │  长期记忆 ❌      │ ← 文件还在磁盘上
│  MCP 配置 ✅      │              │  MCP 配置 ❌      │
└──────────────────┘              └──────────────────┘
                                         │
                                    运行迁移脚本
                                         │
                                         ▼
                                  ┌──────────────────┐
                                  │  账号 B           │
                                  │  27 个对话 ✅     │ ← 合并到当前账号
                                  │  长期记忆 ✅      │ ← 追加去重
                                  │  MCP 配置 ✅      │ ← 深度合并
                                  └──────────────────┘
```

---

## 功能特性

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

---

## 快速开始

### 安装到 WorkBuddy

```bash
git clone https://github.com/Young1108/skillhub.git /tmp/skillhub
mkdir -p ~/.workbuddy/skills
cp -r /tmp/skillhub/account-migrate ~/.workbuddy/skills/
```

重启 WorkBuddy 后，对话中直接说 **「迁移账号数据」** 即可触发（Skill 描述含关键词：切账号、迁移、同步数据、账号切换、数据丢失、记录没了）。

### 命令行使用（推荐，最直观）

```bash
cd ~/.workbuddy/skills/account-migrate
python3 scripts/migrate.py
```

**运行效果：**

```
======================================================================
WorkBuddy 账号迁移向导
======================================================================

请选择迁移方向：先选【目标账号】（接收数据），再选【源账号】（被迁移）

  序号   user_id                                  Sessions     Memory   Connectors
  ------------------------------------------------------------------------
  1      abc12345-6789-...                              18     13.0KB  17mcp/6conn
  2      def67890-1234-...                               7      5.1KB  17mcp/4conn

请选择【目标账号】（接收数据的账号，输入序号）: 1
```

输入序号即可，全程不需要知道 user_id。

### 其他模式

```bash
# 仅诊断 — 查看所有账号数据分布
python3 scripts/migrate.py --diagnose

# 指定源账号迁移（高级用户）
python3 scripts/migrate.py --source <USER_ID>

# 显式指定目标账号（不依赖登录态推断）
python3 scripts/migrate.py --source <USER_ID> --target <USER_ID>

# 跳过确认直接迁移
python3 scripts/migrate.py --source <USER_ID> --yes

# 回滚到指定备份
python3 scripts/migrate.py --rollback <TAG>

# 历史任务概览 / 恢复（旧版 tasks JSON 文件）
python3 scripts/migrate.py --list-tasks
python3 scripts/migrate.py --restore-tasks
```

---

## 迁移内容

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

---

## 工作原理

**Step 1：自动诊断** — 从数据库、Memory 文件、Connector 目录三个来源自动发现所有账号。当前登录账号以 **storage.json 的 genie.userId 为权威来源**，DB 作为辅助验证，不一致时发出警告。

**Step 2：安全备份** — 迁移前自动备份到 `~/.workbuddy/migrate_backups/{timestamp}_{uid}/`。

**Step 3：执行迁移** — Session 用 `UPDATE user_id`，Memory 逐行去重追加，Connector JSON 深度合并。

**Step 4：持久化 + 验证** — 迁移后执行 WAL checkpoint 确保数据落盘，验证源 user_id 归零确认迁移成功。

**Step 5：重启提示** — 提示重启 WorkBuddy 客户端，UI 刷新缓存后数据可见。

### 迁移方向自检（v1.5 关键新增）

历史上发生过迁移方向反了的真实事故（源/目标互换，导致历史会话留在旧账号、当前账号名下几乎为空，任务面板会话记录全部消失）。因此：

- **交互式向导**：强制先选目标、再选源，天然不会搞反
- **手动执行 SQL**（AI 在对话中直接迁移时）必须核对：
  1. **target（当前账号）必须持有当前会话**（以当前对话 session 的 user_id 为准，勿信过时的 storage.json）
  2. **source 必须持有大部分历史 session**（若 source 反而比 target 少，说明方向可能反了，立即中止）
  3. 只允许 `source → target` 方向

---

## 兼容性

| 平台 | 状态 |
|---|---|
| WorkBuddy (macOS) | ✅ 已实测 |
| WorkBuddy (Windows) | ⚠️ 路径已适配（`%APPDATA%`），未实测，欢迎反馈 |
| WorkBuddy (Linux) | ⚠️ 路径已适配（`XDG_CONFIG_HOME`），未实测，欢迎反馈 |

> 本 Skill 只解决 **WorkBuddy 同平台账号切换**的数据合并问题。跨设备同步依赖官方云端能力，不在本工具范围内。

---

## 安全规则

1. **必须先备份** — 迁移前自动创建备份，不可跳过
2. **源 ≠ 目标** — 防止自我覆盖
3. **Memory 追加不覆盖** — 不会丢失当前账号已有记忆
4. **Connector 深度合并** — 保留目标账号已有配置
5. **迁移后重启** — WorkBuddy 客户端有内存缓存
6. **备份 7 天可清** — 手动删除即可

---

## 回滚

```bash
ls ~/.workbuddy/migrate_backups/
python3 scripts/migrate.py --rollback <备份标签>
```

备份标签示例：`20260808020917_0918c8e1`（时间戳_账号前缀）。

---

## 项目结构

```
account-migrate/
├── README.md                              # 本文档
├── SKILL.md                               # WorkBuddy Skill 描述符（含 AI 手动迁移最佳实践）
├── scripts/
│   └── migrate.py                         # 核心迁移脚本（唯一代码文件）
└── references/
    └── data_isolation_map.md              # 数据隔离全景图
```

---

## FAQ

**Q: WorkBuddy 切换账号后对话记录真的没丢吗？**

A: 没丢。数据文件全部还在磁盘上，只是 UI 按 `user_id` 过滤导致看不到。本工具把这些数据合并到当前账号下即可恢复可见。

**Q: 迁移后旧账号数据还在吗？**

A: Session 的 `user_id` 被改为新账号，所以在旧账号的 UI 下不可见了。Memory 和 Connector 的源文件仍然保留，可手动清理。

**Q: 支持双向迁移吗？**

A: 支持。交互式向导可任意选目标/源；命令行可用 `--target` 直接指定目标账号、无需切换登录。Memory 按行去重、Connector 按 key 合并，反向迁移不会产生重复内容。想撤销上一次迁移，用 `--rollback` 更干净。

**Q: 迁移后任务面板的会话记录为什么还是空的？**

A: 说明自动化任务的运行会话（`is_background_automation=1` 的 session）没有随普通会话一起迁到当前账号。检查 `SELECT id, user_id FROM sessions WHERE is_background_automation=1`，把它们的 user_id 一并 UPDATE 到当前账号即可。详见 SKILL.md 的「3.4 自动化任务归属迁移」。

**Q: 可以分享给朋友用吗？**

A: 可以。Skill 是纯文件，复制 `account-migrate/` 目录到对方的 `~/.workbuddy/skills/` 即可。注意：只能迁移**同一台电脑**上的账号数据，不能跨机器把多人的数据合并到一个账号（跨机同步依赖官方云端）。

---

## 更新日志

**v1.5.0 (2026-08-08)** — 关键修复：迁移方向搞反 + 自动化任务会话记录丢失

- **Bug 修复**：迁移方向反了（source/target 互换），导致历史会话全部留在旧账号、当前账号名下几乎为空，且自动化任务面板「会话记录」不显示。新增迁移方向自检（target 必须持有当前会话、source 必须持有大部分历史、只允许 source→target）。
- **Bug 修复**：确认 automations 表有 `owner_user_id` 字段（此前文档误标为"无 user_id、无需迁移"）；任务面板会话记录依赖 automation_runs.conversationId 对应 session 的 user_id 归属，迁移 sessions 时不可跳过自动化会话。
- **文档更新**：SKILL.md 新增 3.4 自动化任务归属迁移、更新踩坑记录与最佳实践。

**v1.4.0** — 跨平台支持（storage.json 路径适配 macOS / Windows / Linux）+ 交互式向导改为手动选择目标/源账号。

**v1.3.0** — 登录态多源交叉验证（storage.json 与 DB 不一致时警告）；WAL checkpoint 保证持久化；迁移后验证源账号归零。

**v1.1.0 / v1.2.0** — 首发：Session / Memory / Connector 迁移；自动备份 + 回滚；历史任务恢复（`--list-tasks` / `--restore-tasks`）。

---

## 致谢

- [xiaoliuzhuan666/workbuddy-account-migrate](https://github.com/xiaoliuzhuan666/workbuddy-account-migrate) — 本文档的结构（问题场景、功能特性、迁移内容、工作原理、FAQ 等章节）参考自该项目，交互式向导"先选目标、再选源账号"的设计思路亦受其启发。本 Skill 的 `scripts/migrate.py` 与之功能同源、独立演进，并在 v1.5.0 中补充了**迁移方向自检**与 **automations 归属处理**（任务面板会话记录修复）两项实战验证的增强。

---

## License

[MIT](../../LICENSE) © 2026 Young1108
