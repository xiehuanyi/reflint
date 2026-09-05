# AI usage disclosure — RefLint

Honest log of which AI tools built what. Kept current per workspace rules.

| Date | Tool | What it did |
|---|---|---|
| 2026-08-31 | Claude (Claude Code agent) | Ideation scoring, idea brief, build plan |
| 2026-08-31 | Claude (Claude Code agent) | Implemented the full codebase (Strands orchestrator + judge sub-agent, tools, Crossref/OpenAlex/Semantic Scholar clients, replay model, CLI, report renderer) under human direction |
| 2026-08-31 | Claude (Claude Code agent) | Authored the demo manuscript with planted integrity failures (marked `DEMO:`), architecture diagram (SVG), README, Devpost copy, video script, builder.aws.com article draft |
| 2026-08-31 | Gemini (gemini-flash-lite-latest / 3.5-flash) | Runtime models inside the product itself: orchestrator reasoning + claim-support judging |
| 2026-08-31 | Claude (Claude Code agent) | Produced the demo video (`docs/video.mp4`): captured the real live run, built the xterm.js replay + Playwright screen recording, slides, and ffmpeg assembly (see `docs/video-notes.md`) |
| 2026-08-31 | Microsoft Edge TTS (`edge-tts`, en-US-AndrewNeural) | Synthetic voiceover narration in the demo video — the narrator voice is TTS, not a human recording; narration text in `docs/video-narration.md` |
| 2026-09-05 | OpenAI Codex | Audited links and submission readiness, verified the replay golden path, and assisted with Devpost registration/submission at the author's request |

## What is real vs. seeded (demo craft, disclosed)

- **Real:** the Strands agent loop, all five tools, live Crossref /
  OpenAlex / Semantic Scholar calls, retraction flags, claim judging,
  report generation, exit codes.
- **Seeded (`DEMO:` markers):** `examples/demo_paper/paper.md` is a
  synthetic manuscript with three planted failures so the demo is
  reproducible; `fixtures/` are recorded real API/model responses used
  only when `DEMO_MODE=1`.
- **DEMO_MODE:** replays a recorded real run (model turns) through the
  real agent loop and real tools against recorded fixtures — for judges
  without keys. Live mode is the default and was verified end-to-end.

## Human contributions

Problem selection (lived pain as a researcher), design decisions, prompt
iteration and thresholds, verification of all runs, and final review of
every file. All AI-generated code was run and its behavior verified
against live APIs before inclusion.
