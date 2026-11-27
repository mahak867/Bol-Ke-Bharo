# Round 2 submission pack: Bol Ke Bharo

Deadline: **29 Nov 2026**. The submit button turns off at the deadline and late entries are not accepted.
Aim to submit on **28 Nov**, so there is a day for a retake or an upload problem.

The form asks for five things. All five are required.

| # | Field | What to put | Status |
|---|---|---|---|
| 0 | "This build is" | **An extension of my Round 1 idea** | Ready |
| 1 | Pain point being solved | Paste `1_pain_point.txt` | Ready |
| 2 | Impact in real-world India | Paste `2_impact.txt` | Ready |
| 3 | 3-minute screen recording | **Record it yourselves**, by voice (below) | To do |
| 4 | GitHub project link | `https://github.com/mahak867/Bol-Ke-Bharo` (public) | Ready |
| 5 | How you used Wispr Flow to build | Fill in the template below. **Every sentence must be true.** | To do |

---

## 3. The recording (the item most likely to cost you)

The rules say "Show the core flow working end to end **by voice**". Do **not** submit `demo/bol-ke-bharo-demo.mp4`:
its speech input is simulated, which would read as a fake demo. Use it only as a guide.

**Set up (laptop, Chrome, sound on):**

```bash
git pull
pip install -r requirements.txt
```

Optional but recommended, so natural speech works: set your Gemini key in the same terminal (PowerShell):

```bash
$env:GEMINI_API_KEY="your-key"
```

```bash
python -m uvicorn backend.app:app --port 8000
```

Open http://localhost:8000, allow the microphone, keep **Hands-free** ticked. The header says which
engine is running ("offline mode" or "with Gemini").

**Shot list (about 2:45).** One person is the operator, one is the citizen. Record with `Win + Alt + R` (Windows)
or OBS. Rehearse twice. Keep it one continuous take if you can.

| Time | What happens | Citizen says |
|---|---|---|
| 0:00 | Operator, on camera or voice-over: "Lakhs of people get pension forms filled at CSCs. One spelling mismatch and the form is rejected weeks later. This is Bol Ke Bharo." | |
| 0:20 | Click **New application**. The app greets her and asks her name. | "जी, मेरा नाम रामवती है" |
| | | "पति का नाम श्याम लाल है" |
| | | "मेरी उम्र अड़सठ साल है" |
| | | "महिला" · "बाराबंकी जिले में रहती हूँ" · "फतेहपुर गाँव" |
| | | "मेरा नंबर 98765 43210 है" |
| 1:05 | Point at the screen: full Aadhaar spoken, only the last 4 kept. | "आधार 1234 5678 9012" |
| 1:15 | **The key moment:** the red "Name mismatch detected" appears and the app asks which name is right. Pause on it. | "पासबुक पर राम वती लिखा है" |
| 1:30 | Fixed by voice. | "रामवती सही है" |
| | | "SBIN 0001234" · "तीस हजार" · "हाँ, आधार कार्ड है" |
| 1:55 | The app reads everything back, digit by digit. Let a few lines play. | |
| 2:10 | Operator: "गाँव बदलो". The app re-asks only the village. | "फतेहपुर गाँव" |
| 2:20 | Read-back again. | "हाँ जी, सब सही है" |
| 2:25 | "Citizen confirmed". Click **Send to portal**: the practice portal fills itself; captcha, OTP and Submit stay empty. | |
| 2:35 | Click **Print slip for the citizen**: her slip in Hindi, with the time she said "हाँ". | |
| 2:45 | Optional: click **தமிழ்** and answer one or two questions in Tamil. End on the GitHub link. | |

If the app mishears a word, keep going: tap the field and correct it, or say "दोबारा". Recovering on camera
shows the safety net working, which judges value more than a perfect take.

Also show Wispr Flow for a few seconds (for example, dictating the Wispr note or a commit message with it).

---

## 5. Wispr Flow note: template

Replace every [bracket] with what you actually did, and delete any sentence that is not true for your team.
Judges and the sponsor may ask about it at the finale.

> We used Wispr Flow as our keyboard while building Bol Ke Bharo. [We dictated our Round 1 idea, prompt and
> impact answers in Wispr Flow, speaking in Hinglish, then edited them.] [During the build we dictated
> prompts to our AI coding assistant, commit messages and parts of the README.] [One specific example:
> ________________________________.]
>
> Using voice ourselves shaped the product. [What you noticed, e.g. names came out spelled differently,
> numbers came out as words, filler words like "mera naam ... hai".] That is why Bol Ke Bharo strips
> filler words, turns spoken numbers into digits ("तीस हजार" becomes 30000), shows the exact words each
> value came from, and never trusts a value without a spoken read-back. Wispr made the keyboard optional
> for us; we built the same for the people who fill India's forms for everyone else.

---

## Before you press Submit

- [ ] Both team members show Round 1 complete on the dashboard.
- [ ] "This build is": extension of my Round 1 idea.
- [ ] Pain point and impact pasted from the files in this folder (latest version, after `git pull`).
- [ ] Recording: real voices, under 3 minutes, shows the whole flow, uploaded and playable.
- [ ] GitHub link opens in a private/incognito window (it is public).
- [ ] Wispr note: every sentence is true.
- [ ] Submitted on 28 Nov, with a screenshot of the confirmation saved.

## If judges ask (finale prep)

- **"Isn't this just a chatbot?"** No. It listens to a two-person conversation, fills a real form, catches
  rejection causes (name mismatches across scripts, age, missing documents) and fills the portal, with a person
  in control of the final submit.
- **"How accurate is it?"** Measured on synthetic conversations and published in the README, including the weak
  number: the offline fallback gets 42% on chatty held-out wording, which is why free speech goes to Gemini or
  Claude. It fails safely: nothing reaches the portal without the citizen's "हाँ".
- **"Privacy?"** No audio stored, Aadhaar kept as last 4 digits, OTPs never captured, sessions deleted after 30
  minutes. Honest caveat: Chrome's speech recognition sends audio to Google to transcribe it.
- **"Will operators pay?"** They are paid per form, so faster forms and fewer rejections mean more income.
  Next step: a one-week pilot with one or two operators, measuring time per form and rejections.
- **"How does it scale?"** A new form or a new language is a data file: the widow pension form and Tamil were
  added that way.
