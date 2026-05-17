#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../frontend"
if [ ! -d node_modules ] || [ ! -x node_modules/.bin/next ]; then
  echo "Installing dependencies..."
  npm install
fi
npm run dev
