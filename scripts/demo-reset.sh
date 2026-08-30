#!/usr/bin/env bash
# Reset to the demo starting state between takes/judging rounds.
cd "$(dirname "$0")/.." || exit 1
rm -f reflint-report.md
clear
echo "RefLint demo ready."
echo "  live:  uv run reflint audit examples/demo_paper/paper.md"
echo "  demo:  DEMO_MODE=1 uv run reflint audit examples/demo_paper/paper.md"
