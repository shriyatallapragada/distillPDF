/* Stage 1 — in-page answer picker for NotebookLM. Local only. */
(function () {
  // Manifest loading and popup recovery can run this script in the same tab.
  if (window.__NLMDF_CONTENT_INITIALIZED) return;
  window.__NLMDF_CONTENT_INITIALIZED = true;

  const state = {
    turns: [],
    selected: new Set(),
    fallbackKeys: new Map(),
    nextFallbackKey: 0,
    instructions: '',
    status: 'Warming the kettle…',
    scanning: false,
    panel: null
  };

  const CUP = '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" ' +
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true"><path d="M6 10h16v8a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6z"/>' +
    '<path d="M22 12h2a3 3 0 0 1 0 6h-2"/>' +
    '<path d="M10 5c0 2 2 2 2 4M15 5c0 2 2 2 2 4"/></svg>';

  function selectors() { return window.NLMDF_SELECTORS || {}; }
  function one(selector, root) {
    try { return (root || document).querySelector(selector); } catch (error) { return null; }
  }
  function all(selector, root) {
    try { return Array.from((root || document).querySelectorAll(selector)); } catch (error) { return []; }
  }
  function first(list, root, many) {
    for (const selector of list || []) {
      const found = many ? all(selector, root) : one(selector, root);
      if (many ? found.length > 0 : Boolean(found)) return found;
    }
    return many ? [] : null;
  }
  function matchesAny(list, element) {
    for (const selector of list || []) {
      try { if (element.matches(selector)) return true; } catch (error) { /* bad selector */ }
    }
    return false;
  }
  function wait(milliseconds) {
    return new Promise(function (resolve) { setTimeout(resolve, milliseconds); });
  }
  function hash(text) {
    let value = 0;
    for (let index = 0; index < text.length; index++) {
      value = (value * 31 + text.charCodeAt(index)) | 0;
    }
    return Math.abs(value).toString(36);
  }
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character];
    });
  }
  function wordCount(text) { return (text.match(/\S+/g) || []).length; }

  async function waitForSelectors() {
    // Wait up to 10 seconds for selectors.js to load selectors.json and
    // populate window.NLMDF_SELECTORS. If it never arrives, fall back to
    // the built-in DOM heuristics in collect()/roleOf().
    for (let attempt = 0; attempt < 200; attempt++) {
      if (Object.keys(selectors()).length) return;
      await wait(50);
    }
  }

  function container() {
    return first(selectors().scrollContainer, document) || document.body;
  }

  function roleOf(element) {
    const config = selectors();
    // Notebook's "to-user" cards are replies sent to the user.
    if (matchesAny(config.assistant, element)) return 'assistant';
    if (matchesAny(config.user, element)) return 'user';
    const attribute = (element.getAttribute('data-message-author-role') ||
      element.getAttribute('data-role') || '').toLowerCase();
    if (/user|human/.test(attribute)) return 'user';
    if (/assistant|model|bot/.test(attribute)) return 'assistant';
    if (/user|human/.test(String(element.className))) return 'user';
    return 'assistant';
  }

  function collect() {
    const config = selectors();
    const root = container();
    let candidates = first(config.turn, root, true);
    if (!candidates.length) {
      candidates = all('article, [role="article"], message-content, [class*="message"]', root);
    }
    // Keep outer turn containers only; virtualized pages nest answer wrappers.
    candidates = candidates.filter(function (element) {
      return !candidates.some(function (other) {
        return other !== element && other.contains(element);
      });
    });

    const found = [];
    const occurrences = new Map();
    candidates.forEach(function (element) {
      if (roleOf(element) !== 'assistant') return;
      const body = first(config.content, element) || element;
      const converted = window.NLK.htmlToMarkdown(body, {
        stripCitations: true,
        citation: config.citation || []
      });
      if (!converted.markdown || /^loading(?:\.{3}|…)?$/i.test(converted.markdown.trim())) return;
      const id = element.getAttribute('data-message-id');
      let key;
      if (id) {
        key = 'message-' + id;
      } else {
        const position = occurrences.get(converted.markdown) || 0;
        occurrences.set(converted.markdown, position + 1);
        if (!state.fallbackKeys.has(converted.markdown)) state.fallbackKeys.set(converted.markdown, []);
        const keys = state.fallbackKeys.get(converted.markdown);
        if (!keys[position]) keys[position] = 'answer-' + (++state.nextFallbackKey);
        key = keys[position];
      }
      found.push({
        key: key,
        role: 'assistant',
        markdown: converted.markdown,
        latex: converted.latex,
        words: wordCount(converted.markdown),
        element: element
      });
    });
    return found;
  }

  function merge(found) {
    const existing = new Map(state.turns.map(function (turn) { return [turn.key, turn]; }));
    found.forEach(function (turn, position) {
      if (existing.has(turn.key)) {
        Object.assign(existing.get(turn.key), turn);
      } else {
        turn.order = state.turns.length + position;
        existing.set(turn.key, turn);
        // Nothing is selected by default: the user picks what matters.
        // A highlight is the only automatic inclusion (see addHighlight).
      }
    });
    state.turns = Array.from(existing.values()).sort(function (a, b) { return a.order - b.order; });
    state.turns.forEach(function (turn, index) { turn.index = index + 1; });
  }

  function status(message) {
    state.status = message;
    const target = state.panel && state.panel.querySelector('[data-nlk-status]');
    if (target) target.textContent = message;
  }

  function renderPanel() {
    if (!state.panel) return;
    const list = state.panel.querySelector('[data-nlk-list]');
    if (!list) return;
    if (!state.turns.length) {
      list.innerHTML = '<div class="nl-kebab-empty">No answers yet — tap Scan chat.</div>';
      return;
    }
    list.innerHTML = state.turns.map(function (turn) {
      const preview = turn.markdown.replace(/[#*`>|\[\]]/g, ' ').replace(/\s+/g, ' ').trim();
      return '<label class="nl-kebab-item" data-nlk-key="' + escapeHtml(turn.key) + '">' +
        '<input type="checkbox" data-nlk-check="' + escapeHtml(turn.key) + '"' +
        (state.selected.has(turn.key) ? ' checked' : '') + '>' +
        '<span><span class="nlk-title">Answer ' + turn.index + ' · ' + turn.words + ' words</span>' +
        '<span class="nlk-preview">' + escapeHtml(preview.slice(0, 96)) + '</span></span></label>';
    }).join('');
    markTurns();
  }

  function markTurns() {
    state.turns.forEach(function (turn) {
      if (turn.element && turn.element.setAttribute) {
        turn.element.setAttribute('data-nlk-selected', state.selected.has(turn.key) ? 'true' : 'false');
      }
    });
  }

  function clearMarks() {
    state.turns.forEach(function (turn) {
      if (turn.element && turn.element.removeAttribute) turn.element.removeAttribute('data-nlk-selected');
    });
  }

  async function scanChat() {
    if (state.scanning) return state.turns.length;
    state.scanning = true;
    try {
      let scroller = container();
      for (let attempt = 0; scroller === document.body && attempt < 40; attempt++) {
        await wait(250);
        scroller = container();
      }
      scroller.scrollTop = 0;
      await wait(250);
      // Gemini Notebook mounts the scrolling pane before its history arrives.
      if (scroller.matches('chat-panel .chat-panel-content')) {
        for (let attempt = 0; attempt < 20; attempt++) {
          const initial = collect();
          if (initial.length) {
            merge(initial);
            break;
          }
          await wait(250);
        }
      }
      let reachedEnd = false;
      for (let pass = 0; pass < 80; pass++) {
        merge(collect());
        renderPanel();
        status('Scouting the menu… ' + state.turns.length + ' answers found');

        const before = scroller.scrollTop;
        const step = Math.max(220, Math.round(scroller.clientHeight * 0.8));
        scroller.scrollTop = before + step;
        await wait(220);
        if (scroller.scrollTop === before) {
          reachedEnd = true;
          break;
        }
      }
      merge(collect());
      renderPanel();
      status(state.turns.length + ' answers ready — ' +
        (reachedEnd ? 'pick the ones you want.' : 'scan limit reached. Check for missing answers.'));
      return state.turns.length;
    } finally {
      state.scanning = false;
    }
  }

  function toggleAll(select) {
    state.turns.forEach(function (turn) {
      if (select) state.selected.add(turn.key); else state.selected.delete(turn.key);
    });
    renderPanel();
    return state.selected.size;
  }

  function addHighlight() {
    const selection = window.getSelection();
    const text = selection ? String(selection).trim() : '';
    if (!text) {
      status('Highlight some chat text first, then tap Add highlight.');
      return null;
    }
    let markdown = '';
    try {
      const wrapper = document.createElement('div');
      wrapper.appendChild(selection.getRangeAt(0).cloneContents());
      markdown = window.NLK.htmlToMarkdown(wrapper, {
        stripCitations: true,
        citation: selectors().citation || []
      }).markdown;
    } catch (error) { /* fall through to plain text */ }
    if (!markdown) markdown = text.replace(/\s+/g, ' ');

    const key = 'h-' + hash(markdown);
    if (!state.turns.some(function (turn) { return turn.key === key; })) {
      merge([{
        key: key,
        role: 'assistant',
        markdown: markdown,
        latex: [],
        words: wordCount(markdown),
        element: selection.anchorNode && selection.anchorNode.parentElement
      }]);
    }
    state.selected.add(key);
    renderPanel();
    status('Highlight added to your basket.');
    return key;
  }

  function payload() {
    const chosen = state.turns.filter(function (turn) { return state.selected.has(turn.key); });
    return {
      title: (document.title || 'NotebookLM chat').split(/\s+[-–]\s+/)[0].trim(),
      source: location.href,
      user_instructions: state.instructions,
      turns: chosen.map(function (turn) {
        return {
          role: 'assistant',
          markdown: turn.markdown,
          latex: turn.latex,
          index: turn.index
        };
      })
    };
  }

  function fileName(path) { return String(path || '').split(/[\\/]/).pop(); }

  /* No chat.json download: the selected answers go straight to the local
     native helper, which writes study-notes.pdf and study-notes.html into the
     browser's Downloads folder. The helper runs the same Python pipeline as
     the command line, so the output is identical. */
  function buildDocuments() {
    merge(collect());
    renderPanel();
    const data = payload();
    if (!data.turns.length) {
      status('Pick at least one answer before brewing.');
      return { ok: false, error: 'No answers selected.' };
    }
    if (JSON.stringify(data).length > 900000) {
      status('Too much text for one build — select fewer answers.');
      return { ok: false, error: 'Payload too large.' };
    }
    status('Brewing PDF + HTML locally…');
    chrome.runtime.sendMessage({ type: 'MAKE_PDF', payload: data }, function (response) {
      const failure = chrome.runtime.lastError && chrome.runtime.lastError.message;
      if (failure) {
        status('Helper unavailable: ' + failure);
        return;
      }
      if (response && response.ok) {
        status('Saved ' + fileName(response.pdf) + ' and ' + fileName(response.html) +
          ' (' + response.answers + ' answers).' +
          (response.passed ? '' : ' Export checks flagged a possible rendering issue.'));
      } else {
        status('Build failed: ' + ((response && response.error) || 'unknown error'));
      }
    });
    return { ok: true, started: true, answers: data.turns.length };
  }

  function closePanel() {
    clearMarks();
    if (state.panel) {
      state.panel.remove();
      state.panel = null;
    }
    // status() writes into the panel, which is now gone; just log to console.
    console.log('[DistillPDF] picker closed.');
  }

  function buildPanel() {
    const panel = document.createElement('aside');
    panel.className = 'nl-kebab-panel';
    panel.innerHTML =
      '<div class="nl-kebab-head">' + CUP +
      '<div><strong>DistillPDF</strong><small>NotebookLM → PDF + HTML</small></div>' +
      '<button class="nl-kebab-link" data-nlk-action="close" style="margin-left:auto;">Close</button></div>' +
      '<p class="nl-kebab-status" data-nlk-status>Ready…</p>' +
      '<div class="nl-kebab-list" data-nlk-list></div>' +
      '<div class="nl-kebab-row">' +
      '<button class="nl-kebab-btn quiet" data-nlk-action="all">Select all</button>' +
      '<button class="nl-kebab-btn quiet" data-nlk-action="none">Clear</button>' +
      '</div>' +
      '<div class="nl-kebab-row">' +
      '<button class="nl-kebab-btn quiet" data-nlk-action="highlight">Add highlighted text</button>' +
      '</div>' +
      '<div class="nl-kebab-row">' +
      '<button class="nl-kebab-btn primary" data-nlk-action="export">Build PDF + HTML</button>' +
      '</div>' +
      '<button class="nl-kebab-link" data-nlk-action="scan">Refresh answers</button>';
    panel.addEventListener('change', function (event) {
      const input = event.target.closest('[data-nlk-check]');
      if (!input) return;
      const key = input.getAttribute('data-nlk-check');
      if (input.checked) state.selected.add(key); else state.selected.delete(key);
      markTurns();
      status(state.selected.size + ' of ' + state.turns.length + ' answers picked.');
    });
    panel.addEventListener('click', function (event) {
      const button = event.target.closest('[data-nlk-action]');
      if (!button) return;
      const action = button.getAttribute('data-nlk-action');
      if (action === 'scan') scanChat();
      if (action === 'all') { toggleAll(true); status('All answers picked.'); }
      if (action === 'none') { toggleAll(false); status('Basket emptied.'); }
      if (action === 'highlight') addHighlight();
      if (action === 'export') buildDocuments();
      if (action === 'close') closePanel();
    });
    (document.body || document.documentElement).appendChild(panel);
    state.panel = panel;
    renderPanel();
  }

  chrome.runtime.onMessage.addListener(function (message, sender, reply) {
    switch (message.type) {
      case 'NLK_STATUS':
        reply({
          status: state.status,
          total: state.turns.length,
          selected: state.selected.size,
          words: payload().turns.reduce(function (sum, turn) {
            return sum + wordCount(turn.markdown);
          }, 0)
        });
        return true;
      case 'NLK_TURNS':
        reply(state.turns.map(function (turn) {
          return {
            key: turn.key,
            index: turn.index,
            words: turn.words,
            preview: turn.markdown.slice(0, 140),
            selected: state.selected.has(turn.key)
          };
        }));
        return true;
      case 'NLK_SCAN':
        scanChat().then(function (count) {
          reply({ ok: true, count: count });
        }).catch(function (error) {
          reply({ ok: false, error: String(error) });
        });
        return true;
      case 'NLK_TOGGLE':
        reply({ ok: true, selected: toggleAll(Boolean(message.value)) });
        return true;
      case 'NLK_SET_SELECTED': {
        const change = message.value || {};
        if (change.value) state.selected.add(change.key);
        else state.selected.delete(change.key);
        markTurns();
        reply({ ok: true, selected: state.selected.size });
        return true;
      }
      case 'NLK_INSTRUCTIONS':
        state.instructions = message.value || '';
        reply({ ok: true });
        return true;
      case 'NLK_EXPORT':
        // Payload only: used by tests and by callers that want the raw data.
        // It never triggers a chat.json download.
        reply({ ok: true, data: payload() });
        return true;
      case 'NLK_BUILD':
        reply(buildDocuments());
        return true;
      default:
        return false;
    }
  });

  window.addEventListener('beforeunload', clearMarks);

  (async function start() {
    await waitForSelectors();
    try {
      const saved = await chrome.storage.sync.get('instructions');
      state.instructions = saved.instructions || '';
    } catch (error) { /* optional */ }
    buildPanel();
    await scanChat();
  })();
})();
