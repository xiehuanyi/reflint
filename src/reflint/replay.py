"""ReplayModel — a custom Strands model provider for DEMO_MODE.

DEMO: In demo mode the REAL Strands agent loop and the REAL tools run;
only the LLM responses are replayed from a recording of a genuine
Gemini-backed run (fixtures/recording.json). Tools execute against
recorded HTTP fixtures, so the whole golden path is deterministic and
needs zero keys and zero network. This is disclosed in the README.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.streaming import StreamEvent

T = TypeVar("T", bound=BaseModel)

_CHUNK = 48  # characters of text per replayed stream chunk


class ReplayError(RuntimeError):
    pass


class ReplayModel(Model):
    """Serves pre-recorded assistant messages through the Model interface."""

    def __init__(self, recording_path: str | Path, delay: float = 0.012) -> None:
        path = Path(recording_path)
        if not path.exists():
            raise ReplayError(
                f"recording not found: {path} — run once with RECORD_FIXTURES=1 "
                "and a real GOOGLE_API_KEY to create it"
            )
        self._messages: list[dict] = json.loads(path.read_text())
        self._index = 0
        self._delay = delay
        self.config: dict[str, Any] = {"model_id": "replay(recorded gemini run)"}

    # -- Model interface ----------------------------------------------------

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(
        self, output_model: type[T], prompt: Any, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        raise ReplayError("structured_output is not recorded; not used in demo path")
        yield  # pragma: no cover

    async def stream(
        self,
        messages: Any,
        tool_specs: Any = None,
        system_prompt: Any = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamEvent, None]:
        if self._index >= len(self._messages):
            raise ReplayError(
                "recording exhausted — the replayed conversation took more model "
                "turns than were recorded"
            )
        message = self._messages[self._index]
        self._index += 1

        yield {"messageStart": {"role": "assistant"}}
        has_tool_use = False
        for block in message.get("content", []):
            if "text" in block and block["text"]:
                yield {"contentBlockStart": {"start": {}}}
                text = block["text"]
                for i in range(0, len(text), _CHUNK):
                    yield {"contentBlockDelta": {"delta": {"text": text[i : i + _CHUNK]}}}
                    if self._delay:
                        await asyncio.sleep(self._delay)  # DEMO: pacing for a live feel
                yield {"contentBlockStop": {}}
            elif "toolUse" in block:
                has_tool_use = True
                tu = block["toolUse"]
                yield {
                    "contentBlockStart": {
                        "start": {
                            "toolUse": {"name": tu["name"], "toolUseId": tu["toolUseId"]}
                        }
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "delta": {"toolUse": {"input": json.dumps(tu.get("input", {}))}}
                    }
                }
                yield {"contentBlockStop": {}}
            # reasoningContent blocks in the recording are skipped on replay

        yield {"messageStop": {"stopReason": "tool_use" if has_tool_use else "end_turn"}}


def save_recording(messages: list[dict], path: str | Path) -> None:
    """Persist the assistant turns of a finished live run for later replay."""
    assistant_turns = []
    for m in messages:
        if m.get("role") != "assistant":
            continue
        content = [b for b in m.get("content", []) if "text" in b or "toolUse" in b]
        assistant_turns.append({"role": "assistant", "content": content})
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(assistant_turns, indent=1))
