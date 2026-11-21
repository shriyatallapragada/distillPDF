const statusEl = document.getElementById('status');
const selectorsEl = document.getElementById('selectors');
const instructionsEl = document.getElementById('instructions');

function note(message) { statusEl.textContent = message; }

async function defaults() {
  const response = await fetch(chrome.runtime.getURL('selectors.json'));
  return response.json();
}

defaults().then(async function (shipped) {
  const saved = await chrome.storage.sync.get(['selectors', 'instructions']);
  selectorsEl.value = JSON.stringify(saved.selectors || shipped, null, 2);
  instructionsEl.value = saved.instructions || '';
  note('Defaults loaded. Edit only if NotebookLM changes its layout.');
}).catch(function (error) { note('Could not load defaults: ' + error.message); });

document.getElementById('save').addEventListener('click', async function () {
  try {
    const selectors = JSON.parse(selectorsEl.value);
    await chrome.storage.sync.set({
      selectors: selectors,
      instructions: instructionsEl.value
    });
    note('Saved. Reload the chat tab to pick up new selectors.');
  } catch (error) {
    note('Selectors must be valid JSON: ' + error.message);
  }
});

document.getElementById('reset').addEventListener('click', async function () {
  const shipped = await defaults();
  selectorsEl.value = JSON.stringify(shipped, null, 2);
  await chrome.storage.sync.remove('selectors');
  note('Selectors reset. Reload the chat tab.');
});
