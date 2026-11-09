---
name: logged-in-cdp-research
description: >-
  复用本机已登录的浏览器态做网页调研与接口取数：拷贝 Chrome profile → 起带 --remote-debugging-port 的独立实例 →
  页面内验证身份 → 用状态码区分「接口不存在」与「需要权限」→ 同源 fetch 批量取数或写数 → 收尾删除临时 profile。
  适用于只有登录后才返回数据、且没有开放 API 的内部系统、面板、工时/审批/报表类站点。
  触发词：需要登录才能看、复用登录态、cookie 复用、CDP、remote-debugging-port、抓需要登录的接口、已登录页面取数、浏览器态调研。
  不负责：绕过审批或权限、模拟账号密码登录、桌面应用控制（走 computer 那套）、纯静态页面（直接 HTTP 取更快）。
metadata:
  version: 1.0.0
  agent_created: true
  short-description: 复用已登录浏览器态做调研取数
---

# 复用已登录浏览器态做网页调研

目标：人已经登录过，机器直接复用这份凭证去取数，而不是让机器去模拟登录。

## 什么时候用

- 目标系统所有接口都要登录，未登录一律 401。
- 登录方式是扫码 / SSO / 多因素，脚本模拟不了。
- 没有开放 API，或者有 API 但需要额外的客户端授权（OAuth 流程被统一拦截）。
- 需要批量读取或写入，UI 点位太碎。

## 安全边界（先读再动手）

1. **拷出来的 profile 等同凭证**：目录权限 0600，用完即删，绝不入仓库、不入云盘。
2. **只读优先**：先能读再谈写。写操作必须与「用户本人会做的动作」同语义，不得借会话绕审批或改权限。
3. **不碰用户的实例**：始终拷到独立 `--user-data-dir`，不干扰正在使用的浏览器。
4. **SSO 过期就停**：需要用户重新扫码时如实告知，不要反复重试或尝试别的绕过路径。
5. 输出里不打印 cookie、token、账号目录全路径。

## 四步走

### 1. 定位 profile

| 平台 | 路径 |
|-|-|
| macOS | `~/Library/Application Support/Google/Chrome` |
| Linux | `~/.config/google-chrome` |
| Windows | `%LOCALAPPDATA%\Google\Chrome\User Data` |

也支持 Chromium 系（Edge、Brave）与 Electron 应用，换成对应目录即可。

### 2. 最小拷贝

整盘 profile 动辄几个 G，只拷登录态需要的：

```bash
SRC="<chrome 数据目录>"; DST="/tmp/cdp-profile"
mkdir -p "$DST/Default"
cp "$SRC/Local State" "$DST/" 2>/dev/null || true
for f in Cookies Preferences "Network/Cookies" "Local Storage"; do
  [ -e "$SRC/Default/$f" ] && mkdir -p "$DST/Default/$(dirname "$f")" && cp -R "$SRC/Default/$f" "$DST/Default/$f"
done
```

约 40MB 量级。`Local State` 里是解密 key，缺了 cookie 解不开，别漏。

### 3. 起独立实例并连 CDP

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=9333 \
  --user-data-dir=/tmp/cdp-profile \
  --no-first-run --no-default-browser-check --disable-gpu about:blank &

curl -s http://127.0.0.1:9333/json/version   # 应返回 Browser / webSocketDebuggerUrl
```

客户端两种连法：`/json/list` 里取 page 的 WebSocket，或用支持 `cdpUrl` 的浏览器工具直接指 `http://127.0.0.1:9333`。

已在运行的 Chrome **不会**因为新参数而开启调试端口，必须新起一个实例。

### 4. 验身份 → 摸接口 → 执行 → 收尾

验身份：在页面上下文里打一个已知接口（如 `/api/me`），看 200 和用户名。**先确认凭证生效，再去摸路径。**

摸接口的关键判据：

| 状态 | 含义 |
|-|-|
| 401 | 存在，但当前会话没有权限（或未登录） |
| 404 | 路径不存在 |
| 200 | 可用 |

未登录时两者都是 401，所以**必须先登录再判断存在性**，否则会把"不存在"误判成"要权限"。

执行：

```js
// 只读
await fetch('/api/items?page=1', {credentials: 'include'}).then(r => r.json())
// 写：形状先抄页面自己的请求，不要自创字段
await fetch('/api/items', {method:'POST', credentials:'include',
  headers:{'content-type':'application/json'}, body: JSON.stringify(payload)})
```

收尾：

```bash
pkill -f 'remote-debugging-port=9333' ; rm -rf /tmp/cdp-profile
```

## 什么时候不要用它（按奥卡姆剃刀排序）

1. **官方 API / 带凭证的 MCP** —— 有就用，最稳，不拷凭证。
2. **静态页直接 HTTP 转文本** —— 不等 JS 渲染的页面，成本低一到两个数量级。
3. **复用登录态的 CDP 直连** —— 本文这条。
4. **relay（浏览器扩展 + 本地服务）** —— 产品化好，但依赖厂商实现；端口不通就整体失效。
5. **桌面控制（辅助功能 + 截图 + 原生键鼠）** —— 只能用于非网页程序；要权限、坐标脆、不适合批量。

每往下走一层，就多一个进程、多一份凭证拷贝、多一类不确定性。

## 对比一张表

| 维度 | CDP 直连 profile | relay | 托管 Chromium | 桌面控制 | API / OAuth |
|-|-|-|-|-|-|
| 登录态 | 自带（拷贝） | 自带（用户会话） | 无 | 借用 | 需授权 |
| 依赖 | 本机 Chrome | 厂商扩展 + 本地服务 | 无 | 辅助功能权限 | 服务方开放 |
| 稳定性 | 高 | 中 | 高 | 低 | 最高 |
| 批量能力 | 强 | 中 | 强 | 弱 | 强 |
| 对用户干扰 | 无 | 占用真实标签 | 无 | 高 | 无 |

## 踩坑清单

1. **单实例锁**：拿用户正在用的 profile 直接起会失败或抢焦点。必须拷到独立目录。
2. **cookie 解不开**：只拷了 `Cookies` 没拷 `Local State`，或跨机器拷贝（key 在本机钥匙串 / 系统密钥里）。
3. **headless 与有头行为差异**：个别站点对 headless UA 有额外风控，必要时改 UA 或换有头模式。
4. **SPA 首屏还没挂完就取数**：等目标接口返回，而不是等 DOM 出现。
5. **写操作用了自己发明的字段名**：先看页面真实请求体，字段名、类型、必填项照抄。
6. **把临时 profile 留在 /tmp**：等于把凭证落在临时目录，必须删。

## 验收清单

- [ ] `/json/version` 有响应，说明 CDP 通了
- [ ] `/api/me`（或等价接口）200 且用户名正确
- [ ] 目标数据能取到，字段与页面显示一致
- [ ] 写操作后能在页面上看到同一条记录
- [ ] 实例已结束、临时 profile 已删除
