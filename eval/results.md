# Offline engine evaluation

Synthetic conversations (written by the team, not real recordings): Devanagari, Hinglish in Latin script and Tamil; digits in both scripts; numbers as words; filler words; Aadhaar/passbook spelling mismatches. The tuned sets were used while building the offline extractor, so they flatter it. Held-out set 1 found one general gap (fixed-format answers inside a sentence), which was fixed; held-out set 2 was written after that and never used for tuning, so it is the fairest number. Real recordings will score lower than both. Run `python -m eval.run_eval` to reproduce.

| Conversations | n | Fields correct | Name mismatches caught | False alarms | Completed to “हाँ” |
|---|---|---|---|---|---|
| Hindi (Devanagari) | 16 | 97.9% | 6/6 | 0 | 100% |
| Hinglish (Latin script) | 12 | 100.0% | 6/6 | 0 | 100% |
| Tamil | 12 | 100.0% | 3/3 | 0 | 100% |
| All tuned sets | 40 | 99.2% | 15/15 | 0 | 100% |
| Held-out set 1 (Hindi, used once to find a gap) | 16 | 97.9% | 6/6 | 0 | 100% |
| **Held-out set 2 (Hindi, never used for tuning)** | 16 | 75.0% | 6/6 | 10 | 100% |

Offline engine, 0.1 ms per turn on this machine. Held-out set 2 fields most often wrong: name (16), bank_account_name (16), guardian_name (16).
