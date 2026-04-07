#!/bin/bash
eval "$(/opt/homebrew/bin/brew shellenv)"
cd "$(dirname "$0")"
exec npm run dev
