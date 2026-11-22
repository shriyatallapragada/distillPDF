const statusEl = document.getElementById('status');
const listEl = document.getElementById('list');
const pickerEl = document.getElementById('picker');
let readyTabId = null;
let lastTab = null;
const NOTEBOOK_ORIGINS = new Set(['https://notebook.google.com', 'https://notebooklm.google.com']);

function note(message) { statusEl.textContent = message; }
function sleep(milliseconds) {
  return new Promise(function (resolve) { setTimeout(resolve, milliseconds); });
}
function isNotebookTab(tab) {
  try {
    const url = new URL(tab.url);
    return NOTEBOOK_ORIGINS.has(url.origin) && /^\/notebook\/[^/]+/.test(url.pathname);
  } catch (error) {
    return false;
  }
}
function hostOf(url) {
  try { return new URL(url).host; } catch (error) { return url || ''; }
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, function (character) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character];
  });
}

function queryTabs(query) {
  return new Promise(function (resolve) { chrome.tabs.query(query, resolve); });
}

function messageTab(tabId, type, value) {
  return new Promise(function (resolve, reject) {
    chrome.tabs.sendMessage(tabId, { type: type, value: value }, function (response) {
      const error = chrome.runtime.lastError;
      if (error) reject(new Error(error.message));
      else resolve(response);
    });
  });
}

async function findNotebookTab() {
  const active = (await queryTabs({ active: true, currentWindow: true }))[0];
  if (isNotebookTab(active)) return active;

  const all = await queryTabs({});
  const matches = (all || []).filter(isNotebookTab);
  matches.sort(function (a, b) { return (b.lastAccessed || 0) - (a.lastAccessed || 0); });
  return matches[0] || null;
}

async function ensurePicker(tab) {
  // A tab may have navigated away since we listed or last used it.
  const current = isNotebookTab(tab) ? await chrome.tabs.get(tab.id).catch(() => null) : null;
  if (!isNotebookTab(current)) {
    throw new Error('Open a NotebookLM chat or choose an existing NotebookLM tab.');
  }
  tab = current;
  // If we already have a live content script in this tab, reuse it.
  if (readyTabId === tab.id) {
    try {
      await messageTab(tab.id, 'NLK_STATUS');
      return tab;
    } catch (error) {
      // Content script is not responding: fall through to re-inject.
      readyTabId = null;
    }
  }
  // Try a quick status probe before injecting (covers tabs where the script
  // is already running but our cached id is stale).
  try {
    await messageTab(tab.id, 'NLK_STATUS');
    readyTabId = tab.id;
    return tab;
  } catch (error) {
    note('Loading the picker into ' + hostOf(tab.url) + '…');
  }
  try {
    await chrome.scripting.insertCSS({
      target: { tabId: tab.id },
      files: ['palette.css', 'content.css']
    });
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['selectors.js', 'converter.js', 'content.js']
    });
  } catch (error) {
    // Scripts may already be present from the manifest content_scripts or an
    // earlier injection. The content script has a double-injection guard, so
    // re-running it is harmless.
    const msg = String(error);
    if (!/duplicate|already|already executing/.test(msg)) {
      throw new Error('Could not inject into this tab: ' + error.message);
    }
  }
  for (let attempt = 0; attempt < 50; attempt++) {
    await sleep(100);
    try {
      await messageTab(tab.id, 'NLK_STATUS');
      readyTabId = tab.id;
      return tab;
    } catch (error) { /* wait for the injected script to start */ }
  }
  throw new Error('The picker did not load. Reload the chat tab and try again.');
}

async function showTabPicker() {
  const all = await queryTabs({});
  const tabs = (all || []).filter(isNotebookTab).sort(function (a, b) {
    return (b.lastAccessed || 0) - (a.lastAccessed || 0);
  });
  const canReload = lastTab && tabs.some(function (tab) { return tab.id === lastTab.id; });
  pickerEl.hidden = false;
  pickerEl.innerHTML = (tabs.length ? '<strong>Choose a NotebookLM tab</strong>' : '') +
    tabs.map(function (tab) {
      return '<button type="button" data-tab-id="' + tab.id + '">' +
        escapeHtml(tab.title || '(untitled)') +
        '<small>' + escapeHtml(hostOf(tab.url)) + '</small></button>';
    }).join('') +
    (canReload ? '<button type="button" data-action="reload">Reload chosen tab and retry</button>' : '') +
    '<button type="button" data-action="open">Open NotebookLM</button>';

  pickerEl.querySelectorAll('[data-tab-id]').forEach(function (button) {
    button.addEventListener('click', function () {
      const id = Number(button.getAttribute('data-tab-id'));
      const tab = tabs.find(function (candidate) { return candidate.id === id; });
      if (tab) connectTo(tab);
    });
  });
  const reload = pickerEl.querySelector('[data-action="reload"]');
  if (reload) reload.addEventListener('click', async function () {
    const tab = await chrome.tabs.get(lastTab.id).catch(() => null);
    if (!isNotebookTab(tab)) {
      lastTab = null;
      refresh();
      return;
    }
    note('Reloading…');
    await chrome.tabs.reload(tab.id).catch(() => {});
    setTimeout(function () { refresh(tab); }, 1500);
  });
  pickerEl.querySelector('[data-action="open"]').addEventListener('click', function () {
    chrome.tabs.create({ url: 'https://notebook.google.com/' });
  });
}

async function connectTo(tab) {
  pickerEl.hidden = true;
  lastTab = tab;
  note('Connecting to ' + hostOf(tab.url) + '…');
  await refresh(tab);
}

async function send(type, value, tab) {
  const target = tab || await findNotebookTab();
  if (!target) {
    throw new Error('Open a NotebookLM chat first.');
  }
  lastTab = target;
  const ready = await ensurePicker(target);
  return messageTab(ready.id, type, value);
}

function render(turns, status) {
  pickerEl.hidden = true;
  note(status || 'Ready.');
  if (!turns || !turns.length) {
    listEl.innerHTML = '<div class="pop-empty">No answers yet. Open a chat and wait for the picker.</div>';
    return;
  }
  listEl.innerHTML = turns.map(function (turn) {
    const preview = turn.preview.replace(/[#*`>\[\]]/g, ' ').replace(/\s+/g, ' ');
    const key = escapeHtml(turn.key);
    return '<label class="pop-item" data-key="' + key + '">' +
      '<input type="checkbox" data-check="' + key + '"' + (turn.selected ? ' checked' : '') + '>' +
      '<span><strong>Answer ' + turn.index + ' · ' + turn.words + ' words</strong>' +
      '<span>' + escapeHtml(preview.slice(0, 72)) + '</span></span></label>';
  }).join('');
}

async function refresh(forceTab) {
  try {
    const status = await send('NLK_STATUS', undefined, forceTab || lastTab);
    const turns = await send('NLK_TURNS', undefined, forceTab || lastTab);
    render(turns, status && status.status);
  } catch (error) {
    note(error.message);
    listEl.replaceChildren();
    await showTabPicker();
  }
}

listEl.addEventListener('change', function (event) {
  const input = event.target.closest('[data-check]');
  if (!input) return;
  // The in-page picker is the source of truth for what gets exported.
  send('NLK_SET_SELECTED', {
    key: input.getAttribute('data-check'),
    value: input.checked
  }, lastTab).then(function () { return refresh(lastTab); }).catch(function (error) {
    note(error.message);
  });
});

/* The helper works in the background; mirror its status into the popup until
   it reports that the two files were saved (or that something went wrong). */
async function followBuild() {
  for (let attempt = 0; attempt < 90; attempt++) {
    await sleep(1000);
    try {
      const response = await send('NLK_STATUS', undefined, lastTab);
      const text = (response && response.status) || '';
      note(text);
      if (/Saved |Build failed|Helper unavailable|Too much text|Pick at least/.test(text)) return;
    } catch (error) {
      return;
    }
  }
}

document.getElementById('build').addEventListener('click', function () {
  send('NLK_BUILD', undefined, lastTab).then(function (result) {
    if (result && result.ok && result.started) {
      note('Building PDF and HTML locally…');
      followBuild();
    } else if (result && result.error) {
      note(result.error);
    }
  }).catch(function (error) { note(error.message); });
});

document.getElementById('options').addEventListener('click', function () {
  chrome.runtime.openOptionsPage();
});

refresh();
