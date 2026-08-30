# Building RefLint: a citation-integrity agent on the Strands Agents SDK

*Draft for builder.aws.com — publish under your AWS Builder ID, then link
it in the Devpost form (bonus points). Fill the repo/video links before
publishing.*

---

Everyone I know uses AI somewhere in their paper-writing pipeline now. And
every reviewer I know has started finding the wreckage: references that
don't exist, retracted studies cited as supporting evidence, real papers
attached to claims they never made. The retracted Surgisphere paper in
The Lancet has collected over 1,200 citations *since* being retracted.

I'm a researcher, and hand-auditing a 40-entry bibliography before each
submission costs me hours. For the Agents for Humans hackathon I built
**RefLint** — a linter for your bibliography — on the AWS **Strands
Agents SDK**. This post covers the three design decisions that mattered.

## One orchestrator, one referee: agents as tools

RefLint is two Strands agents. The orchestrator drives five tools through
Strands' agentic loop:

```python
agent = Agent(
    model=GeminiModel(client_args={"api_key": key}, model_id="gemini-flash-lite-latest"),
    tools=[load_manuscript, verify_references, search_scholar,
           judge_claims, submit_report],
    system_prompt=ORCHESTRATOR_PROMPT,
)
agent(f"Audit the manuscript at {path.name}.")
```

The judgment-heavy step — "does this abstract actually support that
sentence?" — lives in a *second* Strands agent hidden behind the
`judge_claims` tool (the agents-as-tools pattern). It sees only claim +
abstract, runs on a different model id, and returns pydantic-validated
verdicts through `Agent.structured_output`, with one hard rule: quote the
most relevant line of the abstract, or say "no relevant line". An auditor
that can't show receipts is just another hallucination machine.

Strands made this split almost free: a tool is a decorated function, an
agent is three lines, and `structured_output` removes the JSON-parsing
sludge that usually eats a hackathon evening.

## Determinism where it counts, judgment where it pays

The verification core is deliberately *not* LLM work. Deterministic
Python resolves each reference: DOI lookup in OpenAlex, fuzzy
bibliographic search in Crossref with token-set title similarity, an
OpenAlex second opinion before any reference is ruled a phantom, the
`is_retracted` flag (open Retraction Watch data), and a Semantic Scholar
fallback for the publisher-restricted abstracts OpenAlex can't carry.

The agent's job is what's left: deciding when the evidence is good
enough, re-searching suspected phantoms with sharper queries before
accusing, judging claim support, and composing a report the schema will
accept — `submit_report` rejects malformed audits with the validation
error, and the agent fixes and resubmits. The system prompt's core rule:
**never emit a verdict that doesn't trace to tool output.**

## Surviving the free tier (and demoing with zero keys)

Two production lessons hiding in a hackathon:

**Quota is an architecture problem.** My Gemini free tier allows ~20
requests per rolling window per model. An agent that judges six claims
with six sub-agent calls dies mid-audit. Fixes: batch all claim
judgments into ONE structured-output call; run orchestrator and judge on
different model ids (separate quota buckets); and subclass the Strands
`GeminiModel` to remap raw 429/503 responses (whose `status` text the
SDK's matcher misses) into `ModelThrottledException`, so Strands' own
exponential-backoff retry strategy absorbs the spikes:

```python
class ResilientGeminiModel(GeminiModel):
    async def stream(self, *args, **kwargs):
        try:
            async for event in super().stream(*args, **kwargs):
                yield event
        except genai.errors.APIError as error:
            if getattr(error, "code", None) in (429, 500, 502, 503):
                raise ModelThrottledException(str(error)[:500]) from error
            raise
```

**A demo that cannot fail.** Strands' model-agnostic `Model` interface
let me write a ~100-line `ReplayModel` that replays the assistant turns
of a recorded real run. With `DEMO_MODE=1`, the *real* agent loop and the
*real* tools execute against recorded HTTP fixtures while the model turns
replay — deterministic, offline, zero keys. Judges reproduce the exact
golden path in thirty seconds, and it's honestly labeled as a replay.

## The result

```
$ uv run reflint audit examples/demo_paper/paper.md
  ⚙ load_manuscript  → 6 references, 6 claims
  ⚙ verify_references → Crossref + OpenAlex + Semantic Scholar
  ⚙ search_scholar    → double-checking a suspected phantom
  ⚙ judge_claims      → referee sub-agent, evidence required
  ⚙ submit_report     → schema-validated

R002 RETRACTED   [2] cited as supporting evidence — retracted 2020
R001 PHANTOM     [3] exists in no database (likely AI-hallucinated)
R003 UNSUPPORTED [4] abstract never makes the claimed statement
3 error(s) → exit code 1
```

Exit code 1 means RefLint drops into CI: a pre-submission gate that fails
the build when your bibliography lies.

Repo: https://github.com/xiehuanyi/reflint · Demo video: `<VIDEO_URL>` · MIT licensed.

*Built solo for the Agents for Humans hackathon (Professional Agents
track), with an AI coding agent doing implementation under my direction —
full disclosure in the repo.*
