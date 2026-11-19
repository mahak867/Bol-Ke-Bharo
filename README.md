# Bol Ke Bharo — बोल के भरो

A voice co-pilot for people who fill forms for others (CSC operators, bank mitras, ASHA workers).
The operator and the citizen talk naturally in Hindi or Hinglish. The form fills itself, the
rejection guard catches mistakes, and everything is read back to the citizen for a spoken "हाँ".

> Independent assistant, not a government service. Audio is never stored, Aadhaar is masked to
> the last 4 digits, OTPs are never handled, and a person always does the final submit.

## Status: L1 + L2 core (engine, guard, read-back, consent)

| Layer | State |
|---|---|
| L1 Conversation → form | ✅ Claude extractor (structured output) + offline rule fallback |
| L2 Rejection guard + read-back + "हाँ" consent | ✅ name mismatch, minimum age, missing documents |
| Speech | Browser Web Speech API (`hi-IN`) for both listening and speaking — no key needed. Sarvam is next. |
| L3 Portal autofill extension | ⏳ not started; `/export` already gives the final JSON |

## Run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # optional; without it the offline rule extractor is used
python -m uvicorn backend.app:app --port 8000
```

Open http://localhost:8000 in **Chrome** (it has Hindi speech recognition). Tap **Operator** or
**Citizen** before each person speaks, or type into the box.

```bash
python -m pytest -q
```

Settings: `BKB_MODEL` (default `claude-sonnet-5-5`), `BKB_EXTRACTOR=rules` to force offline mode.

## How it works

```
mic (browser, hi-IN) ──text──► POST /turn ──► mask Aadhaar ──► extractor (Claude) ──► fields + confidence
                                                                          │
              speak (browser TTS) ◄── next question ◄── dialog ◄── guard (schema rules)
```

Dialog priority each turn: (1) a rejection risk not yet asked about, (2) the next missing field,
(3) a low-confidence value to confirm, (4) a full read-back that needs a spoken "हाँ".
Any change after the read-back requires a new read-back. `/export` is refused until the citizen confirms.

## Adding a form

Every form is one JSON file in `schemas/`: fields (type, pattern, Hindi question and read-back)
and rules (`min`, `must_be_true`, `name_match`). Rules are data, never code.
`schemas/pension_up.json` is a **demo**: check its fields and rules against the real portal and
CSC operators before relying on it.

## Credits

FastAPI, Pydantic, the Anthropic Python SDK, and the browser Web Speech API.
