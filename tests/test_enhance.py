from __future__ import annotations

import re
from pathlib import Path

import pipeline.enhance as stage
from pipeline.common import split_answers
from pipeline.enhance import _build_prompt, enhance


def _stub_model(monkeypatch, transform) -> None:
    def call(prompt: str, cfg: dict) -> str:
        answer = prompt.split("ANSWER:\n", 1)[1]
        return transform(prompt, answer)

    monkeypatch.setattr(stage, "_call_ollama", call)
    monkeypatch.setattr(stage, "check_ollama", lambda cfg: (True, "stub", []))
    monkeypatch.setattr(
        stage, "validate_mermaid_blocks", lambda blocks, channel: [True] * len(blocks)
    )


def _original_first_answer(tmp_path: Path) -> str:
    return split_answers((tmp_path / "clean.md").read_text(encoding="utf-8"))[0]["text"]


def _run(tmp_path: Path, config: dict, **kwargs):
    return enhance(
        tmp_path / "clean.md",
        tmp_path / "enhanced.md",
        tmp_path / "clean.meta.json",
        config,
        **kwargs,
    )


def test_offline_mode_numbers_headings_and_restores_math(cleaned, tmp_path, config):
    report = _run(tmp_path, config, offline=True)
    text = (tmp_path / "enhanced.md").read_text(encoding="utf-8")
    assert report["mode"] == "offline"
    assert report["answers"] == 2
    assert text.startswith("## 1.")
    assert "\\alpha \\le 1" in text
    assert "`code_0`" in text and "`code_1`" in text
    assert "@@NLMDF_" not in text


def test_prompt_contains_verbatim_rule_and_no_think(config):
    prompt = _build_prompt("answer text", "group by topic", True)
    assert "keep every sentence exactly" in prompt.lower()
    assert "group by topic" in prompt
    assert "/no_think" in prompt
    assert "answer text" in prompt


def test_valid_model_output_is_accepted(cleaned, tmp_path, config, monkeypatch):
    _stub_model(monkeypatch, lambda prompt, answer: "## A new heading\n\n" + answer)
    report = _run(tmp_path, config)
    text = (tmp_path / "enhanced.md").read_text(encoding="utf-8")
    assert report["fallbacks"] == []
    assert "## 1. A new heading" in text
    assert "\\alpha \\le 1" in text


def test_word_loss_triggers_fallback(cleaned, tmp_path, config, monkeypatch):
    def thin_output(prompt: str, answer: str) -> str:
        tokens = " ".join(re.findall(r"@@NLMDF_[A-Z]+_\d+@@", answer))
        return f"## Short\n\n{tokens}"

    _stub_model(monkeypatch, thin_output)
    report = _run(tmp_path, config)
    assert len(report["fallbacks"]) == 2
    assert "original answer was changed" in report["fallbacks"][0]["reason"]
    text = (tmp_path / "enhanced.md").read_text(encoding="utf-8")
    assert "one two three" not in text
    assert "\\alpha \\le 1" in text


def test_mangled_placeholder_triggers_fallback(cleaned, tmp_path, config, monkeypatch):
    def mangled(prompt: str, answer: str) -> str:
        return answer.replace("@@NLMDF_MATH_0@@", "CHANGED")

    _stub_model(monkeypatch, mangled)
    report = _run(tmp_path, config)
    assert report["fallbacks"][0]["reason"] == "original answer was changed or extra prose was added"


def test_same_length_prose_rewrite_is_rejected(cleaned, tmp_path, config, monkeypatch):
    original = _original_first_answer(tmp_path)
    word = re.search(r"(?m)^[A-Za-z]+", original).group()
    _stub_model(monkeypatch, lambda prompt, answer: answer.replace(word, "Altered", 1))

    report = _run(tmp_path, config)
    assert "original answer was changed" in report["fallbacks"][0]["reason"]
    assert "Altered" not in (tmp_path / "enhanced.md").read_text(encoding="utf-8")


def test_invalid_mermaid_triggers_fallback(cleaned, tmp_path, config, monkeypatch):
    def with_diagram(prompt: str, answer: str) -> str:
        return answer.rstrip() + "\n\n```mermaid\nflowchart TD\n A --> B\n```\n"

    monkeypatch.setattr(stage, "_call_ollama", lambda p, c: with_diagram(p, p.split("ANSWER:\n", 1)[1]))
    monkeypatch.setattr(stage, "check_ollama", lambda cfg: (True, "stub", []))
    monkeypatch.setattr(stage, "validate_mermaid_blocks", lambda blocks, channel: [False])
    report = _run(tmp_path, config)
    assert report["fallbacks"][0]["reason"] == "invalid Mermaid block"
    text = (tmp_path / "enhanced.md").read_text(encoding="utf-8")
    assert "```mermaid" not in text


def test_ollama_failure_falls_back_without_crashing(cleaned, tmp_path, config, monkeypatch):
    def explode(prompt, cfg):
        raise ConnectionError("ollama is down")

    monkeypatch.setattr(stage, "_call_ollama", explode)
    monkeypatch.setattr(stage, "check_ollama", lambda cfg: (True, "stub", []))
    report = _run(tmp_path, config)
    assert all("Ollama call failed" in item["reason"] for item in report["fallbacks"])
    assert (tmp_path / "enhanced.md").exists()


def test_unavailable_ollama_falls_back_without_calling(cleaned, tmp_path, config, monkeypatch):
    monkeypatch.setattr(
        stage, "check_ollama", lambda cfg: (False, "not reachable", [])
    )
    monkeypatch.setattr(stage, "_call_ollama", lambda p, c: pytest_fail("should not call"))
    report = _run(tmp_path, config)
    assert report["mode"] == "offline"
    assert report["ollama"]["connected"] is False
    assert all("Ollama unavailable" in item["reason"] for item in report["fallbacks"])


def pytest_fail(message: str) -> None:
    raise AssertionError(message)
