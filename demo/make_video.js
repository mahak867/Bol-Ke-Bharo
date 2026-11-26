// Automated walkthrough video of the real app, with simulated speech input and burned-in captions.
// Usage: start the server (BKB_EXTRACTOR=rules python -m uvicorn backend.app:app --port 8000), then
//   node demo/make_video.js <out_dir>
const { chromium } = require('playwright');
const out = process.argv[2] || '.';
const W = 1280, H = 800;

const LINES = [
  ["जी, मेरा नाम रामवती है", "Yes, my name is Ramvati"],
  ["पति का नाम श्याम लाल है", "My husband's name is Shyam Lal"],
  ["मेरी उम्र ६८ साल है", "I am 68 years old"],
  ["महिला", "Female"],
  ["बाराबंकी जिले में रहती हूँ", "I live in Barabanki district"],
  ["", ""],                                   // silence: the app retries
  ["फतेहपुर गाँव", "Fatehpur village"],
  ["मेरा नंबर 98765 43210 है", "My number is 98765 43210"],
  ["आधार 1234 5678 9012", "Aadhaar 1234 5678 9012 (full number spoken)"],
  ["पासबुक पर राम वती लिखा है", "The passbook says 'Ram Wati'"],
  ["रामवती सही है", "'Ramvati' is correct"],
  ["दोबारा बोलिए", "Please say that again (voice command)"],
  ["SBIN 0001234", "SBIN 0001234"],
  ["तीस हजार", "Thirty thousand"],
  ["हाँ, आधार कार्ड है", "Yes, I have my Aadhaar card"],
  ["हाँ जी, सब सही है", "Yes, everything is correct"],
];

const card = (title, lines, foot) => `data:text/html;charset=utf-8,` + encodeURIComponent(`<!doctype html><html><body style="margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;padding:0 90px;background:#15140f;color:#f1ede4;font:22px/1.5 system-ui,sans-serif">
<div style="color:#5fbfa3;font-size:20px;letter-spacing:.06em;text-transform:uppercase">Bol Ke Bharo · बोल के भरो</div>
<h1 style="font-size:46px;margin:12px 0 22px">${title}</h1>${lines.map(l => `<p style="margin:6px 0;color:#d8d2c4">${l}</p>`).join('')}
<p style="margin-top:34px;color:#a39d90;font-size:17px">${foot}</p></body></html>`);

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: out, size: { width: W, height: H } } });
  const page = await ctx.newPage();

  await page.goto(card("Speak it. It's filled.", [
    "India has about 5.67 lakh Common Service Centres where operators fill pension forms for citizens who can't.",
    "The citizen speaks Hindi. The portal wants typed English. One spelling mismatch, and the form is rejected weeks later.",
    "Bol Ke Bharo listens to the conversation, fills the form, catches the mismatch, and reads it all back for a spoken “हाँ”.",
  ], "Automated walkthrough of the real app. Speech input is simulated here; captions show what is said."));
  await page.waitForTimeout(9000);

  await ctx.addInitScript((lines) => {
    const queue = lines.slice();
    const cap = () => document.getElementById('__cap');
    const show = (who, hi, en) => { const c = cap(); if (!c) return;
      c.innerHTML = `<b>${who}</b> ${hi}${en ? `<div style="font-size:17px;color:#cfc8b8;margin-top:2px">${en}</div>` : ''}`; c.style.opacity = 1; };
    window.addEventListener('DOMContentLoaded', () => {
      const c = document.createElement('div'); c.id = '__cap';
      c.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);max-width:1100px;background:rgba(15,14,10,.88);color:#fff;padding:10px 18px;border-radius:10px;font:22px/1.4 system-ui,sans-serif;z-index:99;opacity:0;transition:opacity .2s;text-align:center';
      document.body.appendChild(c);
    });
    class FakeSR {
      start() { setTimeout(() => {
        const next = queue.shift();
        if (next === undefined) { this.onend && this.onend(); return; }
        const [hi, en] = next;
        if (!hi) { show('🎙', '(silence…)', 'No answer: the app will retry, then re-ask'); setTimeout(() => this.onend && this.onend(), 2200); return; }
        show('🗣 Citizen:', hi, en);
        setTimeout(() => { this.onresult && this.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: hi }], { isFinal: true })] });
                           this.onend && this.onend(); }, 1800);
      }, 1300); }
      abort() {} stop() {}
    }
    for (const k of ['SpeechRecognition', 'webkitSpeechRecognition'])
      Object.defineProperty(window, k, { value: FakeSR, configurable: true, writable: true });
    speechSynthesis.speak = (u) => { show('🔊 App:', u.text.length > 150 ? u.text.slice(0, 150) + '…' : u.text, '');
      setTimeout(() => u.onend && u.onend(), Math.min(1400 + u.text.length * 40, 7500)); };
    speechSynthesis.cancel = () => {};
  }, LINES);

  await page.goto('http://localhost:8000/');
  // Pause on the mismatch moment so it can be read.
  await page.waitForFunction(() => document.querySelector('#warnings').textContent.includes('पासबुक'), null, { timeout: 120000 });
  await page.waitForTimeout(1500);
  await page.waitForFunction(() => document.querySelector('#status').textContent.includes('confirmed'), null, { timeout: 180000 });
  await page.waitForTimeout(2500);
  await page.click('#exportBtn');
  await page.evaluate(() => document.querySelector('#exportOut').scrollIntoView({ behavior: 'smooth' }));
  await page.waitForTimeout(5000);

  await page.goto(card("Conversation in. Verified application out.", [
    "🎙 Hands-free: listens after every question, retries on silence, “दोबारा” and “रुको” voice commands",
    "⚠ Rejection guard: name mismatch, age below 60, missing age proof — fixed by voice at the counter",
    "🔊 Spoken read-back, digit by digit, and a recorded “हाँ” before anything can be exported",
    "🔒 Full Aadhaar masked to last 4 digits · no audio stored · a person always does the final submit",
    "🧩 Every form is one JSON schema: pension today, scholarships and ration cards next",
  ], "github.com/mahak867/Bol-Ke-Bharo"));
  await page.waitForTimeout(9000);
  const video = page.video();
  await ctx.close(); await browser.close();
  console.log(await video.path());
})();
