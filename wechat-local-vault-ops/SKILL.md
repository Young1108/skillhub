---
name: wechat-local-vault-ops
description: |
  yichen-wechat-local-vault（个人微信 Mac 4.x 本地金库）的部署与操作手册。涵盖从 GitHub 部署 skill、首次全量抓 key（frida spawn 模式）、全量/增量解密、到日常查询导出的完整流程。记录 macOS SIP 下的关键实战坑：attach 模式不可用必须 spawn、--wechat-copy 参数陷阱、export --limit 截断、退出微信的方法等。触发词：微信本地解析部署、wechat-local-vault 部署、微信抓 key、微信解密、微信聊天记录导出、yichen-wechat-local-vault 使用、微信 vault 运维。
agent_created: true
---

# yichen-wechat-local-vault 操作手册

本 skill 是 `yichen-wechat-local-vault`（个人微信 Mac 4.x 本地金库）的部署与运维手册。它不重复 yichen-wechat-local-vault 自身 SKILL.md 的查询语法，而是记录**部署、首次全量抓 key、日常运维**中 yichen-wechat-local-vault 文档未覆盖的实战经验与 macOS 平台特定的坑。

## 前置条件

- macOS（脚本仅支持 darwin）
- WeChat 4.x 已安装于 `/Applications/WeChat.app`，容器在 `~/Library/Containers/com.tencent.xinWeChat`
- WorkBuddy 管理 Python（`/Users/huangjiayang/.workbuddy/binaries/python/envs/default/bin/python`）
- 首次抓 key 需要微信可登录（扫码或自动恢复登录）

## 关键路径速查

| 用途 | 路径 |
|---|---|
| skill 安装目录 | `~/.workbuddy/skills/yichen-wechat-local-vault/` |
| Python venv | `~/.workbuddy/binaries/python/envs/default/bin/python` |
| 密钥文件 | `~/.config/wechat-keys.json` |
| 配置文件 | `~/.config/wechat-local-vault.json` |
| 明文 vault | `~/Library/Application Support/wechat-local-vault/decrypted/current/` |
| frida 抓取日志 | `/tmp/wechat_frida_keys.log` |
| 微信副本（spawn 用） | `~/Desktop/WeChat.app` |

## 部署流程

### 1. 从 GitHub 克隆并安装

```bash
cd /tmp && git clone --depth 1 https://github.com/mcncarl/yichen-skills.git yichen-skills-tmp
cp -R /tmp/yichen-skills-tmp/yichen-wechat-local-vault ~/.workbuddy/skills/yichen-wechat-local-vault
rm -rf /tmp/yichen-skills-tmp
```

### 2. 安全审计（必做）

安装前审查所有脚本，重点检查：
- 无网络外发（grep `requests|urllib|http\.client|socket|https?://`）
- 无代码注入（grep `eval\(|exec\(|__import__|pickle\.loads`）
- subprocess 用途是否合法（pip install / pgrep / 本地 frida host）
- shutil.rmtree 是否只在显式 flag 下清除 OUTPUT 目录

yichen-wechat-local-vault 经审计为 P2（安全）：纯本地操作，密钥/配置 chmod 0o600，vault 目录 chmod 0o700。

### 3. 安装 Python 依赖到隔离 venv

```bash
VENV=/Users/huangjiayang/.workbuddy/binaries/python/envs/default
PY=/Users/huangjiayang/.workbuddy/binaries/python/versions/3.13.12/bin/python3
[ -d "$VENV" ] || $PY -m venv "$VENV"
"$VENV/bin/pip" install frida pycryptodome zstandard
```

**注意**：`extract_keys.py` 会自动 pip install frida 和 pycryptodome，但 **zstandard 不会自动安装**（list_contacts.py / export_chat.py 直接 import）。必须预装 zstandard，否则导出/列表会 import 失败。

### 4. 冒烟测试

```bash
VENV_PY=~/.workbuddy/binaries/python/envs/default/bin/python
"$VENV_PY" ~/.workbuddy/skills/yichen-wechat-local-vault/scripts/extract_keys.py --list-dbs
"$VENV_PY" ~/.workbuddy/skills/yichen-wechat-local-vault/scripts/vault_cli.py --help
```

`--list-dbs` 应自动检测到 wxid 和 db_base 路径，列出 18 个本地数据库。

## 首次全量抓 key（最关键，坑最多）

### ⚠️ 核心结论：macOS SIP 下必须用 spawn 模式，attach 不可用

`extract_keys.py --mode attach` 在 macOS SIP 开启时会报：
```
frida.PermissionDeniedError: unable to access process with pid XXXXX from the current user account
```
因为微信有 hardened runtime，frida 无法 attach 到已运行的微信进程。

**必须用 spawn 模式**：脚本复制 `/Applications/WeChat.app` → `~/Desktop/WeChat.app`，用 `codesign --force --deep --sign -` 做 ad-hoc 重签名（去掉 hardened runtime），然后 frida spawn 副本在启动时注入 hook。

### 正确的首次抓 key 流程

#### Step 1: 退出当前微信

osascript 退出会因权限违例失败（`-10004`），改用 SIGTERM 优雅退出：

```bash
# 找到微信主进程 PID
pgrep -f "/Applications/WeChat.app/Contents/MacOS/WeChat$"
# SIGTERM 退出（等同 Cmd+Q，1 秒内退出）
kill -TERM <pid>
# 清理残留 WeChatAppEx helper
pkill -TERM -f "WeChatAppEx"
```

注意：`pgrep -f "WeChat"` 会误匹配企业微信（WeWork）和 WeChatAppEx Helper，要精确匹配 `/Applications/WeChat.app/Contents/MacOS/WeChat$`（个人微信主进程）。

#### Step 2: 启动 spawn 模式抓取（后台运行）

```bash
~/.workbuddy/binaries/python/envs/default/bin/python \
  ~/.workbuddy/skills/yichen-wechat-local-vault/scripts/extract_keys.py \
  --mode spawn --targets all --duration 240
```

**关键参数说明**：
- `--mode spawn`：必须用 spawn，不用 attach
- `--targets all`：抓全部 18 个库的 key
- `--duration 240`：抓取窗口 240 秒
- **不要加 `--skip-prepare`**：首次需要复制+签名微信副本
- **不要加 `--wechat-copy`**：用默认值 `~/Desktop/WeChat.app`，脚本会自动复制

#### Step 3: 用户在微信副本窗口操作（240 秒窗口内）

脚本会 spawn 微信副本，窗口弹出后：
1. 如需登录则扫码登录（通常自动恢复登录）
2. 打开 **收藏**，点开一条收藏内容
3. 打开 **朋友圈**，上下滚动一两次

这两步触发微信解密数据库，frida hook 捕获 PBKDF2 调用。成功后日志显示 `captured N PBKDF2 calls`，典型值 42 次（21 个库 × 2 种 rounds）。

#### Step 4: 等待完成，确认 key 匹配

脚本结束后进入 `[5/5] Matching captured keys to databases...`，应看到全部 18 个库 `matched key`，key 保存到 `~/.config/wechat-keys.json`。

### 抓 key 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| `PermissionDeniedError` | 用了 attach 模式 | 改用 spawn 模式 |
| `WeChat executable not found: ~/Desktop/WeChat.app/...` | attach 模式 + `--skip-prepare` 且副本不存在 | spawn 模式不加 `--skip-prepare` |
| `captured 0 PBKDF2 calls` 全程 | 用户没操作收藏/朋友圈，或微信未登录 | 确认登录后重新打开收藏+朋友圈 |
| 只匹配到部分库 | 抓取窗口内某些库没被触发解密 | 延长 duration，或额外打开会话列表 |

## 全量解密

抓到 key 后，全量解密到私密 vault：

```bash
~/.workbuddy/binaries/python/envs/default/bin/python \
  ~/.workbuddy/skills/yichen-wechat-local-vault/scripts/decrypt_all_dbs.py \
  --mode full
```

典型结果：18 库全部成功，0 失败。manifest 写入 `~/Library/Application Support/wechat-local-vault/manifests/`。

## 日常运维

### 增量刷新 vault

日常只需增量解密（跳过未变化的库，只更新有变化的）：

```bash
~/.workbuddy/binaries/python/envs/default/bin/python \
  ~/.workbuddy/skills/yichen-wechat-local-vault/scripts/decrypt_all_dbs.py \
  --mode incremental
```

增量无需重新抓 key（key 保存在 `~/.config/wechat-keys.json`）。**只有微信大版本升级导致 key 变化时才需要重新抓 key**。

### 查询命令速查

所有查询用 venv python 调用 `vault_cli.py`，默认 JSON 输出（适合 Agent），加 `--format text` 适合人工查看：

```bash
VENV_PY=~/.workbuddy/binaries/python/envs/default/bin/python
SKILL=~/.workbuddy/skills/yichen-wechat-local-vault/scripts

"$VENV_PY" "$SKILL/vault_cli.py" status --format text           # vault 状态
"$VENV_PY" "$SKILL/vault_cli.py" sessions --limit 20 --format text  # 最近会话
"$VENV_PY" "$SKILL/vault_cli.py" contacts --query "关键词" --format text
"$VENV_PY" "$SKILL/vault_cli.py" history "群名" --format text
"$VENV_PY" "$SKILL/vault_cli.py" search "关键词" --format text
"$VENV_PY" "$SKILL/vault_cli.py" stats "群名" --format text     # 群统计
"$VENV_PY" "$SKILL/vault_cli.py" members "群名" --format text
"$VENV_PY" "$SKILL/vault_cli.py" favorites --format text
"$VENV_PY" "$SKILL/vault_cli.py" moments --name "联系人" --format text
```

### ⚠️ 导出聊天记录的关键坑：--limit 默认 500 会截断

`vault_cli.py export` 默认 `--limit 500`，**大群会被截断**（只取前 500 条，按时间正序）。导出前先用 `stats` 看消息总数，再决定 limit：

```bash
# 错误（大群会截断）
"$VENV_PY" "$SKILL/vault_cli.py" export "群名" --format markdown --output ./chat.md

# 正确（调大 limit）
"$VENV_PY" "$SKILL/vault_cli.py" export "群名" \
  --start-time "2026-05-26" --end-time "2026-07-26" \
  --limit 10000 \
  --format markdown --output ./chat.md
```

支持的时间过滤：`--start-time` / `--end-time`（格式 `YYYY-MM-DD`）。消息类型过滤：`--type {text,image,voice,video,sticker,location,link,file,call,system}`。

### 群聊摘要素材包

```bash
"$VENV_PY" "$SKILL/vault_cli.py" digest-source "群名" \
  --start "2026-05-01" --end "2026-05-14" --format text
```

输出落到 `{data_root}/{group_id}-{group_name}/`，含 `sources/*.json`、`sources/*.md`、`profiles/`、`profiles-roast/`、`imgs/`。素材包不自动更新 history.json，摘要确认后才更新锚点。

## 残留物管理

- `~/Desktop/WeChat.app`：ad-hoc 签名的微信副本（约 500MB），spawn 抓 key 产生。**下次抓 key 会复用**（prepare 跳过复制直接重签名）。如不再抓 key 可手动删除释放空间。
- `/tmp/wechat_frida_keys.log`：frida 抓取日志，可保留供 `--match-only --reuse-log` 复用 key。
- `~/.config/wechat-keys.json`：密钥文件，权限 0o600，**不要删除**（删除后需重新抓 key）。

## 与企业微信 skill 的关系

同一作者还有 `yichen-wecom-local-vault`（企业微信本地金库）。两者独立，不冲突：
- `yichen-wechat-local-vault` → 个人微信（`com.tencent.xinWeChat` 容器）
- `yichen-wecom-local-vault` → 企业微信（`com.tencent.WeWorkMac` 容器）

pgrep 时注意区分：个人微信主进程匹配 `/Applications/WeChat.app/Contents/MacOS/WeChat$`，企业微信匹配 `/Applications/企业微信.app`。

## 运行时强制规则

- **始终用 venv python** 调用脚本（`~/.workbuddy/binaries/python/envs/default/bin/python`），确保 frida/pycryptodome/zstandard 可用，且依赖隔离不污染系统环境。
- 抓 key 前确认已退出当前微信，避免 spawn 副本与正运行实例冲突。
- 导出大群前先 `stats` 看消息数，再调 `--limit`。
- 涉及明文 vault 的操作不要把文件复制到项目目录或聊天回复（隐私边界，见 yichen-wechat-local-vault SKILL.md）。
