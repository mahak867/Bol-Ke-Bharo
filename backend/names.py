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


def to_latin(name: str) -> str:
    """'रामवती' -> 'Ramvati', 'श्याम लाल' -> 'Shyam Lal'. Latin input is only tidied."""
    words = []
    for w in str(name).split():
        latin = _word_to_latin(w) if re.search(r"[ऀ-ॿ]", w) else w
        words.append(latin[:1].upper() + latin[1:].lower())
    return " ".join(words)


# --- Sound-alike key ---------------------------------------------------------------------------------
_KEY_RULES = [
    (r"[^a-z]", ""),          # spaces, dots, hyphens
    (r"w", "v"), (r"x", "ks"), (r"ph", "f"), (r"sh", "s"), (r"z", "j"), (r"q", "k"),
    (r"ee|ii|y$", "i"), (r"oo|uu", "u"), (r"aa", "a"),
    (r"(.)\1+", r"\1"),       # doubled letters
    (r"([kgcjtdpb])h", r"\1"),  # aspiration is often dropped in spelling
]


def sound_key(name: str) -> str:
    s = to_latin(name).lower()
    for pattern, repl in _KEY_RULES:
        s = re.sub(pattern, repl, s)
    return s


def compare(a: str, b: str) -> dict:
    la, lb = to_latin(a), to_latin(b)
    same_text = " ".join(la.lower().split()) == " ".join(lb.lower().split())
    similarity = round(SequenceMatcher(None, sound_key(a), sound_key(b)).ratio(), 2)
    if same_text:
        verdict = "same"
    elif sound_key(a) == sound_key(b) or similarity >= 0.8:
        verdict = "spelling"
    else:
        verdict = "different"
    return {"verdict": verdict, "similarity": similarity, "a_latin": la, "b_latin": lb}


def mentions(spoken: str, name: str) -> bool:
    """Did the speaker say this name? Works across script and spacing ('रामवती सही है' mentions 'Ramvati')."""
    target = sound_key(name)
    words = spoken.split()
    for i in range(len(words)):
        for j in range(i + 1, min(len(words), i + 4) + 1):
            if sound_key(" ".join(words[i:j])) == target:
                return True
    return False
