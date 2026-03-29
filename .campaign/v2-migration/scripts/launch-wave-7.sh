#!/usr/bin/env bash
# Launch Wave 7 — Cleanup (macOS)
set -euo pipefail

PROJECT_DIR="/Users/druk/WorkSpace/AetherForge/searchat"
CAMPAIGN_DIR="${PROJECT_DIR}/.campaign/v2-migration"
MARKERS_DIR="${CAMPAIGN_DIR}/.markers"
mkdir -p "${MARKERS_DIR}"

rm -f "${MARKERS_DIR}/terminal-H.done"
chmod +x "${CAMPAIGN_DIR}/scripts/terminal-H.sh"

if osascript -e 'id of application "iTerm2"' &>/dev/null; then
  osascript <<APPLESCRIPT
tell application "iTerm2"
  tell current window
    create tab with default profile
    tell current session of current tab
      set name to "Wave7-H: Cleanup"
      write text "bash ${CAMPAIGN_DIR}/scripts/terminal-H.sh"
    end tell
  end tell
end tell
APPLESCRIPT
  echo "Wave 7 launched in iTerm2 tab."
else
  SESSION="campaign-v2-migration-w7"
  tmux new-session -d -s "${SESSION}" -n "H-Cleanup" -c "${PROJECT_DIR}" \
    "bash ${CAMPAIGN_DIR}/scripts/terminal-H.sh; echo 'Terminal H done.'; read"
  echo "Wave 7 launched in tmux session: ${SESSION}"
  echo "Attach:  tmux attach -t ${SESSION}"
fi

echo "Monitor: ls ${MARKERS_DIR}/*.done"
