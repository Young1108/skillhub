---
name: wake-agent-daily-report
description: "基于 Wake（iAmCorey/Wake，本机 /Applications/Wake.app）的 wake.db 聚合数据生成「当日多 Coding Agent 工作日报」。当用户要求总结今日/某日各 Coding Agent（Claude Code、Codex、Cursor、dsh、Grok、pi、qoder 等）都干了什么、要 agent 日报/日总结/今日工作复盘，或说按项目-时段-干了什么格式出日报时使用。产出 Markdown 报告，结构以「项目 → 时段·Agent·干了什么 + 产出效果」为脉络。依赖本机 wake.db（~/Library/Application Support/wake/wake.db）；若 Wake 未收录某 agent 数据，提示先冷启动 Wake 刷新（pkill -x Wake 后重开，quit 不触发全量扫描）。"
agent_created: true
---

# Wake Agent 日报生成

读取 Wake 聚合库 wake.db，生成指定日期（默认今天）的 Coding Agent 工作日报。
数据为只读；不改动 wake.db 与各 agent 原始文件。

## 触发时机

- "总结今天的 agent 日报 / 今日各 agent 都干了什么"
- "生成指定日期的工作日报"
- "把今天的会话总结成日报文件"
- 数据源是本机 wake.db（约 9 类 agent：claude-code/codex/cursor/dsh/pi/grok/qoder/opencode/gemini…）

## 工作流

1. **前置检查**（30 秒内完成）：确认 wake.db 存在（`~/Library/Application Support/wake/wake.db`）。
   若用户反馈"某 agent 数据不出现"或上次冷启动时间早于目标日活跃时段，用
   `pkill -x Wake && sleep 2 && open /Applications/Wake.app` 冷启动一次再继续
   （Wake 0.4.x 用 quit 重开不跑启动扫描；冷启动才触发全量扫描）。

2. **提取素材**：运行 `python3 scripts/extract_today.py --date YYYY-MM-DD -o /tmp/wake_digest_<date>.txt`
   （默认日期=今天；数据库默认路径已内置）。Read 生成的 digest 文件。
   - digest 含：活跃会话清单、每会话的「首个用户目标 / 末条助手结论 / 前一条 / 操作特征」。
   - 脚本已内置三个坑的处理：cursor 消息 ts 为 NULL（按 sessions.updated_at 归属）；
     跨日会话按 ts 窗口切分；时间戳毫秒。

3. **补料（按需）**：digest 中"干了什么/产出效果"证据不足的会话，回读对应源文件精读
   局部（文件路径规则见脚本尾部注释或 SKILL 末尾）；只读关键轮次，避免全文灌入。

4. **撰写报告**：加载 `references/report-structure.md`（报告结构模板与写作纪律），
   产出 `Agent日报_<date>.md`。
   - 骨架：头部 → 总览表（Agent/会话数/项目/一句话贡献）→ 按项目详述
     （每事件行 = 时段 | Agent | 干了什么 | 产出/效果）→ 产出物清单 → 风险备注。
   - 多 Agent 同项目按时间轴合并成一节，勿按 Agent 拆散同一战役。
   - 子代理会话归并到父任务条目。
   - 纪律：一切内容须有会话文本证据；不可验证写"待验证/无记录"，禁止编造；
     敏感信息（key/邀请码/密码）脱敏。

5. **交付**：文件放用户当前工作区根目录；用 present_files 呈现；回复里给
   3-5 行总结（今日脉络 + 关键产出 + 1-2 个注意点），不再复述全文。

## 输出位置

- 报告：`<工作区>/Agent日报_<date>.md`（用户指定路径则从其指定）。

## 已知限制（写入报告备注，不影响主体）

- Wake 只入库 text 与 role（user/assistant）；工具调用被压平成文本片段，
  无独立 tool 表、无 thinking 字段——精确到命令级复盘需回读 agent 原始日志。
- model/tokens 字段部分 agent 缺失。
- 会话删除后 wake.db 有 tombstone，不展示；不影响按日期查询其余会话。

## 源文件回读路径速查

| agent | 原始数据 |
|---|---|
| Claude Code | ~/.claude/projects/-<cwd转义>-/<uuid>.jsonl |
| Codex | ~/.codex/sessions（state_5.sqlite 元数据 + rollouts/*.jsonl） |
| dsh | $DSH_HOME 或 ~/.dsh/sessions/-<ws>-/<uuid>/session.jsonl[.zstd] |
| Cursor | ~/.cursor/projects/**/agent-transcripts |
| pi | ~/.pi/agent/sessions/**/*.jsonl |
| grok | ~/.grok/sessions/**/updates.jsonl |
| qoder | ~/.qoder/projects/*/*.jsonl |
