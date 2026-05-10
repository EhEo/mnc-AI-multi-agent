#!/usr/bin/env bash
# multi-debate.sh — Phase 1: initialize a 3-AI debate session.
#
# Usage: multi-debate.sh "토론 질문"
#
# Creates a timestamped session directory, saves question.txt,
# and prints instructions for Claude to write claude-r1.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

[ -d "$AGENTS_DIR" ] || {
  echo "error: .agents-dev/ directory not found. Run from the project root." >&2
  exit 1
}

if [ "$#" -lt 1 ]; then
  echo "usage: $0 \"토론 질문\"" >&2
  exit 2
fi

QUESTION="$1"

detect_team() {
  if [ -n "${AGENT_TEAM:-}" ]; then echo "$AGENT_TEAM"; return; fi
  if [ -n "${TMUX:-}" ]; then
    local n tmux_t=()
    [ -n "${TMUX_PANE:-}" ] && tmux_t=(-t "$TMUX_PANE")
    n=$(tmux show-options -wqv "${tmux_t[@]}" '@team-name' 2>/dev/null) || n=""
    [ -n "$n" ] && { echo "$n"; return; }
    n=$(tmux display-message -p "${tmux_t[@]}" '#{session_name}' 2>/dev/null) || n=""
    [ -n "$n" ] && { echo "$n"; return; }
  fi
  echo default
}

TEAM=$(detect_team)
TEAM="${TEAM//\//-}"

TS="$(date +%Y%m%d-%H%M%S)"
SESSION_NAME="debate-${TS}"
SESSION_DIR="$AGENTS_DIR/log/$TEAM/$SESSION_NAME"

mkdir -p "$SESSION_DIR"
printf '%s\n' "$QUESTION" > "$SESSION_DIR/question.txt"

CLAUDE_R1="$SESSION_DIR/claude-r1.md"
AUTO_CMD="$SCRIPT_DIR/multi-debate-auto.sh $SESSION_DIR"

cat <<EOF

╔══════════════════════════════════════════╗
║  🗣️  3-AI 토론 세션 시작                 ║
╚══════════════════════════════════════════╝
세션: $SESSION_NAME
로그: $SESSION_DIR/

━━━ Round 1: Claude 답변 필요 ━━━
질문: "$QUESTION"

→ 답변을 작성하고 아래 파일에 저장하세요:
  $CLAUDE_R1

완료 후 실행:
  $AUTO_CMD
EOF
