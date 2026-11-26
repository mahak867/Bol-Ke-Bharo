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
           "can_you_hear": "क्या आप मुझे सुन पा रहे हैं?"},
    "ta": {"yes": "ஆம்", "no": "இல்லை", "female": "பெண்", "male": "ஆண்", "other": "மற்றவர்",
           "again": "சரி, மீண்டும் சொல்லுங்கள்.", "heard": "நான் கேட்டது: {value}. இது சரியா?",
           "thanks": "நன்றி. விண்ணப்பம் போர்ட்டலில் நிரப்பத் தயாராக உள்ளது.",
           "can_you_hear": "நான் சொல்வது உங்களுக்குக் கேட்கிறதா?"},
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
