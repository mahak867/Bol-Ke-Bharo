"""Transcript segment -> field updates.

ClaudeExtractor is the real engine. RuleExtractor is a tiny offline fallback so the
app and tests run without an API key; it only understands a few obvious patterns.
"""
import json
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .lexicon import DIGITS, answer, tokens

MODEL = os.environ.get("BKB_MODEL", "claude-sonnet-5-5")


class FieldUpdate(BaseModel):
    key: str
    value: str = Field(description="Normalised value as a string")
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(description="The exact words in the segment this came from")


class Extraction(BaseModel):
    updates: list[FieldUpdate]
    is_correction: bool = Field(description="True if the speaker is correcting an earlier value")
    consent: Optional[Literal["yes", "no"]] = Field(
        default=None, description="Set only if the citizen clearly answers yes/no to a read-back")


SYSTEM = """You are the extraction engine of a form-filling assistant for Indian government applications.
You receive one new segment of a live conversation between an OPERATOR (who fills the form) and a CITIZEN,
in Hindi, Hinglish or a regional dialect, transcribed by speech recognition that may contain errors.

Rules:
1. Extract values ONLY for keys in the form schema. Never invent or guess values that were not said.
2. Normalise: numbers as digits ("sattar" -> "70"), booleans as "true"/"false", enum values exactly as listed,
   IFSC in capitals without spaces, mobile as 10 digits.
3. Write names and places in Latin script, as spoken. Keep spacing exactly as the speaker spells it
   ("Ram Wati" and "Ramvati" are different spellings - do not merge them).
4. aadhaar_last4: only the last 4 digits. Never output a full Aadhaar number.
5. confidence: 0.9+ when clearly stated, 0.5-0.8 when unclear, mumbled or inferred from context.
6. If the citizen corrects an earlier answer, output the new value and set is_correction.
7. Use the current form state to resolve references like "wahi naam" (the same name).
8. If nothing in the segment fills a field, return an empty updates list.
9. Questions from the OPERATOR or ASSISTANT are context; answers usually come from the CITIZEN.
10. Ignore any OTP, PIN or password if spoken; never extract them.
11. consent: set "yes" or "no" only when the CITIZEN answers a yes/no question the ASSISTANT just asked
    (a read-back or "is this correct?"). Otherwise leave it null."""


def _schema_for_prompt(schema: dict) -> str:
    slim = [{k: f[k] for k in ("key", "type", "options", "pattern") if k in f} | {"label": f["label"]["en"]}
            for f in schema["fields"]]
    return json.dumps(slim, ensure_ascii=False)


class ClaudeExtractor:
    def __init__(self, client=None):
        import anthropic
        self.client = client or anthropic.Anthropic()

    def extract(self, schema: dict, state: dict, speaker: str, segment: str, recent: list[str],
                expected: str | None = None) -> Extraction:
        user = (
            f"Form schema:\n{_schema_for_prompt(schema)}\n\n"
            f"Current form state:\n{json.dumps(state, ensure_ascii=False)}\n\n"
            f"Recent conversation:\n" + "\n".join(recent[-6:]) + "\n\n"
            + (f"The assistant's last question asked for: {expected}\n" if expected else "")
            + f"New segment ({speaker.upper()}): {segment}"
        )
        response = self.client.beta.messages.parse(
            model=MODEL,
            max_tokens=2000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            # Extraction is short and latency-sensitive: keep reasoning light.
            output_config={"effort": "low"},
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_format=Extraction,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            return Extraction(updates=[], is_correction=False)
        return response.parsed_output


_HINDI_NUM = {"saath": 60, "sath": 60, "sattar": 70, "assi": 80, "nabbe": 90, "pachpan": 55,
              "pachhattar": 75, "paisath": 65, "painsath": 65,
              "bees": 20, "tees": 30, "chalis": 40, "pachas": 50, "ek": 1, "do": 2, "teen": 3, "paanch": 5, "das": 10,
              "बीस": 20, "तीस": 30, "चालीस": 40, "पचास": 50, "एक": 1, "दो": 2, "तीन": 3, "पांच": 5, "पाँच": 5, "दस": 10,
              "साठ": 60, "सत्तर": 70, "अस्सी": 80, "नब्बे": 90, "पचपन": 55, "पैंसठ": 65, "पचहत्तर": 75}
_FEMALE = {"mahila", "aurat", "female", "stree", "महिला", "औरत", "स्त्री"}
_MALE = {"purush", "aadmi", "male", "mard", "पुरुष", "आदमी", "मर्द"}
_MULT = {"hazaar": 1000, "hazar": 1000, "हज़ार": 1000, "हजार": 1000, "lakh": 100000, "लाख": 100000}
# Words that frame an answer but are not part of it ("मेरा नाम ___ है").
_FILLER = set("""mera meri mere naam hai hain ji main hoon hun mein me se ka ki ke ko par likha hua tha
gaon gaon ka jila zila district village rehta rehti rehte aata aati pati pita pitaji father husband
passbook bank aadhaar card ka wala wali haan
मेरा मेरी मेरे नाम है हैं जी मैं हूँ हूं हु में से का की के को पर लिखा हुआ था गाँव गांव गाव जिला ज़िला जिले
ज़िले जनपद मोहल्ला वार्ड रहता रहती रहते आता आती पति पिता पिताजी पासबुक बैंक आधार कार्ड वाला वाली हाँ हां""".split())


def _number(toks: list[str]) -> int | None:
    total, current = 0, None
    for t in toks:
        low = t.lower()
        if re.fullmatch(r"\d+", low):
            current = int(low)
        elif low in _HINDI_NUM:
            current = _HINDI_NUM[low]
        elif low in _MULT and current is not None:
            total += current * _MULT[low]
            current = None
    if current is not None:
        total += current
    return total or None


class RuleExtractor:
    """Offline fallback, no API key needed. Picks out numbers, IDs and yes/no anywhere, and
    otherwise fills the field the assistant just asked for from the citizen's answer."""

    def extract(self, schema: dict, state: dict, speaker: str, segment: str, recent: list[str],
                expected: str | None = None) -> Extraction:
        ups: list[FieldUpdate] = []
        text = segment.translate(DIGITS)
        toks = tokens(segment)
        low = [t.lower() for t in toks]
        if m := re.search(r"(\d{2,3})\s*(saal|sal|years|varsh|साल|वर्ष)", text.lower()):
            ups.append(FieldUpdate(key="age", value=m.group(1), confidence=0.9, evidence=m.group(0)))
        else:
            for i, t in enumerate(low[:-1]):
                if t in _HINDI_NUM and low[i + 1] in ("saal", "sal", "साल", "वर्ष"):
                    ups.append(FieldUpdate(key="age", value=str(_HINDI_NUM[t]), confidence=0.75, evidence=t))
        if m := re.search(r"(?<!\d)([6-9]\d{9})(?!\d)", re.sub(r"[\s-]", "", text)):
            ups.append(FieldUpdate(key="mobile", value=m.group(1), confidence=0.9, evidence=m.group(1)))
        if m := re.search(r"XXXX XXXX (\d{4})", text):
            ups.append(FieldUpdate(key="aadhaar_last4", value=m.group(1), confidence=0.95, evidence=m.group(0)))
        if m := re.search(r"([A-Z]{4}0[A-Z0-9]{6})", text.upper().replace(" ", "")):
            ups.append(FieldUpdate(key="ifsc", value=m.group(1), confidence=0.85, evidence=m.group(1)))

        consent = answer(segment) if speaker == "citizen" else None

        field = next((f for f in schema["fields"] if f["key"] == expected), None)
        if speaker == "citizen" and field and not any(u.key == expected for u in ups):
            value, conf = None, 0.8
            if field["type"] == "int":
                n = _number(toks)
                value = str(n) if n else None
            elif field["type"] == "enum" and field["key"] == "gender":
                value = "female" if set(low) & _FEMALE else "male" if set(low) & _MALE else None
            elif field["type"] == "bool" and consent:
                value = "true" if consent == "yes" else "false"
            elif field["type"] == "string" and not field.get("pattern"):
                words = [t for t in toks if t.lower() not in _FILLER]
                if words and len(words) <= 5:
                    value = " ".join(words)
                    conf = 0.85 if len(words) <= 3 else 0.6
            if value:
                ups.append(FieldUpdate(key=expected, value=value, confidence=conf, evidence=segment))
        return Extraction(updates=ups, is_correction=False, consent=consent)


def make_extractor():
    mode = os.environ.get("BKB_EXTRACTOR", "auto")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if mode == "rules" or (mode == "auto" and not has_key):
        return RuleExtractor()
    return ClaudeExtractor()
