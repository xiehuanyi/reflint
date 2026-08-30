"""Orchestrator agent wiring: model selection (Gemini live / Replay demo)."""

from __future__ import annotations

import os

from strands import Agent

from . import config
from .replay import ReplayModel
from .tools import AuditContext, make_tools

ORCHESTRATOR_PROMPT = """\
You are RefLint, a citation-integrity auditor for scientific manuscripts.
You verify; you never invent. Every verdict must trace to tool output.

Workflow (follow strictly, in order):
1. Call load_manuscript.
2. Call verify_references.
3. For any reference whose status is 'ambiguous' or 'not_found', call
   search_scholar once with a sharper query (e.g. exact title in quotes, or
   title plus first author) to make sure you are not mislabeling a real
   paper as phantom. Decide from the evidence.
4. Call judge_claims ONCE with the complete list of claim-reference pairs
   whose cited reference resolved (include every claim; pairs without an
   abstract come back 'unverifiable' automatically). Do not judge pairs
   yourself; use the tool.
5. Call submit_report exactly once with the complete report JSON:
   - reference verdicts: 'retracted' if the record says is_retracted;
     'phantom' if no matching work exists after double-checking;
     'mismatch' if it resolved but metadata_mismatches is present;
     'unverifiable' if sources were unavailable; else 'ok'.
   - claim verdicts: copy the judge_claim verdicts verbatim, with their
     evidence quotes and explanations.
   - detail fields: one to three factual sentences citing the record
     (retraction status, similarity scores, cited_by_count...).
   - recommendations: one concrete action per finding (e.g. "remove [3] or
     replace with a real source"; "cite [2] only as a retracted example").
   If submit_report returns REJECTED, fix the JSON and resubmit.
6. Finish with a 2-3 sentence executive summary in plain text. Mention the
   count of errors and the single most serious finding.

Rules: never skip verify_references; never fabricate DOIs, quotes, or
abstracts; if a source was unavailable, say so honestly in the report.
"""


def build_model(demo: bool, model_id: str | None = None):
    if demo:
        return ReplayModel(config.RECORDING_FILE)
    from google import genai
    from strands.models.gemini import GeminiModel  # imported lazily: needs key
    from strands.types.exceptions import ModelThrottledException

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add it to .env, or run with DEMO_MODE=1 "
            "(no key needed)."
        )

    class ResilientGeminiModel(GeminiModel):
        """Maps raw 429/503 client errors to ModelThrottledException so the
        Strands event loop's exponential-backoff retry (4s->64s) kicks in.
        Upstream only matches error.status == "RESOURCE_EXHAUSTED", which
        some quota responses don't set."""

        async def stream(self, *args, **kwargs):
            try:
                async for event in super().stream(*args, **kwargs):
                    yield event
            except genai.errors.APIError as error:  # ClientError AND ServerError
                if getattr(error, "code", None) in (429, 500, 502, 503) or any(
                    s in str(error) for s in ("RESOURCE_EXHAUSTED", "UNAVAILABLE")
                ):
                    raise ModelThrottledException(str(error)[:500]) from error
                raise

    return ResilientGeminiModel(
        client_args={"api_key": api_key},
        model_id=model_id or config.DEFAULT_MODEL_ID,
        params={"temperature": 0.2},
    )


def build_agent(ctx: AuditContext, demo: bool, callback_handler=None) -> Agent:
    from strands.event_loop._retry import ModelRetryStrategy

    # The judge sub-agent gets its own model on a different quota bucket
    # (agents-as-tools). In demo mode judge verdicts come from fixtures.
    ctx.judge_model_factory = lambda: build_model(demo=False,
                                                  model_id=config.JUDGE_MODEL_ID)
    return Agent(
        model=build_model(demo),
        tools=make_tools(ctx),
        system_prompt=ORCHESTRATOR_PROMPT,
        callback_handler=callback_handler,
        # Free-tier quota windows need patience, but bounded: 8..60s waits.
        retry_strategy=ModelRetryStrategy(max_attempts=5, initial_delay=8,
                                          max_delay=60),
    )
