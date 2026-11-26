"""Session state + dialog manager: applies extractions, runs the guard, picks what to say next."""
import time
import uuid

from . import guard, names
from .lexicon import answer, tokens
from .privacy import mask_aadhaar, mask_for_display, mentions_secret
from .schema import coerce, field_map

LOW_CONFIDENCE = 0.7
SESSION_TTL_SECONDS = 30 * 60

BOOL_HI = {True: "हाँ", False: "नहीं"}
GENDER_HI = {"female": "महिला", "male": "पुरुष", "other": "अन्य"}


class Session:
    def __init__(self, schema: dict):
        self.id = uuid.uuid4().hex
        self.schema = schema
        self.fields = field_map(schema)
        self.values: dict = {}
        self.meta: dict = {}          # key -> {confidence, evidence, corrected}
        self.transcript: list[str] = []
        self.phase = "collect"        # collect -> readback -> done
        self.consent: dict | None = None
        self.pending_confirm: str | None = None   # field key we asked the citizen to confirm
        self.asked_failures: dict = {}            # rule id -> values snapshot when we asked
        self.events: list[dict] = []              # audit trail, no raw audio
        self.started = time.time()
        self.touched = time.time()
        self.say: str = ""
        self.expecting: str | None = None         # field the last question asked for
        self.open_failure: dict | None = None     # guard failure the last question asked about

    # ---------- applying input ----------
    def add_turn(self, speaker: str, text: str, extractor) -> None:
        self.touched = time.time()
        text = mask_aadhaar(text.strip())
        if not text:
            return
        if mentions_secret(text):
            self.events.append({"t": time.time(), "type": "secret_warning"})
        self.transcript.append(f"{speaker.upper()}: {text}")
        if (key := self._edit_command(text)) is not None:
            # "गाँव बदलो" / "naam galat hai": clear that field and ask for it again.
            self.values.pop(key, None)
            self.meta.pop(key, None)
            self.events.append({"t": time.time(), "type": "voice_edit", "key": key})
            if self.phase != "collect":
                self.phase, self.consent = "collect", None
            self.expecting, self.open_failure, self.pending_confirm = key, None, None
            self.say = "ठीक है, फिर से बताइए। " + self.fields[key]["ask"]["hi"]
            self.transcript.append(f"ASSISTANT: {self.say}")
            return
        if speaker == "citizen" and self._resolve_name_choice(text):
            self.say = self.next_prompt()
            self.transcript.append(f"ASSISTANT: {self.say}")
            return
        result = extractor.extract(self.schema, self.values, speaker, text, self.transcript[:-1],
                                   expected=self.expecting)

        # Consent / confirmation answers from the citizen
        if speaker == "citizen" and result.consent:
            if self.phase == "readback":
                self.consent = {"answer": result.consent, "at": time.time(), "evidence": text}
                self.events.append({"t": time.time(), "type": "consent", "answer": result.consent})
                self.phase = "done" if result.consent == "yes" else "collect"
            elif self.pending_confirm and result.consent == "yes":
                self.meta[self.pending_confirm]["confidence"] = 1.0
                self.pending_confirm = None
            elif self.pending_confirm and result.consent == "no":
                # Drop the doubtful value so we ask for it again.
                self.values.pop(self.pending_confirm, None)
                self.meta.pop(self.pending_confirm, None)
                self.pending_confirm = None

        # Nothing usable from the citizen (noise, garbled speech): repeat the question.
        if speaker == "citizen" and not result.updates and not result.consent:
            sorry = self.schema.get("not_heard", {}).get("hi", "")
            last = self.say[len(sorry):].strip() if sorry and self.say.startswith(sorry) else self.say
            self.say = f"{sorry} {last}".strip()
            self.transcript.append(f"ASSISTANT: {self.say}")
            return

        changed = False
        for up in result.updates:
            before = self.values.get(up.key)
            if self.set_field(up.key, up.value, up.confidence, up.evidence, source="voice"):
                changed |= self.values[up.key] != before

        # A changed value after read-back means we must read back again.
        if changed and self.phase in ("readback", "done"):
            self.phase = "collect"
            self.consent = None
        self.say = self.next_prompt()
        self.transcript.append(f"ASSISTANT: {self.say}")

    def _edit_command(self, text: str) -> str | None:
        """Field the speaker asked to change ("पति का नाम बदलो"), or None. The most specific alias
        wins, so "पति का नाम" picks the husband's name rather than the applicant's name."""
        low = text.lower()
        if not set(tokens(low)) & set(self.schema.get("edit_words", [])):
            return None
        hits = [(max(len(a) for a in f["aliases"] if a in low), f["key"])
                for f in self.schema["fields"] if any(a in low for a in f.get("aliases", []))]
        if not hits:
            return None
        if len(hits) > 1:
            hits = [h for h in hits if h[1] != "name"] or hits     # "नाम" alone is the least specific
        return max(hits)[1]

    def _resolve_name_choice(self, text: str) -> bool:
        """After 'Aadhaar says X, passbook says Y', an answer that names one of them (in any script or
        spacing), or a plain yes to 'is the Aadhaar name right?', sets both fields to that spelling."""
        f = self.open_failure
        if not f or f["id"] != "name_match":
            return False
        a, b = f["fields"]
        # Aadhaar (field a) is the reference when both spellings sound the same.
        chosen = names.mentions(text, self.values[a], self.values[b])
        if chosen is None and f.get("verdict") == "spelling" and answer(text) == "yes":
            chosen = self.values[a]
        if chosen is None:
            return False
        for k in (a, b):
            self.set_field(k, chosen, 1.0, text, source="voice")
        self.events.append({"t": time.time(), "type": "name_resolved", "value": chosen})
        self.open_failure = None
        return True

    def set_field(self, key, raw, confidence=1.0, evidence="", source="operator") -> bool:
        field = self.fields.get(key)
        if field is None:
            return False
        try:
            value = coerce(field, raw)
        except ValueError as e:
            self.events.append({"t": time.time(), "type": "rejected_value", "key": key, "why": str(e)})
            return False
        old = self.values.get(key)
        self.values[key] = value
        self.meta[key] = {"confidence": confidence, "evidence": mask_aadhaar(evidence),
                          "corrected": old is not None and old != value, "source": source}
        if key == self.pending_confirm:
            self.pending_confirm = None
        self.touched = time.time()
        return True

    def operator_edit(self, key, raw) -> bool:
        ok = self.set_field(key, raw, 1.0, "typed by operator", source="operator")
        if ok and self.phase != "collect":
            self.phase, self.consent = "collect", None
        self.say = self.next_prompt()
        self.transcript.append(f"ASSISTANT: {self.say}")
        return ok

    # ---------- deciding what to say ----------
    def display(self, key) -> str:
        v = self.values[key]
        if isinstance(v, bool):
            return BOOL_HI[v]
        if key == "gender":
            return GENDER_HI.get(v, v)
        return mask_for_display(self.fields[key], v)

    def latin(self, key):
        """Portal spelling of a Hindi-script value, for fields the schema marks portal_script=latin."""
        v = self.values.get(key)
        if self.fields[key].get("portal_script") == "latin" and names.has_devanagari(v):
            return names.to_latin(v)
        return None

    def spoken(self, key) -> str:
        """How a value is read aloud: IDs and numbers digit by digit, in groups, so they can be checked."""
        v = self.values[key]
        if key == "mobile":
            return " ".join(v[:5]) + ", " + " ".join(v[5:])
        if key in ("aadhaar_last4", "ifsc"):
            return " ".join(str(v))
        return self.display(key)

    def warnings(self) -> list[dict]:
        """Guard result for the current values, computed once per change."""
        snapshot = tuple(sorted((k, str(v)) for k, v in self.values.items()))
        if getattr(self, "_warnings_for", None) != snapshot:
            self._warnings_for, self._warnings = snapshot, guard.check(self.schema, self.values)
        return self._warnings

    def missing(self) -> list[str]:
        return [f["key"] for f in self.schema["fields"] if f.get("required") and f["key"] not in self.values]

    def next_prompt(self) -> str:
        if self.phase == "done":
            return "धन्यवाद। आवेदन पोर्टल में भरने के लिए तैयार है।"

        self.expecting, self.open_failure = None, None
        # 1. Rejection risks we haven't asked about with these values.
        for failure in self.warnings():
            snapshot = {k: self.values.get(k) for k in failure["fields"]}
            if self.asked_failures.get(failure["id"]) != snapshot:
                self.asked_failures[failure["id"]] = snapshot
                self.open_failure = failure
                if len(failure["fields"]) == 1:
                    self.expecting = failure["fields"][0]
                return failure["message"]

        # 2. Missing required fields.
        missing = self.missing()
        if missing:
            self.expecting = missing[0]
            return self.fields[missing[0]]["ask"]["hi"]

        # 3. Low-confidence values: confirm one at a time.
        for key in self.values:
            if self.meta[key]["confidence"] < LOW_CONFIDENCE:
                self.pending_confirm = key
                return f"मैंने सुना: {self.spoken(key)}। क्या यह सही है?"

        # 4. Everything filled: read back for consent.
        self.phase = "readback"
        lines = [self.fields[f["key"]]["readback"]["hi"].format(value=self.spoken(f["key"]))
                 for f in self.schema["fields"] if f["key"] in self.values]
        return " ".join([self.schema["done"]["hi"], *lines, self.schema["confirm"]["hi"]])

    # ---------- output ----------
    def public_state(self) -> dict:
        return {
            "session_id": self.id,
            "form_id": self.schema["form_id"],
            "phase": self.phase,
            "say": self.say,
            "fields": [
                {"key": f["key"], "label": f["label"], "required": f.get("required", False),
                 "value": self.display(f["key"]) if f["key"] in self.values else None,
                 "latin": self.latin(f["key"]),
                 "low": f["key"] in self.meta and self.meta[f["key"]]["confidence"] < LOW_CONFIDENCE,
                 **({k: self.meta[f["key"]][k] for k in ("confidence", "evidence", "corrected", "source")}
                    if f["key"] in self.meta else {})}
                for f in self.schema["fields"]
            ],
            "warnings": self.warnings(),
            "missing": self.missing(),
            "consent": self.consent,
            "transcript": self.transcript[-20:],
            "elapsed_seconds": round(time.time() - self.started),
        }

    def export(self) -> dict:
        """Final payload for the portal-fill extension. Only after spoken consent."""
        if not (self.consent and self.consent["answer"] == "yes"):
            raise PermissionError("citizen has not confirmed the read-back")
        portal = {k: (self.latin(k) or v) for k, v in self.values.items()}
        return {"form_id": self.schema["form_id"], "values": self.values, "portal_values": portal,
                "consent_at": self.consent["at"], "warnings": self.warnings()}


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def purge(self):
        now = time.time()
        for sid in [s for s, v in self._sessions.items() if now - v.touched > SESSION_TTL_SECONDS]:
            del self._sessions[sid]

    def create(self, schema: dict) -> Session:
        self.purge()
        s = Session(schema)
        greeting = schema.get("greeting", {}).get("hi", "")
        s.say = f"{greeting} {s.next_prompt()}".strip()
        s.transcript.append(f"ASSISTANT: {s.say}")
        self._sessions[s.id] = s
        return s

    def get(self, sid: str) -> Session:
        self.purge()
        return self._sessions[sid]

    def latest_confirmed(self) -> "Session":
        """Most recently touched session whose citizen said "हाँ" (for the portal extension)."""
        self.purge()
        done = [s for s in self._sessions.values() if s.consent and s.consent["answer"] == "yes"]
        if not done:
            raise KeyError("no confirmed application")
        return max(done, key=lambda s: s.touched)

    def delete(self, sid: str):
        self._sessions.pop(sid, None)
