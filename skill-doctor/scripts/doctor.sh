#!/usr/bin/env bash
# skill-doctor 体检脚本
#
# 用法:
#   doctor.sh                      # 全量体检 ~/.agents/skills 下所有 skill
#   doctor.sh <name> [<name>...]   # 只体检指定 skill
#   doctor.sh --init <name>        # 为该 skill 创建账本骨架
#
# 检查项:
#   1 frontmatter 完整性（name / description / version / agent_created，name 与目录名一致）
#   2 description 是否含触发词（本机自建 skill 的检索依赖它）
#   3 分发状态（7 个工具目录：拷贝型 + 软链型）
#   4 SKILL.md 行数预算
#   5 账本：缺失 / 长期未迭代 / 未采纳积压
#   6 跨 skill 触发词重叠（疑似职责重复）
#
# 只读，不修改任何 skill；--init 只写 ~/.agents/skill-ledger/，不碰 skills/。
# 兼容 macOS bash 3.2（不使用关联数组），无需 GNU 工具。
#
# ⚠ bash 3.2 踩坑：变量展开后面紧跟非 ASCII 字符（全角空格/「（」/「，」）会被
#   当成变量名的一部分，报 "SRC: unbound variable"。本脚本一律写成 ${VAR}。

set -uo pipefail

SRC="$HOME/.agents/skills"
LEDGER_DIR="$HOME/.agents/skill-ledger"
LINE_LIMIT=200
STALE_DAYS=30
MAX_UNACTIONED=3

COPY_TARGETS=(
  "$HOME/.codex/skills"
  "$HOME/.cursor/skills"
  "$HOME/.workbuddy/skills"
  "$HOME/.grok/skills"
  "$HOME/Doubao/skills"
  "$HOME/.kun/skills"
)
LINK_TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.kiro/skills"
  "$HOME/.codebuddy/skills"
)

# 取 frontmatter 中的简单 key: value
fm_field() {
  awk -v k="$2" '
    NR==1 && $0 !~ /^---[[:space:]]*$/ { exit }
    NR>1 && /^---[[:space:]]*$/ { exit }
    NR>1 {
      line=$0
      if (line ~ ("^[[:space:]]*" k "[[:space:]]*:")) {
        sub(("^[[:space:]]*" k "[[:space:]]*:[[:space:]]*"), "", line)
        sub(/[[:space:]]+$/, "", line)
        gsub(/^"|"$/, "", line)
        gsub(/^'"'"'|'"'"'$/, "", line)
        print line; exit
      }
    }
  ' "$1"
}

# 提取 description 中「触发词：」到「不负责」之间的词条
triggers_of() {
  local d seg
  d=$(fm_field "$1" description)
  [ -z "$d" ] && return 0
  seg="${d#*触发词：}"
  [ "$seg" = "$d" ] && return 0
  seg="${seg%%不负责*}"
  printf '%s' "$seg" | awk '{
    n=split($0,a,"、")
    for(i=1;i<=n;i++){ gsub(/^[[:space:]]+|[[:space:]]+$/,"",a[i]); if(a[i]!="") print a[i] }
  }'
}

days_since() {
  local d="$1" then_s now_s
  [ -z "$d" ] && return 0
  then_s=$(date -j -f "%Y-%m-%d" "$d" +%s 2>/dev/null || date -d "$d" +%s 2>/dev/null) || true
  [ -z "${then_s:-}" ] && return 0
  now_s=$(date +%s)
  echo $(( (now_s - then_s) / 86400 ))
}

init_ledger() {
  local name="$1" file="$LEDGER_DIR/$1.md" ver="1.0.0" today
  today=$(date +%Y-%m-%d)
  if [ -f "$file" ]; then
    echo "已存在，未覆盖: $file"
    return 0
  fi
  [ -f "$SRC/$name/SKILL.md" ] || { echo "错误: 规范源无此 skill: $SRC/$name" >&2; return 1; }
  v=$(fm_field "$SRC/$name/SKILL.md" version)
  [ -n "${v:-}" ] && ver="$v"
  mkdir -p "$LEDGER_DIR"
  cat > "$file" <<EOF
# $name · 迭代账本

- 当前版本：$ver
- 首次记录：$today
- 最后迭代：$today
- 累计场景：0　累计补丁：0　未采纳：0

## 场景矩阵

| # | 日期 | 场景（可辨识特征） | 命中章节 | 结果 | 动作 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |

## 补丁历史（倒序）

## 观察未采纳

EOF
  echo "created -> $file"
  echo "格式说明: ~/.agents/skills/skill-doctor/references/ledger-format.md"
}

# ---------- 参数 ----------
TARGETS=()
if [ "${1:-}" = "--init" ]; then
  shift
  [ $# -ge 1 ] || { echo "用法: doctor.sh --init <skill-name>" >&2; exit 1; }
  for n in "$@"; do init_ledger "$n"; done
  exit 0
fi
if [ $# -ge 1 ]; then
  TARGETS=("$@")
else
  for d in "$SRC"/*/; do
    [ -f "$d/SKILL.md" ] || continue
    TARGETS+=("$(basename "$d")")
  done
fi

[ ${#TARGETS[@]} -gt 0 ] || { echo "规范源下没有 skill: $SRC" >&2; exit 1; }

TRIGGER_TMP=$(mktemp)
trap 'rm -f "$TRIGGER_TMP"' EXIT

ATTENTION=""
CRITICAL=""

echo "skill-doctor 体检　规范源: ${SRC}　账本: $LEDGER_DIR"
echo "================================================================"

for name in "${TARGETS[@]}"; do
  f="$SRC/$name/SKILL.md"
  echo
  if [ ! -f "$f" ]; then
    echo "[$name] ✗ 规范源无 SKILL.md"
    CRITICAL="$CRITICAL\n  - $name: 规范源缺 SKILL.md"
    continue
  fi

  fm_name=$(fm_field "$f" name)
  desc=$(fm_field "$f" description)
  ver=$(fm_field "$f" version)
  ac=$(fm_field "$f" agent_created)
  lines=$(wc -l < "$f" | tr -d ' ')

  issues=""

  if [ -z "${fm_name:-}" ]; then
    issues="$issues\n    ✗ frontmatter 缺 name"
  elif [ "$fm_name" != "$name" ]; then
    issues="$issues\n    ✗ name($fm_name) 与目录名($name) 不一致"
  fi
  [ -z "${desc:-}" ] && issues="$issues\n    ✗ frontmatter 缺 description"

  OWN=0
  [ "${ac:-}" = "true" ] && OWN=1

  tcount=$(triggers_of "$f" | wc -l | tr -d ' ')
  if [ "$OWN" = "1" ]; then
    [ -z "${ver:-}" ] && issues="$issues\n    ⚠ 缺 version"
    if [ -n "${desc:-}" ]; then
      case "$desc" in
        *触发词*) : ;;
        *) issues="$issues\n    ⚠ description 无「触发词：」段（检索命中率会低）" ;;
      esac
    fi
    [ "$tcount" = "0" ] && [ -n "${desc:-}" ] && issues="$issues\n    ⚠ 触发词数量为 0"
  else
    issues="$issues\n    ℹ 外部 skill（未标 agent_created）：正文迭代只能产出建议 patch 或建本地 override"
  fi

  if [ "$lines" -gt "$LINE_LIMIT" ]; then
    issues="$issues\n    ⚠ SKILL.md $lines 行 > ${LINE_LIMIT}，细则该下沉 references/"
  fi

  # 分发状态
  marks=""
  for base in "${COPY_TARGETS[@]}"; do
    [ -e "$base/$name" ] && marks="$marks $(basename "$(dirname "$base")")"
  done
  for base in "${LINK_TARGETS[@]}"; do
    [ -e "$base/$name" ] && marks="$marks $(basename "$(dirname "$base")")"
  done
  [ -z "$marks" ] && issues="$issues\n    ⚠ 未分发到任何工具目录（跑 sync-skill.sh ${name}）"

  # 账本
  lf="$LEDGER_DIR/$name.md"
  if [ ! -f "$lf" ]; then
    if [ "$OWN" = "1" ]; then
      issues="$issues\n    ⚠ 无账本（doctor.sh --init $name 建一份）"
      ATTENTION="$ATTENTION\n  - $name: 无账本"
    else
      issues="$issues\n    ℹ 无账本（可选：doctor.sh --init ${name}）"
    fi
  else
    last=$(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' "$lf" | sort | tail -1)
    scen=$(awk '/^## 场景矩阵/{f=1;next} /^## /{f=0} f && /^\|/ && $0 !~ /^\| *-+/ && $0 !~ /^\| *# /' "$lf" | wc -l | tr -d ' ')
    pat=$(grep -cE '^### v' "$lf" | tr -d ' ')
    una=$(awk '/^## 观察未采纳/{f=1;next} /^## /{f=0} f && /^- /' "$lf" | wc -l | tr -d ' ')
    age=$(days_since "$last")
    [ -n "${age:-}" ] && [ "$age" -gt "$STALE_DAYS" ] && issues="$issues\n    ⚠ 账本最后迭代距今 ${age} 天（>${STALE_DAYS}），可能与实际脱节"
    [ "$una" -ge "$MAX_UNACTIONED" ] && issues="$issues\n    ⚠ 未采纳积压 $una 条（≥${MAX_UNACTIONED}），同类应已可升级为补丁"
    printf '  账本: 场景 %s · 补丁 %s · 未采纳 %s · 最后迭代 %s\n' "$scen" "$pat" "$una" "${last:-无}"
  fi

  printf '[%s] v%s · %s 行 · 触发词 %s · 分发:%s\n' "$name" "${ver:-?}" "$lines" "$tcount" "${marks:- 无}"

  # 收集触发词做重叠检测
  triggers_of "$f" | while read -r t; do
    [ -z "$t" ] && continue
    printf '%s\t%s\n' "$t" "$name" >> "$TRIGGER_TMP"
  done
  [ -z "$fm_name" ] || true

  if [ -n "$issues" ]; then
    printf '%b\n' "$issues"
    case "$issues" in *"✗"*) CRITICAL="$CRITICAL\n  - $name";; esac
  else
    echo "    ✓ 无问题"
  fi
done

echo
echo "================================================================"

# 跨 skill 触发词重叠
if [ -s "$TRIGGER_TMP" ]; then
  dup=$(sort "$TRIGGER_TMP" | awk -F'\t' '
    { if ($1==prev) { if (!shown) { printf "  %s -> %s", $1, pskill; shown=1 } printf ", %s", $2 }
      else { if (shown) printf "\n"; prev=$1; pskill=$2; shown=0 } }
    END { if (shown) printf "\n" }
  ')
  if [ -n "${dup:-}" ]; then
    echo "疑似触发词重叠（同一触发词被多个 skill 声明，确认是否职责重复）:"
    printf '%s\n' "$dup"
    echo
  fi
fi

if [ -n "$CRITICAL" ]; then
  echo "结构问题（须修）:"
  printf '%b\n' "$CRITICAL"
  echo
fi
if [ -n "$ATTENTION" ]; then
  echo "待关注:"
  printf '%b\n' "$ATTENTION"
  echo
fi
[ -z "$CRITICAL" ] && [ -z "$ATTENTION" ] && echo "全部通过。"
echo "体检结束（本脚本只读；迭代动作由 skill-doctor 流程执行）。"
