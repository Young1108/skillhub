---
name: 账号迁移工具
description: WorkBuddy 账号切换后一键同步数据，将旧账号的 Session 历史、Memory 记忆、Connector 配置迁移到当前账号。触发关键词：切账号、迁移、同步数据、账号切换、数据丢失、记录没了。
version: 1.5.0
agent_created: true
---

# 账号迁移工具

WorkBuddy 切换账号后，数据通过 `user_id` 隔离，旧账号的 Session、Memory、Connectors 在新账号下不可见。本 Skill 实现一键迁移，将所有历史数据合并到当前登录账号。

## 快速使用

**最简方式（交互式向导，用户无需知道 user_id）：**

```bash
python3 scripts/migrate.py
```

运行后自动诊断、列出可选账号、用户输入序号即可。

**其他模式：**

```bash
python3 scripts/migrate.py --diagnose              # 仅诊断，查看数据分布
python3 scripts/migrate.py --source <USER_ID>      # 指定源账号迁移（高级用户）
python3 scripts/migrate.py --rollback <TAG>        # 回滚到指定备份
```

## 问题背景

WorkBuddy 数据存储架构：**本地优先 + 账号隔离**

| 数据类型 | 存储位置 | 隔离方式 | 切账号后 |
|:---|:---|:---|:---|
| Session 历史 | `workbuddy.db` sessions 表 | `user_id` 字段 | ❌ 不可见 |
| 长期记忆 Memory | `~/.workbuddy/memory/{user_id}_memory.md` | 按文件名 | ❌ 不可见 |
| Connectors | `~/.workbuddy/connectors/{user_id}/` | 按子目录 | ❌ 不可见 |
| **历史任务** | `~/.workbuddy/tasks/{session_id}/*.json` | 按 session | ⚠️ 文件在但 UI 不读 |
| Skills | `~/.workbuddy/skills/` | 无隔离 | ✅ 可见 |
| Settings/MCP/Plugins | 全局文件 | 无隔离 | ✅ 可见 |
| 工作空间 Memory | `{workspace}/.workbuddy/memory/` | 绑定工作空间 | ✅ 可见 |

## 迁移执行流程

### Phase 1：环境诊断

1. 自动读取当前登录 `user_id`（**多源交叉验证**，见下方说明）
2. 自动扫描所有已有 `user_id`：
   - `workbuddy.db` sessions 表：`SELECT DISTINCT user_id FROM sessions`
   - `~/.workbuddy/memory/` 下的 `*_memory.md` 文件
   - `~/.workbuddy/connectors/` 下的子目录
3. 展示对比表格，用户输入序号选择要迁移的源账号（无需知道 user_id）

**⚠️ 获取当前 user_id 的关键逻辑（v1.3 修复）**：

账号切换后，`storage.json` 中的 `genie.userId` 可能**没有同步更新**，仍为旧 ID。如果脚本误读旧 ID 作为 target，会导致"源=目标，无需迁移"的假象。

修复策略：**优先从 DB 最新 session 推断，而非 storage.json**：
```python
# 方法1（最可靠）：DB 中最新创建的 session 的 user_id
cur.execute("SELECT user_id FROM sessions ORDER BY created_at DESC LIMIT 1")

# 方法2（备选）：storage.json 中的 genie.userId
data.get("genie.userId", "")

# 两者不一致时，优先用 DB 的值并发出警告
```

**AI 手动迁移时的最佳实践**：

当 AI 在对话中直接执行迁移（而非运行 migrate.py），应：
1. 先查询 `SELECT user_id, COUNT(*) FROM sessions GROUP BY user_id` 看分布
2. 通过当前对话 session 的 user_id 确定目标 ID（最可靠）
3. **不要**依赖 storage.json 的 genie.userId（可能过时）
4. **⚠️ 迁移方向自检（v1.5 必做，防方向搞反）**：执行 UPDATE 前打印两侧分布并核对——
   - **target（当前账号）必须持有当前会话**（`SELECT id FROM sessions WHERE id='<当前session_id>'` 的 user_id）
   - **source 必须持有大部分历史 session**（数量应远大于 target 侧的历史数；若 source 反而比 target 少，或 target 侧已有大量历史，说明方向可能反了，中止并重新确认）
   - 只允许 `UPDATE ... SET user_id=target WHERE user_id=source`（source→target），禁止反向
5. 执行 UPDATE 后**必须**做 `PRAGMA wal_checkpoint(TRUNCATE)` 确保持久化
6. 验证 `SELECT COUNT(*) FROM sessions WHERE user_id = '{sourceID}'` 确认归零
7. **重启客户端后才生效**（客户端有 DB 内存缓存），并让用户确认「任务面板会话记录」等 UI 恢复正常

### Phase 2：备份（必须）

1. 备份 `workbuddy.db`：
   ```bash
   cp ~/.workbuddy/workbuddy.db ~/.workbuddy/workbuddy.db.bak.$(date +%Y%m%d%H%M%S)
   ```
2. 备份 Memory 文件：
   ```bash
   cp ~/.workbuddy/memory/{target_user_id}_memory.md \
      ~/.workbuddy/memory/{target_user_id}_memory.md.bak.$(date +%Y%m%d%H%M%S)
   ```
3. 备份 Connectors：
   ```bash
   cp -r ~/.workbuddy/connectors/{target_user_id}/ \
      ~/.workbuddy/connectors/{target_user_id}.bak.$(date +%Y%m%d%H%M%S)/
   ```

### Phase 3：执行迁移

#### 3.1 Session 历史迁移

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('$HOME/.workbuddy/workbuddy.db')
cur = conn.cursor()

# 迁移前 WAL checkpoint
cur.execute('PRAGMA wal_checkpoint(TRUNCATE)')

# 执行迁移
cur.execute(\"UPDATE sessions SET user_id = '{target_user_id}' WHERE user_id = '{source_user_id}'\")
print(f'Migrated {cur.rowcount} sessions')
conn.commit()

# 迁移后 WAL checkpoint（确保持久化）
cur.execute('PRAGMA wal_checkpoint(TRUNCATE)')
print(f'WAL checkpoint: {cur.fetchone()}')

# 验证源 user_id 归零
cur.execute(\"SELECT COUNT(*) FROM sessions WHERE user_id = '{source_user_id}'\")
remaining = cur.fetchone()[0]
if remaining > 0:
    print(f'⚠️ 警告：源账号仍有 {remaining} 个 session 未迁移！')
else:
    print('✅ 验证通过：源账号 session 已全部迁移')

conn.close()
"
```

**注意**：
- 这是**合并**操作，不是覆盖。只改变旧 session 的 user_id，不影响当前账号已有的 session
- 迁移后旧账号的 session 在 UI 上"消失"，但所有数据归到新账号下可见
- **必须包含自动化任务（automations）关联的 session**：`automation_runs.conversationId` 就是 sessions 表中的一行（`is_background_automation=1`）。整体 UPDATE 后它们自动归属当前账号，任务面板的"会话记录"才能显示。若只迁移普通会话而漏掉这些，会出现"任务在、会话记录没有"的现象

#### 3.4 自动化任务归属迁移

`automations` 表有 `owner_user_id` 字段，若任务本身也归属旧账号，需一并修正：

```bash
python3 -c "
import sqlite3, os
conn = sqlite3.connect(os.path.expanduser('~/.workbuddy/workbuddy.db'))
cur = conn.cursor()
cur.execute(\"UPDATE automations SET owner_user_id=? WHERE owner_user_id=?\", (TARGET, SOURCE))
print('automations updated:', cur.rowcount)
conn.commit()
cur.execute('PRAGMA wal_checkpoint(TRUNCATE)')
conn.close()
"
```

验证：
- `SELECT user_id, COUNT(*) FROM sessions GROUP BY user_id` → 源账号归零
- `SELECT owner_user_id FROM automations` → 全部为当前账号
- `SELECT id, user_id FROM sessions WHERE is_background_automation=1` → 自动化会话归属当前账号

#### 3.2 Memory 迁移

Memory 是追加式文本文件，策略是**合并而非覆盖**：

```bash
python3 -c "
import os
home = os.path.expanduser('~')
src = f'{home}/.workbuddy/memory/{source_user_id}_memory.md'
dst = f'{home}/.workbuddy/memory/{target_user_id}_memory.md'

if not os.path.exists(src):
    print('No source memory file, skipping')
elif not os.path.exists(dst):
    # 目标不存在，直接复制
    with open(src) as f: content = f.read()
    with open(dst, 'w') as f: f.write(content)
    print('Copied memory (target was empty)')
else:
    # 目标已存在，追加去重
    with open(src) as f: src_content = f.read()
    with open(dst) as f: dst_content = f.read()
    # 找出源中有但目标中没有的段落
    src_lines = set(src_content.strip().split('\n'))
    dst_lines = set(dst_content.strip().split('\n'))
    new_lines = [l for l in src_content.strip().split('\n') if l not in dst_lines]
    if new_lines:
        with open(dst, 'a') as f:
            f.write('\n\n## Migrated from {source_user_id}\n\n')
            f.write('\n'.join(new_lines))
        print(f'Appended {len(new_lines)} unique lines')
    else:
        print('No new content to migrate')
"
```

#### 3.3 Connector 配置迁移

Connector 配置是 JSON 文件，策略是**深度合并**（目标没有的 key 从源补充，已有的保留）：

```bash
python3 -c "
import json, os, shutil
home = os.path.expanduser('~')
src_dir = f'{home}/.workbuddy/connectors/{source_user_id}'
dst_dir = f'{home}/.workbuddy/connectors/{target_user_id}'

for fname in ['mcp.json', 'connector-states.json']:
    src_file = os.path.join(src_dir, fname)
    dst_file = os.path.join(dst_dir, fname)
    if not os.path.exists(src_file):
        continue
    with open(src_file) as f: src_data = json.load(f)
    if os.path.exists(dst_file):
        with open(dst_file) as f: dst_data = json.load(f)
        # 深度合并
        if isinstance(src_data, dict) and isinstance(dst_data, dict):
            for k, v in src_data.items():
                if k not in dst_data:
                    dst_data[k] = v
            with open(dst_file, 'w') as f: json.dump(dst_data, f, indent=2)
            print(f'Merged {fname}')
        else:
            # 非字典类型，不覆盖
            print(f'Skipped {fname} (type conflict)')
    else:
        with open(dst_file, 'w') as f: json.dump(src_data, f, indent=2)
        print(f'Copied {fname}')
"
```

### Phase 4：验证

1. 查询 sessions 数量：
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('$HOME/.workbuddy/workbuddy.db')
   cur = conn.cursor()
   cur.execute('SELECT user_id, COUNT(*) FROM sessions GROUP BY user_id')
   for row in cur.fetchall():
       print(f'  {row[0]}: {row[1]} sessions')
   conn.close()
   "
   ```
2. 检查 Memory 文件是否存在且非空
3. 检查 Connectors 配置是否完整

### Phase 5：收尾

- 告知用户**重启 WorkBuddy 客户端**让变更生效
- 备份文件保留 7 天，可手动删除
- 如果迁移有问题，用备份恢复：
  ```bash
  cp ~/.workbuddy/workbuddy.db.bak.{timestamp} ~/.workbuddy/workbuddy.db
  ```

### Phase 6：历史任务恢复（新版兼容）

**问题**：新版 WorkBuddy 的 `/todos` 面板只读取当前 session 的内存数据，不会扫描 `~/.workbuddy/tasks/` 下的历史 JSON 文件。迁移后这些任务文件虽然还在磁盘上，但 UI 不可见。

**诊断**：

```bash
python3 scripts/migrate.py --list-tasks
```

输出示例：
```
📋 7e46a1bb... | WorkBuddy会议纪要生成与账号迁移工具开发
   13 个任务: 12 完成 / 1 待办
   🔲 待办: 调研 WorkBuddy 数据存储与账号切换机制
```

**恢复方式一：AI 直接用 TaskCreate 创建（推荐）**

这是最可靠的方式，因为 TaskCreate 创建的任务会立即出现在 `/todos` 面板：

```bash
python3 scripts/migrate.py --restore-tasks --generate-commands
```

会生成每个 pending 任务的 TaskCreate 参数 JSON，将它们逐个传给 AI 的 TaskCreate 工具即可。

**恢复方式二：写入文件系统**

将历史任务文件复制到当前 session 的 tasks 目录：

```bash
# 恢复所有 pending 任务
python3 scripts/migrate.py --restore-tasks

# 恢复指定 session 的全部任务（含 completed）
python3 scripts/migrate.py --restore-tasks --session <SESSION_ID>
```

⚠️ 此方式写入文件后需要重启编辑器才可能生效，且新版 UI 可能仍不读取这些文件。

**恢复方式三：在对话中直接执行（最推荐）**

当用户报告"任务记录丢失"时，AI 应：

1. 先用 `--list-tasks` 诊断历史任务
2. 读取 `~/.workbuddy/tasks/` 下各 session 的 JSON 文件
3. 对每个 pending 任务，使用 TaskCreate 工具在当前 session 中重新创建
4. 告知用户任务已恢复

示例：
```python
# 读取历史任务
import json, glob
for f in glob.glob(os.path.expanduser("~/.workbuddy/tasks/*/*.json")):
    with open(f) as fh:
        task = json.load(fh)
    if task.get("status") == "pending":
        # 使用 TaskCreate 工具创建
        pass
```

## 踩坑记录

| 坑 | 说明 | 解决 |
|:---|:---|:---|
| Session 查询按 user_id 过滤 | UI 层只展示当前 user_id 的 session | UPDATE sessions SET user_id 迁移 |
| Memory 按文件名隔离 | `{user_id}_memory.md` 命名绑定账号 | 合并内容到新文件 |
| Connector 按目录隔离 | `connectors/{user_id}/mcp.json` | 深度合并 JSON |
| automations 表有 owner_user_id | 定时任务按 owner_user_id 归属账号，但 UI 过滤的是当前登录账号 | 任务本身若归属旧账号需 UPDATE owner_user_id；更常见的是任务在新账号下可见、但运行会话记录不可见（见下） |
| **任务面板会话记录为空** | **自动化任务（automations）的每次运行记录在 automation_runs 表，其 conversationId 指向 sessions 表的一条 session。UI 按当前登录 user_id 过滤 session。若该 session 归属旧账号，任务可见但会话记录不显示** | **迁移 sessions 时必须包含自动化 run 关联的 session（如 f843f702...），即整体 UPDATE sessions SET user_id=target 即可一并修复；不要跳过** |
| Skills 全局共享 | 不按账号隔离 | 无需迁移 |
| 修改 DB 后需重启 | WorkBuddy 客户端有内存缓存 | 迁移后提示重启 |
| workbuddy.db 有 WAL 模式 | SQLite WAL 日志可能导致数据不一致 | 迁移前先 checkpoint |
| 迁移中创建的会话 user_id 不匹配 | 迁移脚本运行时，当前对话可能以旧 user_id 写入 sessions 表 | Phase 4 验证后追加检查：`SELECT COUNT(*) FROM sessions WHERE user_id NOT IN (target)` 并修复 |
| **历史任务 UI 不可见** | **新版 /todos 只读当前 session 内存，不扫描 `tasks/` 目录** | **AI 用 TaskCreate 工具重新创建 pending 任务** |
| **tasks 文件格式兼容** | **旧版任务 JSON 有 subject/description/status 等字段，新版 TaskCreate 参数格式一致** | **字段可直接映射** |
| **storage.json 中 genie.userId 过时** | **账号切换后 storage.json 的 genie.userId 可能没有同步更新，仍为旧 ID。迁移脚本读到旧 ID 作为 target，导致 source=target 跳过迁移** | **v1.3 修复：优先从 DB 最新 session 推断 user_id，交叉验证不一致时发出警告** |
| **迁移方向反了（source/target 互换）** | **2026-08-08 实际事故：把企业版账号 session 误迁到个人版名下，27 条历史（含自动化任务运行会话 f843f702）留在旧账号，当前账号名下只剩 1 条当前会话。结果：任务本身可见但「任务面板会话记录」为空** | **v1.5 修复：执行前必做方向自检——target 必须持有当前会话 session，source 必须持有大部分历史；只允许 source→target 方向，反向立即中止** |
| **WAL 未 checkpoint 导致迁移丢失** | **即使 UPDATE sessions 成功 + commit，如果 WAL 日志没有 checkpoint，客户端重启后可能读不到修改，数据恢复为旧状态** | **v1.3 修复：迁移前后各做一次 PRAGMA wal_checkpoint(TRUNCATE)，并验证源 user_id 归零** |
| **AI 手动迁移时的常见错误** | **AI 在对话中直接写 SQL 迁移时，可能：(1) 从 storage.json 读到错误的 target_uid (2) 忘记 WAL checkpoint (3) 不验证结果** | **必须：(1) 从当前对话 session 的 user_id 确定目标 (2) UPDATE 后做 WAL checkpoint (3) 验证源 user_id 归零** |

## 安全规则

1. **必须先备份**，Phase 2 不可跳过
2. **源 user_id 和目标 user_id 必须不同**，防止自我覆盖
3. **Memory 合并用追加而非覆盖**，避免丢失目标账号已有记忆
4. **Connector 用深度合并**，保留目标账号已有配置
5. **迁移完成后提示重启**，确保 UI 刷新缓存
6. **备份文件 7 天后可手动清理**

## 参考文件

- `references/data_isolation_map.md` — 数据隔离全景图
