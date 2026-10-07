/* No cookies, webRequest, debugger or arbitrary evaluation permission. */
const approved = new Map();
const allSites = {origins: ["http://*/*", "https://*/*"]};
let port = null;
let mode = "manual";
function eligible(tab) {
  try { return !tab.incognito && ["http:", "https:"].includes(new URL(tab.url).protocol); }
  catch (_) { return false; }
}
function origin(url) { return new URL(url).origin; }
function safeUrl(url) { const u = new URL(url); return u.origin + u.pathname; }
async function refreshBadge() {
  await browser.browserAction.setBadgeText({text: mode === "all" ? "ALL" : ""});
  for (const id of approved.keys())
    await browser.browserAction.setBadgeText({tabId: id, text: "ON"});
}
async function allAccess() {
  return mode === "all" && await browser.permissions.contains(allSites);
}
async function allowed(tab) {
  return eligible(tab) && (await allAccess() || approved.get(tab.id) === origin(tab.url));
}
async function dispatch(request) {
  await ready;
  if (request.op === "tabs") {
    const candidates = await allAccess() ? await browser.tabs.query({}) :
      await Promise.all(Array.from(approved.keys(), id => browser.tabs.get(id).catch(() => null)));
    const tabs = [];
    for (const tab of candidates) {
      if (tab && await allowed(tab))
        tabs.push({tab_id: String(tab.id), title: tab.title, url: safeUrl(tab.url)});
    }
    return {mode, tabs};
  }
  const id = Number(request.tab_id);
  const tab = await browser.tabs.get(id);
  if (!await allowed(tab)) throw new Error("Tab not approved. Use the extension popup to grant access.");
  if (!["snapshot", "act"].includes(request.op)) throw new Error("Unsupported operation");
  // Content code is packaged and fixed; requests are data, never executable JS.
  await browser.tabs.executeScript(id, {file: "content.js"});
  const current = await browser.tabs.get(id);
  if (current.url !== tab.url || !await allowed(current)) throw new Error("Tab changed; inspect before retrying.");
  return browser.tabs.sendMessage(id, {drima: true, ...request});
}
function connect() {
  if (port) return;
  const connection = browser.runtime.connectNative("drima_regular_browser");
  port = connection;
  connection.onMessage.addListener(async request => {
    try { connection.postMessage({id: request.id, result: await dispatch(request)}); }
    catch (error) { try { connection.postMessage({id: request.id, error: error.message}); } catch (_) {} }
  });
  connection.onDisconnect.addListener(() => {
    if (port === connection) port = null;
    browser.browserAction.setBadgeText({text: "ERR"});
    for (const id of approved.keys()) browser.browserAction.setBadgeText({tabId: id, text: "ERR"});
  });
}
async function manualMode() {
  mode = "manual"; // Stop broad access before asynchronous cleanup.
  for (const id of approved.keys()) await browser.browserAction.setBadgeText({tabId: id, text: ""});
  approved.clear();
  await browser.storage.local.set({mode});
  await refreshBadge();
}
const ready = (async () => {
  const settings = await browser.storage.local.get("mode");
  if (settings.mode === "all" && await browser.permissions.contains(allSites)) {
    mode = "all";
    connect();
  }
  await refreshBadge();
})();
browser.runtime.onMessage.addListener(async (request, sender) => {
  // Only packaged UI changes access settings; never native MCP/page requests.
  if (sender.id !== browser.runtime.id || sender.url !== browser.runtime.getURL("popup.html"))
    throw new Error("Access settings may only be changed in the extension popup.");
  await ready;
  if (request.ui === "state") {
    const [tab] = await browser.tabs.query({active: true, currentWindow: true});
    return {mode, connected: !!port, eligible: !!tab && eligible(tab),
      approved: !!tab && eligible(tab) && approved.get(tab.id) === origin(tab.url), tabId: tab?.id};
  }
  if (request.ui === "manual") { await manualMode(); return {ok: true}; }
  if (request.ui === "all") {
    if (request.confirmed !== true || !await browser.permissions.contains(allSites))
      throw new Error("Explicit consent and Firefox website permission are required.");
    await manualMode();
    mode = "all";
    await browser.storage.local.set({mode});
    connect();
    await refreshBadge();
    return {ok: true};
  }
  if (request.ui === "toggle") {
    if (mode !== "manual") throw new Error("Switch to manual mode to approve individual tabs.");
    const [tab] = await browser.tabs.query({active: true, currentWindow: true});
    if (!tab || tab.id !== request.tabId || !eligible(tab)) throw new Error("Active tab changed or is unsupported.");
    if (approved.has(tab.id)) {
      approved.delete(tab.id);
      await browser.browserAction.setBadgeText({tabId: tab.id, text: ""});
    } else {
      approved.set(tab.id, origin(tab.url));
      connect();
      await browser.browserAction.setBadgeText({tabId: tab.id, text: "ON"});
    }
    return {ok: true};
  }
  throw new Error("Unsupported UI request");
});
browser.permissions.onRemoved.addListener(async () => {
  if (mode === "all" && !await browser.permissions.contains(allSites)) await manualMode();
});
browser.tabs.onRemoved.addListener(id => approved.delete(id));
browser.tabs.onUpdated.addListener((id, change) => {
  if (approved.has(id) && change.url && origin(change.url) !== approved.get(id)) {
    approved.delete(id);
    browser.browserAction.setBadgeText({tabId: id, text: ""});
  }
});
