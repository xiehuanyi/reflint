#!/usr/bin/env bash
# Re-record DEMO_MODE fixtures from a real run (needs GOOGLE_API_KEY in .env).
cd "$(dirname "$0")/.." || exit 1
rm -f fixtures/recording.json fixtures/judge.json
RECORD_FIXTURES=1 uv run reflint audit examples/demo_paper/paper.md "$@"
# Mirror the HTTP cache into fixtures (same key scheme) so replay is complete.
mkdir -p fixtures/http && cp -f .cache/http/*.json fixtures/http/ 2>/dev/null
echo "fixtures updated: $(ls fixtures/http | wc -l) http, recording=$(test -f fixtures/recording.json && echo yes || echo NO)"
