// Captioned walkthrough using the app's own captions mode (?captions=1) and title cards.
// The citizen's answers are fed in by a script (no microphone here); the opening card says so.
// Usage: start the server, then  node demo/make_captioned_video.js <out_dir>
const { chromium } = require('playwright');
const out = process.argv[2] || '.';
const BASE = 'http://localhost:8000';
const HINDI = ["जी, मेरा नाम रामवती है", "पति का नाम श्याम लाल है", "मेरी उम्र अड़सठ साल है", "महिला",
  "बाराबंकी जिले में रहती हूँ", "फतेहपुर गाँव", "मेरा नंबर 98765 43210 है", "आधार 1234 5678 9012",
  "पासबुक पर राम वती लिखा है", "रामवती सही है", "SBIN 0001234", "तीस हजार", "हाँ, आधार कार्ड है",
  "गाँव बदलो", "फतेहपुर गाँव", "हाँ जी, सब सही है"];
const TAMIL = ["ஆம், என் பெயர் செல்வி", "கணவர் பெயர் முருகன்", "என் வயது 67"];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: out, size: { width: 1280, height: 800 } } });
  await ctx.addInitScript(() => {
    const queue = JSON.parse(sessionStorage.getItem('__answers') || '[]');
    window.__answers = (a) => { queue.splice(0, queue.length, ...a); };
    class ScriptedRecogniser {          // stands in for the microphone: "hears" the next scripted answer
      start() { setTimeout(() => {
        const t = queue.shift();
        if (t === undefined) { this.onend && this.onend(); return; }
        // interim result first, like real recognition, then the final one
        this.onresult && this.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: t.slice(0, Math.ceil(t.length / 2)) }], { isFinal: false })] });
        setTimeout(() => {
          this.onresult && this.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: t }], { isFinal: true })] });
          this.onend && this.onend();
        }, 900);
      }, 900); }
      abort() {} stop() {}
    }
    for (const k of ['SpeechRecognition', 'webkitSpeechRecognition'])
      Object.defineProperty(window, k, { value: ScriptedRecogniser, configurable: true, writable: true });
    // No speakers here: hold each spoken line on screen for a readable time.
    speechSynthesis.speak = (u) => setTimeout(() => u.onend && u.onend(), Math.min(1600 + u.text.length * 38, 7000));
    speechSynthesis.cancel = () => {};
  });
  const page = await ctx.newPage();

  await page.goto(`${BASE}/web/title.html?sim`);
  await page.waitForTimeout(7000);

  await page.goto(`${BASE}/?captions=1`);
  await page.evaluate((a) => window.__answers(a), HINDI);
  await page.waitForFunction(() => document.querySelector('#warnings').textContent.includes('पासबुक'), null, { timeout: 120000 });
  await page.waitForTimeout(1500);                       // let the mismatch moment sit
  await page.waitForFunction(() => document.querySelector('#status').textContent.includes('confirmed'), null, { timeout: 240000 });
  await page.waitForTimeout(2500);

  const { sid, snap } = await page.evaluate(() => ({ sid: state.session_id, snap: state.snapshot }));
  await page.goto(`${BASE}/web/portal.html?session=${sid}#s=${snap}`);
  await page.waitForFunction(() => document.getElementById('status').textContent.includes('fields filled'), null, { timeout: 60000 });
  await page.waitForTimeout(3000);
  await page.goto(`${BASE}/web/slip.html?session=${sid}#s=${snap}`);
  await page.waitForSelector('.consent');
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
  await page.waitForTimeout(3500);

  await page.goto(`${BASE}/?captions=1`);
  await page.evaluate(() => { stopListening(); });
  await page.evaluate((a) => window.__answers(a), TAMIL);
  await page.click('#langPick button[data-lang="ta"]');
  await page.waitForFunction(() => document.querySelectorAll('#form tr:not(.empty)').length >= 3, null, { timeout: 60000 });
  await page.waitForTimeout(3000);

  await page.goto(`${BASE}/web/title.html?end`);
  await page.waitForTimeout(6000);
  const video = page.video();
  await ctx.close(); await browser.close();
  console.log(await video.path());
})();
