"""RefLint CLI — `reflint audit <manuscript.md>`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

console = Console()


class RichCallbackHandler:
    """Streams the agent's thinking and tool calls to the terminal."""

    TOOL_LABELS = {
        "load_manuscript": "parsing manuscript",
        "verify_references": "checking references against Crossref + OpenAlex",
        "search_scholar": "double-checking the scholarly record",
        "judge_claims": "judging claim support (referee sub-agent)",
        "submit_report": "compiling the audit report",
    }

    def __init__(self) -> None:
        self.tool_count = 0
        self._streamed = False

    def __call__(self, **kwargs) -> None:
        data = kwargs.get("data", "")
        tool_use = (
            kwargs.get("event", {})
            .get("contentBlockStart", {})
            .get("start", {})
            .get("toolUse")
        )
        if data:
            self._streamed = True
            console.print(data, end="", style="dim", highlight=False, soft_wrap=True)
        if tool_use:
            if self._streamed:
                console.print()
                self._streamed = False
            self.tool_count += 1
            name = tool_use.get("name", "?")
            label = self.TOOL_LABELS.get(name, name)
            console.print(
                f"[bold cyan]  ⚙ tool {self.tool_count}[/] [bold]{name}[/] — {label}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reflint",
        description="RefLint — a citation-integrity agent: every reference in "
        "your paper, actually checked (Strands Agents SDK).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="audit a manuscript's citations")
    audit.add_argument("manuscript", help="path to a Markdown manuscript")
    audit.add_argument("--out", default="reflint-report.md",
                       help="markdown report path (default: reflint-report.md)")
    audit.add_argument("--demo", action="store_true",
                       help="force DEMO_MODE (offline, recorded fixtures, no keys)")
    args = parser.parse_args(argv)

    # Load .env from the project root and the cwd (either works).
    from . import config as cfg

    load_dotenv(cfg.PROJECT_ROOT / ".env")
    load_dotenv()

    if args.demo:
        import os

        os.environ["DEMO_MODE"] = "1"

    demo = cfg.demo_mode()

    from .agent import build_agent
    from .replay import ReplayError, save_recording
    from .tools import AuditContext

    path = Path(args.manuscript)
    if not path.exists():
        console.print(f"[red]manuscript not found:[/] {path}")
        return 2

    mode = "[yellow]DEMO_MODE — offline replay of a recorded real run[/]" if demo \
        else f"[green]live — Gemini ({cfg.DEFAULT_MODEL_ID}) + Crossref + OpenAlex[/]"
    console.print(Panel.fit(
        f"[bold]RefLint[/] · citation-integrity agent · {mode}",
        border_style="cyan"))

    ctx = AuditContext(manuscript_path=path)
    try:
        agent = build_agent(ctx, demo=demo, callback_handler=RichCallbackHandler())
        agent(f"Audit the manuscript at {path.name}.")
    except ReplayError as exc:
        console.print(f"[red]demo replay failed:[/] {exc}")
        return 2
    except KeyboardInterrupt:
        console.print("\n[red]interrupted[/]")
        return 2
    except Exception as exc:
        console.print(
            Panel(
                f"[red]The live model call failed:[/] {exc}\n\n"
                "The APIs may be down or the key exhausted. The full golden path "
                "still runs offline: [bold]DEMO_MODE=1 reflint audit ...[/]",
                border_style="red",
            )
        )
        return 2

    if cfg.record_fixtures() and not demo:
        save_recording(agent.messages, cfg.RECORDING_FILE)
        console.print(f"[dim]recorded {cfg.RECORDING_FILE}[/]")

    if ctx.report is None:
        console.print("[red]the agent finished without submitting a report[/]")
        return 2

    from .report import exit_code, render_console, write_markdown

    render_console(ctx.report, console)
    out = write_markdown(ctx.report, args.out)
    console.print(f"[bold]report written:[/] {out.resolve()}")
    return exit_code(ctx.report)


if __name__ == "__main__":
    sys.exit(main())
