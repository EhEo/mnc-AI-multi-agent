#!/usr/bin/env bash
# dashboard.sh — live, formatted summary view of gemini/codex wrapper runs.
#
# Usage:
#   dashboard.sh gemini    # render Gemini researcher status
#   dashboard.sh codex     # render Codex reviewer status
#
# Run this in a side tmux pane. Re-renders only when the source log changes
# (no flicker), and shows distilled key points — the full raw output stays
# in the Claude (PM) pane and on disk.
#
# Controls:
#   l       open full log in less (q to return)
#   space   toggle pause (auto-refresh on/off)
#   q       quit
#   Ctrl-C  also quits
set -uo pipefail

ROLE="${1:?usage: $0 gemini|codex [subtitle]}"
SUBTITLE="${2:-}"

case "$ROLE" in
  gemini)
    ICON="🔍"; TITLE="GEMINI · ${SUBTITLE:-researcher}"
    HEADER_COLOR=$'\033[1;36m'   # bright cyan
    LABEL="Query"
    ;;
  codex)
    ICON="🧐"; TITLE="CODEX · ${SUBTITLE:-reviewer}"
    HEADER_COLOR=$'\033[1;35m'   # bright magenta
    LABEL="Focus"
    ;;
  *)
    echo "usage: $0 gemini|codex [subtitle]" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Team namespace — must match what wrappers use.
# Priority: $AGENT_TEAM env > tmux @team-name window option > tmux session name > "default"
detect_team() {
  if [ -n "${AGENT_TEAM:-}" ]; then echo "$AGENT_TEAM"; return; fi
  if [ -n "${TMUX:-}" ]; then
    local n
    n=$(tmux show-options -wqv -t "${TMUX_PANE:-}" '@team-name' 2>/dev/null) || n=""
    [ -n "$n" ] && { echo "$n"; return; }
    n=$(tmux display-message -p -t "${TMUX_PANE:-}" '#{session_name}' 2>/dev/null) || n=""
    [ -n "$n" ] && { echo "$n"; return; }
  fi
  echo default
}
TEAM=$(detect_team)
TEAM="${TEAM//\//-}"   # / → - : prevent path breakage in log dir / filenames
LOG_DIR="$AGENTS_DIR/log/$TEAM"
LATEST="$LOG_DIR/latest-$ROLE.log"

RESET=$'\033[0m'
DIM=$'\033[2m'
BOLD=$'\033[1m'
GREEN=$'\033[1;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[1;31m'
CYAN=$'\033[1;36m'

cleanup() { printf '\033[?25h\033[H\033[2J'; exit 0; }   # show cursor + clear
trap cleanup INT TERM
printf '\033[?25l'   # hide cursor

get_wrap_width() {
  local c
  c=$(tput cols 2>/dev/null || echo 80)
  [ "$c" -lt 40 ] && c=40
  echo $((c - 6))
}

LAST_HASH=""
PAUSED=0

while true; do
  if [ "$PAUSED" = "0" ]; then
    WRAP_W=$(get_wrap_width)
    SEP=""; for ((i=0; i<WRAP_W+6; i++)); do SEP+="═"; done
    BUF=""
    BUF+="${HEADER_COLOR}${SEP}${RESET}"$'\n'
    BUF+="${HEADER_COLOR}  ${ICON}  ${TITLE}${RESET}"$'\n'
    BUF+="  ${DIM}[team: ${TEAM}]${RESET}"$'\n'
    BUF+="${HEADER_COLOR}${SEP}${RESET}"$'\n\n'

    if [ ! -e "$LATEST" ]; then
      BUF+="  ${DIM}(no runs yet — waiting for first call)${RESET}"$'\n'
      _DPATH="${LATEST/#$HOME/\~}"
      _DMAX=$(( WRAP_W - 8 ))
      [ "${#_DPATH}" -gt "$_DMAX" ] && _DPATH="...${_DPATH: -$((_DMAX - 3))}"
      BUF+="  ${DIM}path: ${_DPATH}${RESET}"$'\n\n'
    else
      TS=$(grep "^=== ask-${ROLE}.sh @ " "$LATEST" 2>/dev/null | tail -1 | awk '{print $4}')
      BUF+="  ${BOLD}Started:${RESET} ${TS:-unknown}"$'\n\n'

      # Query/Focus body
      if [ "$ROLE" = "gemini" ]; then
        BODY=$(awk '/^=== QUERY ===$/{flag=1; next} /^=== /{flag=0} flag' "$LATEST" 2>/dev/null)
      else
        BODY=$(awk '/^=== FOCUS ===$/{flag=1; next} /^=== /{flag=0} flag' "$LATEST" 2>/dev/null)
      fi
      BUF+="  ${BOLD}${LABEL}:${RESET}"$'\n'
      if [ -n "$BODY" ]; then
        WRAPPED=$(echo "$BODY" | fold -s -w "$WRAP_W" | head -5)
        while IFS= read -r line; do BUF+="    $line"$'\n'; done <<< "$WRAPPED"
      fi
      BUF+=$'\n'

      # Extract real response (codex echoes its prompt + duplicates final
      # response after "tokens used"; gemini doesn't have such framing).
      RESPONSE=""
      if [ "$ROLE" = "codex" ]; then
        RESPONSE=$(awk '/^tokens used/{flag=1; next} /^=== END /{flag=0} flag' "$LATEST" 2>/dev/null)
      fi
      if [ -z "$RESPONSE" ]; then
        RESPONSE=$(awk '/^=== RESPONSE ===$/{flag=1; next} /^=== END /{flag=0} flag' "$LATEST" 2>/dev/null)
      fi

      # Status (END marker = done)
      DONE=0; RC=""
      if grep -q '^=== END ' "$LATEST" 2>/dev/null; then
        DONE=1
        RC=$(grep '^=== END ' "$LATEST" | tail -1 | sed 's/.*rc=\([0-9]*\).*/\1/')
        if [ "$RC" = "0" ]; then
          BUF+="  ${BOLD}Status:${RESET} ${GREEN}✓ done${RESET}"$'\n\n'
        else
          BUF+="  ${BOLD}Status:${RESET} ${RED}✗ failed (rc=$RC)${RESET}"$'\n\n'
        fi
      else
        BUF+="  ${BOLD}Status:${RESET} ${YELLOW}⏳ running...${RESET}"$'\n\n'
      fi

      # ── Role-specific summary ────────────────────────────────────────────
      if [ "$ROLE" = "gemini" ] && [ "$DONE" = "1" ]; then
        # Lead: first paragraph of answer (skip Gemini CLI preamble lines)
        LEAD=$(echo "$RESPONSE" | awk '
          BEGIN { started=0 }
          /^Ripgrep|^Falling back/ { next }
          /^[^[:space:]]/ {
            if (!started) started=1
            if (started) print
          }
          started && /^$/ { exit }
        ')
        if [ -n "$LEAD" ]; then
          BUF+="  ${BOLD}Answer (lead):${RESET}"$'\n'
          WRAPPED=$(echo "$LEAD" | fold -s -w "$WRAP_W" | head -8)
          while IFS= read -r line; do
            BUF+="    ${line}"$'\n'
          done <<< "$WRAPPED"
          BUF+=$'\n'
        fi

        # Source count (URLs cited)
        SRC_COUNT=$(echo "$RESPONSE" | grep -cE 'https?://' || true)
        SRC_COUNT=${SRC_COUNT//[^0-9]/}; SRC_COUNT=${SRC_COUNT:-0}
        BUF+="  ${BOLD}Sources cited:${RESET} ${SRC_COUNT}"$'\n\n'

      elif [ "$ROLE" = "codex" ] && [ "$DONE" = "1" ]; then
        # Verdict bar
        VERDICT_LINE=$(echo "$RESPONSE" | grep -A 1 '^## Verdict' 2>/dev/null | tail -1 | sed 's/^[[:space:]]*//')
        if [ -n "$VERDICT_LINE" ]; then
          VERB=$(echo "$VERDICT_LINE" | awk '{print $1}')
          case "$VERB" in
            SHIP)      VC="$GREEN" ;;
            NEEDS-FIX) VC="$RED" ;;
            DISCUSS)   VC="$YELLOW" ;;
            *)         VC="$CYAN" ;;
          esac
          VWRAP=$(echo "$VERDICT_LINE" | fold -s -w $((WRAP_W - 8)))
          FIRST=1
          while IFS= read -r line; do
            if [ "$FIRST" = "1" ]; then
              BUF+="  ${VC}┃${RESET} ${BOLD}Verdict:${RESET} $line"$'\n'
              FIRST=0
            else
              BUF+="  ${VC}┃${RESET}   $line"$'\n'
            fi
          done <<< "$VWRAP"
          BUF+=$'\n'
        fi

        # Section-aware findings extraction
        SECS=$(echo "$RESPONSE" | awk '
          /^### Blocker/ { sec="bl"; next }
          /^### Major/   { sec="mj"; next }
          /^### Minor/   { sec="mn"; next }
          /^## /         { sec=""; next }
          sec=="bl" && /^- / && tolower($0) !~ /^- none/ { print "BL:" $0; next }
          sec=="mj" && /^- / && tolower($0) !~ /^- none/ { print "MJ:" $0; next }
          sec=="mn" && /^- / && tolower($0) !~ /^- none/ { print "MN:" $0; next }
        ' 2>/dev/null)
        BL=$(echo "$SECS" | grep -c '^BL:' 2>/dev/null || true); BL=${BL//[^0-9]/}; BL=${BL:-0}
        MJ=$(echo "$SECS" | grep -c '^MJ:' 2>/dev/null || true); MJ=${MJ//[^0-9]/}; MJ=${MJ:-0}
        MN=$(echo "$SECS" | grep -c '^MN:' 2>/dev/null || true); MN=${MN//[^0-9]/}; MN=${MN:-0}

        BUF+="  ${BOLD}Findings:${RESET} ${RED}${BL} blocker${RESET} · ${YELLOW}${MJ} major${RESET} · ${DIM}${MN} minor${RESET}"$'\n\n'

        if [ "$BL" -gt 0 ] || [ "$MJ" -gt 0 ]; then
          BUF+="  ${BOLD}${RED}Blockers + Major:${RESET}"$'\n'
          BLMJ=$(echo "$SECS" | grep -E '^(BL|MJ):' | sed 's/^BL://; s/^MJ://')
          WRAPPED=$(echo "$BLMJ" | fold -s -w "$WRAP_W")
          while IFS= read -r line; do
            [ -n "$line" ] && BUF+="    $line"$'\n'
          done <<< "$WRAPPED"
          BUF+=$'\n'
        fi
      fi

      REAL=$(readlink "$LATEST" 2>/dev/null || basename "$LATEST")
      _RPATH="${REAL/#$HOME/\~}"
      _RMAX=$(( WRAP_W - 8 ))
      [ "${#_RPATH}" -gt "$_RMAX" ] && _RPATH="...${_RPATH: -$((_RMAX - 3))}"
      BUF+="  ${DIM}log: ${_RPATH}${RESET}"$'\n'
    fi

    # Bottom control hint
    BUF+=$'\n'
    BUF+="  ${DIM}controls: ${BOLD}l${RESET}${DIM}=full log · ${BOLD}space${RESET}${DIM}=pause · ${BOLD}q${RESET}${DIM}=quit${RESET}"$'\n'

    # Flicker-free render: only redraw if content changed.
    # Use cursor-home + per-line erase-EOL + erase-to-end-of-screen instead
    # of a full \033[2J clear, so even when redrawing there's no visible blink.
    HASH=$(printf '%s' "$BUF" | cksum 2>/dev/null | awk '{print $1}')
    if [ "$HASH" != "$LAST_HASH" ]; then
      RENDERED="${BUF//$'\n'/$'\033[K\n'}"
      printf '\033[H%s\033[J' "$RENDERED"
      LAST_HASH="$HASH"
    fi
  fi

  # Wait up to 1s for keypress (also serves as the polling cadence).
  KEY=""
  IFS= read -rs -t 1 -n 1 KEY 2>/dev/null || true
  case "$KEY" in
    l)
      # Hand off to less for scrollable full-log view.
      printf '\033[?25h\033[H\033[2J'
      if [ -e "$LATEST" ]; then
        less -R "$LATEST" || true
      else
        echo "(no log yet — waiting for first call)"; sleep 1
      fi
      printf '\033[?25l'
      LAST_HASH=""   # force redraw on return
      ;;
    ' ')
      if [ "$PAUSED" = "0" ]; then
        PAUSED=1
        printf "\n  %s[PAUSED]%s press space to resume — Ctrl-b [ to scroll\n" "$YELLOW" "$RESET"
        # Show cursor while paused so tmux scroll feels normal
        printf '\033[?25h'
      else
        PAUSED=0
        printf '\033[?25l'
        LAST_HASH=""   # force redraw
      fi
      ;;
    q) cleanup ;;
  esac
done
