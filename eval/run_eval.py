"""Measure the offline engine on scripted conversations.

The conversations are synthetic (written by us, not recorded from real people) but vary the things
real speech recognition produces: Devanagari and Latin script, Tamil, digits in both scripts, numbers
as words, filler words ("जी, मेरा नाम ... है"), and Aadhaar/passbook name mismatches.

    python -m eval.run_eval            # prints a table and writes eval/results.md
"""
import random
import time
from pathlib import Path

from backend.dialog import SessionStore
from backend.extractor import RuleExtractor
from backend.schema import load_schema

random.seed(7)
HI_NAMES = [("रामवती", "राम वती"), ("सुनीता देवी", "सुनीता"), ("कमला", "कमला देवी"), ("शांति", "शान्ति"),
            ("गीता", "गीता"), ("उर्मिला", "उर्मिला"), ("सावित्री", "सावित्री"), ("लक्ष्मी", "लक्ष्मी")]
HINGLISH_NAMES = [("Ramvati", "Ram Wati"), ("Sunita Devi", "Sunita Devi"), ("Kamla", "Kamla"), ("Geeta", "Gita")]
TA_NAMES = [("செல்வி", "செல்வி"), ("லட்சுமி", "லக்ஷ்மி"), ("பார்வதி", "பார்வதி"), ("முத்தம்மா", "முத்தம்மா")]
HUSBANDS = {"hi": ["श्याम लाल", "रमेश", "हरि प्रसाद"], "lat": ["Shyam Lal", "Ramesh"], "ta": ["முருகன்", "கண்ணன்"]}
PLACES = {"hi": [("बाराबंकी", "फतेहपुर"), ("लखनऊ", "रामपुर"), ("सीतापुर", "मिश्रिख")],
          "lat": [("Barabanki", "Fatehpur"), ("Lucknow", "Rampur")], "ta": [("மதுரை", "மேலூர்"), ("சேலம்", "ஆத்தூர்")]}
AGE_WORDS = {68: "अड़सठ", 70: "सत्तर", 75: "पचहत्तर", 80: "अस्सी", 65: "पैंसठ"}
HINDI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def conversation(style: str, i: int):
    """Returns (lang, citizen lines in order of the questions, expected values)."""
    age = random.choice(list(AGE_WORDS))
    mobile = random.choice("6789") + "".join(random.choice("0123456789") for _ in range(9))
    last4 = "".join(random.choice("0123456789") for _ in range(4))
    income = random.choice([20000, 30000, 40000])
    if style == "ta":
        name, bank = TA_NAMES[i % len(TA_NAMES)]
        husband, (district, village) = random.choice(HUSBANDS["ta"]), random.choice(PLACES["ta"])
        lines = [f"ஆம், என் பெயர் {name}", f"கணவர் பெயர் {husband}", f"என் வயது {age}", "பெண்",
                 f"{district} மாவட்டம்", f"{village} கிராமம்", f"என் நம்பர் {mobile[:5]} {mobile[5:]}",
                 f"ஆதார் 1234 5678 {last4}", f"பாஸ்புக்கில் {bank}", "SBIN 0001234", f"{income}", "ஆம், ஆதார் இருக்கு"]
        return "ta", lines, name, bank, dict(guardian_name=husband, age=age, district=district, village=village,
                                              mobile=mobile, aadhaar_last4=last4, income=income)
    if style == "lat":
        name, bank = HINGLISH_NAMES[i % len(HINGLISH_NAMES)]
        husband, (district, village) = random.choice(HUSBANDS["lat"]), random.choice(PLACES["lat"])
        lines = [f"ji, mera naam {name} hai", f"pati ka naam {husband} hai", f"meri umar {age} saal hai", "mahila",
                 f"{district} jila", f"{village} gaon", f"mera number {mobile} hai", f"aadhaar 1234 5678 {last4}",
                 f"passbook par {bank} likha hai", "SBIN 0001234", f"{income // 1000} hazaar", "haan, aadhaar card hai"]
        return "hi", lines, name, bank, dict(guardian_name=husband, age=age, district=district, village=village,
                                              mobile=mobile, aadhaar_last4=last4, income=income)
    name, bank = HI_NAMES[i % len(HI_NAMES)]
    husband, (district, village) = random.choice(HUSBANDS["hi"]), random.choice(PLACES["hi"])
    age_said = random.choice([f"{age} साल", f"{str(age).translate(HINDI_DIGITS)} साल", f"{AGE_WORDS[age]} साल"])
    income_said = random.choice([f"{income // 1000} हजार", f"{income}", {20000: "बीस हजार", 30000: "तीस हजार", 40000: "चालीस हजार"}[income]])
    lines = [f"जी, मेरा नाम {name} है", f"पति का नाम {husband} है", f"मेरी उम्र {age_said} है", "महिला",
             f"{district} जिले में रहती हूँ", f"{village} गाँव", f"मेरा नंबर {mobile[:5]} {mobile[5:]} है",
             f"आधार 1234 5678 {last4}", f"पासबुक पर {bank} लिखा है", "SBIN 0001234", income_said, "हाँ, आधार कार्ड है"]
    return "hi", lines, name, bank, dict(guardian_name=husband, age=age, district=district, village=village,
                                          mobile=mobile, aadhaar_last4=last4, income=income)


def heldout(i: int):
    """Different wording, written after the extractor was tuned and NOT used to tune it."""
    name, bank = HI_NAMES[i % len(HI_NAMES)]
    husband, (district, village) = random.choice(HUSBANDS["hi"]), random.choice(PLACES["hi"])
    age = random.choice(list(AGE_WORDS))
    mobile = random.choice("6789") + "".join(random.choice("0123456789") for _ in range(9))
    last4 = "".join(random.choice("0123456789") for _ in range(4))
    lines = [f"{name} नाम है मेरा", f"मेरे पति {husband}", f"{AGE_WORDS[age]} की हो गई हूँ", "औरत हूँ",
             f"जिला {district}", f"गाँव का नाम {village} है", f"नंबर है {mobile}", f"आधार के आख़िरी चार {last4}",
             f"बैंक में {bank} लिखा है", "IFSC है SBIN0001234", "साल का करीब तीस हजार", "हाँ है"]
    return "hi", lines, name, bank, dict(guardian_name=husband, age=age, district=district, village=village,
                                          mobile=mobile, aadhaar_last4=last4, income=30000)


def heldout2(i: int):
    """Second held-out set, written after the fix prompted by the first one. Not used to tune anything."""
    name, bank = HI_NAMES[(i + 3) % len(HI_NAMES)]
    husband, (district, village) = random.choice(HUSBANDS["hi"]), random.choice(PLACES["hi"])
    age = random.choice(list(AGE_WORDS))
    mobile = random.choice("6789") + "".join(random.choice("0123456789") for _ in range(9))
    last4 = "".join(random.choice("0123456789") for _ in range(4))
    lines = [f"हाँ बेटा, {name}", f"घरवाले का नाम {husband} था", f"उम्र {age} बरस", "मैं महिला हूँ",
             f"{district} से हूँ", f"{village} में रहते हैं", f"{mobile[:3]} {mobile[3:6]} {mobile[6:]}",
             f"{last4} है आख़िरी", f"खाते में नाम {bank}", "sbin0001234", "तीस हज़ार के आसपास", "जी हाँ, है"]
    return "hi", lines, name, bank, dict(guardian_name=husband, age=age, district=district, village=village,
                                          mobile=mobile, aadhaar_last4=last4, income=30000)


def heldout3(i: int):
    """Third held-out set, written after the everyday-speech words were added. Half Hindi, half Tamil.
    Never used for tuning: its score is reported as it comes out."""
    age = random.choice(list(AGE_WORDS))
    mobile = random.choice("6789") + "".join(random.choice("0123456789") for _ in range(9))
    last4 = "".join(random.choice("0123456789") for _ in range(4))
    if i % 2:
        name, bank = TA_NAMES[(i + 1) % len(TA_NAMES)]
        husband, (district, village) = random.choice(HUSBANDS["ta"]), random.choice(PLACES["ta"])
        lines = [f"சார், {name} தான் என் பேரு", f"வீட்டுக்காரர் {husband}", f"{age} வயசு ஆகுது", "நான் பெண்",
                 f"{district} பக்கம்", f"{village} தான் எங்க ஊரு", f"நம்பர் {mobile}", f"கடைசி நாலு {last4}",
                 f"பாஸ்புக்ல {bank} னு இருக்கு", "SBIN0001234 சார்", "முப்பதாயிரம் ரூபாய்", "ஆமா இருக்கு"]
        return "ta", lines, name, bank, dict(guardian_name=husband, age=age, district=district, village=village,
                                              mobile=mobile, aadhaar_last4=last4, income=30000)
    name, bank = HI_NAMES[(i + 5) % len(HI_NAMES)]
    husband, (district, village) = random.choice(HUSBANDS["hi"]), random.choice(PLACES["hi"])
    lines = [f"अरे साहब, नाम {name} है", f"उनका नाम {husband} है", f"अभी {age} की हूँ", "लेडीज़",
             f"{district} district", f"हमारा गाँव {village}", f"मोबाइल {mobile} है जी", f"last four {last4}",
             f"बैंक वाली कॉपी में {bank}", f"IFSC SBIN0001234", "पूरे साल में तीस हजार", "जी, आधार है"]
    return "hi", lines, name, bank, dict(guardian_name=husband, age=age, district=district, village=village,
                                          mobile=mobile, aadhaar_last4=last4, income=30000)


def run_one(style: str, i: int) -> dict:
    lang, lines, name, bank, exp = (heldout(i) if style == "held" else heldout2(i) if style == "held2" else heldout3(i) if style == "held3"
                                    else conversation(style, i))
    s = SessionStore().create(load_schema("pension_up"), lang)
    ex, turns, mismatch_flagged = RuleExtractor(), 0, False
    for line in lines:
        s.add_turn("citizen", line, ex)
        turns += 1
        if any(w["id"] == "name_match" for w in s.warnings()):
            mismatch_flagged = True
            s.add_turn("citizen", f"{name} सही है" if lang == "hi" else f"{name} சரி", ex)   # resolve by voice
            turns += 1
    expected = {"name": name, "bank_account_name": name, "gender": "female", "ifsc": "SBIN0001234",
                "has_age_proof": True, "guardian_name": exp["guardian_name"], "age": exp["age"],
                "district": exp["district"], "village": exp["village"], "mobile": exp["mobile"],
                "aadhaar_last4": exp["aadhaar_last4"], "annual_income": exp["income"]}
    from backend.names import to_latin
    def same(k, got, want):   # names count as correct when the portal spelling matches (शांति == शान्ति)
        return to_latin(got) == to_latin(want) if isinstance(want, str) and got is not None else got == want
    correct = {k: same(k, s.values.get(k), v) for k, v in expected.items()}
    yes = "हाँ जी, सब सही है" if lang == "hi" else "ஆம், எல்லாம் சரி"
    s.add_turn("citizen", yes, ex)
    turns += 1
    from backend.names import compare
    should_flag = compare(name, bank)["verdict"] != "same"
    return {"style": style, "correct": correct, "turns": turns, "done": s.phase == "done",
            "should_flag": should_flag, "flagged": mismatch_flagged}


def main():
    styles = ["hi"] * 16 + ["lat"] * 12 + ["ta"] * 12 + ["held"] * 16 + ["held2"] * 16 + ["held3"] * 20
    t0 = time.perf_counter()
    results = [run_one(st, i) for i, st in enumerate(styles)]
    ms = (time.perf_counter() - t0) * 1000 / sum(r["turns"] for r in results)
    rows = []
    groups = [("Hindi (Devanagari)", {"hi"}), ("Hinglish (Latin script)", {"lat"}), ("Tamil", {"ta"}),
              ("All tuned sets", {"hi", "lat", "ta"}), ("Held-out set 1 (Hindi, used once to find a gap)", {"held"}),
              ("Held-out set 2 (Hindi, used once to find a gap)", {"held2"}),
              ("**Held-out set 3 (Hindi + Tamil, never used for tuning)**", {"held3"})]
    for label, sel in groups:
        rs = [r for r in results if r["style"] in sel]
        fields = [ok for r in rs for ok in r["correct"].values()]
        flag_cases = [r for r in rs if r["should_flag"]]
        rows.append((label, len(rs), 100 * sum(fields) / len(fields),
                     f"{sum(r['flagged'] for r in flag_cases)}/{len(flag_cases)}",
                     sum(r["flagged"] and not r["should_flag"] for r in rs),
                     100 * sum(r["done"] for r in rs) / len(rs)))
    misses = {}
    for r in results:
        if r["style"] != "held3":
            continue
        for k, ok in r["correct"].items():
            if not ok:
                misses[k] = misses.get(k, 0) + 1
    out = ["| Conversations | n | Fields correct | Name mismatches caught | False alarms | Completed to “हाँ” |",
           "|---|---|---|---|---|---|"]
    out += [f"| {a} | {n} | {acc:.1f}% | {caught} | {fa} | {done:.0f}% |" for a, n, acc, caught, fa, done in rows]
    out.append(f"\nOffline engine, {ms:.1f} ms per turn on this machine. Held-out set 3 fields most often wrong: "
               + (", ".join(f"{k} ({v})" for k, v in sorted(misses.items(), key=lambda x: -x[1])) or "none") + ".")
    text = "\n".join(out)
    print(text)
    (Path(__file__).parent / "results.md").write_text(
        "# Offline engine evaluation\n\nSynthetic conversations (written by the team, not real recordings): "
        "Devanagari, Hinglish in Latin script and Tamil; digits in both scripts; numbers as words; filler words; "
        "Aadhaar/passbook spelling mismatches. The tuned sets were used while building the offline extractor, "
        "so they flatter it. Held-out set 1 found one general gap (fixed-format answers inside a sentence), "
        "which was fixed; set 2 found another (everyday words like बेटा, घरवाले), which was fixed in general form. "
        "Set 3 was written after both fixes, in a different style, half in Tamil, and never used for tuning, "
        "so it is the fairest number. "
        "Real recordings will score lower than both. Run `python -m eval.run_eval` to reproduce.\n\n" + text + "\n")


if __name__ == "__main__":
    main()
