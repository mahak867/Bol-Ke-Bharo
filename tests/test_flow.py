from fastapi.testclient import TestClient

from backend import guard
from backend.dialog import SessionStore
from backend.extractor import Extraction, FieldUpdate, RuleExtractor
from backend.privacy import mask_aadhaar
from backend.schema import load_schema


class Scripted:
    """Stands in for Claude: returns a fixed extraction per turn."""
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.seen = []

    def extract(self, schema, state, speaker, segment, recent, expected=None):
        self.seen.append(segment)
        return self.outputs.pop(0)


def ups(consent=None, **kv):
    return Extraction(updates=[FieldUpdate(key=k, value=str(v), confidence=0.95, evidence=str(v)) for k, v in kv.items()],
                      is_correction=False, consent=consent)


FULL = dict(name="Ramvati", guardian_name="Shiv Prasad", age=68, gender="female", district="Barabanki",
            village="Fatehpur", mobile="9876543210", aadhaar_last4="9012", ifsc="SBIN0001234",
            annual_income=30000, has_age_proof="true")


def test_name_mismatch_is_caught_then_fixed_then_consent():
    s = SessionStore().create(load_schema("pension_up"))
    ex = Scripted([
        ups(**FULL),
        ups(bank_account_name="Ram Wati"),        # passbook spelling differs
        # "Ramvati sahi hai" is resolved by the name-choice step, without the extractor
        ups(consent="yes"),                        # "haan" to the read-back
    ])
    s.add_turn("citizen", "…", ex)
    assert s.missing() == ["bank_account_name"]

    s.add_turn("citizen", "passbook mein Ram Wati likha hai", ex)
    assert "Ram Wati" in s.say and "Ramvati" in s.say      # guard asks which is right
    assert [w["id"] for w in guard.check(s.schema, s.values)] == ["name_match"]

    s.add_turn("citizen", "Ramvati sahi hai", ex)
    assert s.phase == "readback" and "हाँ या ना" in s.say
    assert "9 0 1 2" in s.say and "1234" not in s.say      # only last 4, read digit by digit

    s.add_turn("citizen", "haan", ex)
    assert s.phase == "done"
    out = s.export()
    assert out["values"]["bank_account_name"] == "Ramvati" and out["warnings"] == []


def test_export_blocked_without_consent():
    s = SessionStore().create(load_schema("pension_up"))
    s.add_turn("citizen", "x", Scripted([ups(**FULL, bank_account_name="Ramvati")]))
    assert s.phase == "readback"
    try:
        s.export()
        assert False
    except PermissionError:
        pass


def test_no_to_readback_reopens_and_change_needs_new_consent():
    s = SessionStore().create(load_schema("pension_up"))
    ex = Scripted([ups(**FULL, bank_account_name="Ramvati"), ups(consent="no"), ups(age=72), ups(consent="yes")])
    s.add_turn("citizen", "x", ex)
    s.add_turn("citizen", "nahi", ex)
    assert s.phase in ("collect", "readback")
    s.add_turn("citizen", "umar 72 hai", ex)
    assert s.phase == "readback" and "72" in s.say
    s.add_turn("citizen", "haan", ex)
    assert s.phase == "done" and s.values["age"] == 72


def test_underage_flagged_once():
    s = SessionStore().create(load_schema("pension_up"))
    ex = Scripted([ups(age=55), ups(name="Ramvati")])
    s.add_turn("citizen", "55 saal", ex)
    assert "60" in s.say
    s.add_turn("citizen", "Ramvati", ex)
    assert "60 साल होना" not in s.say          # not repeated while value unchanged


def test_low_confidence_is_confirmed():
    s = SessionStore().create(load_schema("pension_up"))
    full = {k: v for k, v in FULL.items()} | {"bank_account_name": "Ramvati"}
    ex = Scripted([
        Extraction(updates=[FieldUpdate(key=k, value=str(v), confidence=0.5 if k == "village" else 0.95, evidence="")
                            for k, v in full.items()], is_correction=False),
        ups(consent="yes"),
    ])
    s.add_turn("citizen", "x", ex)
    assert s.pending_confirm == "village" and "Fatehpur" in s.say
    s.add_turn("citizen", "haan", ex)
    assert s.phase == "readback"


def test_invalid_values_rejected():
    s = SessionStore().create(load_schema("pension_up"))
    s.add_turn("citizen", "x", Scripted([ups(mobile="12345", ifsc="sbin 0001234")]))
    assert "mobile" not in s.values and s.values["ifsc"] == "SBIN0001234"


def test_privacy_masks_full_aadhaar_before_extractor():
    assert mask_aadhaar("mera aadhaar 1234 5678 9012 hai") == "mera aadhaar XXXX XXXX 9012 hai"
    s = SessionStore().create(load_schema("pension_up"))
    ex = Scripted([ups()])
    s.add_turn("citizen", "1234-5678-9012", ex)
    assert "1234" not in ex.seen[0] and "9012" in ex.seen[0]


def test_rule_extractor():
    r = RuleExtractor().extract(load_schema("pension_up"), {}, "citizen", "haan ji, meri umar 68 saal hai", [])
    assert r.consent == "yes" and r.updates[0].value == "68"


def test_api_roundtrip(monkeypatch):
    monkeypatch.setenv("BKB_EXTRACTOR", "rules")
    import importlib
    import backend.app as appmod
    importlib.reload(appmod)
    c = TestClient(appmod.app)
    s = c.post("/api/sessions", json={"form_id": "pension_up"}).json()
    s = c.post(f"/api/sessions/{s['session_id']}/turn", json={"speaker": "citizen", "text": "70 saal"}).json()
    assert next(f for f in s["fields"] if f["key"] == "age")["value"] == "70"
    r = c.post(f"/api/sessions/{s['session_id']}/edit", json={"key": "name", "value": "Ramvati"})
    assert r.status_code == 200
    assert c.get(f"/api/sessions/{s['session_id']}/export").status_code == 409
    assert c.post("/api/sessions", json={"form_id": "../etc"}).status_code == 404
    assert c.get("/").status_code == 200


def test_greeting_and_garbled_repeat():
    s = SessionStore().create(load_schema("pension_up"))
    assert s.say.startswith("नमस्ते") and "नाम" in s.say
    ex = Scripted([ups(), ups()])
    s.add_turn("citizen", "khhshh", ex)
    assert s.say.startswith("माफ़ कीजिए") and "नाम" in s.say
    s.add_turn("citizen", "hmm", ex)
    assert s.say.count("माफ़ कीजिए") == 1      # no stacking of apologies


def test_full_spoken_conversation_offline_devanagari():
    """What Chrome's hi-IN recogniser actually returns: Devanagari words, often with digits."""
    s = SessionStore().create(load_schema("pension_up"))
    ex = RuleExtractor()
    for said in ["जी, मेरा नाम रामवती है", "पति का नाम श्याम लाल है", "मेरी उम्र ६८ साल है", "महिला",
                 "बाराबंकी जिले में रहती हूँ", "फतेहपुर गाँव", "मेरा नंबर 98765 43210 है", "आधार 1234 5678 9012",
                 "पासबुक पर राम वती लिखा है"]:
        s.add_turn("citizen", said, ex)
    assert s.values["name"] == "रामवती" and s.values["bank_account_name"] == "राम वती"
    assert "आधार वाला नाम सही है" in s.say               # mismatch caught
    s.add_turn("citizen", "रामवती सही है", ex)
    assert s.values["bank_account_name"] == "रामवती"
    for said in ["SBIN 0001234", "तीस हजार", "हाँ, आधार कार्ड है"]:
        s.add_turn("citizen", said, ex)
    assert s.values["annual_income"] == 30000 and s.values["has_age_proof"] is True
    assert s.values["guardian_name"] == "श्याम लाल" and s.values["district"] == "बाराबंकी"
    assert s.phase == "readback", s.say
    s.add_turn("citizen", "हाँ जी, सब सही है", ex)
    assert s.phase == "done"
    assert s.export()["values"]["aadhaar_last4"] == "9012"


# ---------- name matching across scripts and spellings ----------
from backend import names


def test_transliteration():
    assert [names.to_latin(n) for n in ["रामवती", "श्याम लाल", "अंजलि", "राजेन्द्र", "कृष्णा"]] == \
        ["Ramvati", "Shyam Lal", "Anjali", "Rajendra", "Krishna"]


def test_compare_verdicts():
    assert names.compare("रामवती", "Ramvati")["verdict"] == "same"          # script only
    assert names.compare("Ramvati", "Ram Wati")["verdict"] == "spelling"    # rejection risk
    assert names.compare("Laxmi", "लक्ष्मी")["verdict"] == "spelling"
    assert names.compare("Ramvati", "Sunita")["verdict"] == "different"     # wrong account?
    assert names.mentions("राम वती सही है", "Ramvati")


def _filled(**over):
    s = SessionStore().create(load_schema("pension_up"))
    s.add_turn("citizen", "x", Scripted([ups(**(FULL | over))]))
    return s


def test_same_name_in_two_scripts_is_not_flagged():
    s = _filled(name="रामवती", bank_account_name="Ramvati")
    assert s.phase == "readback"
    assert s.export.__self__.latin("name") == "Ramvati"


def test_different_person_gets_stronger_question():
    s = _filled(bank_account_name="Sunita")
    assert "अलग नाम" in s.say and "अपना बैंक खाता" in s.say


def test_spelling_conflict_resolved_by_yes():
    s = _filled(bank_account_name="Ram Wati")
    s.add_turn("citizen", "हाँ जी", Scripted([]))
    assert s.values["bank_account_name"] == "Ramvati" and s.phase == "readback"


def test_export_has_portal_spelling():
    s = _filled(name="रामवती", bank_account_name="रामवती", village="फतेहपुर")
    s.add_turn("citizen", "हाँ", Scripted([ups(consent="yes")]))
    out = s.export()["portal_values"]
    assert out["name"] == "Ramvati" and out["village"] == "Fatehpur"
