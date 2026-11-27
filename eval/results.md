# Offline engine evaluation

Synthetic conversations (written by the team, not real recordings): Devanagari, Hinglish in Latin script and Tamil; digits in both scripts; numbers as words; filler words; Aadhaar/passbook spelling mismatches. The tuned sets were used while building the offline extractor, so they flatter it. Held-out set 1 found one general gap (fixed-format answers inside a sentence), which was fixed; set 2 found another (everyday words like बेटा, घरवाले), which was fixed in general form. Set 3 was written after both fixes, in a different style, half in Tamil, and never used for tuning, so it is the fairest number. Real recordings will score lower than both. Run `python -m eval.run_eval` to reproduce.

| Conversations | n | Fields correct | Name mismatches caught | False alarms | Completed to “हाँ” |
|---|---|---|---|---|---|
| Hindi (Devanagari) | 16 | 100.0% | 6/6 | 0 | 100% |
| Hinglish (Latin script) | 12 | 100.0% | 6/6 | 0 | 100% |
| Tamil | 12 | 100.0% | 3/3 | 0 | 100% |
| All tuned sets | 40 | 100.0% | 15/15 | 0 | 100% |
| Held-out set 1 (Hindi, used once to find a gap) | 16 | 100.0% | 6/6 | 0 | 100% |
| Held-out set 2 (Hindi, used once to find a gap) | 16 | 100.0% | 6/6 | 0 | 100% |
| **Held-out set 3 (Hindi + Tamil, never used for tuning)** | 20 | 41.7% | 0/2 | 10 | 0% |

Offline engine, 0.1 ms per turn on this machine. Held-out set 3 fields most often wrong: bank_account_name (20), has_age_proof (20), district (20), village (20), annual_income (20), gender (10), guardian_name (10), aadhaar_last4 (10), name (10).
