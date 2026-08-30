"""Clients for the open scholarly record: Crossref + OpenAlex.

Every external call goes through `cached_get`, which layers, in order:
fresh disk cache -> live request (timeout + retries) -> stale cache ->
graceful error marker. In DEMO_MODE nothing touches the network at all —
responses come from recorded fixtures (see fixtures/http/).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from . import config

USER_AGENT = "RefLint/0.1 (citation-integrity agent; hackathon project)"


# ---------------------------------------------------------------------------
# transport layer
# ---------------------------------------------------------------------------

def _key(url: str, params: dict[str, Any] | None) -> str:
    raw = url + "?" + urlencode(sorted((params or {}).items()))
    return hashlib.sha1(raw.encode()).hexdigest()


def _read_json(path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def cached_get(url: str, params: dict[str, Any] | None = None) -> dict:
    """GET a JSON API with cache / fixture / stale fallbacks.

    Returns the parsed JSON body. On total failure returns
    ``{"_unavailable": "<reason>"}`` so callers degrade instead of crashing.
    """
    key = _key(url, params)
    fixture_path = config.HTTP_FIXTURES_DIR / f"{key}.json"
    cache_path = config.CACHE_DIR / f"{key}.json"

    if config.demo_mode():
        # DEMO: serve recorded fixtures only — zero network, zero keys.
        data = _read_json(fixture_path)
        if data is not None:
            return data
        return {"_unavailable": "no fixture recorded for this request (DEMO_MODE)"}

    # Fresh cache?
    cached = _read_json(cache_path)
    if cached is not None:
        try:
            age = time.time() - cache_path.stat().st_mtime
        except OSError:
            age = 1e9
        if age < config.CACHE_TTL:
            if config.record_fixtures():  # mirror cache hits into fixtures too
                config.HTTP_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
                fixture_path.write_text(json.dumps(cached))
            return cached

    # Live request: timeout + retries with backoff.
    last_err = ""
    for attempt in range(config.HTTP_RETRIES + 1):
        try:
            resp = httpx.get(
                url,
                params=params,
                timeout=config.HTTP_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            if resp.status_code == 404:
                data = {"_not_found": True}
            elif resp.status_code == 429:
                last_err = "rate limited"
                time.sleep(1.5 * (attempt + 1))
                continue
            else:
                resp.raise_for_status()
                data = resp.json()
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data))
            if config.record_fixtures():
                config.HTTP_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
                fixture_path.write_text(json.dumps(data))
            return data
        except (httpx.HTTPError, json.JSONDecodeError) as exc:  # noqa: PERF203
            last_err = str(exc)
            time.sleep(1.0 * (attempt + 1))

    # Stale cache beats nothing.
    if cached is not None:
        cached["_stale"] = True
        return cached
    return {"_unavailable": f"request failed after retries: {last_err[:200]}"}


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

def crossref_search(bibliographic: str, rows: int = 3) -> list[dict]:
    """Fuzzy-search Crossref by citation text; returns candidate works."""
    data = cached_get(
        "https://api.crossref.org/works",
        {
            "query.bibliographic": bibliographic,
            "rows": rows,
            "select": "DOI,title,author,score,container-title,issued,type",
        },
    )
    if "_unavailable" in data or "_not_found" in data:
        return [{"_unavailable": data.get("_unavailable", "not found")}]
    items = data.get("message", {}).get("items", [])
    out = []
    for it in items:
        year = None
        try:
            year = it.get("issued", {}).get("date-parts", [[None]])[0][0]
        except (IndexError, TypeError):
            pass
        authors = [
            f"{a.get('family', '')}" for a in it.get("author", [])[:6] if a.get("family")
        ]
        out.append(
            {
                "doi": it.get("DOI"),
                "title": (it.get("title") or [""])[0],
                "year": year,
                "venue": (it.get("container-title") or [""])[0],
                "authors": authors,
                "crossref_score": it.get("score"),
                "type": it.get("type"),
            }
        )
    return out


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

def _deinvert_abstract(inv: dict[str, list[int]] | None) -> str | None:
    if not inv:
        return None
    slots: dict[int, str] = {}
    for word, positions in inv.items():
        for pos in positions:
            slots[pos] = word
    return " ".join(slots[i] for i in sorted(slots))


def openalex_work_by_doi(doi: str) -> dict:
    """Fetch one work from OpenAlex by DOI: retraction flag, abstract, metadata."""
    doi = doi.lower().removeprefix("https://doi.org/").strip()
    data = cached_get(f"https://api.openalex.org/works/doi:{doi}")
    if "_unavailable" in data:
        return {"unavailable": data["_unavailable"]}
    if "_not_found" in data:
        return {"not_found": True, "doi": doi}
    return {
        "doi": doi,
        "title": data.get("title"),
        "year": data.get("publication_year"),
        "venue": ((data.get("primary_location") or {}).get("source") or {}).get(
            "display_name"
        ),
        "authors": [
            (a.get("author") or {}).get("display_name")
            for a in (data.get("authorships") or [])[:8]
        ],
        "is_retracted": bool(data.get("is_retracted")),
        "cited_by_count": data.get("cited_by_count"),
        "abstract": (_deinvert_abstract(data.get("abstract_inverted_index")) or "")[
            :3000
        ]
        or None,
        "stale": bool(data.get("_stale")),
    }


def openalex_search_title(title: str, per_page: int = 3) -> list[dict]:
    """Search OpenAlex by title — the second opinion for suspected phantoms."""
    safe = re.sub(r"[,:;()]", " ", title)
    data = cached_get(
        "https://api.openalex.org/works",
        {"filter": f"title.search:{safe}", "per-page": per_page},
    )
    if "_unavailable" in data or "_not_found" in data:
        return [{"_unavailable": data.get("_unavailable", "not found")}]
    out = []
    for w in data.get("results", []):
        out.append(
            {
                "doi": (w.get("doi") or "").removeprefix("https://doi.org/") or None,
                "title": w.get("title"),
                "year": w.get("publication_year"),
                "is_retracted": bool(w.get("is_retracted")),
                "cited_by_count": w.get("cited_by_count"),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Semantic Scholar (abstract fallback — OpenAlex lacks many Elsevier abstracts)
# ---------------------------------------------------------------------------

def semanticscholar_abstract(doi: str) -> str | None:
    doi = doi.removeprefix("https://doi.org/").strip()
    data = cached_get(
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
        {"fields": "abstract"},
    )
    if "_unavailable" in data or "_not_found" in data:
        return None
    abstract = data.get("abstract")
    return abstract[:3000] if abstract else None


# ---------------------------------------------------------------------------
# similarity
# ---------------------------------------------------------------------------

_STOP = {"a", "an", "the", "of", "for", "and", "in", "on", "to", "with", "via", "by"}


def title_similarity(a: str, b: str) -> float:
    """Token-set Jaccard similarity between two titles (0..1)."""

    def toks(s: str) -> set[str]:
        return {
            t
            for t in re.findall(r"[a-z0-9]+", (s or "").lower())
            if t not in _STOP
        }

    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
