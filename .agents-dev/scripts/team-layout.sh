#!/usr/bin/env bash
# team-layout.sh — set up the 3-agent team layout in tmux.
#
#   ┌─────────────────┬──────────────────┐
#   │                 │  gemini          │
#   │  Claude (PM)    │  dashboard       │
#   │  shell —        ├──────────────────┤
#   │  run 'claude'   │  codex           │
#   │  yourself       │  dashboard       │
#   └─────────────────┴──────────────────┘
#
# Default: creates a new tmux session named "agents" and attaches.
# Use --here to apply to the current window instead.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DASH="$SCRIPT_DIR/dashboard.sh"

SESSION="agents"
HERE=0
ATTACH=1
AUTO_CLAUDE=0
GEMINI_LABEL="researcher"
CODEX_LABEL="reviewer"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Sets up the 3-agent team tmux layout (Claude main + Gemini/Codex dashboards).

Options:
  -n NAME        Session name (default: ${SESSION})
  --here         Apply layout to the current tmux window instead of creating a
                 new session. Splits the current pane in place.
  --no-attach    Create the session detached; do not attach.
  --auto-claude  Automatically run 'claude' in the main pane on startup.
  --debate       Use debate labels (Debate P2 / Debate P3) instead of researcher/reviewer.
  -h, --help     Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -n) SESSION="$2"; shift 2 ;;
    --here) HERE=1; shift ;;
    --no-attach) ATTACH=0; shift ;;
    --auto-claude) AUTO_CLAUDE=1; shift ;;
    --debate) GEMINI_LABEL="Debate P2"; CODEX_LABEL="Debate P3"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

command -v tmux >/dev/null 2>&1 || { echo "error: tmux not installed" >&2; exit 2; }
[ -x "$DASH" ] || { echo "error: $DASH not found or not executable" >&2; exit 2; }

if [ "$AUTO_CLAUDE" = "1" ] && [ "$ATTACH" = "0" ]; then
  echo "warning: --auto-claude with --no-attach: claude may exit immediately without a TTY" >&2
fi

if [ "$HERE" = "1" ]; then
  [ -n "${TMUX:-}" ] || { echo "error: --here requires running inside tmux" >&2; exit 2; }
  # Capture the main pane ID before any pane splits to avoid relying on select-pane success.
  HERE_MAIN_P="$(tmux display-message -p '#{pane_id}')"
  # Stamp this window with the team name (used by wrappers/dashboard for log isolation)
  # and rename the window for visibility.
  tmux set-option -w '@team-name' "$SESSION"
  tmux rename-window "$SESSION"
  GEMINI_P=$(tmux split-window -h -c "$REPO_DIR" -P -F "#{pane_id}")
  tmux send-keys -t "$GEMINI_P" "$DASH gemini \"$GEMINI_LABEL\"" Enter
  CODEX_P=$(tmux split-window -v -t "$GEMINI_P" -c "$REPO_DIR" -P -F "#{pane_id}")
  tmux send-keys -t "$CODEX_P" "$DASH codex \"$CODEX_LABEL\"" Enter
  tmux select-pane -L 2>/dev/null || true
  if [ "$AUTO_CLAUDE" = "1" ]; then
    tmux send-keys -t "$HERE_MAIN_P" "claude" Enter
    echo "✓ Layout applied to current window (team: ${SESSION}). Starting claude..."
  else
    echo "✓ Layout applied to current window (team: ${SESSION}). Run 'claude' in the left pane."
  fi
  exit 0
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already exists — attaching."
else
  # Use pane IDs (#{pane_id}, e.g. %42) rather than session:window.pane indexes
  # so the script works regardless of the user's base-index / pane-base-index.
  # -n NAME sets the initial window name; @team-name option isolates logs.
  MAIN_P=$(tmux new-session -d -s "$SESSION" -n "$SESSION" -c "$REPO_DIR" -P -F "#{pane_id}")
  tmux set-option -w -t "$SESSION" '@team-name' "$SESSION"
  GEMINI_P=$(tmux split-window -h -t "$MAIN_P" -c "$REPO_DIR" -P -F "#{pane_id}")
  tmux send-keys -t "$GEMINI_P" "$DASH gemini \"$GEMINI_LABEL\"" Enter
  CODEX_P=$(tmux split-window -v -t "$GEMINI_P" -c "$REPO_DIR" -P -F "#{pane_id}")
  tmux send-keys -t "$CODEX_P" "$DASH codex \"$CODEX_LABEL\"" Enter
  tmux select-pane -t "$MAIN_P"
  if [ "$AUTO_CLAUDE" = "1" ]; then
    tmux send-keys -t "$MAIN_P" "claude" Enter
  else
    tmux send-keys -t "$MAIN_P" "# 3-agent team ready (team: ${SESSION}). Run 'claude' to start." Enter
  fi
fi

if [ "$ATTACH" = "1" ]; then
  if [ -n "${TMUX:-}" ]; then
    tmux switch-client -t "$SESSION"
  else
    tmux attach -t "$SESSION"
  fi
else
  echo "✓ Session '$SESSION' ready (detached). Attach with:  tmux attach -t $SESSION"
fi
