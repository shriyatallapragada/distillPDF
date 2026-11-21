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

  function katex(node, ctx) {
    const annotation = node.querySelector('annotation[encoding="application/x-tex"]')
      || (node.tagName && node.tagName.toLowerCase() === 'annotation' ? node : null);
    if (!annotation) return node.textContent.trim();
    const source = annotation.textContent.trim();
    if (source && ctx.latex.indexOf(source) < 0) ctx.latex.push(source);
    const display = node.classList.contains('katex-display')
      || (node.parentElement && node.parentElement.classList.contains('katex-display'));
    const fence = display ? '$$' : '$';
    return fence + source + fence;
  }

  function list(node, ordered, depth, ctx) {
    let out = '\n';
    const items = Array.from(node.children).filter(function (child) {
      return child.tagName.toLowerCase() === 'li';
    });
    items.forEach(function (item, index) {
      const marker = ordered ? (index + 1) + '.' : '-';
      let body = '';
      Array.from(item.childNodes).forEach(function (child) {
        if (child.nodeType === 1 && /^(UL|OL)$/.test(child.tagName)) return;
        body += walk(child, ctx);
      });
      body = body.replace(/\s+/g, ' ').trim();
      out += '  '.repeat(depth) + marker + ' ' + body + '\n';
      Array.from(item.children).forEach(function (child) {
        const tag = child.tagName.toLowerCase();
        if (tag === 'ul' || tag === 'ol') out += list(child, tag === 'ol', depth + 1, ctx);
      });
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

    if (tag === 'katex' || node.classList.contains('katex')) return katex(node, ctx);
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
      return '\n' + '#'.repeat(Number(tag[1])) + ' ' + inline(node, ctx).trim() + '\n';
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
    if (tag === 'li') return '- ' + inline(node, ctx).trim() + '\n';
    if (tag === 'table') return table(node, ctx);
    if (tag === 'blockquote') {
      return '\n' + inline(node, ctx).trim().split('\n').map(function (line) {
        return '> ' + line;
      }).join('\n') + '\n';
    }
    if (tag === 'p') return '\n' + inline(node, ctx).trim() + '\n';
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
    const ctx = { latex: [], options: opts };
    const rawText = root.textContent || '';
    const markdown = tidy(inline(root, ctx));
    debugWhitespace(root, rawText, markdown, opts);
    return { markdown: markdown, latex: ctx.latex };
  };
})();
