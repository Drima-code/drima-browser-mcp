const $ = id => document.getElementById(id);
const allSites = {origins: ["http://*/*", "https://*/*"]};
let state;
async function render() {
  state = await browser.runtime.sendMessage({ui: "state"});
  $("status").textContent = `Mode: ${state.mode === "all" ? "automatic (all website tabs)" : "manual approval"}. Native host: ${state.connected ? "connected" : "not connected"}.`;
  $("toggle").disabled = state.mode !== "manual" || !state.eligible;
  $("toggle").textContent = state.approved ? "Revoke this tab" : "Approve this tab";
  $("all").disabled = state.mode === "all" || !$("consent").checked;
}
function fail(error) { $("error").textContent = error.message; }
$("consent").addEventListener("change", () => {
  $("all").disabled = !$("consent").checked || state?.mode === "all";
});
$("toggle").addEventListener("click", async () => {
  try { await browser.runtime.sendMessage({ui: "toggle", tabId: state.tabId}); await render(); }
  catch (error) { fail(error); }
});
$("manual").addEventListener("click", async () => {
  try {
    await browser.runtime.sendMessage({ui: "manual"});
    await browser.permissions.remove(allSites);
    $("consent").checked = false;
    await render();
  } catch (error) { fail(error); }
});
$("all").addEventListener("click", async () => {
  if (!$("consent").checked) return;
  try {
    // Directly in the user click handler, before any other awaited work.
    const granted = await browser.permissions.request(allSites);
    if (!granted) throw new Error("Website access denied; automatic mode was not enabled.");
    await browser.runtime.sendMessage({ui: "all", confirmed: true});
    await render();
  } catch (error) { fail(error); }
});
render().catch(fail);
