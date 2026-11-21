/* Load the page hooks once, merging any overrides saved in Options. */
(function () {
  window.NLMDF_SELECTORS = {};

  async function load() {
    let defaults = {};
    try {
      const response = await fetch(chrome.runtime.getURL('selectors.json'));
      defaults = await response.json();
    } catch (error) {
      console.warn('[DistillPDF] could not read selectors.json', error);
    }
    let overrides = {};
    try {
      const saved = await chrome.storage.sync.get('selectors');
      overrides = saved.selectors || {};
    } catch (error) {
      /* storage may be unavailable in a fresh profile; defaults still work */
    }
    window.NLMDF_SELECTORS = Object.assign({}, defaults, overrides);
  }

  load();
})();
