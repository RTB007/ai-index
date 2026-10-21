#!/usr/bin/env bash
# ai-index healthcheck - push via ntfy als de dashboard-data te oud wordt
# (symptoom van o.a. een verlopen Claude-login). Draait dagelijks via systemd timer.
set -uo pipefail
TOPIC_URL="https://ntfy.sh/lowland-aiindex-alsj2zmwz2"
DATA="$HOME/ai-index/web/data.json"
MAX_AGE_DAYS=2

now=$(date +%s)
if [[ -f "$DATA" ]]; then
  mtime=$(stat -c %Y "$DATA")
  age=$(( (now - mtime) / 86400 ))
  when=$(date -d "@$mtime" '+%Y-%m-%d %H:%M')
else
  age=9999; when="(geen data.json)"
fi

if (( age > MAX_AGE_DAYS )); then
  curl -fsS     -H "Title: ai-index dashboard staat stil"     -H "Priority: high"     -H "Tags: warning"     -d "Data is ${age} dagen oud (laatste export: ${when}). Waarschijnlijk Claude-login verlopen op de VPS. Fix: ssh root@188.245.161.132 -t \"sudo -u ai-index -H /home/ai-index/.local/bin/claude /login\""     "$TOPIC_URL" >/dev/null && echo "ALERT verstuurd (age=${age}d)" || echo "ALERT-curl faalde"
else
  echo "OK (age=${age}d)"
fi
