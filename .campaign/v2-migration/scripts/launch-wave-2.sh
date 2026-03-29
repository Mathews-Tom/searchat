#!/usr/bin/env bash
# Launch Wave 2 — Storage + Agents (macOS, 2 terminals parallel)
set -euo pipefail

PROJECT_DIR="/Users/druk/WorkSpace/AetherForge/searchat"
CAMPAIGN_DIR="${PROJECT_DIR}/.campaign/v2-migration"
MARKERS_DIR="${CAMPAIGN_DIR}/.markers"
mkdir -p "${MARKERS_DIR}"

rm -f "${MARKERS_DIR}/terminal-B.done" "${MARKERS_DIR}/terminal-C.done"
chmod +x "${CAMPAIGN_DIR}/scripts/terminal-B.sh" "${CAMPAIGN_DIR}/scripts/terminal-C.sh"

if osascript -e 'id of application "iTerm2"' &>/dev/null; then
  launch_iterm_tab() {
    local title="$1"
    local script="$2"
    osascript <<APPLESCRIPT
tell application "iTerm2"
  tell current window
    create tab with default profile
    tell current session of current tab
      set name to "${title}"
      write text "bash ${script}"
    end tell
  end tell
end tell
APPLESCRIPT
  }

  echo "Launching Terminal B — DuckDB dual-write..."
  launch_iterm_tab "Wave2-B: DuckDB" "${CAMPAIGN_DIR}/scripts/terminal-B.sh"

  echo "Launching Terminal C — Agent framework..."
  launch_iterm_tab "Wave2-C: Agents" "${CAMPAIGN_DIR}/scripts/terminal-C.sh"

  echo "Wave 2 launched in iTerm2 tabs."
else
  SESSION="campaign-v2-migration-w2"
  tmux new-session -d -s "${SESSION}" -n "B-DuckDB" -c "${PROJECT_DIR}" \
    "bash ${CAMPAIGN_DIR}/scripts/terminal-B.sh; echo 'Terminal B done.'; read"
  tmux new-window -t "${SESSION}" -n "C-Agents" -c "${PROJECT_DIR}" \
    "bash ${CAMPAIGN_DIR}/scripts/terminal-C.sh; echo 'Terminal C done.'; read"
  echo "Wave 2 launched in tmux session: ${SESSION}"
  echo "Attach:  tmux attach -t ${SESSION}"
fi

echo "Monitor: ls ${MARKERS_DIR}/*.done"
