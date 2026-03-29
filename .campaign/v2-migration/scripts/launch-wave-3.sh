#!/usr/bin/env bash
# Launch Wave 3 — Search Upgrade (macOS)
set -euo pipefail

PROJECT_DIR="/Users/druk/WorkSpace/AetherForge/searchat"
CAMPAIGN_DIR="${PROJECT_DIR}/.campaign/v2-migration"
MARKERS_DIR="${CAMPAIGN_DIR}/.markers"
mkdir -p "${MARKERS_DIR}"

rm -f "${MARKERS_DIR}/terminal-D.done"
chmod +x "${CAMPAIGN_DIR}/scripts/terminal-D.sh"

if osascript -e 'id of application "iTerm2"' &>/dev/null; then
  osascript <<APPLESCRIPT
tell application "iTerm2"
  tell current window
    create tab with default profile
    tell current session of current tab
      set name to "Wave3-D: Search"
      write text "bash ${CAMPAIGN_DIR}/scripts/terminal-D.sh"
    end tell
  end tell
end tell
APPLESCRIPT
  echo "Wave 3 launched in iTerm2 tab."
else
  SESSION="campaign-v2-migration-w3"
  tmux new-session -d -s "${SESSION}" -n "D-Search" -c "${PROJECT_DIR}" \
    "bash ${CAMPAIGN_DIR}/scripts/terminal-D.sh; echo 'Terminal D done.'; read"
  echo "Wave 3 launched in tmux session: ${SESSION}"
  echo "Attach:  tmux attach -t ${SESSION}"
fi

echo "Monitor: ls ${MARKERS_DIR}/*.done"
