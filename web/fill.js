// Portal autofill: types confirmed values into a portal form using a field map.
// Shared by the practice portal page and the Chrome extension. Never touches captcha, OTP or submit.
async function bkbFill(values, map, { delay = 35, onField } = {}) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const filled = [];
  for (const [key, spec] of Object.entries(map.fields)) {
    if (!(key in values)) continue;
    const el = document.querySelector(spec.selector);
    if (!el || (map.never_touch || []).some((sel) => el.matches(sel))) continue;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    el.focus();
    let v = values[key];
    if (spec.type === "checkbox") {
      el.checked = v === true;
    } else if (el.tagName === "SELECT") {
      el.value = (spec.options && spec.options[v]) || v;
    } else {
      el.value = "";
      for (const ch of String(v)) { el.value += ch; await sleep(delay); }  // visible typing
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    filled.push(key);
    onField && onField(key, el);
    await sleep(delay * 4);
  }
  return filled;
}
if (typeof module !== "undefined") module.exports = { bkbFill };
