/* Runs inside study-notes.html after KaTeX and Mermaid are loaded. */
(function () {
  var problems = [];
  var state = {
    ready: false,
    katexCount: 0,
    katexErrors: 0,
    mermaidBlocks: 0,
    mermaidErrors: 0,
    tables: 0,
    fittedBlocks: 0,
    minDiagramScale: 1,
    diagramLines: [],
    diagramAligned: true,
    problems: problems
  };
  window.__NLMDF = state;

  var CIRCUIT_CHARS = /[─│┌┐└┘├┤┬┴┼═║■►▼◆◀]/;

  function renderMath() {
    // Math is rendered at build time as static inline SVG (the same technique
    // used for circuit diagrams). KaTeX is no longer used: its HTML/MathML
    // output corrupts the plain-unicode symbols NotebookLM emits in prose.
    var symbols = document.querySelectorAll('.nlmdf-symbol');
    state.katexCount = symbols.length;
    state.katexErrors = document.querySelectorAll('.katex-error').length;
  }

  async function renderMermaid() {
    var blocks = document.querySelectorAll('pre code.language-mermaid');
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'loose',
      theme: 'neutral',
      flowchart: { useMaxWidth: true }
    });
    for (var i = 0; i < blocks.length; i++) {
      var code = blocks[i];
      var source = code.textContent || '';
      state.mermaidBlocks += 1;
      try {
        await mermaid.parse(source);
        var result = await mermaid.render('nlmdf-diagram-' + (i + 1), source);
        var figure = document.createElement('div');
        figure.className = 'mermaid-figure';
        figure.innerHTML = result.svg;
        code.parentElement.replaceWith(figure);
      } catch (error) {
        state.mermaidErrors += 1;
        problems.push('Mermaid: ' + String(error));
      }
    }
  }

  /* Measure a line with the exact font of the code block, without the
     transform/scaling that may already be applied to it. */
  function measureLine(line, style) {
    var probe = document.createElement('span');
    probe.textContent = line;
    probe.style.cssText = 'position:absolute;left:-99999px;top:0;' +
      'visibility:hidden;white-space:pre;';
    probe.style.fontFamily = style.fontFamily;
    probe.style.fontSize = style.fontSize;
    probe.style.fontWeight = style.fontWeight;
    probe.style.fontStyle = style.fontStyle;
    probe.style.letterSpacing = style.letterSpacing;
    document.body.appendChild(probe);
    var width = probe.getBoundingClientRect().width;
    document.body.removeChild(probe);
    return width;
  }

  /* NotebookLM's ASCII export often misaligns the control square, the
     vertical connector and the target gate: e.g. ■ at col 62, │ at col 55,
     U box centred at col 56. Re-align the lower rows to the square so the
     connection is actually drawn, while row 0 (the long register-1 line)
     is left completely untouched. */
  function alignCircuit(lines) {
    var squareRow = -1, barRow = -1;
    for (var i = 0; i < lines.length; i++) {
      if (squareRow < 0 && lines[i].indexOf('■') >= 0) squareRow = i;
      if (barRow < 0 && /^\s*│\s*$/.test(lines[i])) barRow = i;
    }
    // Multi-control circuits (│ │ │ │) are already rebuilt at build time.
    // Rewriting those rows here would collapse distinct connectors into one.
    if (squareRow < 0 || barRow < 0 ||
        (lines[barRow].match(/│/g) || []).length !== 1) return lines.slice();

    var out = lines.slice();
    var col = out[squareRow].indexOf('■');
    out[barRow] = new Array(col + 1).join(' ') + '│';

    for (var r = barRow + 1; r < out.length; r++) {
      var match = out[r].match(/\[[^\]]+\]/);
      if (!match) continue;
      var start = match.index;
      var centre = start + (match[0].length - 1) / 2;
      var delta = Math.round(col - centre);
      if (delta !== 0) {
        var before = out[r].slice(0, start);
        var after = out[r].slice(start + match[0].length);
        if (delta > 0) {
          // Borrow horizontal wire from the right of the gate.
          var borrowed = after.slice(0, delta);
          if (/^─+$/.test(borrowed)) {
            after = after.slice(delta);
            before += borrowed;
          } else {
            before += new Array(delta + 1).join(' ');
          }
        } else {
          var need = -delta;
          var tail = before.slice(-need);
          if (/^─+$/.test(tail)) {
            before = before.slice(0, -need);
            after = new Array(need + 1).join('─') + after;
          } else {
            after = new Array(need + 1).join('─') + after;
          }
        }
        out[r] = before + match[0] + after;
      }
      break;
    }
    return out;
  }

  /* Turn a wide preformatted block into one scalable SVG whose viewBox fits
     the longest source line. Every line is pinned to the same monospace
     character grid with textLength, so ■, │ and the gate stay vertically
     connected at any rendered size, and no printer can re-wrap a row. */
  function fitWideBlocks() {
    var fitted = 0;
    var minimum = 1;
    var blocks = Array.from(document.querySelectorAll('pre'));

    // Diagrams embedded at build time are already correctly aligned and
    // scaled; count them so validation still reports the whole picture.
    document.querySelectorAll('figure.nlmdf-diagram[data-nlmdf-static]').forEach(function (fig) {
      fitted += 1;
      state.diagramLines.push(Number(fig.getAttribute('data-nlmdf-lines')) || 0);
      minimum = Math.min(minimum, parseFloat(fig.getAttribute('data-nlmdf-scale')) || 1);
    });

    for (var b = 0; b < blocks.length; b++) {
      var pre = blocks[b];
      var code = pre.querySelector('code');
      if (!code || code.classList.contains('language-mermaid')) continue;

      // Keep every blank and trailing space: only tabs are expanded, to the
      // same four columns that CSS tab-size uses. NBSP stays as intentional
      // alignment inside a diagram.
      var source = (code.textContent || '').replace(/\t/g, '    ').replace(/\n$/, '');
      var lines = CIRCUIT_CHARS.test(source) ? alignCircuit(source.split('\n'))
                                             : source.split('\n');
      var style = window.getComputedStyle(code);
      var preStyle = window.getComputedStyle(pre);
      var padding = parseFloat(preStyle.paddingLeft) + parseFloat(preStyle.paddingRight);
      var available = pre.clientWidth - padding - 2;
      if (!available) continue;

      var cell = measureLine('M', style); // one monospace character
      var widths = lines.map(function (line) { return line.length * cell; });
      var contentWidth = Math.max.apply(null, widths);
      if (!contentWidth) continue;
      // Narrow blocks stay as ordinary <pre>; wide ones become SVG.
      var naturalWidth = Math.max.apply(null, lines.map(function (line) {
        return measureLine(line, style);
      }));
      if (naturalWidth <= available) continue;

      var fontSize = parseFloat(style.fontSize);
      var lineHeight = parseFloat(style.lineHeight);
      if (!isFinite(lineHeight)) lineHeight = fontSize * 1.45;
      var height = lines.length * lineHeight + 2;

      var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 ' + (contentWidth + 2) + ' ' + height);
      svg.setAttribute('width', '100%');
      svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', 'Circuit / diagram');

      for (var i = 0; i < lines.length; i++) {
        var text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', '0');
        text.setAttribute('y', String(i * lineHeight + fontSize));
        text.setAttribute('xml:space', 'preserve');
        text.setAttribute('font-family', style.fontFamily);
        text.setAttribute('font-size', style.fontSize);
        text.setAttribute('font-weight', style.fontWeight);
        // Pin every glyph to one character cell: alignment cannot drift even
        // when Unicode gate symbols come from a fallback font.
        text.setAttribute('textLength', String(lines[i].length * cell));
        text.setAttribute('lengthAdjust', 'spacingAndGlyphs');
        text.style.whiteSpace = 'pre';
        text.textContent = lines[i];
        svg.appendChild(text);
      }

      var figure = document.createElement('figure');
      figure.className = 'nlmdf-diagram';
      figure.setAttribute('data-nlmdf-lines', String(lines.length));
      if (CIRCUIT_CHARS.test(source)) figure.classList.add('nlmdf-circuit');
      figure.setAttribute('data-nlmdf-scale', (available / contentWidth).toFixed(4));
      figure.appendChild(svg);
      pre.replaceWith(figure);

      fitted += 1;
      minimum = Math.min(minimum, available / contentWidth);
      state.diagramLines.push(lines.length);
    }

    state.fittedBlocks = fitted;
    state.minDiagramScale = Number(minimum.toFixed(4));
  }

  /* Confirm the drawn ■ / │ / gate are on the same x coordinate. */
  function checkCircuitAlignment() {
    var figures = Array.from(document.querySelectorAll('figure.nlmdf-diagram'));
    for (var i = 0; i < figures.length; i++) {
      var texts = figures[i].querySelectorAll('svg text');
      if (texts.length < 3) continue;
      var row0 = texts[0].textContent || '';
      var row1 = texts[1].textContent || '';
      var row2 = texts[2].textContent || '';
      var square = row0.indexOf('■');
      var bar = row1.indexOf('│');
      var box = row2.match(/\[[^\]]+\]/);
      if (square < 0 || bar < 0 || !box) continue;
      var centre = Math.round(box.index + (box[0].length - 1) / 2);
      var xs = texts[0].getStartPositionOfChar(square).x;
      var xb = texts[1].getStartPositionOfChar(bar).x;
      var xg = texts[2].getStartPositionOfChar(centre).x;
      if (Math.abs(xs - xb) > 2 || Math.abs(xb - xg) > 4) {
        state.diagramAligned = false;
        problems.push('Circuit control square, connector and gate misaligned');
      }
    }
  }

  async function start() {
    renderMath();
    try {
      await renderMermaid();
    } catch (error) {
      problems.push('Mermaid setup: ' + String(error));
    }
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }
    fitWideBlocks();
    checkCircuitAlignment();
    state.tables = document.querySelectorAll('table').length;
    state.ready = true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
