#!/usr/bin/env bash
# Idempotent installer: materializes Hermes plugin from repo source of truth.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HOME/.hermes/plugins/vizier_tools"

mkdir -p "$PLUGIN_DIR"
cp "$REPO_DIR/plugins/hermes_loader/__init__.py" "$PLUGIN_DIR/__init__.py"
cp "$REPO_DIR/plugins/hermes_loader/plugin.yaml" "$PLUGIN_DIR/plugin.yaml"
echo "Plugin installed to $PLUGIN_DIR from $REPO_DIR/plugins/hermes_loader/"
