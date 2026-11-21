"""Command line entry point: ``nlm-pdf`` (or ``python -m pipeline.cli``)."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from . import clean as clean_stage
from . import enhance as enhance_stage
from . import render as render_stage
from . import validate as validate_stage
from .common import load_config


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="path to config.yaml")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nlm-pdf",
        description="NotebookLM chat -> study-ready PDF, one local pipeline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("doctor", help="show local setup status (Ollama + Chrome)")
    _add_config(check)

    run = sub.add_parser("all", help="run clean -> enhance -> render -> validate")
    run.add_argument("chat", help="chat.json captured from NotebookLM")
    run.add_argument("--outdir", help="output directory (default: <chat dir>/out)")
    run.add_argument("--offline", action="store_true", help="skip the Ollama call")
    run.add_argument("--instructions", help="override user_instructions")
    _add_config(run)

    stage = sub.add_parser("clean", help="chat.json -> clean.md")
    stage.add_argument("chat")
    stage.add_argument("output", nargs="?")
    stage.add_argument("--meta")
    _add_config(stage)

    stage = sub.add_parser("enhance", help="clean.md -> enhanced.md")
    stage.add_argument("input")
    stage.add_argument("output", nargs="?")
    stage.add_argument("--meta")
    stage.add_argument("--offline", action="store_true")
    stage.add_argument("--instructions")
    _add_config(stage)

    stage = sub.add_parser("render", help="enhanced.md -> study-notes.pdf + .html")
    stage.add_argument("input")
    stage.add_argument("output", nargs="?")
    stage.add_argument("--html")
    _add_config(stage)

    stage = sub.add_parser("validate", help="verify the PDF and write report.json")
    stage.add_argument("pdf")
    stage.add_argument("--html")
    stage.add_argument("--md")
    stage.add_argument("--meta")
    stage.add_argument("--report")
    _add_config(stage)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = load_config(args.config)

    if args.command == "doctor":
        from .enhance import check_ollama

        connected, detail, models = check_ollama(config)
        channel = (config.get("render", {}) or {}).get("chrome_channel", "chrome")
        chrome = shutil.which(str(channel)) if channel else shutil.which("chromium")
        if not chrome:
            known = [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            ]
            chrome = next(str(path) for path in known if path.is_file())
        print(f"ollama : {'OK' if connected else 'NOT READY'} — {detail}")
        print(f"model  : {config.get('model')}")
        print(f"chrome : {'OK — ' + str(chrome) if chrome else 'not found on PATH'}")
        print(
            "note   : Ollama is optional. Without it the pipeline still builds the PDF "
            "with plain numbered headings."
        )
        return 0

    if args.command == "all":
        chat = Path(args.chat)
        outdir = Path(args.outdir) if args.outdir else chat.parent / "out"
        outdir.mkdir(parents=True, exist_ok=True)
        clean_file = outdir / "clean.md"
        meta_file = outdir / "clean.meta.json"
        enhanced_file = outdir / "enhanced.md"
        pdf_file = outdir / "study-notes.pdf"

        clean_stage.clean(chat, clean_file, meta_file, config)
        print(f"clean: -> {clean_file}")
        enhance_stage.enhance(
            clean_file,
            enhanced_file,
            meta_file,
            config,
            offline=args.offline,
            instructions=args.instructions,
        )
        print(f"enhance: -> {enhanced_file}")
        render_stage.render(enhanced_file, pdf_file, config=config)
        print(f"render: -> {pdf_file}")
        report = validate_stage.validate(
            pdf_file,
            html_path=outdir / "study-notes.html",
            enhanced_path=enhanced_file,
            meta_path=meta_file,
            config=config,
        )
        return 0 if report["passed"] else 1

    if args.command == "clean":
        out = Path(args.output) if args.output else Path(args.chat).parent / "clean.md"
        manifest = clean_stage.clean(args.chat, out, args.meta, config)
        print(f"clean: {len(manifest['answers'])} answers -> {out}")
        return 0

    if args.command == "enhance":
        out = (
            Path(args.output)
            if args.output
            else Path(args.input).with_name("enhanced.md")
        )
        report = enhance_stage.enhance(
            args.input,
            out,
            args.meta,
            config,
            offline=args.offline,
            instructions=args.instructions,
        )
        print(f"enhance: {report['answers']} answers -> {out}")
        return 0

    if args.command == "render":
        out = (
            Path(args.output)
            if args.output
            else Path(args.input).with_name("study-notes.pdf")
        )
        report = render_stage.render(args.input, out, args.html, config)
        print(f"render: -> {report['pdf']}")
        return 0

    if args.command == "validate":
        report = validate_stage.validate(
            args.pdf,
            args.html,
            args.md,
            args.meta,
            args.report,
            config,
        )
        return 0 if report["passed"] else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
