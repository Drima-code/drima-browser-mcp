/* No all_urls, cookies, webRequest, debugger or arbitrary evaluation permission. */
const approved = new Map();
let port = null;
const allowedHosts = new Set(["wellfound.com", "www.wellfound.com", "chiletrabajos.cl", "www.chiletrabajos.cl"]);
function eligible(url) {
  try { const u = new URL(url); return u.protocol === "https:" && allowedHosts.has(u.hostname); }
  catch (_) { return false; }
}
function origin(url) { return new URL(url).origin; }
function safeUrl(url) { const u = new URL(url); return u.origin + u.pathname; }
async function dispatch(request) {
  if (request.op === "tabs") {
    const tabs = [];
    for (const [id, grantedOrigin] of approved) {
      try {
        const tab = await browser.tabs.get(id);
        if (eligible(tab.url) && origin(tab.url) === grantedOrigin)
          tabs.push({tab_id: String(id), title: tab.title, url: safeUrl(tab.url)});
      } catch (_) { approved.delete(id); }
    }
    return {tabs};
  }
  const id = Number(request.tab_id);
  const tab = await browser.tabs.get(id);
  if (!approved.has(id) || !eligible(tab.url) || approved.get(id) !== origin(tab.url))
    throw new Error("Tab not approved. Click the connector toolbar button on this job-site tab.");
  if (!["snapshot", "act"].includes(request.op)) throw new Error("Unsupported operation");
  // Content code is packaged and fixed; requests are data, never executable JS.
  await browser.tabs.executeScript(id, {file: "content.js"});
  return browser.tabs.sendMessage(id, {drima: true, ...request});
}
function connect() {
  if (port) return;
  port = browser.runtime.connectNative("drima_regular_browser");
  port.onMessage.addListener(async request => {
    const current = port;
    try { current.postMessage({id: request.id, result: await dispatch(request)}); }
    catch (error) { try { current.postMessage({id: request.id, error: error.message}); } catch (_) {} }
  });
  port.onDisconnect.addListener(() => {
    port = null;
    for (const id of approved.keys()) browser.browserAction.setBadgeText({tabId: id, text: "ERR"});
  });
}
browser.browserAction.onClicked.addListener(async tab => {
  if (!eligible(tab.url)) {
    await browser.browserAction.setBadgeText({tabId: tab.id, text: "NO"});
    return;
  }
  if (approved.has(tab.id)) {
    approved.delete(tab.id);
    await browser.browserAction.setBadgeText({tabId: tab.id, text: ""});
  } else {
    approved.set(tab.id, origin(tab.url));
    connect();
    await browser.browserAction.setBadgeText({tabId: tab.id, text: "ON"});
  }
});
browser.tabs.onRemoved.addListener(id => approved.delete(id));
browser.tabs.onUpdated.addListener((id, change) => {
  if (approved.has(id) && change.url && (!eligible(change.url) || origin(change.url) !== approved.get(id))) {
    approved.delete(id);
    browser.browserAction.setBadgeText({tabId: id, text: ""});
  }
});
