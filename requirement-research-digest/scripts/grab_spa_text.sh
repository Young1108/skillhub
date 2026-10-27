#!/usr/bin/env bash
# 用独立 Chrome（干净 profile、无登录态）渲染 SPA 页面并抽取纯文本。
# 适用：doc.weixin.qq.com smartpage、手写 SPA、无 API 的分享页。
# 用法: grab_spa_text.sh <url> <out.txt> [waitHintSeconds]
#
# 退出码: 0 成功 / 3 文本过短（疑似登录墙）/ 1 环境问题
set -uo pipefail

URL="${1:?usage: grab_spa_text.sh <url> <out.txt>}"
OUT="${2:?usage: grab_spa_text.sh <url> <out.txt>}"
PORT="${PORT:-9333}"
PROFILE="/tmp/chrome-spa-$PORT"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ -x "$CHROME" ] || { echo "chrome not found: $CHROME" >&2; exit 1; }
command -v node >/dev/null || { echo "node not found" >&2; exit 1; }

cleanup() {
  pkill -f "user-data-dir=$PROFILE" 2>/dev/null
  sleep 0.5
  rm -rf "$PROFILE" "$PROFILE.log"
}
trap cleanup EXIT

# 端口被旧实例占用 -> 先清掉
if curl -s --max-time 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
  pkill -f "remote-debugging-port=$PORT" 2>/dev/null
  sleep 1
fi

rm -rf "$PROFILE"; mkdir -p "$PROFILE"
# 后台起浏览器。--no-sandbox 必须加，否则沙箱内会 network service crashed 后退出。
"$CHROME" --user-data-dir="$PROFILE" --remote-debugging-port="$PORT" \
  --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --no-first-run --no-default-browser-check --disable-sync \
  --window-size=1280,900 "about:blank" >"$PROFILE.log" 2>&1 &

for _ in $(seq 1 20); do
  curl -s --max-time 1 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -s --max-time 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 || {
  echo "chrome devtools port $PORT not ready; see $PROFILE.log" >&2; exit 1; }

node "$HERE/grab_text.mjs" "$URL" "$OUT" "$PORT" "${3:-25}"
rc=$?
echo "--- result: $OUT ($(wc -c <"$OUT" 2>/dev/null || echo 0) bytes) rc=$rc" >&2
exit $rc
