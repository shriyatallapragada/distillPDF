const statusEl = document.getElementById('status');
const listEl = document.getElementById('list');
const pickerEl = document.getElementById('picker');
let readyTabId = null;
let lastTab = null;

function note(message) { statusEl.textContent = message; }
function sleep(milliseconds) {
  return new Promise(function (resolve) { setTimeout(resolve, milliseconds); });
}
function isWebTab(tab) { return Boolean(tab && /^https?:/i.test(tab.url || '')); }
function looksLikeChat(tab) {
  return /notebooklm/i.test((tab.url || '') + ' ' + (tab.title || ''));
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
  if (active && isWebTab(active) && looksLikeChat(active)) return active;

  const all = await queryTabs({});
  const matches = (all || []).filter(function (tab) {
    return isWebTab(tab) && looksLikeChat(tab);
  });
  matches.sort(function (a, b) { return (b.lastAccessed || 0) - (a.lastAccessed || 0); });
  return matches[0] || null;
}

async function ensurePicker(tab) {
  if (!isWebTab(tab)) {
    throw new Error('Choose a web tab below, or open a NotebookLM chat first.');
  }
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
  const tabs = (all || []).filter(isWebTab).sort(function (a, b) {
    return (b.lastAccessed || 0) - (a.lastAccessed || 0);
  });
  pickerEl.hidden = false;
  pickerEl.innerHTML = '<strong>Choose the chat tab</strong>' +
    tabs.map(function (tab) {
      return '<button type="button" data-tab-id="' + tab.id + '">' +
        escapeHtml(tab.title || '(untitled)') +
        '<small>' + escapeHtml(hostOf(tab.url)) + '</small></button>';
    }).join('') +
    '<button type="button" data-action="reload">Reload chosen tab and retry</button>';

  pickerEl.querySelectorAll('[data-tab-id]').forEach(function (button) {
    button.addEventListener('click', function () {
      const id = Number(button.getAttribute('data-tab-id'));
      const tab = tabs.find(function (candidate) { return candidate.id === id; });
      if (tab) connectTo(tab);
    });
  });
  pickerEl.querySelector('[data-action="reload"]').addEventListener('click', function () {
    if (lastTab) chrome.tabs.reload(lastTab.id);
    note('Reloading…');
    setTimeout(function () { refresh(lastTab); }, 1500);
  });
}

async function connectTo(tab) {
  pickerEl.hidden = true;
  lastTab = tab;
  note('Connecting to ' + hostOf(tab.url) + '…');
  try {
    await refresh(tab);
  } catch (error) {
    note(error.message);
    showTabPicker();
  }
}

async function send(type, value, tab) {
  const target = tab || await findNotebookTab();
  if (!target) {
    showTabPicker();
    throw new Error('No chat tab found — choose one below.');
  }
  lastTab = target;
  await ensurePicker(target);
  return messageTab(target.id, type, value);
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
    return '<label class="pop-item" data-key="' + turn.key + '">' +
      '<input type="checkbox" data-check="' + turn.key + '"' + (turn.selected ? ' checked' : '') + '>' +
      '<span><strong>Answer ' + turn.index + ' · ' + turn.words + ' words</strong>' +
      '<span>' + preview.slice(0, 72) + '</span></span></label>';
  }).join('');
}

async function refresh(forceTab) {
  try {
    const status = await send('NLK_STATUS', undefined, forceTab || lastTab);
    const turns = await send('NLK_TURNS', undefined, forceTab || lastTab);
    render(turns, status && status.status);
  } catch (error) {
    note(error.message);
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
      note('Building study-notes.pdf and study-notes.html…');
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
