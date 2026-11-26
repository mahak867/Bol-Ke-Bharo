const { chromium } = require('playwright');
const ANSWERS = ["", "जी, मेरा नाम रामवती है","दोबारा बोलिए","पति का नाम श्याम लाल है","मेरी उम्र ६८ साल है","महिला","बाराबंकी जिले में रहती हूँ","फतेहपुर गाँव","मेरा नंबर 98765 43210 है","आधार 1234 5678 9012","पासबुक पर राम वती लिखा है","रामवती सही है","SBIN 0001234","तीस हजार","हाँ, आधार कार्ड है","हाँ जी, सब सही है"];
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); 
  await p.addInitScript((answers) => {
    window.__heard = [];
    // Fake recogniser: each start() "hears" the next scripted answer ("" = silence).
    class FakeSR { start() {  const t = answers.shift(); setTimeout(() => {
        if (t === undefined) { this.onend && this.onend(); return; }
        if (t) { window.__heard.push(t); this.onresult && this.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: t }], { isFinal: true })] }); }
        this.onend && this.onend(); }, 120); }
      abort() {} stop() {} }
    for (const k of ['SpeechRecognition','webkitSpeechRecognition']) Object.defineProperty(window, k, { value: FakeSR, configurable: true, writable: true });
    // Fast fake TTS so the loop runs quickly.
    window.speechSynthesis.speak = (u) => { setTimeout(() => u.onend && u.onend(), 50); };
    window.speechSynthesis.cancel = () => {};
  }, ANSWERS);
  await p.goto('http://localhost:8000/');
  await p.waitForFunction(() => document.querySelector('#status').textContent.includes('confirmed'), null, { timeout: 30000 }).catch(() => {});
  console.log('status:', await p.textContent('#status'));
  console.log('heard:', (await p.evaluate(() => window.__heard)).length, 'errors:', errs);
  console.log('log:', (await p.$$eval('.log div', d => d.map(x => x.textContent))).slice(0, 4));
  await b.close();
})();
