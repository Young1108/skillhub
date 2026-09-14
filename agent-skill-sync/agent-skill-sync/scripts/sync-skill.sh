#!/usr/bin/env bash
# 把一个 skill 从规范源 ~/.agents/skills/<name> 同步到各 Agent 工具的 skills 目录。
#
# 用法:
#   sync-skill.sh <skill-name>        # 同步指定 skill
#   sync-skill.sh                     # 列出当前可同步的 skill 与各目标状态
#
# 目标约定（本机现状，2026-09 探测）:
#   ~/.agents/skills          规范源，真实的技能目录（其他目标从这里取）
#   以下目录是符号链接农场，统一指向 ../../.agents/skills/<name>：
#     ~/.claude/skills  ~/.kiro/skills  ~/.codebuddy/skills
#   以下目录各自存真实副本，需要拷贝：
#     ~/.codex/skills  ~/.cursor/skills  ~/.workbuddy/skills
#     ~/.grok/skills   ~/Doubao/skills   ~/.kun/skills
#
# 不要动的目录（工具自管 / 内置 / 远端）:
#   ~/.cursor/skills-cursor  ~/.codex/skills/.system  ~/.codex/vendor_imports/skills
#   ~/.codex/memories/skills  ~/.pi/remote/skills  ~/.grok/bundled/skills
#   ~/.workbuddy/connectors/skills  ~/.codebuddy/skills-marketplace/skills  ~/.gemini/**
#
# 注意: 本脚本只会删除 <目标skills目录>/<skill-name> 这一个子目录，不会触碰其他内容。

set -euo pipefail

SKILLS_SRC="$HOME/.agents/skills"
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

if [ $# -lt 1 ]; then
  echo "规范源: $SKILLS_SRC"
  echo
  echo "可用 skill:"
  for d in "$SKILLS_SRC"/*/; do
    name="$(basename "$d")"
    [ -f "$d/SKILL.md" ] || continue
    marks=""
    for base in "${COPY_TARGETS[@]}"; do
      [ -e "$base/$name" ] && marks="$marks $(basename "$(dirname "$base")")"
    done
    [ -e "$LINK_TARGETS[0]/$name" ] && marks="$marks claude"
    [ -e "${LINK_TARGETS[1]}/$name" ] && marks="$marks kiro"
    [ -e "${LINK_TARGETS[2]}/$name" ] && marks="$marks codebuddy"
    printf '  %-40s%s\n' "$name" "${marks:+  →${marks}}"
  done
  echo
  echo "用法: $(basename "$0") <skill-name>"
  exit 0
fi

SKILL="$1"
SRC="$SKILLS_SRC/$SKILL"

if [ ! -d "$SRC" ]; then
  echo "错误: 规范源目录不存在: $SRC" >&2
  exit 1
fi
if [ ! -f "$SRC/SKILL.md" ]; then
  echo "错误: $SRC 下没有 SKILL.md，不像一个 skill 目录" >&2
  exit 1
fi

# 目录拷贝型目标
for base in "${COPY_TARGETS[@]}"; do
  if [ ! -d "$base" ]; then
    echo "跳过（目录不存在）: $base"
    continue
  fi
  dest="$base/$SKILL"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    rm -rf -- "$dest"
  fi
  cp -R "$SRC" "$dest"
  echo "copied  -> $dest"
done

# 符号链接型目标（沿用本机既有约定：指向 ../../.agents/skills/<name>）
for base in "${LINK_TARGETS[@]}"; do
  if [ ! -d "$base" ]; then
    echo "跳过（目录不存在）: $base"
    continue
  fi
  dest="$base/$SKILL"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    rm -rf -- "$dest"
  fi
  ln -s "../../.agents/skills/$SKILL" "$dest"
  echo "symlink -> $dest"
done

echo
echo "完成。规范源: $SRC"
echo "提示: 改完规范源后重跑本脚本即可全量生效；不要直接改各工具目录下的副本。"
