#!/usr/bin/env bash
# 导出企业微信(macOS)本机缓存的表情包，供跨设备/跨企业重新收藏。
#
# 用法:
#   export_emotions.sh                     # 交互列出所有账号的 Emotion 缓存，全部导出
#   export_emotions.sh <账号ID> ...        # 只导出指定账号目录
#   export_emotions.sh --out <目录>        # 指定导出根目录（默认 ./wecom-emotions-<日期>）
#   export_emotions.sh --zip               # 导出后额外打 zip 包
#
# 产物:
#   <out>/<账号ID>/NNN_<原文件名>   表情图片（含 gif/png/jpg/mp4 等，去重）
#   <out>/<账号ID>/manifest.csv     URL→文件 映射清单
#   <out>/index.html                网格预览页（浏览器打开，人工挑选重新收藏用）
#
# 原理: Emotion 目录是 CDN 缓存，mapping.db 记录 远程URL→本地文件 的映射。
#       表情列表本体在云端（跟账号走），本地导出的图片用于在新环境重新收藏。

set -euo pipefail

BASE="$HOME/Library/Containers/com.tencent.WeWorkMac/Data/Library/Application Support/WXWork/Data"
OUT=""
ZIP=0
ACCOUNTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --zip) ZIP=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) ACCOUNTS+=("$1"); shift ;;
  esac
done

[[ -d "$BASE" ]] || { echo "错误: 未找到企业微信数据目录 $BASE（是否未安装/未登录过？）" >&2; exit 1; }

if [[ -z "$OUT" ]]; then
  OUT="./wecom-emotions-$(date +%Y%m%d)"
fi
mkdir -p "$OUT"

# 收集有 Emotion 内容的账号目录
declare -a TARGETS=()
if [[ ${#ACCOUNTS[@]} -gt 0 ]]; then
  for a in "${ACCOUNTS[@]}"; do
    [[ -d "$BASE/$a/Emotion" ]] || { echo "跳过: $a 无 Emotion 目录" >&2; continue; }
    TARGETS+=("$a")
  done
else
  for d in "$BASE"/*/; do
    a=$(basename "$d")
    [[ "$a" =~ ^[0-9]+$ ]] || continue   # 只取纯数字的账号目录，跳过 Global/FunviewTemplate 等
    [[ -d "$d/Emotion" ]] || continue
    n=$(find "$d/Emotion" -type f ! -path "*/Temp/*" ! -name "*.db*" | wc -l | tr -d ' ')
    [[ "$n" -gt 0 ]] && TARGETS+=("$a") && echo "发现账号 $a: $n 个缓存文件"
  done
fi

[[ ${#TARGETS[@]} -gt 0 ]] || { echo "没有可导出的账号 Emotion 缓存。" >&2; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

TOTAL=0
for a in "${TARGETS[@]}"; do
  EMO="$BASE/$a/Emotion"
  DEST="$OUT/$a"
  mkdir -p "$DEST"

  # 拷贝 db 三件套到临时目录再打开，避免锁与 wal 一致性问题
  cp "$EMO"/*.db "$EMO"/*.db-wal "$EMO"/*.db-shm "$TMP/" 2>/dev/null || true
  DB="$TMP/$(ls "$EMO" | grep '\.db$' | head -1)"

  detect_ext() {
  # 读文件头魔法字节判断类型，比逐个调 file 命令快两个数量级
  local sig
  sig=$(od -An -tx1 -N16 "$1" | tr -d ' \n')
  case "$sig" in
    47494638*) echo gif ;;
    89504e47*) echo png ;;
    ffd8ff*)   echo jpg ;;
    52494646*) echo webp ;;   # RIFF....WEBP
    *66747970*|*6d6f6f76*|*6d646174*) echo mp4 ;;  # ftyp/moov/mdat
    000000*)   echo mp4 ;;    # mp4 box 头常以 00 长度开头
    *) echo bin ;;
  esac
}

idx=0
  echo "account,seq,file,source_path,url,last_modify_time" > "$DEST/manifest.csv"

  if [[ -f "$DB" ]]; then
    # mapping 表: type,key(远程URL),file_name(相对路径),last_modify_time,file_md5
    sqlite3 "$DB" "select key, file_name, last_modify_time from mapping where file_name != '' order by last_modify_time;" \
    | while IFS='|' read -r url rel mtime; do
        src="$EMO/$rel"
        [[ -f "$src" ]] || continue
        idx=$((idx+1))
        base="${rel##*/}"; base=${base#cover_}
        ext="${base##*.}"
        # 无扩展名的按文件头判断
        if [[ "$ext" == "$base" || -z "$ext" ]]; then
          ext=$(detect_ext "$src")
          base="$base.$ext"
        fi
        name=$(printf "%03d_%s" "$idx" "$base")
        cp -p "$src" "$DEST/$name"
        echo "$a,$idx,$name,$rel,$url,$mtime" >> "$DEST/manifest.csv"
      done
  fi

  # fallback: 目录里有但 db 没登记的文件（按源相对路径集合对比，O(n)）
  cut -d, -f4 "$DEST/manifest.csv" | sort -u > "$TMP/mapped.txt"
  touch "$TMP/mapped.txt"
  ( cd "$EMO" && find . -type f ! -path "./Temp/*" ! -name "*.db*" | sed 's|^\./||' | sort ) > "$TMP/all.txt"
  comm -13 "$TMP/mapped.txt" "$TMP/all.txt" > "$TMP/unmatched.txt"
  if [[ -s "$TMP/unmatched.txt" ]]; then
    { echo "account,relative_path"; while read -r f; do echo "$a,$f"; done < "$TMP/unmatched.txt"; } > "$DEST/manifest.unmatched.csv"
    echo "  (其中 $(wc -l < "$TMP/unmatched.txt" | tr -d ' ') 个文件未在云端索引中登记)"
  fi

  c=$(ls "$DEST" | grep -vc manifest || true)
  echo "账号 $a: 导出 $c 个表情 → $DEST"
  TOTAL=$((TOTAL + c))
done

# 生成预览页
HTML="$OUT/index.html"
{
  echo '<!DOCTYPE html><html><head><meta charset="utf-8"><title>企微表情包导出预览</title>'
  echo '<style>body{font-family:-apple-system,sans-serif;margin:24px;color:#222}h2{margin:24px 0 8px}'
  echo '.grid{display:flex;flex-wrap:wrap;gap:8px}.cell{width:96px;text-align:center;font-size:11px;color:#888;word-break:break-all}'
  echo '.cell img,.cell video{width:96px;height:96px;object-fit:contain;background:#f5f5f5;border-radius:6px}</style></head><body>'
  echo '<h1>企微表情包导出预览</h1><p>在新设备/新企业上：把想要的图拖进任意聊天窗口发送 → 右键 → 添加到表情。</p>'
  for a in "${TARGETS[@]}"; do
    echo "<h2>账号 $a</h2><div class=\"grid\">"
    (cd "$OUT/$a" && ls | grep -v manifest | while read -r f; do
      case "${f##*.}" in
        gif|png|jpg|jpeg|webp) echo "<div class=\"cell\"><img src=\"$a/$f\"><br>$f</div>" ;;
        mp4) echo "<div class=\"cell\"><video src=\"$a/$f\" muted loop onmouseover=\"this.play()\" onmouseout=\"this.pause()\"></video><br>$f</div>" ;;
      esac
    done)
    echo '</div>'
  done
  echo '</body></html>'
} > "$HTML"

if [[ $ZIP -eq 1 ]]; then
  (cd "$OUT/.." && zip -rq "$(basename "$OUT").zip" "$(basename "$OUT")")
  echo "已打包: $OUT/../$(basename "$OUT").zip"
fi

echo "完成: 共导出 $TOTAL 个表情"
echo "预览页: $HTML"
