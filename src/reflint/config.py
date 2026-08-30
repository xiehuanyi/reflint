"""Runtime configuration: paths, DEMO_MODE, fixture recording."""

from __future__ import annotations

import os
from pathlib import Path

# Project root = two levels above this file (src/reflint/config.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

FIXTURES_DIR = Path(os.environ.get("REFLINT_FIXTURES", PROJECT_ROOT / "fixtures"))
HTTP_FIXTURES_DIR = FIXTURES_DIR / "http"
RECORDING_FILE = FIXTURES_DIR / "recording.json"
JUDGE_FIXTURES_FILE = FIXTURES_DIR / "judge.json"

CACHE_DIR = Path(os.environ.get("REFLINT_CACHE", PROJECT_ROOT / ".cache" / "http"))

# Orchestrator and judge run on different model ids on purpose: separate
# free-tier quota buckets, and the judge needs no tool-calling strength.
DEFAULT_MODEL_ID = os.environ.get("REFLINT_MODEL", "gemini-flash-lite-latest")
JUDGE_MODEL_ID = os.environ.get("REFLINT_JUDGE_MODEL", "gemini-3.5-flash")

# How long a cached API response counts as fresh (seconds).
CACHE_TTL = int(os.environ.get("REFLINT_CACHE_TTL", 6 * 3600))

HTTP_TIMEOUT = float(os.environ.get("REFLINT_HTTP_TIMEOUT", 12.0))
HTTP_RETRIES = 2


def demo_mode() -> bool:
    """True when running offline against recorded fixtures (zero keys needed)."""
    return os.environ.get("DEMO_MODE", "").lower() in {"1", "true", "yes"}


def record_fixtures() -> bool:
    """True when a live run should also write fixtures for later DEMO_MODE replay."""
    return os.environ.get("RECORD_FIXTURES", "").lower() in {"1", "true", "yes"}
