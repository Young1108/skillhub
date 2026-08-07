# 数据隔离全景图

## WorkBuddy 数据存储位置与隔离机制

### 核心存储目录

```
~/.workbuddy/
├── workbuddy.db                  # SQLite 主数据库
│   ├── sessions 表               # 按 user_id 隔离 ← 迁移目标
│   ├── workspaces 表             # 无 user_id，全局共享
│   ├── automations 表            # 无 user_id，全局共享
│   └── automation_runs 表        # 无 user_id，全局共享
│
├── memory/                       # 长期记忆
│   ├── {user_id}_memory.md       # 按文件名隔离 ← 迁移目标
│   └── ...
│
├── connectors/                   # Connector 配置
│   ├── {user_id}/                # 按子目录隔离 ← 迁移目标
│   │   ├── mcp.json
│   │   └── connector-states.json
│   ├── default/
│   └── skills/
│
├── skills/                       # 用户自建 Skills
│   └── {skill_name}/             # 无隔离，全局共享 ✅
│
├── settings.json                 # 全局设置，无隔离 ✅
├── mcp.json                      # 全局 MCP 配置，无隔离 ✅
├── models.json                   # 自定义模型，无隔离 ✅
│
├── projects/                     # 对话日志
│   └── {workspace_path}/         # 按工作空间路径，不按账号 ✅
│
├── tasks/                        # 任务列表
│   └── {session_id}/             # 按 session 归属，新版 UI 不读取 ← 恢复目标
│       └── {id}.json             # 任务 JSON（subject/description/status等）
│
└── logs/                         # 日志，全局共享 ✅
```

### 当前登录 user_id 获取方式

```bash
cat ~/Library/Application\ Support/WorkBuddy/User/globalStorage/storage.json | \
  python3 -c "import json,sys; print(json.load(sys.stdin).get('genie.userId',''))"
```

### 隔离层级速查表

| 数据 | 隔离维度 | 迁移方式 | 风险等级 |
|:---|:---|:---|:---|
| sessions | user_id 字段 | UPDATE SQL | 🟡 中（改DB） |
| memory | 文件名 | 追加合并 | 🟢 低（文本） |
| connectors/mcp.json | 子目录 | JSON 深度合并 | 🟡 中（配置） |
| connectors/states.json | 子目录 | JSON 深度合并 | 🟢 低 |
| **tasks** | **按 session** | **TaskCreate 重建 / 文件复制** | **🟡 中（新版 UI 不读文件）** |
| skills | 无 | 不需要迁移 | - |
| automations | 无 | 不需要迁移 | - |
| settings/mcp/models | 无 | 不需要迁移 | - |

### WAL 模式处理

workbuddy.db 使用 SQLite WAL（Write-Ahead Logging）模式。迁移前应执行 checkpoint：

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('$HOME/.workbuddy/workbuddy.db')
conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
conn.close()
print('WAL checkpoint done')
"
```

这确保所有 WAL 日志写入主数据库文件，避免数据不一致。
