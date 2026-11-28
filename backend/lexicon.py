import re

"""Words and characters shared by the extractor, the type coercion and the dialog (one copy only)."""

DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
PUNCT = "।,.?!:;\"'"

YES = {"haan", "han", "ha", "ji", "yes", "sahi", "theek", "हाँ", "हां", "हा", "जी", "सही", "ठीक", "बिल्कुल",
       "ஆம்", "ஆமாம்", "ஆமா", "சரி", "aam", "aamaa", "sari"}
NO = {"nahi", "nahin", "na", "no", "galat", "नहीं", "नही", "ना", "गलत", "ग़लत", "இல்லை", "தவறு", "வேண்டாம்", "illai"}

# Words the app itself says, per language. Schemas hold everything form-specific.
PHRASES = {
    "hi": {"yes": "हाँ", "no": "नहीं", "female": "महिला", "male": "पुरुष", "other": "अन्य",
           "again": "ठीक है, फिर से बताइए।", "heard": "मैंने सुना: {value}। क्या यह सही है?",
           "thanks": "धन्यवाद। आवेदन पोर्टल में भरने के लिए तैयार है।",
           "can_you_hear": "क्या आप मुझे सुन पा रहे हैं?",
           "which_wrong": "कौन सी जानकारी गलत है? जैसे बोलिए: गाँव, या उम्र।"},
    "ta": {"yes": "ஆம்", "no": "இல்லை", "female": "பெண்", "male": "ஆண்", "other": "மற்றவர்",
           "again": "சரி, மீண்டும் சொல்லுங்கள்.", "heard": "நான் கேட்டது: {value}. இது சரியா?",
           "thanks": "நன்றி. விண்ணப்பம் போர்ட்டலில் நிரப்பத் தயாராக உள்ளது.",
           "can_you_hear": "நான் சொல்வது உங்களுக்குக் கேட்கிறதா?",
           "which_wrong": "எந்த விவரம் தவறு? உதாரணமாக: ஊர், அல்லது வயது."},
}
LANGS = tuple(PHRASES)


def pick(texts: dict, lang: str) -> str:
    """A schema text in the session language, falling back to Hindi."""
    return texts.get(lang) or texts["hi"]


def tokens(text: str) -> list[str]:
    """Words with punctuation stripped and Devanagari digits made ASCII."""
    return [t.strip(PUNCT) for t in text.translate(DIGITS).split() if t.strip(PUNCT)]


def answer(text: str) -> str | None:
    """'yes' / 'no' if the utterance opens with one (or says 'no' early), else None."""
    low = [t.lower() for t in tokens(text)]
    if not low:
        return None
    if low[0] in YES:
        return "yes"
    if low[0] in NO or any(t in NO for t in low[:3]):
        return "no"
    return None


# ---------- codes spoken letter by letter (IFSC, mobile, Aadhaar digits) ----------
# Speech recognition writes what it hears: "SBIN 0001234" said aloud comes back as
# "एस बी आई एन ज़ीरो ज़ीरो ज़ीरो वन टू थ्री फोर". These tables turn that back into the code.
_LETTER_NAMES = {
    "ए": "A", "बी": "B", "सी": "C", "डी": "D", "ई": "E", "एफ": "F", "जी": "G", "एच": "H", "आई": "I",
    "जे": "J", "के": "K", "एल": "L", "एम": "M", "एन": "N", "ओ": "O", "पी": "P", "क्यू": "Q", "आर": "R",
    "एस": "S", "टी": "T", "यू": "U", "वी": "V", "डब्ल्यू": "W", "एक्स": "X", "वाई": "Y", "ज़ेड": "Z", "जेड": "Z",
}
_DIGIT_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "oh": "0",
    "ज़ीरो": "0", "जीरो": "0", "शून्य": "0", "वन": "1", "टू": "2", "थ्री": "3", "फोर": "4", "फ़ोर": "4",
    "फाइव": "5", "फ़ाइव": "5", "सिक्स": "6", "सेवन": "7", "एट": "8", "नाइन": "9",
    "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5", "पाँच": "5", "छह": "6", "छः": "6", "छे": "6",
    "सात": "7", "आठ": "8", "नौ": "9",
    "பூஜ்ஜியம்": "0", "ஒன்று": "1", "இரண்டு": "2", "மூன்று": "3", "நான்கு": "4", "ஐந்து": "5",
    "ஆறு": "6", "ஏழு": "7", "எட்டு": "8", "ஒன்பது": "9",
}
_DOUBLE = {"double", "डबल"}
_TRIPLE = {"triple", "ट्रिपल"}
_SPELL = sorted(list(_LETTER_NAMES.items()) + list(_DIGIT_WORDS.items()), key=lambda kv: -len(kv[0]))


def _spell_word(word: str) -> str | None:
    """'एसबीआईएन' -> 'SBIN' (letter names run together), 'वन' -> '1'; None if not all spelling."""
    out, i, w = "", 0, word.lower()
    while i < len(w):
        for name, char in _SPELL:
            if w.startswith(name, i):
                out, i = out + char, i + len(name)
                break
        else:
            return None
    return out


def spelled(text: str) -> list[str]:
    """Each word of `text`, with spelled letters/digits turned into characters and ASCII letters/digits
    upper-cased, so codes can be matched: 'एस बी आई एन ज़ीरो' -> ['S','B','I','N','0']. Words that are not
    spelling stay as they are. "डबल ज़ीरो" -> '00'."""
    out, repeat = [], 1
    for t in tokens(text):
        low = t.lower()
        if low in _DOUBLE or low in _TRIPLE:
            repeat = 2 if low in _DOUBLE else 3
            continue
        if re.fullmatch(r"[A-Za-z0-9]+", t):
            ch = t.upper()
        else:
            ch = _spell_word(t) or t
        out.append(ch * repeat if len(ch) == 1 else ch)
        repeat = 1
    return out
