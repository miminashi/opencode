#!/bin/bash
set -eu
cd /home/ubuntu/projects/opencode/tmp/feat-bench
if [ ! -f package.json ]; then
  printf '{\n  "name": "feat-bench-pw",\n  "private": true,\n  "dependencies": { "playwright": "^1.60.0" }\n}\n' > package.json
fi
/home/ubuntu/.bun/bin/bun install
echo "playwright installed"
