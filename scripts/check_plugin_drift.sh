#!/usr/bin/env bash
# Detect drift between repo-owned plugin source and deployed plugin.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HOME/.hermes/plugins/vizier_tools"
DRIFT=0

for f in __init__.py plugin.yaml; do
  if [ ! -f "$PLUGIN_DIR/$f" ]; then
    echo "MISSING: $PLUGIN_DIR/$f"
    DRIFT=1
  elif ! diff -q "$REPO_DIR/plugins/hermes_loader/$f" "$PLUGIN_DIR/$f" >/dev/null 2>&1; then
    echo "DRIFT: $f differs between repo and deployed"
    diff "$REPO_DIR/plugins/hermes_loader/$f" "$PLUGIN_DIR/$f" || true
    DRIFT=1
  fi
done

if [ "$DRIFT" -eq 0 ]; then
  echo "No drift detected."
else
  echo "Run scripts/install_plugin.sh to sync."
  exit 1
fi
