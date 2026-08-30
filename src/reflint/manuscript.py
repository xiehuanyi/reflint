"""Deterministic manuscript parser.

Input format (golden path): a Markdown manuscript with numeric citations
``[1]`` / ``[2, 3]`` in the body and a ``## References`` section whose
entries look like ``[1] Authors (Year). Title. Venue. https://doi.org/...``.
"""

from __future__ import annotations

import re
from pathlib import Path

_REF_LINE = re.compile(r"^\s*\[(\d+)\]\s+(.*\S)\s*$")
_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_YEAR = re.compile(r"\((\d{4})[a-z]?\)")
_DOI = re.compile(r"(?:doi\.org/|doi:\s*)(10\.\S+?)(?:[.\s]*$|\s)", re.IGNORECASE)
# Guard against splitting sentences at "et al." / "Fig." / "e.g." etc.
_SENT_SPLIT = re.compile(
    r"(?<!\bal\.)(?<!Fig\.)(?<!e\.g\.)(?<!i\.e\.)(?<=[.!?])\s+(?=[A-Z\[])"
)


def _parse_reference(num: str, raw: str) -> dict:
    entry: dict = {"key": f"[{num}]", "raw": raw, "authors": None, "year": None,
                   "title": None, "venue": None, "doi": None}

    doi_m = _DOI.search(raw)
    if doi_m:
        entry["doi"] = doi_m.group(1).rstrip(".,;")
        raw = raw[: doi_m.start()].strip()

    year_m = _YEAR.search(raw)
    if year_m:
        entry["year"] = int(year_m.group(1))
        entry["authors"] = raw[: year_m.start()].strip().rstrip(",.")
        rest = raw[year_m.end():].lstrip(". ")
    else:
        rest = raw

    # "Title. Venue, vol(iss), pages." — title runs to the first period.
    parts = re.split(r"(?<!\bvs)(?<![A-Z])\.\s+", rest, maxsplit=1)
    entry["title"] = parts[0].strip().rstrip(".")
    if len(parts) > 1:
        entry["venue"] = parts[1].strip().rstrip(".")
    return entry


def parse_manuscript(path: str | Path) -> dict:
    """Parse a manuscript file into title, claims (cited sentences), references."""
    text = Path(path).read_text(encoding="utf-8")

    title = "Untitled manuscript"
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Split body vs references section.
    m = re.search(r"^#{1,3}\s*References\s*$", text, re.MULTILINE | re.IGNORECASE)
    body, ref_block = (text[: m.start()], text[m.end():]) if m else (text, "")

    references = []
    for line in ref_block.splitlines():
        rm = _REF_LINE.match(line)
        if rm:
            references.append(_parse_reference(rm.group(1), rm.group(2)))

    # Claims: body sentences that carry at least one citation marker.
    claims = []
    flat = re.sub(r"\s+", " ", re.sub(r"^#.*$", "", body, flags=re.MULTILINE)).strip()
    for sent in _SENT_SPLIT.split(flat):
        cited = _CITE.findall(sent)
        if not cited:
            continue
        nums = sorted({int(n) for grp in cited for n in re.split(r"\s*,\s*", grp)})
        claims.append(
            {
                "id": f"C{len(claims) + 1}",
                "text": sent.strip(),
                "refs": [f"[{n}]" for n in nums],
            }
        )

    return {
        "title": title,
        "claims": claims,
        "references": references,
        "stats": {"n_claims": len(claims), "n_references": len(references)},
    }
