#!/usr/bin/env bash
# debate-codex.sh — invoke Codex as debate participant P3.
#
# Usage:
#   debate-codex.sh r1 "question" outfile
#   debate-codex.sh r2 "question" outfile other1-file other2-file
#   debate-codex.sh r3 "question" outfile other1-file other2-file
#
# Writes clean response to <outfile> for use by subsequent rounds.
# Also writes a dashboard-compatible structured log and updates the
# latest-codex.log symlink so dashboard.sh can display live status.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROLE_FILE="$AGENTS_DIR/roles/debater-codex.md"

ROUND="${1:?usage: $0 <r1|r2|r3> <question> <outfile> [other1] [other2]}"
QUESTION="${2:?question required}"
OUTFILE="${3:?outfile required}"
OTHER1="${4:-}"
OTHER2="${5:-}"

# ── Dashboard log setup ───────────────────────────────────────────────────
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
LOG_DIR="$AGENTS_DIR/log/$TEAM"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
STRUCTURED_LOG="$LOG_DIR/codex-debate-${ROUND}-${TS}.log"
ln -sfn "$STRUCTURED_LOG" "$LOG_DIR/latest-codex.log"

[ -f "$ROLE_FILE" ] || { echo "error: role file not found: $ROLE_FILE" >&2; exit 2; }
ROLE="$(cat "$ROLE_FILE")"

case "$ROUND" in
  r1)
    PROMPT="$ROLE

---
다음 질문에 토론 참가자(P3: Codex)로서 답하라.

질문: $QUESTION

주장을 1문장으로 제시하고 핵심 근거 3가지를 번호 목록으로 서술하라. 500자 이내."
    ;;
  r2)
    [ -f "$OTHER1" ] || { echo "error: other1 file not found: $OTHER1" >&2; exit 2; }
    [ -f "$OTHER2" ] || { echo "error: other2 file not found: $OTHER2" >&2; exit 2; }
    PROMPT="$ROLE

---
질문: $QUESTION

## 다른 참가자들의 Round 1 답변

### Claude (P1)
$(cat "$OTHER1")

### Gemini (P2)
$(cat "$OTHER2")

---
위 두 답변을 분석하라. ## 동의 / ## 반대 / ## 추가 의견 섹션으로 구분해 작성하라."
    ;;
  r3)
    [ -f "$OTHER1" ] || { echo "error: other1 file not found: $OTHER1" >&2; exit 2; }
    [ -f "$OTHER2" ] || { echo "error: other2 file not found: $OTHER2" >&2; exit 2; }
    PROMPT="$ROLE

---
질문: $QUESTION

## 다른 참가자들의 Round 2 교차 분석

### Claude (P1)
$(cat "$OTHER1")

### Gemini (P2)
$(cat "$OTHER2")

---
위 두 분석에 대해 반론하거나 보충 설명하라. 필요하다면 추가 근거를 제시하라.
## 반론 / ## 보충 섹션으로 구분해 작성하라."
    ;;
  *)
    echo "error: unknown round '$ROUND'. Use r1, r2, or r3." >&2
    exit 2
    ;;
esac

# ── Write structured log header (dashboard-compatible) ───────────────────
{
  echo "=== ask-codex.sh @ $TS ==="
  echo "=== FOCUS ==="
  echo "[debate-codex ${ROUND}] $QUESTION"
  echo "=== RESPONSE ==="
} > "$STRUCTURED_LOG"

# ── Run Codex: full output → structured log, clean response → OUTFILE ────
RC=0
FULL_OUTPUT=$("${REVIEWER_CLI:-${CODEX_CLI:-codex}}" exec "$PROMPT" 2>&1) || RC=$?
printf '%s\n' "$FULL_OUTPUT" >> "$STRUCTURED_LOG"

# Extract clean response: text after "tokens used" + skip the token-count line
CLEAN=$(printf '%s\n' "$FULL_OUTPUT" | awk '
  /^tokens used/ { skip=2; buf=""; next }
  skip > 0       { skip--; next }
  { buf = buf $0 "\n" }
  END            { printf "%s", buf }
' | sed '/^[[:space:]]*$/{ /./!d }')
# Fallback: strip codex preamble lines only
if [ -z "$CLEAN" ]; then
  CLEAN=$(printf '%s\n' "$FULL_OUTPUT" | grep -v "^Reading additional\|^OpenAI Codex\|^--------\|^workdir:\|^model:\|^provider:\|^approval:\|^sandbox:\|^reasoning\|^session id:\|^tokens used\|^[0-9,]*$" || true)
fi
printf '%s\n' "$CLEAN" > "$OUTFILE"
printf '\n=== END (rc=%d) ===\n' "$RC" >> "$STRUCTURED_LOG"
exit "$RC"
