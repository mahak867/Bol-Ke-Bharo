# Bol Ke Bharo — Master Plan & Build Playbook
*India Runs on Voice (Scaler × Wispr Flow) · Living document — follow it top to bottom.*

---

## 0. The idea (final, frozen)

**One line:** A voice co-pilot for the people who fill India's forms for others (CSC operators, bank mitras, ASHA workers). It listens to the natural conversation between operator and citizen, fills the application live, catches rejection-causing mistakes, reads everything back to the citizen in their language, and types it into the real portal. A human does the captcha, the OTP, and the final submit.

**Pitch:** "Wispr made the keyboard optional for knowledge workers. We make it optional for the people who fill India's forms for everyone else: conversation in, verified application out."

**Final refinements from the last rethink**
1. **Three layers, one engine.** Built in this order, so the project is demoable at every stage:
   - L1 *Conversation → structured form* (core, must work)
   - L2 *Rejection guard*: cross-field checks plus a follow-up question by voice (the "wow" moment)
   - L3 *Portal autofill extension* (the last mile; it is a bonus if time runs out, never a dependency)
2. **One form, one state, one language pair for the demo.** Default: old-age pension application (e.g. UP), Hindi/Awadhi + Hinglish. Confirm the choice after the CSC visits.
3. **"Haan" consent loop.** Every confirmed field is read back and the citizen answers yes/no by voice. This is the trust and compliance story and the accuracy safety net.
4. **Schema-driven.** Any form = a JSON schema. That is the Round 2 insurance.
5. **Operator economics on screen.** A live timer, "4m 10s vs 22m typical", where the typical time is our own measured number.

**What we never do:** store full Aadhaar, touch OTPs, bypass captchas, auto-submit, or use government logos or branding.

---

## 1. Team roles (lock before the first submission — the team freezes then)

| Role | Owns |
|---|---|
| **A — Builder / Lead** | Backend, engine, deploy, extension |
| **B — Voice & AI** | STT/TTS integration, prompts, extraction accuracy, test set |
| **C — Product & Field** | CSC interviews, audio samples, Round 1 text, demo script, video, slides |

Solo or a team of 2? A takes on B's work; C's work is non-negotiable, so schedule it anyway.

---

## 2. Architecture

```
[Operator phone/PC browser — PWA]
   mic ──► audio chunks (WebSocket) ──► [FastAPI backend]
                                            ├─ STT: Sarvam Saarika (fallback: Whisper / IndicConformer)
                                            ├─ Speaker tag: tap buttons (Operator/Citizen); auto-diarization = bonus
                                            ├─ Extractor LLM: strict JSON per form schema + per-field confidence
                                            ├─ Guard: rule checks (age cutoff, name mismatch, missing docs)
                                            ├─ Dialog manager: next question for missing/low-confidence fields
                                            └─ TTS: Sarvam Bulbul → read-back + follow-ups in citizen's language
   live form view ◄── field updates (WebSocket)
   [Chrome extension] ◄── final JSON ──► fills the real portal fields; human submits
```

**Stack:** Python 3.12 + FastAPI + WebSockets · Vanilla/React PWA · SQLite (session only, auto-purge) · Chrome MV3 extension · Deploy: Render/Railway or a Vercel frontend + one backend box.
**LLM:** Claude (`claude-sonnet-5-5` for low-latency extraction; `claude-opus-5-5` for offline eval/prompt tuning). Any LLM with structured output works; keep it behind one interface.

**Repo layout**
```
bol-ke-bharo/
  backend/
    app.py            # FastAPI + WS
    stt.py tts.py     # provider adapters with fallback
    extractor.py      # schema → prompt → JSON + confidence
    guard.py          # validation rules per schema
    dialog.py         # picks next question / read-back
    privacy.py        # Aadhaar masking, purge timer
  schemas/
    pension_up.json   # fields, types, rules, question templates (hi/en)
  web/                # PWA: record, speaker buttons, live form, timer
  extension/          # MV3: map schema fields → portal DOM selectors
  eval/
    samples/          # consented audio (gitignored if real)
    run_eval.py       # field accuracy, latency report
  docs/ README.md (bilingual) demo.gif
```

**Schema format (the heart of reusability)**
```json
{
  "form_id": "pension_up",
  "fields": [
    {"key": "name", "type": "string", "required": true,
     "ask": {"hi": "Aapka poora naam kya hai?"},
     "readback": {"hi": "Aapka naam {value} hai, sahi?"}},
    {"key": "age", "type": "int", "required": true, "rules": ["age >= 60"]},
    {"key": "aadhaar_last4", "type": "string", "pattern": "^\\d{4}$"},
    {"key": "bank_name_on_passbook", "type": "string"}
  ],
  "cross_rules": [
    {"id": "name_match", "check": "fuzzy(name, bank_name_on_passbook) > 0.85",
     "on_fail": {"hi": "Aadhaar par naam {name} hai, bank mein {bank_name_on_passbook}. Kaunsa sahi hai?"}}
  ]
}
```

---

## 3. Timeline & milestones (today = 12 Nov)

### Phase 1 — Lock & Learn (12–15 Nov)
- [ ] Lock the team on the Wispr/Scaler portal (C)
- [ ] Install Wispr Flow for every member; use it for all writing and coding from now on (all)
- [ ] Join the Discord; read the Round 1 rules the moment they are posted (C)
- [ ] Get API keys: Sarvam, LLM provider (A)
- [ ] **Submit the Round 1 Idea** (50–500 words, built around one named person) (C)
- [ ] 13 Nov: do the Round 1 "Prompt" activity; save every good prompt to `/prompts` (B)

### Phase 2 — Field truth (14–18 Nov) ← highest leverage
- [ ] Visit 3–5 CSC operators or bank mitras (C, + B for audio)
  - Time 3 real applications with a stopwatch
  - Ask: top 3 rejection reasons? forms per day? earnings per form? would you pay ₹199/month?
  - Record 20+ consented conversation samples (noisy, code-mixed)
- [ ] Pick the final demo form + state + language from what you hear
- [ ] Collect one written or WhatsApp letter of intent
- [ ] Write the numbers into `docs/evidence.md` (sources for every figure)

### Phase 3 — Engine L1 (15–20 Nov)
- [ ] STT adapter with fallback; streaming partial transcripts (B)
- [ ] Schema loader + extractor with JSON + confidence (B)
- [ ] PWA: record, speaker buttons, live form panel, timer (A)
- [ ] `run_eval.py` on the samples → **target ≥85% field accuracy, <2s per turn** (B)
- **Done when:** a 60-second conversation fills the form on screen.

### Phase 4 — L2 Guard + read-back (20–24 Nov)
- [ ] Cross-field rules + fuzzy name match (A)
- [ ] Dialog manager: asks about missing or low-confidence fields by voice (B)
- [ ] TTS read-back + yes/no "haan" consent capture (B)
- [ ] Privacy: Aadhaar masking, audio never stored, session purge after 30 minutes (A)
- [ ] 20 Nov: Round 1 "Impact" activity, using the field evidence (C)
- **Done when:** the name mismatch is caught, asked about, and fixed by voice.

### Phase 5 — L3 Extension + polish (24–26 Nov)
- [ ] MV3 extension maps schema keys → portal selectors; fill-only, no submit (A)
- [ ] Test on a saved local copy of the portal page (never hammer the live site)
- [ ] Bilingual README, demo GIF, 90s demo video v1, backup offline recording (C)
- [ ] **Round 2 template frozen:** `schemas/_template.json`, a deploy script, a slide template
- [ ] 26 Nov: Round 1 closes; confirm all three stages are submitted

### Phase 6 — Round 2 (27–29 Nov, 48h playbook)
| Hour | Action |
|---|---|
| 0–2 | Read the problem statement as a team. Map it: who speaks, what structured output, what action. Write the new schema. |
| 2–4 | Decide: does our engine fit directly (just swap the schema) or need a new layer? Cut scope ruthlessly. |
| 4–20 | Build: schema + guard rules + any new output (A/B). C finds 3 real users to test with by phone. |
| 20–24 | **Sleep.** Non-negotiable. |
| 24–36 | Real-user tests, fix the top 3 failures, run the eval and report the numbers. |
| 36–44 | Demo video, README, slides, metrics on screen. |
| 44–48 | Submit early, with a buffer for upload failures. Show Wispr Flow usage in the video. |

### Phase 7 — Finale prep (2–13 Dec, if shortlisted)
- [ ] Pilot with 1–2 operators for a week; collect real usage numbers
- [ ] Rehearse the 3-minute pitch 10+ times; Q&A drill (section 6)
- [ ] Hardware: two phones, a hotspot, the offline demo, printed backup slides
- [ ] Prepare the business slide: price, buyer, number of operators, path to pilots

---

## 4. Demo script (3 minutes)
1. **0:00 Hook:** a photo or name of the real citizen from our visit. "She visited a CSC three times for one form."
2. **0:20 Live:** the operator and "citizen" talk naturally; the form fills itself; the timer runs.
3. **1:10 Wow:** the guard flags "Ramvati vs Ram Wati", asks by voice, the citizen answers, it is fixed.
4. **1:40 Trust:** read-back in dialect, the "haan" consent, Aadhaar masked on screen.
5. **2:00 Last mile:** the extension fills the portal; a human clicks submit.
6. **2:20 Proof:** measured time saved, field accuracy on N samples, the operator's letter of intent.
7. **2:45 Close:** the one-line pitch + "schema swap = any form in India".

---

## 5. Metrics we must show (measured, never invented)
- Time per application: baseline (stopwatch at a CSC) vs ours
- Field accuracy on the held-out samples (%), plus % of errors caught by read-back
- Turn latency (p50/p90)
- Languages and dialects tested
- Operator willingness to pay (number of interviews, quotes)

---

## 6. Q&A drill (memorize)
- **"Isn't this Haqdarshak or Jugalbandi?"** They are human-run or Q&A tools; we turn a live two-person conversation into a checked application in the real portal.
- **"Privacy?"** Audio is never stored, Aadhaar is masked to the last 4 digits, consent is spoken and logged, there is no OTP handling, and sessions are purged.
- **"Why would operators pay?"** They earn per form; faster forms mean more income. We have a letter of intent.
- **"What if the STT is wrong?"** Per-field confidence, voice follow-ups, and a mandatory read-back.
- **"Portal automation is risky."** Fill-only and human-in-the-loop; we never bypass captchas or submit.
- **"Scale?"** One JSON schema per form; we can show a live swap.

---

## 7. Risk register
| Risk | Mitigation |
|---|---|
| Diarization fails live | Speaker tap buttons are the primary design; auto-diarization is a bonus |
| API outage or slow network | STT fallback, hotspot, pre-recorded backup demo |
| Round 2 problem is unrelated | Schema engine + 48h playbook; reuse only the voice loop |
| Weak evidence | Field visits are Phase 2 priority, before polish |
| Rules require something we missed | Re-read the rules on every round launch; update this doc |
| Burnout | A mandatory sleep block in Round 2 |

---

## 8. Compliance checklist (tick before each submission)
- [ ] All members 18+, in India, registered with their Wispr Flow login email
- [ ] Team unchanged since the first submission
- [ ] Wispr Flow visibly used (screenshots/video)
- [ ] Original code; open models and libraries credited in the README
- [ ] No full Aadhaar, OTPs, or raw audio stored; consent captured
- [ ] No government logos or branding; labelled "independent assistant"
- [ ] Demo uses synthetic or consented data only

---

## 9. Daily rhythm
- 10-minute stand-up: yesterday / today / blocker
- End of day: update the checkboxes here, commit, push
- Every change to the idea goes into section 0; if it is not here, we are not doing it.
