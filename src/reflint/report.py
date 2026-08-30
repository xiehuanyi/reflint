"""Report schema, lint-rule taxonomy, console rendering and markdown output."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# schema (what the agent must submit)
# ---------------------------------------------------------------------------

RefVerdict = Literal["ok", "phantom", "retracted", "mismatch", "unverifiable"]
ClaimVerdict = Literal["supported", "partial", "unsupported", "unverifiable"]


class RefFinding(BaseModel):
    key: str = Field(description="reference key, e.g. [2]")
    title: str
    verdict: RefVerdict
    doi: str | None = None
    detail: str = Field(description="one-to-three sentence justification")
    evidence: str | None = Field(default=None, description="quoted evidence from the record")


class ClaimFinding(BaseModel):
    id: str = Field(description="claim id, e.g. C3")
    ref_key: str
    verdict: ClaimVerdict
    claim: str
    evidence: str = Field(description="quote from the cited paper's abstract")
    explanation: str


class AuditReport(BaseModel):
    manuscript_title: str
    summary: str
    references: list[RefFinding]
    claims: list[ClaimFinding]
    recommendations: list[str] = []


# ---------------------------------------------------------------------------
# lint rules
# ---------------------------------------------------------------------------

RULES: dict[str, tuple[str, str, str]] = {
    # code: (name, severity, badge style)
    "R001": ("PHANTOM — reference not found in the scholarly record", "error", "bold white on red"),
    "R002": ("RETRACTED — cited work has been retracted", "error", "bold white on red"),
    "R003": ("UNSUPPORTED — source does not support the claim", "error", "bold white on red"),
    "R004": ("MISMATCH — reference metadata does not match the record", "warning", "black on yellow"),
    "R005": ("UNVERIFIABLE — could not be checked against the record", "warning", "black on yellow"),
    "R006": ("PARTIAL — source only partially supports the claim", "warning", "black on yellow"),
}

_REF_CODE = {"phantom": "R001", "retracted": "R002", "mismatch": "R004", "unverifiable": "R005"}
_CLAIM_CODE = {"unsupported": "R003", "partial": "R006", "unverifiable": "R005"}


def findings(report: AuditReport) -> list[dict]:
    out = []
    for r in report.references:
        if r.verdict in _REF_CODE:
            code = _REF_CODE[r.verdict]
            out.append({"code": code, "severity": RULES[code][1], "where": r.key,
                        "title": r.title, "detail": r.detail, "evidence": r.evidence,
                        "doi": r.doi})
    for c in report.claims:
        if c.verdict in _CLAIM_CODE:
            code = _CLAIM_CODE[c.verdict]
            out.append({"code": code, "severity": RULES[code][1], "where": f"{c.id} → {c.ref_key}",
                        "title": c.claim, "detail": c.explanation, "evidence": c.evidence,
                        "doi": None})
    return out


def exit_code(report: AuditReport) -> int:
    return 1 if any(f["severity"] == "error" for f in findings(report)) else 0


# ---------------------------------------------------------------------------
# console rendering
# ---------------------------------------------------------------------------

_VERDICT_STYLE = {
    "ok": "bold green", "supported": "bold green",
    "phantom": "bold red", "retracted": "bold red", "unsupported": "bold red",
    "mismatch": "yellow", "partial": "yellow", "unverifiable": "dim yellow",
}


def render_console(report: AuditReport, console: Console) -> None:
    console.print()
    table = Table(title=f"RefLint audit — {report.manuscript_title}",
                  title_style="bold", show_lines=False, pad_edge=False)
    table.add_column("Ref", style="bold", no_wrap=True)
    table.add_column("Title", max_width=52, overflow="ellipsis")
    table.add_column("Verdict", no_wrap=True)
    table.add_column("DOI", overflow="fold", style="dim")
    for r in report.references:
        table.add_row(
            r.key, r.title,
            Text(r.verdict.upper(), style=_VERDICT_STYLE.get(r.verdict, "")),
            r.doi or "—",
        )
    console.print(table)

    fs = findings(report)
    if not fs:
        console.print(Panel("[bold green]No integrity findings. Bibliography is clean.[/]",
                            border_style="green"))
    for f in fs:
        name, severity, style = RULES[f["code"]]
        body = Text()
        body.append(f"{f['title']}\n", style="bold")
        body.append(f"{f['detail']}\n")
        if f["evidence"]:
            body.append(f'\n  "{f["evidence"]}"\n', style="italic dim")
        if f["doi"]:
            body.append(f"\n  https://doi.org/{f['doi']}", style="dim")
        console.print(Panel(body, title=f"[{style}] {f['code']} [/] {name}  ·  {f['where']}",
                            border_style="red" if severity == "error" else "yellow",
                            title_align="left"))

    n_err = sum(1 for f in fs if f["severity"] == "error")
    n_warn = len(fs) - n_err
    console.print(f"\n[bold]{n_err} error(s), {n_warn} warning(s)[/] · {report.summary}\n")


# ---------------------------------------------------------------------------
# markdown output
# ---------------------------------------------------------------------------

def write_markdown(report: AuditReport, path: str | Path) -> Path:
    lines = [
        f"# RefLint audit — {report.manuscript_title}",
        "",
        f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        "by RefLint (Strands Agents SDK + Gemini · Crossref · OpenAlex).*",
        "",
        f"**Summary:** {report.summary}",
        "",
        "## References",
        "",
        "| Ref | Title | Verdict | DOI |",
        "|---|---|---|---|",
    ]
    for r in report.references:
        doi = f"[{r.doi}](https://doi.org/{r.doi})" if r.doi else "—"
        lines.append(f"| {r.key} | {r.title} | **{r.verdict.upper()}** | {doi} |")

    fs = findings(report)
    lines += ["", "## Findings", ""]
    if not fs:
        lines.append("No integrity findings. Bibliography is clean.")
    for f in fs:
        name = RULES[f["code"]][0]
        lines += [f"### {f['code']} · {name}", "", f"**Where:** {f['where']} — {f['title']}",
                  "", f["detail"], ""]
        if f["evidence"]:
            lines += [f"> {f['evidence']}", ""]
        if f["doi"]:
            lines += [f"DOI: https://doi.org/{f['doi']}", ""]

    if report.claims:
        lines += ["", "## Claim-by-claim verdicts", "",
                  "| Claim | Ref | Verdict | Why |", "|---|---|---|---|"]
        for c in report.claims:
            lines.append(
                f"| {c.id}: {c.claim[:80]} | {c.ref_key} | **{c.verdict}** | {c.explanation[:120]} |"
            )

    if report.recommendations:
        lines += ["", "## Recommended actions", ""]
        lines += [f"1. {r}" for r in report.recommendations]

    out = Path(path)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
