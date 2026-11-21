"""Stage 3 -- model enhancement (one Ollama call per answer).

Code does everything it can; the model only adds a heading and Mermaid
diagrams. Guardrails discard any output that drops words, mangles a protected
placeholder or produces an unparseable Mermaid block.

    python -m pipeline.enhance sample/out/clean.md sample/out/enhanced.md \\
        --meta sample/out/clean.meta.json --config config.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import httpx

from .common import (
    load_config,
    placeholder_keys,
    read_json,
    restore_placeholders,
    split_answers,
    word_count,
    write_json,
)
from .mermaid_validate import extract_mermaid_sources, validate_mermaid_blocks

_WRAPPER_FENCE_RE = re.compile(r"(?s)^\s*```(?:markdown|md)?\s*\n(.*)\n```\s*$")

SYSTEM_PROMPT = """You prepare NotebookLM answers for a study PDF. Structural edits ONLY.

HARD RULES:
1. Keep every sentence EXACTLY as written. Never summarize, rewrite, reword,
   shorten, expand or paraphrase. Do not add or remove any fact.
2. Tokens such as @@NLMDF_MATH_0@@ and @@NLMDF_CODE_1@@ are protected originals.
   Copy them through byte-for-byte, exactly once each. Never translate,
   expand, reformat or explain them.
3. Start with one short, specific Markdown heading (##). Keep the original
   text below it unchanged.
4. If the text describes a flowchart or a step-by-step process, ADD a Mermaid
   fenced code block (```mermaid ... ```) that diagrams it. Keep the original
   prose as well. Use `flowchart TD` and simple node labels.
5. Output only the finished Markdown. No preamble, no commentary, no apology.
6. Preserve all mathematical and Unicode symbols exactly."""


def _build_prompt(text: str, instructions: str, no_think: bool) -> str:
    suffix = " /no_think" if no_think else ""
    request = instructions.strip() or "Use a clear topic heading; keep the default structure."
    return (
        f"{SYSTEM_PROMPT}{suffix}\n\n"
        f"USER REQUEST (may change headings, order and emphasis, never words):\n{request}\n\n"
        f"ANSWER:\n{text}"
    )


def _call_ollama(prompt: str, cfg: dict[str, Any]) -> str:
    enhance_cfg = cfg.get("enhance", {})
    model = str(cfg.get("model", "qwen3:8b"))
    base = str(cfg.get("ollama_url", "http://localhost:11434")).rstrip("/")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": float(enhance_cfg.get("temperature", 0.1))},
    }
    with httpx.Client(timeout=float(enhance_cfg.get("timeout_seconds", 120))) as client:
        response = client.post(f"{base}/api/generate", json=payload)
        response.raise_for_status()
        body = response.json()
    if "response" not in body:
        raise ValueError(f"Unexpected Ollama response: {str(body)[:200]}")
    return str(body["response"])


def check_ollama(
    cfg: dict[str, Any], timeout: float = 4.0
) -> tuple[bool, str, list[str]]:
    """Report whether Ollama is reachable and the configured model is present.

    Kept separate from the generation call so a missing server is reported
    once, immediately, instead of surfacing as a timeout on every answer.
    """
    base = str(cfg.get("ollama_url", "http://localhost:11434")).rstrip("/")
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base}/api/tags")
            response.raise_for_status()
            models = [
                str(item.get("name", ""))
                for item in response.json().get("models", [])
            ]
    except Exception as exc:
        return False, f"not reachable at {base} ({type(exc).__name__})", []

    if not models:
        return False, f"reachable at {base}, but no models are installed", []
    model = str(cfg.get("model", ""))
    installed = any(
        name == model or name.split(":")[0] == model.split(":")[0] for name in models
    )
    if not installed:
        return (
            False,
            f"reachable, but '{model}' is missing (run: ollama pull {model})",
            models,
        )
    return True, f"reachable at {base}; '{model}' is installed", models


def _clean_model_output(raw: str) -> str:
    text = raw.strip()
    wrapped = _WRAPPER_FENCE_RE.match(text)
    if wrapped:
        text = wrapped.group(1).strip()
    return text


def _ensure_heading(text: str, ordinal: int) -> str:
    lines = text.splitlines()
    if lines and re.match(r"^\s{0,3}#{1,6}\s+\S", lines[0]):
        title = re.sub(r"^\s{0,3}#{1,6}\s+", "", lines[0]).strip()
        title = re.sub(r"^\d+\.\s*", "", title)
        lines[0] = f"## {ordinal}. {title}"
    else:
        lines.insert(0, f"## {ordinal}. Section {ordinal}")
    return "\n".join(lines)


def enhance(
    clean_path: str | Path,
    enhanced_path: str | Path,
    meta_path: str | Path | None = None,
    config: dict[str, Any] | None = None,
    *,
    offline: bool = False,
    instructions: str | None = None,
) -> dict[str, Any]:
    """Run Stage 3 and return a report of model calls and fallbacks."""
    cfg = config or load_config()
    clean_file = Path(clean_path)
    if meta_path is None:
        meta_path = clean_file.with_name("clean.meta.json")
    manifest = read_json(meta_path)
    answers = split_answers(clean_file.read_text(encoding="utf-8"))
    if not answers:
        raise ValueError(f"No answer sections found in {clean_file}")

    meta_cfg = cfg.get("enhance", {})
    use_model = bool(meta_cfg.get("enabled", True)) and not offline
    connection: dict[str, Any] = {
        "checked": False,
        "connected": False,
        "detail": "not checked (offline mode)" if offline else "not checked",
    }
    if use_model:
        connected, detail, models = check_ollama(cfg)
        connection = {
            "checked": True,
            "connected": connected,
            "detail": detail,
            "models": models,
        }
        if not connected:
            # Still produce the PDF: deterministic headings are a safe fallback.
            use_model = False
    if instructions is None:
        instructions = (
            str(manifest.get("user_instructions", ""))
            or str(meta_cfg.get("user_instructions", ""))
        )
    max_loss = float(cfg.get("max_word_loss", 0.05))
    channel = (cfg.get("render", {}) or {}).get("chrome_channel", "chrome")

    output_sections: list[str] = []
    calls: list[dict[str, Any]] = []
    fallbacks: list[dict[str, Any]] = []

    for answer in answers:
        ordinal = int(answer["ordinal"])
        # Keep the answer verbatim, including a leading blank line that may be
        # part of a diagram. Only the word-count baseline ignores outer blank
        # space; the emitted text never gets trimmed.
        original = answer["text"]
        expected_tokens = sorted(placeholder_keys(original))
        baseline = word_count(original.strip())
        candidate: str | None = None
        reason = ""

        if not use_model:
            reason = (
                "offline mode (no model call)"
                if offline
                else f"Ollama unavailable: {connection['detail']}"
            )
        else:
            prompt = _build_prompt(
                original, instructions, bool(meta_cfg.get("no_think", True))
            )
            calls.append({"ordinal": ordinal, "model": cfg.get("model")})
            try:
                candidate = _clean_model_output(_call_ollama(prompt, cfg))
            except Exception as exc:
                reason = f"Ollama call failed: {exc}"
                candidate = None

        if candidate is not None:
            if sorted(placeholder_keys(candidate)) != expected_tokens:
                reason = "protected placeholders changed or missing"
                candidate = None
            elif word_count(candidate) < baseline * (1 - max_loss):
                reason = (
                    f"word count {word_count(candidate)} < {baseline * (1 - max_loss):.1f} "
                    f"({max_loss:.0%} limit)"
                )
                candidate = None
            else:
                blocks = extract_mermaid_sources(candidate)
                valid = validate_mermaid_blocks(blocks, channel)
                if not all(valid):
                    # The original answer already contains the plain-text
                    # description, so a whole-answer fallback cannot lose it.
                    reason = "invalid Mermaid block"
                    candidate = None

        if candidate is None:
            output_sections.append(_ensure_heading(original, ordinal))
            fallbacks.append(
                {
                    "ordinal": ordinal,
                    "reason": reason or "no candidate",
                    "word_count": baseline,
                }
            )
        else:
            output_sections.append(_ensure_heading(candidate, ordinal))

    enhanced_file = Path(enhanced_path)
    enhanced_file.parent.mkdir(parents=True, exist_ok=True)
    plain = "\n\n---\n\n".join(output_sections) + "\n"
    mapping: dict[str, str] = manifest.get("placeholders", {})
    enhanced_file.write_text(restore_placeholders(plain, mapping), encoding="utf-8")

    report = {
        "mode": "offline" if not use_model else "model",
        "model": cfg.get("model") if use_model else None,
        "ollama": connection,
        "answers": len(answers),
        "calls": calls,
        "fallbacks": fallbacks,
        "enhanced_path": str(enhanced_file.resolve()),
    }
    write_json(enhanced_file.with_name("enhance.meta.json"), report)
    if connection["checked"] and not connection["connected"]:
        print(
            f"enhance: Ollama {connection['detail']}; using plain headings",
            file=sys.stderr,
        )
    for fallback in fallbacks:
        print(
            f"enhance: answer {fallback['ordinal']} kept original ({fallback['reason']})",
            file=sys.stderr,
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 3: clean.md -> enhanced.md")
    parser.add_argument("input", help="input clean.md")
    parser.add_argument("output", nargs="?", help="output enhanced.md")
    parser.add_argument("--meta", help="clean.meta.json (default: alongside input)")
    parser.add_argument("--config", help="config.yaml")
    parser.add_argument("--offline", action="store_true", help="skip Ollama entirely")
    parser.add_argument("--instructions", help="override user_instructions")
    args = parser.parse_args(argv)

    out = Path(args.output) if args.output else Path(args.input).with_name("enhanced.md")
    report = enhance(
        args.input,
        out,
        args.meta,
        load_config(args.config),
        offline=args.offline,
        instructions=args.instructions,
    )
    print(
        f"enhance: {report['answers']} answers, mode={report['mode']}, "
        f"{len(report['fallbacks'])} fallbacks -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
