"""Matching Indian names across scripts and spellings.

Speech recognition writes "रामवती", the operator types "Ramvati", the passbook says "Ram Wati".
Portals compare names exactly, so the guard needs to tell three cases apart:

  same      - identical once both are in Latin script (रामवती == Ramvati): nothing to fix
  spelling  - sound the same but are written differently (Ramvati / Ram Wati / Ramwati): rejection risk
  different - genuinely different names (Ramvati / Sunita): wrong person or wrong account?
"""
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

# --- Devanagari -> Latin (simple, readable romanisation, as Indians type names) ---------------------
_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",
    "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
    "ध": "dh", "न": "n", "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r",
    "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
}
_NUKTA = {"क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f"}
_VOWELS = {"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri", "ए": "e", "ऐ": "ai",
           "ओ": "o", "औ": "au", "ऑ": "o"}
_MATRAS = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o",
           "ौ": "au", "ॉ": "o"}
_VIRAMA, _NUKTA_SIGN = "्", "़"
_NASAL = {"ं": "n", "ँ": "n", "ः": "h"}


def _word_to_latin(word: str) -> str:
    word = unicodedata.normalize("NFC", word)
    # Build syllables: (consonant, vowel) where vowel is None for the inherent 'a', "" after virama.
    units, i = [], 0
    while i < len(word):
        ch = word[i]
        if ch in _CONS:
            cons = _CONS[ch]
            if i + 1 < len(word) and word[i + 1] == _NUKTA_SIGN:
                cons = _NUKTA.get(ch, cons)
                i += 1
            vowel = None
            if i + 1 < len(word):
                nxt = word[i + 1]
                if nxt == _VIRAMA:
                    vowel, i = "", i + 1
                elif nxt in _MATRAS:
                    vowel, i = _MATRAS[nxt], i + 1
            units.append([cons, vowel])
        elif ch in _VOWELS:
            units.append(["", _VOWELS[ch]])
        elif ch in _NASAL and units:
            if units[-1][1] is None:          # inherent a before anusvara is pronounced: "ban"
                units[-1][1] = "a"
            units[-1].append(_NASAL[ch])
        elif ch.isascii():
            units.append([ch, ""])
        i += 1

    # Schwa deletion: drop the inherent 'a' at the end of a word, and between a vowel-ending
    # syllable and a following consonant+vowel (रामवती -> ramvati, not ramavati).
    # Decide left to right, so two schwas in a row are never both dropped.
    out, spoken = [], []           # spoken[k]: did syllable k end up with a vowel sound?
    for k, u in enumerate(units):
        cons, vowel, *tail = u
        if vowel is None:
            last = k == len(units) - 1
            prev_open = k > 0 and spoken[k - 1] and len(units[k - 1]) == 2   # vowel, no nasal tail
            next_is_cv = k + 1 < len(units) and units[k + 1][0] and units[k + 1][1] != ""
            after_conjunct = k > 0 and units[k - 1][1] == ""      # राजेन्द्र: final 'a' is spoken
            vowel = "" if (last and k > 0 and not after_conjunct) or (prev_open and next_is_cv) else "a"
        spoken.append(vowel != "")
        out.append(cons + vowel + "".join(tail))
    return "".join(out)


_DEVANAGARI = re.compile("[\u0900-\u097F]")
_TAMIL = re.compile("[\u0B80-\u0BFF]")

# --- Tamil -> Latin, as Tamil names are usually spelled in English ---------------------------------
_TA_CONS = {"க": "k", "ங": "ng", "ச": "s", "ஞ": "nj", "ட": "t", "ண": "n", "த": "th", "ந": "n", "ப": "p",
            "ம": "m", "ய": "y", "ர": "r", "ல": "l", "வ": "v", "ழ": "zh", "ள": "l", "ற": "r", "ன": "n",
            "ஜ": "j", "ஷ": "sh", "ஸ": "s", "ஹ": "h"}
_TA_VOWELS = {"அ": "a", "ஆ": "a", "இ": "i", "ஈ": "i", "உ": "u", "ஊ": "u", "எ": "e", "ஏ": "e", "ஐ": "ai",
              "ஒ": "o", "ஓ": "o", "ஔ": "au"}
_TA_SIGNS = {"ா": "a", "ி": "i", "ீ": "i", "ு": "u", "ூ": "u", "ெ": "e", "ே": "e", "ை": "ai", "ொ": "o",
             "ோ": "o", "ௌ": "au", "்": ""}
_TA_VOICED = {"k": "g", "t": "d", "p": "b"}       # between vowels / after a nasal (முருகன் -> Murugan)
_TA_NASAL = {"ங", "ஞ", "ண", "ந", "ம", "ன"}


def _tamil_word_to_latin(word: str) -> str:
    sylls = []                                     # [letter, consonant, vowel]
    for ch in word:
        if ch in _TA_CONS:
            sylls.append([ch, _TA_CONS[ch], "a"])
        elif ch in _TA_SIGNS and sylls:
            sylls[-1][2] = _TA_SIGNS[ch]
        elif ch in _TA_VOWELS:
            sylls.append([ch, "", _TA_VOWELS[ch]])
    out = []
    for i, (letter, cons, vowel) in enumerate(sylls):
        prev = sylls[i - 1] if i else None
        if prev and vowel and cons in _TA_VOICED and (prev[2] or prev[0] in _TA_NASAL):
            cons = _TA_VOICED[cons]
        if letter == "ச" and prev and not prev[2]:  # after a consonant: ட்ச -> "tch"
            cons = "ch"
        out.append(cons + vowel)
    return "".join(out)


def has_devanagari(text) -> bool:
    return bool(_DEVANAGARI.search(str(text)))


def needs_romanising(text) -> bool:
    """Written in an Indian script we can romanise (Devanagari or Tamil)."""
    return bool(_DEVANAGARI.search(str(text)) or _TAMIL.search(str(text)))


@lru_cache(maxsize=512)
def to_latin(name: str) -> str:
    """'रामवती' -> 'Ramvati', 'முருகன்' -> 'Murugan'. Latin input is only tidied (case, spaces)."""
    words = []
    for w in str(name).split():
        latin = (_word_to_latin(w) if has_devanagari(w) else
                 _tamil_word_to_latin(w) if _TAMIL.search(w) else w)
        words.append(latin[:1].upper() + latin[1:].lower())
    return " ".join(words)


# --- Sound-alike key ---------------------------------------------------------------------------------
_KEY_RULES = [(re.compile(p), r) for p, r in [
    (r"[^a-z]", ""),            # spaces, dots, hyphens
    (r"tch", "ksh"),            # Tamil writes the "ksh" of Lakshmi as ட்ச: Latchumi
    (r"w", "v"), (r"x", "ks"), (r"ph", "f"), (r"sh", "s"), (r"z", "j"), (r"q", "k"),
    (r"ee|ii|y$", "i"), (r"oo|uu", "u"), (r"aa", "a"),
    (r"(.)\1+", r"\1"),         # doubled letters
    (r"([kgcjtdpb])h", r"\1"),  # aspiration is often dropped in spelling
]]


@lru_cache(maxsize=2048)
def sound_key(name: str) -> str:
    s = to_latin(name).lower()
    for pattern, repl in _KEY_RULES:
        s = pattern.sub(repl, s)
    return s


def compare(a: str, b: str) -> dict:
    la, lb = to_latin(a), to_latin(b)
    similarity = round(SequenceMatcher(None, sound_key(a), sound_key(b)).ratio(), 2)
    # Equal sound keys give similarity 1.0, so one threshold covers "sounds the same".
    # One name being the other plus or minus a word ("Sunita" / "Sunita Devi") is a spelling problem
    # for the portal, not a different person.
    wa, wb = {sound_key(w) for w in la.split()}, {sound_key(w) for w in lb.split()}
    subset = bool(wa and wb) and (wa <= wb or wb <= wa)
    verdict = "same" if la == lb else "spelling" if similarity >= 0.8 or subset else "different"
    return {"verdict": verdict, "similarity": similarity, "a_latin": la, "b_latin": lb}


def mentions(spoken: str, *candidates: str) -> str | None:
    """The first candidate the speaker named, in any script or spacing, else None.
    ('रामवती सही है', 'Ramvati') -> 'Ramvati'."""
    words = spoken.split()
    said = {sound_key(" ".join(words[i:j]))
            for i in range(len(words)) for j in range(i + 1, min(len(words), i + 4) + 1)}
    return next((c for c in candidates if sound_key(c) in said), None)
