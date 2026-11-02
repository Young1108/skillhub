#!/usr/bin/env bash
# 把源账号的表情注入到目标账号本地 db + Emotion 目录（跨企业身份迁移的实验性方案）。
#
# 原理: 企微表情 key 是公共 CDN URL(wework.qpic.cn / p.qpic.cn)，跨账号可访问。
#       把源账号 mapping 记录 + 图片复制到目标账号，目标客户端重启后读 db 或许直接显示。
#       若客户端用云端收藏列表覆盖本地 db，则注入无效(回到原状)，需改走"添加到表情"。
#
# 前置(实跑): 必须先完全退出企业微信客户端(db 被占用会失败/数据不一致)。dry-run 只读，不要求退出。
# 安全: 脚本强制要求 --backup 目录(已备份的目标 Emotion)，实跑前再次校验企微未运行。
#
# 用法:
#   inject_emotions.sh <src账号ID> <dst账号ID> --backup <备份目录> [--limit N] [--dry-run]
#   inject_emotions.sh 1688855662819100 1688854942900883 --backup ~/.../backup --limit 50   # 先试 50 个

set -euo pipefail

BASE="$HOME/Library/Containers/com.tencent.WeWorkMac/Data/Library/Application Support/WXWork/Data"
SRC=""; DST=""; BACKUP=""; LIMIT=""; DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup) BACKUP="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) [[ -z "$SRC" ]] && SRC="$1" || DST="$1"; shift ;;
  esac
done

[[ -n "$SRC" && -n "$DST" && -n "$BACKUP" ]] || { echo "用法: $0 <src> <dst> --backup <dir> [--limit N] [--dry-run]" >&2; exit 1; }
SRC_EMO="$BASE/$SRC/Emotion"; DST_EMO="$BASE/$DST/Emotion"
[[ -d "$SRC_EMO" && -d "$DST_EMO" ]] || { echo "错误: 源/目标 Emotion 目录不存在" >&2; exit 1; }
[[ -d "$BACKUP" ]] || { echo "错误: 备份目录不存在: $BACKUP" >&2; exit 1; }

if [[ $DRY -eq 0 ]]; then
  if pgrep -x WeWorkMac >/dev/null 2>&1 || pgrep -f "com.tencent.WeWorkMac" >/dev/null 2>&1; then
    echo "错误: 企业微信仍在运行，请先完全退出(含菜单栏图标)再执行。" >&2; exit 1
  fi
fi

# 拷 db 三件套到临时目录（避锁、保证 wal 一致）
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp_db() {  # $1=源Emotion  $2=目标临时目录
  mkdir -p "$2"
  for f in "$1"/*.db "$1"/*.db-wal "$1"/*.db-shm; do [[ -f "$f" ]] && cp "$f" "$2/"; done
  return 0
}
cp_db "$SRC_EMO" "$TMP/src"
cp_db "$DST_EMO" "$TMP/dst"
SRC_DB=""; for f in "$TMP/src"/*.db; do SRC_DB="$f"; break; done
DST_DB=""; for f in "$TMP/dst"/*.db; do DST_DB="$f"; break; done
echo "源: $SRC  db=$(basename "$SRC_DB")"
echo "目标: $DST db=$(basename "$DST_DB")"

# 差集查询：在目标 db 上下文，attach 源，取源有目标无的 file_name
LIMIT_CLAUSE=""; [[ -n "$LIMIT" ]] && LIMIT_CLAUSE="order by last_modify_time limit $LIMIT"
DIFF_SQL="attach '$SRC_DB' as src; select file_name from src.mapping where file_name!='' and key not in (select key from mapping) $LIMIT_CLAUSE;"
sqlite3 "$DST_DB" "$DIFF_SQL" > "$TMP/files.txt"
N=$(grep -c . "$TMP/files.txt" || true)
echo "待注入: $N 个表情"

if [[ $DRY -eq 1 ]]; then
  echo "[dry-run] 待复制文件(前5):"; head -5 "$TMP/files.txt"; echo "(共 $N 条)"; exit 0
fi

# 复制图片到目标 Emotion
copied=0; missing=0
while IFS= read -r rel; do
  [[ -z "$rel" ]] && continue
  src="$SRC_EMO/$rel"; dst="$DST_EMO/$rel"
  if [[ -f "$src" ]]; then mkdir -p "$(dirname "$dst")"; cp -p "$src" "$dst"; copied=$((copied+1))
  else missing=$((missing+1)); fi
done < "$TMP/files.txt"
echo "复制图片: $copied 成功, $missing 源缺失"

# 插入 mapping 记录（目标 db 上下文，attach 源）
INSERT_SQL="attach '$SRC_DB' as src; insert or ignore into mapping(type,key,file_name,last_modify_time,file_md5) select type,key,file_name,last_modify_time,file_md5 from src.mapping where key not in (select key from mapping) $LIMIT_CLAUSE;"
sqlite3 "$DST_DB" "$INSERT_SQL"
sqlite3 "$DST_DB" "pragma wal_checkpoint(TRUNCATE);" >/dev/null

# 覆盖回目标（主 db 已 checkpoint，无需 wal/shm）
cp "$DST_DB" "$DST_EMO/$(basename "$DST_DB")"
rm -f "$DST_EMO"/*.db-wal "$DST_EMO"/*.db-shm

after=$(sqlite3 "$DST_DB" "select count(*) from mapping;")
echo "注入完成: 目标 db 现有 $after 条 mapping"
echo "下一步: 启动企业微信 → 切到火运账号 → 查看表情面板。"
echo "若未出现(被云端覆盖): 还原 → cp -r $BACKUP/Emotion/* $DST_EMO/"
