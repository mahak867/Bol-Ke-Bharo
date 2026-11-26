// Fetch the latest confirmed application and the field map, then fill the active tab.
const out = document.getElementById("out");
const base = document.getElementById("base");
chrome.storage.local.get("base", (v) => { if (v.base) base.value = v.base; });
document.getElementById("fill").onclick = async () => {
  chrome.storage.local.set({ base: base.value });
  try {
    const [app, map] = await Promise.all([
      fetch(`${base.value}/api/latest-confirmed`).then((r) => { if (!r.ok) throw new Error("No confirmed application yet"); return r.json(); }),
      fetch(`${base.value}/web/portal-map.json`).then((r) => r.json()),
    ]);
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["fill.js"] });
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id }, args: [app.portal_values, map],
      func: (values, map) => bkbFill(values, map),
    });
    out.textContent = `Filled ${result.length} fields. Check them, then do the captcha, OTP and submit yourself.`;
  } catch (e) { out.style.color = "#a8321f"; out.textContent = e.message; }
};
