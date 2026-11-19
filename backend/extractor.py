"""Transcript segment -> field updates.

ClaudeExtractor is the real engine. RuleExtractor is a tiny offline fallback so the
app and tests run without an API key; it only understands a few obvious patterns.
"""
import json
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

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

    def extract(self, schema: dict, state: dict, speaker: str, segment: str, recent: list[str]) -> Extraction:
        user = (
            f"Form schema:\n{_schema_for_prompt(schema)}\n\n"
            f"Current form state:\n{json.dumps(state, ensure_ascii=False)}\n\n"
            f"Recent conversation:\n" + "\n".join(recent[-6:]) + "\n\n"
            f"New segment ({speaker.upper()}): {segment}"
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
              "pachhattar": 75, "paisath": 65, "painsath": 65}
_YES_WORDS = re.compile(r"^\W*(haan|han|ha|ji haan|ji|yes|sahi hai|हाँ|हां|जी)\b", re.I)
_NO_WORDS = re.compile(r"^\W*(nahi|nahin|na|no|galat|नहीं|ना|गलत)\b", re.I)


class RuleExtractor:
    """Offline fallback: age, mobile, Aadhaar last 4, IFSC, yes/no. Good enough for UI tests only."""

    def extract(self, schema: dict, state: dict, speaker: str, segment: str, recent: list[str]) -> Extraction:
        ups: list[FieldUpdate] = []
        low = segment.lower()
        if m := re.search(r"(\d{2,3})\s*(saal|sal|years|varsh|साल|वर्ष)", low):
            ups.append(FieldUpdate(key="age", value=m.group(1), confidence=0.9, evidence=m.group(0)))
        else:
            for w, n in _HINDI_NUM.items():
                if re.search(rf"\b{w}\s*(saal|sal)\b", low):
                    ups.append(FieldUpdate(key="age", value=str(n), confidence=0.75, evidence=w))
        if m := re.search(r"(?<!\d)([6-9]\d{9})(?!\d)", re.sub(r"[\s-]", "", segment)):
            ups.append(FieldUpdate(key="mobile", value=m.group(1), confidence=0.9, evidence=m.group(1)))
        if m := re.search(r"XXXX XXXX (\d{4})", segment):
            ups.append(FieldUpdate(key="aadhaar_last4", value=m.group(1), confidence=0.95, evidence=m.group(0)))
        if m := re.search(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", segment.upper().replace(" ", "")):
            ups.append(FieldUpdate(key="ifsc", value=m.group(1), confidence=0.85, evidence=m.group(1)))
        consent = None
        if speaker == "citizen":
            if _YES_WORDS.search(segment):
                consent = "yes"
            elif _NO_WORDS.search(segment):
                consent = "no"
        return Extraction(updates=ups, is_correction=False, consent=consent)


def make_extractor():
    mode = os.environ.get("BKB_EXTRACTOR", "auto")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if mode == "rules" or (mode == "auto" and not has_key):
        return RuleExtractor()
    return ClaudeExtractor()
