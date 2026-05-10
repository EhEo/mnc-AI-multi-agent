#!/usr/bin/env bash
# multi-debate-auto.sh — Phase 2: full 3-round debate automation.
#
# Usage: multi-debate-auto.sh <session-dir>
#
# Expects <session-dir>/question.txt and <session-dir>/claude-r1.md to exist.
# Runs Gemini and Codex in parallel per round; Claude via claude -p sequentially.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEBATE_GEMINI="$SCRIPT_DIR/debate-gemini.sh"
DEBATE_CODEX="$SCRIPT_DIR/debate-codex.sh"

SESSION_DIR="${1:?usage: $0 <session-dir>}"
[ -d "$SESSION_DIR" ] || { echo "error: session dir not found: $SESSION_DIR" >&2; exit 2; }
SESSION_DIR="$(cd "$SESSION_DIR" && pwd)"

QUESTION_FILE="$SESSION_DIR/question.txt"
[ -f "$QUESTION_FILE" ] || { echo "error: question.txt not found in $SESSION_DIR" >&2; exit 2; }
QUESTION="$(cat "$QUESTION_FILE")"

CLAUDE_R1="$SESSION_DIR/claude-r1.md"
[ -f "$CLAUDE_R1" ] || {
  echo "error: claude-r1.md not found. Write your Round 1 answer first:" >&2
  echo "  $CLAUDE_R1" >&2
  exit 2
}

# Git repo check (required for Codex); check against AGENTS_DIR, not CWD
git -C "$AGENTS_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "error: not a git repository. Codex requires git. Run: git init" >&2
  exit 2
}

TEAM_DIR="$(dirname "$SESSION_DIR")"
CLAUDE_ROLE_FILE="$AGENTS_DIR/roles/debater-claude.md"
[ -f "$CLAUDE_ROLE_FILE" ] || { echo "error: debater-claude.md not found" >&2; exit 2; }

_update_symlinks() {
  local suffix="$1"
  ln -sfn "$SESSION_DIR/gemini-${suffix}.md" "$TEAM_DIR/latest-gemini.log" 2>/dev/null || true
  ln -sfn "$SESSION_DIR/codex-${suffix}.md"  "$TEAM_DIR/latest-codex.log"  2>/dev/null || true
}

_run_claude() {
  local outfile="$1"; local prompt="$2"
  echo "[Claude auto] 실행 중..."
  "${CLAUDE_CLI:-claude}" -p "$prompt" > "$outfile"
  echo "[Claude auto] 완료 → $(basename "$outfile")"
}


# ── Round 1 ──────────────────────────────────────────────────────────────
echo && echo "[R1] Gemini + Codex 병렬 호출 중..."
_update_symlinks r1

GPID=0; CPID=0; GRC=0; CRC=0
"$DEBATE_GEMINI" r1 "$QUESTION" "$SESSION_DIR/gemini-r1.md" &
GPID=$!
"$DEBATE_CODEX"  r1 "$QUESTION" "$SESSION_DIR/codex-r1.md" &
CPID=$!
wait $GPID || GRC=$?
wait $CPID || CRC=$?
[ $GRC -eq 0 ] || { echo "error: Gemini R1 failed (rc=$GRC)" >&2; exit 1; }
[ $CRC -eq 0 ] || { echo "error: Codex R1 failed (rc=$CRC)"  >&2; exit 1; }
[ -s "$SESSION_DIR/gemini-r1.md" ] || { echo "error: gemini-r1.md is empty" >&2; exit 1; }
[ -s "$SESSION_DIR/codex-r1.md"  ] || { echo "error: codex-r1.md is empty"  >&2; exit 1; }
echo "[R1] 완료 ✓"

# ── Round 2 ──────────────────────────────────────────────────────────────
echo && echo "[R2] 교차 분석 시작..."

CLAUDE_ROLE="$(cat "$CLAUDE_ROLE_FILE")"

_run_claude "$SESSION_DIR/claude-r2.md" "$CLAUDE_ROLE

---
질문: $QUESTION

## 다른 참가자들의 Round 1 답변

### Gemini (P2)
$(cat "$SESSION_DIR/gemini-r1.md")

### Codex (P3)
$(cat "$SESSION_DIR/codex-r1.md")

---
위 두 답변을 분석하라. ## 동의 / ## 반대 / ## 추가 의견 섹션으로 구분해 작성하라."

_update_symlinks r2
GRC=0; CRC=0
"$DEBATE_GEMINI" r2 "$QUESTION" "$SESSION_DIR/gemini-r2.md" \
  "$SESSION_DIR/claude-r1.md" "$SESSION_DIR/codex-r1.md" &
GPID=$!
"$DEBATE_CODEX"  r2 "$QUESTION" "$SESSION_DIR/codex-r2.md" \
  "$SESSION_DIR/claude-r1.md" "$SESSION_DIR/gemini-r1.md" &
CPID=$!
wait $GPID || GRC=$?
wait $CPID || CRC=$?
[ $GRC -eq 0 ] || { echo "error: Gemini R2 failed (rc=$GRC)" >&2; exit 1; }
[ $CRC -eq 0 ] || { echo "error: Codex R2 failed (rc=$CRC)"  >&2; exit 1; }
[ -s "$SESSION_DIR/gemini-r2.md" ] || { echo "error: gemini-r2.md is empty" >&2; exit 1; }
[ -s "$SESSION_DIR/codex-r2.md"  ] || { echo "error: codex-r2.md is empty"  >&2; exit 1; }
echo "[R2] 완료 ✓"

# ── Round 3 ──────────────────────────────────────────────────────────────
echo && echo "[R3] 반론·보충 시작..."

_run_claude "$SESSION_DIR/claude-r3.md" "$CLAUDE_ROLE

---
질문: $QUESTION

## 다른 참가자들의 Round 2 교차 분석

### Gemini (P2)
$(cat "$SESSION_DIR/gemini-r2.md")

### Codex (P3)
$(cat "$SESSION_DIR/codex-r2.md")

---
위 두 분석에 대해 반론하거나 보충 설명하라. 필요하다면 추가 근거를 제시하라.
## 반론 / ## 보충 섹션으로 구분해 작성하라."

_update_symlinks r3
GRC=0; CRC=0
"$DEBATE_GEMINI" r3 "$QUESTION" "$SESSION_DIR/gemini-r3.md" \
  "$SESSION_DIR/claude-r2.md" "$SESSION_DIR/codex-r2.md" &
GPID=$!
"$DEBATE_CODEX"  r3 "$QUESTION" "$SESSION_DIR/codex-r3.md" \
  "$SESSION_DIR/claude-r2.md" "$SESSION_DIR/gemini-r2.md" &
CPID=$!
wait $GPID || GRC=$?
wait $CPID || CRC=$?
[ $GRC -eq 0 ] || { echo "error: Gemini R3 failed (rc=$GRC)" >&2; exit 1; }
[ $CRC -eq 0 ] || { echo "error: Codex R3 failed (rc=$CRC)"  >&2; exit 1; }
echo "[R3] 완료 ✓"

# ── Final report ──────────────────────────────────────────────────────────
echo && echo "[Final] 최종 보고서 생성 중..."

NOW="$(date '+%Y-%m-%d %H:%M')"
_run_claude "$SESSION_DIR/final-report.md" \
"당신은 3-AI 토론 시스템의 오케스트레이터입니다.
아래는 Claude(P1) · Gemini(P2) · Codex(P3) 세 AI가 3라운드에 걸쳐 진행한 토론 전체 내용입니다.

질문: $QUESTION
일시: $NOW | 참여: Claude(P1) · Gemini(P2) · Codex(P3)

---

## Round 1 — 독립 답변

### Claude (P1)
$(cat "$SESSION_DIR/claude-r1.md")

### Gemini (P2)
$(cat "$SESSION_DIR/gemini-r1.md")

### Codex (P3)
$(cat "$SESSION_DIR/codex-r1.md")

---

## Round 2 — 교차 분석

### Claude (P1)
$(cat "$SESSION_DIR/claude-r2.md")

### Gemini (P2)
$(cat "$SESSION_DIR/gemini-r2.md")

### Codex (P3)
$(cat "$SESSION_DIR/codex-r2.md")

---

## Round 3 — 반론·보충

### Claude (P1)
$(cat "$SESSION_DIR/claude-r3.md")

### Gemini (P2)
$(cat "$SESSION_DIR/gemini-r3.md")

### Codex (P3)
$(cat "$SESSION_DIR/codex-r3.md")

---
위 토론 전체를 종합해 다음 형식으로 최종 보고서를 작성하라:

# 최종 토론 보고서
질문: \"$QUESTION\"
일시: $NOW | 참여: Claude · Gemini · Codex

## 1. 각 AI 핵심 주장 요약
(각 AI의 R1 핵심 주장을 2-3문장으로 요약)

## 2. 합의 영역
(3개 AI가 공통으로 동의한 포인트)

## 3. 쟁점 영역
(의견 차이가 있었던 포인트와 각 입장)

## 4. 최종 결론 / 종합 판단
(오케스트레이터로서의 최종 종합 의견)

## 5. 로그 경로
- R1: claude-r1.md | gemini-r1.md | codex-r1.md
- R2: claude-r2.md | gemini-r2.md | codex-r2.md
- R3: claude-r3.md | gemini-r3.md | codex-r3.md
- 세션: $SESSION_DIR"

echo
echo "╔══════════════════════════════════════════╗"
echo "║  완료! 토론이 완성되었습니다.             ║"
echo "╚══════════════════════════════════════════╝"
echo "최종 보고서: $SESSION_DIR/final-report.md"
