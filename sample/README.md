# Sample chat

`chat.json` is a hand-written fixture in the same shape the Chrome extension
will emit (Stage 1). It contains two user turns and three assistant answers,
with inline/display LaTeX, a Markdown table, a Mermaid flowchart, a code span,
citations and non-ASCII symbols.

Run the whole pipeline without Ollama:

```bash
.venv/bin/python -m pipeline.cli all sample/chat.json --offline
```

Outputs land in `sample/out/`:

| File | Purpose |
| --- | --- |
| `clean.md` | Stage 2 output with `@@NLMDF_*@@` placeholders |
| `clean.meta.json` | Protected originals and expected counts |
| `enhanced.md` | Stage 3 output with restored LaTeX/code |
| `enhance.meta.json` | Model calls and fallback reasons |
| `study-notes.html` | Offline fallback, CSS/fonts/KaTeX/Mermaid inlined |
| `study-notes.pdf` | The printed result |
| `contact-sheet.png` | One thumbnail per page for the visual check |
| `report.json` | Six verification checks |
