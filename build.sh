#!/bin/sh

bun install &&
  cd packages/opencode &&
  bun run build --single &&
  bun run typecheck &&
  echo "" &&
  echo "ビルド済みバイナリ:" &&
  echo "  /home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode"
