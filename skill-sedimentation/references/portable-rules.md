# 可粘贴规则块

给任何 Agent 用。整段复制，粘到系统指令文件末尾即可，不需要其他依赖。

---

## 收尾自检：该不该沉淀

任务结束前，逐条自问，**只认证据不认感觉**：

1. **会再发生吗** —— 周期性任务，或同类场景已出现两次以上？
2. **有固定常量吗** —— 有三个以上「下次还得重查」的值（token、路径、账号、profile、命令）？
3. **踩过不明显的坑吗** —— 至少一个「报错后换路径才成功」或「文档没写但必须做」的点？
4. **是一串动作吗** —— 三步以上可执行命令，且有明确先后顺序？

**四条全过**：写成 skill（已有同主题的就改，不要新建第二个）。
**两到三条**：先在项目记忆里记一条，第二次复现再升级成 skill。
**一条或零条**：不沉淀，只在当天记录里留一句。

判断沉淀成什么：

- 有动作序列、下次要照做 → **skill**
- 只是一条事实或一次事件 → **记忆/笔记**
- 两者都有 → 两份都写：记忆记「这次发生了什么」，skill 记「下次怎么做」

## 写 skill 的最低标准

五段齐全才算写完：

1. 常量表（token、路径、账号、固定命令参数）
2. 流程（每步给可直接执行的命令，不给描述）
3. 坑（格式：症状 → 根因 → 修复）
4. 验收（什么算做完：期望输出、退出码、要校验的字段）
5. 反例（什么情况不要用这个 skill）

三条禁令：

- 不写「注意安全」「保持整洁」这类正确的废话。
- description 必须含真实触发语（它是唯一被检索的字段）。
- 命令优先于描述。

## 反例（这些不要沉淀）

- 一次性调研、单次故障排查
- 没有具体对象的纯方法论
- 你自己的常识（三次以内能重推一遍的）
- 三行以内就说完的操作

---

## English short version

At task end, check four things before writing anything down:

1. Will this recur (periodic, or seen twice already)?
2. Are there ≥3 constants I'd have to look up again (tokens, paths, accounts, flags)?
3. Did I hit ≥1 non-obvious failure (worked only after changing approach)?
4. Is it ≥3 sequential commands?

All four → write a skill (update an existing one instead of creating a duplicate). Two or three → note it once, promote on the second occurrence. One or none → skip.

Skill or note: actionable sequence → skill; a single fact or event → note; both → write both.

A finished skill has: constants table, runnable steps, pitfalls (symptom → cause → fix), acceptance checks, and explicit "don't use this when". No generic advice.
