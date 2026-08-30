"""RefLint's tool belt — what the orchestrator agent can DO.

Five tools: load_manuscript, verify_references, search_scholar,
judge_claim (a second, focused Strands agent behind a tool interface —
the "agents as tools" pattern), and submit_report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from strands import tool

from . import config, scholar
from .manuscript import parse_manuscript
from .report import AuditReport

MATCH_GOOD = 0.75
MATCH_GRAY = 0.40


@dataclass
class AuditContext:
    """Shared state between the CLI, the tools, and the report renderer."""

    manuscript_path: Path
    manuscript: dict | None = None
    verification: dict[str, dict] = field(default_factory=dict)
    report: AuditReport | None = None
    judge_model_factory: Any = None  # callable -> strands Model (lazy)
    events: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# deterministic verification core (shared by the tool)
# ---------------------------------------------------------------------------

def _resolve_by_title(ref: dict, result: dict) -> list[str]:
    """Candidate DOIs for a reference by title search (Crossref + OpenAlex)."""
    title = ref.get("title") or ""
    query = " ".join(str(x) for x in (ref.get("title"), ref.get("authors"),
                                      ref.get("year")) if x)
    dois: list[str] = []

    candidates = scholar.crossref_search(query)
    if candidates and "_unavailable" in candidates[0]:
        result["note"] = candidates[0]["_unavailable"]
        candidates = []
    best, best_sim = None, 0.0
    for c in candidates:
        sim = scholar.title_similarity(title, c.get("title") or "")
        if sim > best_sim:
            best, best_sim = c, sim
    result["best_match"] = best
    result["title_similarity"] = round(best_sim, 2)
    if best and best_sim >= MATCH_GOOD and best.get("doi"):
        dois.append(best["doi"])

    # Second opinion from OpenAlex (indexes some works Crossref maps oddly).
    for c in scholar.openalex_search_title(title):
        if "_unavailable" in c:
            break
        sim = scholar.title_similarity(title, c.get("title") or "")
        if sim >= MATCH_GOOD and c.get("doi"):
            result["title_similarity"] = max(result["title_similarity"], round(sim, 2))
            dois.append(c["doi"])

    if not dois and best and best_sim >= MATCH_GRAY:
        result["ambiguous"] = True
    return dois


def _verify_one(ref: dict) -> dict:
    """Resolve one reference against Crossref + OpenAlex; deterministic."""
    result: dict[str, Any] = {"key": ref["key"], "given": {k: ref[k] for k in
                              ("title", "authors", "year", "venue", "doi")}}
    notes: list[str] = []

    doi = ref.get("doi")
    work: dict = {"not_found": True}
    if doi:
        work = scholar.openalex_work_by_doi(doi)
    if work.get("not_found"):
        # No DOI, or a DOI the record does not know: match by title.
        for doi2 in _resolve_by_title(ref, result):
            work = scholar.openalex_work_by_doi(doi2)
            if not work.get("not_found") and not work.get("unavailable"):
                if doi:
                    notes.append(
                        f"cited DOI {doi} is not indexed in OpenAlex; work "
                        f"matched by title instead "
                        f"(similarity {result.get('title_similarity')})"
                    )
                break
        else:
            if result.pop("ambiguous", False):
                result["status"] = "ambiguous"
                result["note"] = ("closest match is only partially similar; use "
                                  "search_scholar to double-check before deciding")
                return result

    if work.get("unavailable"):
        result["status"] = "source_unavailable"
        result["note"] = work["unavailable"]
        return result
    if work.get("not_found"):
        result["status"] = "not_found"
        result["note"] = "; ".join(
            notes
            + ["no sufficiently similar work found in Crossref or OpenAlex; "
               "likely a phantom (hallucinated) reference"]
        )
        return result

    # Abstract fallback: OpenAlex lacks many publisher abstracts.
    if not work.get("abstract") and work.get("doi"):
        work["abstract"] = scholar.semanticscholar_abstract(work["doi"])
        if work["abstract"]:
            notes.append("abstract retrieved via Semantic Scholar")

    result["status"] = "resolved"
    result["record"] = work
    if notes:
        result["notes"] = notes

    mismatches = []
    if ref.get("year") and work.get("year") and abs(ref["year"] - work["year"]) > 1:
        mismatches.append(f"year: cited {ref['year']}, record says {work['year']}")
    if ref.get("title") and work.get("title"):
        sim = scholar.title_similarity(ref["title"], work["title"])
        if sim < MATCH_GOOD:
            mismatches.append(f"title similarity to record only {sim:.2f}")
    if mismatches:
        result["metadata_mismatches"] = mismatches
    return result


# ---------------------------------------------------------------------------
# tool factory
# ---------------------------------------------------------------------------

def make_tools(ctx: AuditContext) -> list:
    """Build the orchestrator's tools, closed over the audit context."""

    @tool
    def load_manuscript() -> dict:
        """Parse the manuscript under audit. Returns its title, the list of
        references, and every claim sentence that carries a citation marker.
        Always call this first."""
        ctx.manuscript = parse_manuscript(ctx.manuscript_path)
        ctx.events.append("load_manuscript")
        return ctx.manuscript

    @tool
    def verify_references() -> dict:
        """Check every reference against the scholarly record (Crossref +
        OpenAlex): does it exist, is it retracted, does its metadata match,
        and what does its abstract say. Call after load_manuscript."""
        if not ctx.manuscript:
            return {"error": "call load_manuscript first"}
        results = {}
        for ref in ctx.manuscript["references"]:
            results[ref["key"]] = _verify_one(ref)
        ctx.verification = results
        ctx.events.append("verify_references")
        return {"results": results,
                "hint": ("for refs with status 'ambiguous' or 'not_found' you may "
                         "double-check with search_scholar; judge each claim whose "
                         "reference resolved with an abstract using judge_claim")}

    @tool
    def search_scholar(query: str) -> dict:
        """Free-form search of Crossref and OpenAlex — use it to double-check a
        suspected phantom reference or to disambiguate a partial match.

        Args:
            query: title fragment, author + title, or any bibliographic string
        """
        ctx.events.append(f"search_scholar:{query[:40]}")
        return {
            "crossref": scholar.crossref_search(query, rows=3),
            "openalex": scholar.openalex_search_title(query),
        }

    @tool
    def judge_claims(pairs_json: str) -> dict:
        """Judge whether each cited paper's abstract actually supports the claim
        made in the manuscript. Give ALL claim-reference pairs in one call.
        Verdicts: supported | partial | unsupported | unverifiable, each with a
        quoted evidence line.

        Args:
            pairs_json: JSON list like [{"claim_id": "C2", "ref_key": "[3]"}, ...]
        """
        try:
            pairs = json.loads(pairs_json)
            assert isinstance(pairs, list)
        except (json.JSONDecodeError, AssertionError):
            return {"error": 'pairs_json must be a JSON list of {"claim_id","ref_key"}'}
        ctx.events.append(f"judge_claims:{len(pairs)}")

        verdicts: list[dict] = []
        judgeable: list[dict] = []
        for p in pairs[:12]:
            claim_id, ref_key = p.get("claim_id"), p.get("ref_key")
            claim = next((c for c in (ctx.manuscript or {}).get("claims", [])
                          if c["id"] == claim_id), None)
            ver = ctx.verification.get(ref_key, {})
            record = ver.get("record") or {}
            abstract = record.get("abstract")
            if not claim:
                verdicts.append({"claim_id": claim_id, "ref_key": ref_key,
                                 "verdict": "unverifiable", "evidence": "",
                                 "explanation": f"unknown claim id {claim_id}"})
            elif ver.get("status") != "resolved" or not abstract:
                verdicts.append({"claim_id": claim_id, "ref_key": ref_key,
                                 "verdict": "unverifiable", "evidence": "",
                                 "explanation": "no abstract available in the "
                                                "record for this reference"})
            else:
                judgeable.append({"claim_id": claim_id, "ref_key": ref_key,
                                  "claim": claim["text"], "record": record,
                                  "abstract": abstract})

        if judgeable:
            if config.demo_mode():
                # DEMO: replay judge verdicts recorded from a real Gemini run.
                fixtures = _load_judge_fixtures()
                for j in judgeable:
                    key = f"{j['claim_id']}|{j['ref_key']}"
                    verdicts.append(fixtures.get(key) or {
                        "claim_id": j["claim_id"], "ref_key": j["ref_key"],
                        "verdict": "unverifiable", "evidence": "",
                        "explanation": "no recorded judge verdict (DEMO_MODE)"})
            else:
                judged = _run_judge_batch(ctx, judgeable)
                verdicts.extend(judged)
                if config.record_fixtures():
                    for v in judged:
                        _save_judge_fixture(f"{v['claim_id']}|{v['ref_key']}", v)

        return {"verdicts": verdicts}

    @tool
    def submit_report(report_json: str) -> str:
        """Submit the final audit report EXACTLY ONCE, as a JSON string matching:
        {"manuscript_title": str, "summary": str,
         "references": [{"key","title","verdict","doi","detail","evidence"}],
         "claims": [{"id","ref_key","verdict","claim","evidence","explanation"}],
         "recommendations": [str]}
        Reference verdicts: ok|phantom|retracted|mismatch|unverifiable.
        Claim verdicts: supported|partial|unsupported|unverifiable.

        Args:
            report_json: the full report as a JSON string
        """
        try:
            ctx.report = AuditReport.model_validate(json.loads(report_json))
        except (json.JSONDecodeError, ValidationError) as exc:
            return f"REJECTED — fix and resubmit. Validation error: {exc}"
        ctx.events.append("submit_report")
        return "Report accepted and rendered. Now reply with a 2-3 sentence executive summary."

    return [load_manuscript, verify_references, search_scholar, judge_claims,
            submit_report]


# ---------------------------------------------------------------------------
# the judge sub-agent (agents as tools)
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = (
    "You are a strict citation referee. For EACH numbered case you get a CLAIM "
    "from a manuscript and the ABSTRACT of the paper it cites. Decide per case "
    "whether the abstract supports the claim.\n"
    "Verdicts: 'supported' (abstract clearly backs the claim), 'partial' (related "
    "but weaker/narrower than claimed), 'unsupported' (abstract is about something "
    "else or contradicts the claim), 'unverifiable' (cannot tell from the abstract).\n"
    "Quote the single most relevant line of the abstract as evidence (or say "
    "'no relevant line'). Judge ONLY from the abstract text given. Be terse. "
    "Return one verdict per case, echoing its claim_id and ref_key exactly."
)


def _run_judge_batch(ctx: AuditContext, judgeable: list[dict]) -> list[dict]:
    """One focused sub-agent call judges all claim-abstract pairs (1 LLM call)."""
    import time

    from pydantic import BaseModel
    from strands import Agent

    class JudgeVerdict(BaseModel):
        claim_id: str
        ref_key: str
        verdict: str
        evidence: str
        explanation: str

    class JudgeVerdicts(BaseModel):
        verdicts: list[JudgeVerdict]

    cases = []
    for i, j in enumerate(judgeable, 1):
        rec = j["record"]
        cases.append(
            f"CASE {i} (claim_id={j['claim_id']}, ref_key={j['ref_key']})\n"
            f"CLAIM: {j['claim']}\n"
            f"CITED PAPER: {rec.get('title')} ({rec.get('year')}, {rec.get('venue')})\n"
            f"ABSTRACT: {j['abstract']}\n"
        )
    prompt = "\n".join(cases)

    def fallback(reason: str) -> list[dict]:
        return [{"claim_id": j["claim_id"], "ref_key": j["ref_key"],
                 "verdict": "unverifiable", "evidence": "",
                 "explanation": f"judge unavailable ({reason}); manual check "
                                "recommended"} for j in judgeable]

    last = "unknown"
    for attempt in range(2):  # timeout+retry, then graceful degradation
        try:
            judge = Agent(model=ctx.judge_model_factory(),
                          system_prompt=_JUDGE_PROMPT, tools=[],
                          callback_handler=None)
            result = judge.structured_output(JudgeVerdicts, prompt)
            out = []
            by_key = {f"{v.claim_id}|{v.ref_key}": v for v in result.verdicts}
            for j in judgeable:
                v = by_key.get(f"{j['claim_id']}|{j['ref_key']}")
                if v is None:
                    out.append(fallback("missing verdict")[0] | {
                        "claim_id": j["claim_id"], "ref_key": j["ref_key"]})
                    continue
                verdict = v.verdict.lower().strip()
                if verdict not in {"supported", "partial", "unsupported",
                                   "unverifiable"}:
                    verdict = "unverifiable"
                out.append({"claim_id": j["claim_id"], "ref_key": j["ref_key"],
                            "verdict": verdict, "evidence": v.evidence[:400],
                            "explanation": v.explanation[:400]})
            return out
        except Exception as exc:  # noqa: PERF203
            last = type(exc).__name__
            if attempt == 0:
                time.sleep(15)
    return fallback(last)


# ---------------------------------------------------------------------------
# judge fixtures (DEMO_MODE)
# ---------------------------------------------------------------------------

def _load_judge_fixtures() -> dict:
    try:
        return json.loads(config.JUDGE_FIXTURES_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_judge_fixture(key: str, verdict: dict) -> None:
    config.FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_judge_fixtures()
    data[key] = verdict
    config.JUDGE_FIXTURES_FILE.write_text(json.dumps(data, indent=1))
