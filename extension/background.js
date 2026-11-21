/* Local bridge: content script -> native messaging host -> Python pipeline.
   The host writes study-notes.pdf / study-notes.html to Downloads and returns
   only their paths, so large self-contained HTML never crosses the 1 MB
   native-messaging response limit. */
const HOST = 'com.distillpdf.host';

function callHost(payload) {
  return new Promise(function (resolve) {
    let port;
    let settled = false;
    try {
      port = chrome.runtime.connectNative(HOST);
    } catch (error) {
      const detail = error && error.message ? error.message : String(error);
      resolve({
        ok: false,
        error: 'Local helper is not installed (' + detail + '). Run the project installer once.'
      });
      return;
    }

    // 5 minutes: large PDFs with many formulas and diagrams can take a while.
    const timer = setTimeout(function () {
      if (settled) return;
      settled = true;
      try { port.disconnect(); } catch (error) { /* ignore */ }
      resolve({ ok: false, error: 'The local helper took too long. Check whether Chrome is allowed to run it.' });
    }, 300000);

    port.onMessage.addListener(function (message) {
      // Heartbeat frames keep this worker alive during a long render; the
      // first real result is the only reply the caller cares about.
      if (message && message.type === 'progress') return;
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try { port.disconnect(); } catch (error) { /* ignore */ }
      resolve(message && typeof message === 'object' ? message : { ok: false, error: 'Unexpected helper response.' });
    });
    port.onDisconnect.addListener(function () {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const detail = chrome.runtime.lastError && chrome.runtime.lastError.message;
      resolve({
        ok: false,
        error: detail
          ? 'Local helper: ' + detail
          : 'Local helper closed before answering. Run the project installer once.'
      });
    });
    port.postMessage({ type: 'build', chat: payload });
  });
}

chrome.runtime.onMessage.addListener(function (message, sender, reply) {
  if (!message || message.type !== 'MAKE_PDF') return false;
  callHost(message.payload).then(reply).catch(function (error) {
    reply({ ok: false, error: String(error && error.message || error) });
  });
  return true;
});
