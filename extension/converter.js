/* HTML -> Markdown, with KaTeX annotation recovery. No libraries, no network. */
(function () {
  const SKIP = new Set([
    'script', 'style', 'svg', 'noscript', 'iframe', 'annotation',
    'button', 'input', 'select', 'textarea', 'template', 'thinking-chain-view'
  ]);

  /* Raw text is never trimmed or whitespace-collapsed here: the Markdown
     parser decides paragraphs and line breaks. NBSP in prose becomes a normal
     space so lines can wrap; inside <pre> it is kept as intentional padding. */
  function escapeMd(value) {
    return String(value)
      .replace(/\u00a0/g, ' ')
      .replace(/\\/g, '\\\\')
      .replace(/([*_`\[\]])/g, '\\$1');
  }

  function inline(node, ctx) {
    return Array.from(node.childNodes).map(function (child) {
      return walk(child, ctx);
    }).join('');
  }

  function isCitation(node, options) {
    return (options.citation || []).some(function (selector) {
      try { return node.matches(selector); } catch (error) { return false; }
    });
  }

  function mathML(node) {
    const tag = node.localName;
    const children = Array.from(node.children);
    const parts = children.map(mathML);
    if (tag === 'annotation' || tag === 'annotation-xml') return '';
    if (tag === 'semantics') return parts[0] || '';
    if (tag === 'msqrt') return '\\sqrt{' + parts.join('') + '}';
    if (tag === 'mroot' && parts.length === 2) return '\\sqrt[' + parts[1] + ']{' + parts[0] + '}';
    if (tag === 'mfrac' && parts.length === 2) return '\\frac{' + parts[0] + '}{' + parts[1] + '}';
    if (tag === 'msup' && parts.length === 2) return '{' + parts[0] + '}^{' + parts[1] + '}';
    if (tag === 'msub' && parts.length === 2) return '{' + parts[0] + '}_{' + parts[1] + '}';
    if (tag === 'msubsup' && parts.length === 3) {
      return '{' + parts[0] + '}_{' + parts[1] + '}^{' + parts[2] + '}';
    }
    if (tag === 'mfenced') {
      const open = node.getAttribute('open') ?? '(';
      const close = node.getAttribute('close') ?? ')';
      return open + parts.join(node.getAttribute('separators')?.[0] ?? ',') + close;
    }
    if (tag === 'mspace') return ' ';
    if (parts.length) return parts.join('');
    const text = node.textContent.trim();
    if (tag === 'mi' && node.getAttribute('mathvariant') === 'double-struck') {
      return '\\mathbb{' + text + '}';
    }
    if (tag === 'mo' && /^[=<>≤≥≈≠∈∉]$/.test(text)) return ' ' + text + ' ';
    return text.replace(/[{}%$#&_]/g, '\\$&');
  }

  /* NotebookLM renders KaTeX with `output: "html"`: there is no MathML
     annotation and no data-latex attribute, only semantic spans such as
     .mfrac and .msupsub. Rebuild the TeX from those spans so a fraction is
     not flattened into its concatenated glyphs. Both KaTeX 0.16 class names
     (.base, .sizing) and the 0.18 katex- prefixes are accepted. */
  const KATEX_SYMBOLS = {
    '∣': '|', '−': '-', '∗': '*', '⟨': '\\langle ', '⟩': '\\rangle ',
    'α': '\\alpha', 'β': '\\beta', 'γ': '\\gamma', 'δ': '\\delta',
    'θ': '\\theta', 'λ': '\\lambda', 'μ': '\\mu', 'π': '\\pi',
    'σ': '\\sigma', 'ψ': '\\psi', 'ω': '\\omega', '∞': '\\infty',
    '∑': '\\sum', '∏': '\\prod', '∫': '\\int', '⋅': '\\cdot',
    '≤': '\\le ', '≥': '\\ge ', '≠': '\\ne ', '≈': '\\approx ',
    '∈': '\\in ', '∉': '\\notin ', '⊗': '\\otimes ', '…': '\\ldots'
  };
  const KATEX_FONTS = {
    mathbb: 'mathbb', mathbf: 'mathbf', mathit: 'mathit',
    mathsf: 'mathsf', mathtt: 'mathtt'
  };

  function hasClass(node, name) {
    const classes = new Set(String(node.className || '').split(/\s+/).filter(Boolean));
    return classes.has(name) || classes.has('katex-' + name);
  }

  function mapTexText(value) {
    let out = '';
    for (const character of String(value)) {
      if (character === '\u200b' || character === '\ufeff') continue;
      if (Object.prototype.hasOwnProperty.call(KATEX_SYMBOLS, character)) {
        out += KATEX_SYMBOLS[character];
      } else if (/[\\{}%$#&_^~]/.test(character)) {
        out += '\\' + character;
      } else {
        out += character;
      }
    }
    return out;
  }

  function fontWrap(node, value) {
    for (const name of Object.keys(KATEX_FONTS)) {
      if (hasClass(node, name)) return '\\' + KATEX_FONTS[name] + '{' + value + '}';
    }
    return value;
  }

  function braceTex(value) {
    if (/^\\?[A-Za-z0-9|+\-]$/.test(value)) return value;
    if (value.startsWith('{') && value.endsWith('}')) return value;
    return '{' + value + '}';
  }

  function topValue(node) {
    const match = /(-?[\d.]+)em/.exec((node.style && node.style.top) || '');
    return match ? Number(match[1]) : Number.POSITIVE_INFINITY;
  }

  function texRow(row) {
    return Array.from(row.childNodes).filter(function (child) {
      if (child.nodeType !== Node.ELEMENT_NODE) return true;
      return !hasClass(child, 'pstrut') && !hasClass(child, 'frac-line')
        && !hasClass(child, 'hide-tail') && !hasClass(child, 'vlist-s');
    }).map(texFromNode).join('');
  }

  function fractionTex(node) {
    const vlist = node.querySelector('.vlist');
    if (!vlist) return '';
    const rows = Array.from(vlist.children).filter(function (row) {
      if (hasClass(row, 'pstrut') || hasClass(row, 'vlist-s')) return false;
      return !Array.from(row.children).some(function (child) {
        return hasClass(child, 'frac-line') || hasClass(child, 'hide-tail');
      });
    }).sort(function (a, b) { return topValue(a) - topValue(b); });
    if (rows.length < 2) return '';
    return '\\frac{' + texRow(rows[0]) + '}{' + texRow(rows[1]) + '}';
  }

  function sqrtTex(node) {
    const elements = Array.from(node.querySelectorAll('*'));
    const padded = elements.find(function (element) {
      return element.style && element.style.paddingLeft;
    });
    const source = padded || elements.find(function (element) {
      return hasClass(element, 'svg-align');
    });
    return '\\sqrt{' + (source ? texRow(source) : '') + '}';
  }

  function scriptTex(node) {
    const vlist = node.querySelector('.vlist');
    if (!vlist) return '';
    const rows = Array.from(vlist.children).filter(function (row) {
      return !hasClass(row, 'pstrut') && !hasClass(row, 'vlist-s')
        && !hasClass(row, 'hide-tail');
    });
    const value = rows.length ? texRow(rows[0]) : '';
    return (node.querySelector('.vlist-s') ? '_{' : '^{') + value + '}';
  }

  function texFromNode(node) {
    if (node.nodeType === Node.TEXT_NODE) return mapTexText(node.nodeValue || '');
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    const tag = node.tagName.toLowerCase();
    if (tag === 'svg' || tag === 'path' || tag === 'annotation') return '';
    if (hasClass(node, 'strut') || hasClass(node, 'pstrut') || hasClass(node, 'frac-line')
      || hasClass(node, 'hide-tail') || hasClass(node, 'nulldelimiter')) return '';
    if (hasClass(node, 'mfrac')) return fractionTex(node);
    if (hasClass(node, 'sqrt')) return sqrtTex(node);
    if (hasClass(node, 'msupsub') || hasClass(node, 'msubsup')) return scriptTex(node);
    if (hasClass(node, 'mspace')) {
      return (node.style && node.style.marginRight === '1em') ? '\\quad' : '\\ ';
    }
    if (hasClass(node, 'delimsizing')) {
      return mapTexText(node.textContent.trim()) || '|';
    }
    if (Array.from(node.childNodes).every(function (child) {
      return child.nodeType === Node.TEXT_NODE;
    })) {
      return node.textContent ? fontWrap(node, mapTexText(node.textContent)) : '';
    }
    let result = '';
    let scripts = '';
    Array.from(node.childNodes).forEach(function (child) {
      if (child.nodeType === Node.ELEMENT_NODE
        && (hasClass(child, 'msupsub') || hasClass(child, 'msubsup'))) {
        scripts += scriptTex(child);
      } else {
        result += texFromNode(child);
      }
    });
    return scripts ? braceTex(result) + scripts : result;
  }

  function katexHtmlToTex(node) {
    return texFromNode(node).trim() || null;
  }

  function captureMath(node, ctx) {
    const annotation = node.querySelector('annotation[encoding="application/x-tex"], annotation[encoding="application/tex"]');
    const math = node.localName === 'math' ? node : node.querySelector('math');
    const html = node.classList.contains('katex-html') ? node : node.querySelector('.katex-html');
    const source = annotation?.textContent.trim() || node.getAttribute('data-latex')
      || (math && mathML(math)) || (html && katexHtmlToTex(html));
    if (!source) {
      ctx.mathWarnings.push((node.textContent || '').trim().slice(0, 80) || 'unreadable math element');
      return node.textContent.trim();
    }
    if (ctx.latex.indexOf(source) < 0) ctx.latex.push(source);
    const display = node.classList.contains('katex-display')
      || (node.parentElement && node.parentElement.classList.contains('katex-display'))
      || math?.getAttribute('display') === 'block'
      || node.getAttribute('display') === 'true';
    const fence = display ? '$$' : '$';
    return fence + source + fence;
  }

  function list(node, ordered, depth, ctx) {
    let out = '\n';
    const items = Array.from(node.querySelectorAll('li')).filter(function (item) {
      return item.closest('ul, ol') === node;
    });
    items.forEach(function (item, index) {
      const marker = ordered ? (index + 1) + '.' : '-';
      let body = '';
      Array.from(item.childNodes).forEach(function (child) {
        if (child.nodeType === 1 && /^(UL|OL)$/.test(child.tagName)) return;
        body += walk(child, ctx);
      });
      const indent = '  '.repeat(depth);
      const continuation = indent + ' '.repeat(marker.length + 1);
      const paragraphs = body.split(/\n(?:[ \t]*\n)+/).map(function (paragraph) {
        return paragraph.replace(/\s+/g, ' ').trim();
      }).filter(Boolean);
      out += indent + marker + ' ' + paragraphs.join('\n\n' + continuation) + '\n';
      Array.from(item.children).forEach(function (child) {
        const tag = child.tagName.toLowerCase();
        if (tag === 'ul' || tag === 'ol') out += list(child, tag === 'ol', depth + 1, ctx);
      });
      if (index + 1 < items.length) out += '\n';
    });
    return out + '\n';
  }

  function table(node, ctx) {
    const rows = Array.from(node.querySelectorAll('tr')).map(function (row) {
      return Array.from(row.querySelectorAll('th, td')).map(function (cell) {
        return inline(cell, ctx).replace(/\|/g, '\\|').replace(/\n/g, ' ').trim();
      });
    }).filter(function (row) { return row.length; });
    if (!rows.length) return '';
    const separator = rows[0].map(function () { return '---'; });
    const lines = [rows[0], separator].concat(rows.slice(1)).map(function (row) {
      return '| ' + row.join(' | ') + ' |';
    });
    return '\n' + lines.join('\n') + '\n';
  }

  function walk(node, ctx) {
    if (node.nodeType === Node.TEXT_NODE) return escapeMd(node.nodeValue || '');
    if (node.nodeType !== Node.ELEMENT_NODE) return '';

    const tag = node.tagName.toLowerCase();
    const options = ctx.options;
    if (SKIP.has(tag)) return '';
    if (isCitation(node, options)) return '';

    if (tag === 'math' || tag === 'mjx-container' || tag === 'katex'
      || node.classList.contains('katex') || node.hasAttribute('data-latex')) return captureMath(node, ctx);
    if (tag === 'annotation') return '';

    if (tag === 'pre') {
      let language = '';
      const code = node.querySelector('code') || node;
      const match = (code.className || '').match(/language-([\w-]+)/);
      if (match) language = match[1];
      const raw = code.textContent || '';
      // Tabs become four columns; every other character (NBSP, blank lines,
      // trailing spaces) survives exactly as written.
      const diagram = raw.replace(/\t/g, '    ').replace(/\n$/, '');
      return '\n```' + language + '\n' + diagram + '\n```\n';
    }
    if (tag === 'code') return '`' + (node.textContent || '').replace(/\s+/g, ' ') + '`';
    if (tag === 'br') return '\n';
    if (tag === 'hr') return '\n---\n';

    if (/^h[1-6]$/.test(tag)) {
      return '\n\n' + '#'.repeat(Number(tag[1])) + ' ' + inline(node, ctx).trim() + '\n\n';
    }
    if (tag === 'strong' || tag === 'b') return '**' + inline(node, ctx).trim() + '**';
    if (tag === 'em' || tag === 'i') return '*' + inline(node, ctx).trim() + '*';
    if (tag === 'del' || tag === 's' || tag === 'strike') {
      return '~~' + inline(node, ctx).trim() + '~~';
    }
    if (tag === 'a') {
      const label = inline(node, ctx).trim();
      if (options.stripCitations && /^\[?\d+\]?$/.test(label)) return '';
      const href = node.getAttribute('href') || '';
      if (!href || href.charAt(0) === '#') return label;
      return '[' + label + '](' + href + ')';
    }
    if (tag === 'ul' || tag === 'ol') return list(node, tag === 'ol', 0, ctx);
    if (tag === 'li') return '\n\n- ' + inline(node, ctx).trim() + '\n\n';
    if (tag === 'table') return table(node, ctx);
    if (tag === 'blockquote') {
      return '\n' + inline(node, ctx).trim().split('\n').map(function (line) {
        return '> ' + line;
      }).join('\n') + '\n';
    }
    if (tag === 'p') return '\n\n' + inline(node, ctx).trim() + '\n\n';
    if (tag === 'div') return '\n\n' + inline(node, ctx) + '\n\n';
    if (tag === 'img') return node.getAttribute('alt') ? '[' + node.getAttribute('alt') + ']' : '';

    return inline(node, ctx);
  }

  /* CRLF is normalized and excess blank lines are eased only in prose. Fenced
     blocks are never touched, so their columns, blank lines and trailing
     spaces survive. No trim(), no per-line trailing-space strip. */
  function tidy(markdown) {
    const text = markdown.replace(/\r\n/g, '\n');
    const parts = text.split(/(```[\s\S]*?```|~~~[\s\S]*?~~~)/g);
    const joined = parts.map(function (part, index) {
      return index % 2 ? part : part.replace(/\n{3,}/g, '\n\n');
    }).join('');
    return joined.replace(/^\n+/, '').replace(/\n+$/, '');
  }

  function debugWhitespace(root, rawText, markdown, options) {
    const hasDiagram = /```/.test(markdown);
    if (!hasDiagram && !options.debugWhitespace && !window.NLMDF_DEBUG_WHITESPACE) return;
    // Exact before/after strings: raw message text vs. the HTML in that block.
    console.debug(
      '[DistillPDF whitespace] rawText=' + JSON.stringify(rawText) +
      ' html=' + JSON.stringify(root.innerHTML) +
      ' markdown=' + JSON.stringify(markdown)
    );
  }

  window.NLK = window.NLK || {};
  window.NLK.htmlToMarkdown = function (root, options) {
    const opts = Object.assign({ stripCitations: true, citation: [], debugWhitespace: false }, options || {});
    const ctx = { latex: [], mathWarnings: [], options: opts };
    const rawText = root.textContent || '';
    const listItems = Array.from(root.querySelectorAll('li')).filter(function (item) {
      return !item.closest('thinking-chain-view');
    }).length;
    const markdown = tidy(inline(root, ctx));
    debugWhitespace(root, rawText, markdown, opts);
    return {
      markdown: markdown,
      latex: ctx.latex,
      mathWarnings: ctx.mathWarnings,
      listItems: listItems
    };
  };
})();
