# 企微表情包存储与迁移参考

## macOS 路径（5.0.13 实测）

```
~/Library/Containers/com.tencent.WeWorkMac/Data/Library/Application Support/WXWork/Data/<账号ID>/Emotion/
```

- `<账号ID>` 为纯数字（uin 维度），**每个企业身份一个目录**，互不共享。切到哪个企业，客户端就用哪个目录。
- 目录内结构（2026-11 实测）：
  - `<YYYY-MM>/` 按月分片的缓存图片（png/gif/mp4），文件名为 uuid 或 md5
  - `Temp/` 临时文件，跳过
  - `<hash>.db`（+ `-wal`/`-shm`）SQLite 索引，表 `mapping`：

```sql
CREATE TABLE mapping(type integer, key text, file_name text, last_modify_time integer, file_md5 integer, primary key(type,key));
-- key = 腾讯 CDN URL（wework.qpic.cn / p.qpic.cn），file_name = 相对 Emotion 的缓存路径
```

- `cover_` 前缀文件是视频表情的封面帧；视频本体为同目录下无扩展名的 mp4。
- 客户端每次登录会从云端拉表情列表并重建缓存 → **表情列表的权威源在云端，跟账号/企业身份走**。

## Windows 路径（未实测，供排查）

- 旧版：`C:\Users\<user>\AppData\Local\企业微信\WeWork\<企业ID>\Image\Emotion`
- 新版疑似与 mac 同构：`%AppData%\..\Local\企业微信\WXWork\Data\<账号ID>\Emotion`
- 排查法：在安装目录/用户目录全局搜 `Emotion` 或 `mapping*.db`。

## 迁移事实边界（2026-11 检索结论）

| 场景 | 结果 | 依据 |
| --- | --- | --- |
| 企业主体变更认证 | corpid/unionid 不变，表情不受影响 | 官方帮助 20185 + 开发者社区技术支持答复 |
| 同账号换设备 | 自定义表情云端同步自动恢复 | 官方 1.1 版本日志"自定义表情，表情云端同步" |
| 换企业/换公司 | 不跟随；官方无导入通道 | 本地按企业身份隔离 + 迁移工具按企业维度 |
| 聊天记录迁移/.bak 导入 | 不含表情 | 官方帮助 16757：仅迁移会话信息，且仅限同一账号同一企业 |

- 官方明确：**不支持批量导入表情包**，不支持把微信收藏导入企微（帮助 17570）。
- 重新收藏的原生办法只有：图片发到会话 → 右键/长按 →「添加到表情」。

## 已知坑

1. **直接 sqlite3 打开原 db 会撞锁**：先拷 db/-wal/-shm 三件套再开。
2. **file_name 无扩展名**：gif/mp4 缓存文件名是裸 hash，需按 mime 探测补扩展名。
3. **mapping 里的文件可能已被清理**：导出前判 `-f`，跳过缺失项。
4. **目录文件数 > mapping 行数**：差值来自 Temp、未登记缓存，走 fallback 并用 md5 去重。
5. **wal 未合并**：拷贝后 sqlite3 打开即自动回放 wal，无需手动 checkpoint。
6. **导出的图片在新环境没有"顺序"语义**：表情顺序是云端账号属性，重新收藏后需手动长按排序。
7. **`ls ... | head -1` 在 `set -euo pipefail` 下静默退出**：head 截断管道使 ls 收 SIGPIPE 返回非零，pipefail 触发 set -e。改 glob 取首个元素。
8. **函数末尾 `[[ -f ... ]]` 返回 1 会让 set -e 杀掉整个脚本**：函数结尾补 `return 0`。

## db 注入方案已验证无效（2026-11-02 实测）

结论：**本地写 `mapping` 表无法让表情出现在面板里**，不要重复尝试。

实测过程：火运账号（150 条 mapping）注入百运 50 条记录 + 50 张图片 → db 变 201 条 → 重启客户端后 db 仍是 201 条（**未被云端覆盖**）→ 但表情面板不显示这 50 个。

推断：`mapping` 表只是「已下载资源的缓存索引」，不是「收藏列表」。面板渲染依据的是云端账号维度的收藏列表，本地缓存索引与之解耦。因此注入的 key 虽在 CDN 可达，但不在云端收藏列表中，客户端不渲染。

推论：跨企业迁移**只有一条路**——导出图片后在目标账号下重新收藏（本地上传 / 发送到会话后添加）。`scripts/inject_emotions.sh` 保留作实验记录与诊断工具，默认不用于迁移。

## 跨企业实操建议（2026-11-02 实测路径）

1. 导出图片，按格式分组（gif/png/jpg），文件名带序号便于挑选。
2. 目标账号：会话表情面板 → 我的表情 → `+` → 本地上传；动图优先（gif 最常用且体积小）。
3. 单文件 >1MB 的上传易失败，先跳过（实测 2580 个里有 35 个）。
4. 火运账号与百运表情有 150 个重复（火运是百运子集），重复收藏会去重。
