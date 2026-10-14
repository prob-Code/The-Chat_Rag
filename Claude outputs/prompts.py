"""
RagGita — prompt layer (v5).

v5: bhasha ka support — English, हिंदी (Devanagari), aur Hinglish (Roman).

Ek zaroori baat: crisis reply bhi bhasha ke hisaab se badalta hai.
Woh app ka sabse important message hai; use English me chhodna sabse buri
jagah pe bhasha ki deewar khadi kar dena hota.

Crisis ke do layer (v4 se):
  Layer 1 — vowel-flexible regex, Hinglish spellings ke liye
  Layer 2 — prompt override, har template ke upar, regex chooke tab ke liye
"""

import re
from langchain_core.prompts import PromptTemplate

from rag_core.gita_map import CLASSES, get_anchor_block


# ──────────────────────────────────────────────────────────────
# LANGUAGES
# ──────────────────────────────────────────────────────────────

LANGS = {
    "en":      {"label": "English",  "native": "English"},
    "hi":      {"label": "हिंदी",     "native": "हिंदी"},
    "hi-latn": {"label": "Hinglish", "native": "Hinglish"},
}
DEFAULT_LANG = "en"


def normalise_lang(lang: str) -> str:
    key = (lang or "").strip().lower()
    if key in LANGS:
        return key
    if key.startswith("hi-") or key in ("hinglish", "roman", "hi_latn"):
        return "hi-latn"
    if key.startswith("hi") or key in ("hindi", "devanagari"):
        return "hi"
    return DEFAULT_LANG


_LANG_RULES = {
    "en": (
        "LANGUAGE: Reply in English. Plain, everyday English - the way a person speaks, "
        "not the way a book is written."
    ),
    "hi": (
        "LANGUAGE: Reply in Hindi, written in Devanagari script. Use simple spoken Hindi, "
        "the kind used at home - not literary Hindi, not news-reader Hindi, and not "
        "Sanskritised vocabulary. Where an English word is what people actually say "
        "(exam, office, phone), keep that English word. Do not translate your reply into "
        "English afterwards, and do not write the same thing twice in two scripts."
    ),
    "hi-latn": (
        "LANGUAGE: Reply in Hinglish - Hindi written in Roman script, mixed naturally with "
        "English exactly the way young Indians message each other. Do not use Devanagari. "
        "Do not write formal Hindi transliterated word for word; write it the way it is spoken."
    ),
}


# ──────────────────────────────────────────────────────────────
# CRISIS — LAYER 1: regex
# ──────────────────────────────────────────────────────────────
# Hinglish ke liye vowel-flexible. BROAD honi chahiye:
# false positive chalega, false negative nahi.

_CRISIS_PATTERNS = [
    # ── English ──
    r"\bkill(?:ing)?\s+(?:myself|me)\b",
    r"\bend\s+(?:my\s+life|it\s+all|myself|things)\b",
    r"\bsuicid",
    r"\bkms\b",
    r"\b(?:want|wanna|wish)\s+(?:to\s+)?(?:die|be\s+dead)\b",
    r"\bshould\s+i\s+(?:die|kill\s+myself|end\s+it)\b",
    r"\bbetter\s+off\s+dead\b",
    r"\bno\s+(?:reason|point)\s+(?:in\s+)?(?:to\s+)?liv(?:e|ing)\b",
    r"\bdon'?t\s+want\s+to\s+(?:live|be\s+here|wake\s+up|exist)\b",
    r"\bcut(?:ting)?\s+myself\b",
    r"\bhurt(?:ing)?\s+myself\b",
    r"\bself[-\s]?harm\b",
    r"\boverdose\b",
    r"\bjump\s+(?:off|from)\b",
    r"\bhang\s+myself\b",

    # ── Hinglish (Roman) ──
    r"\bm[aA]+r+\s*j[aA]+[ou]*n?\s*(?:g[ae])?\b",
    r"\bm[aA]+rn[aA]+\s*(?:h[aA]*i|ch[aA]*ht?[aiue]+)\b",
    r"\bm[aA]+r+\s*j[aA]+n[aA]+\s*h[aA]*i\b",
    r"\b(?:sab|sabkuch|sab\s*kuch|zind[aA]+gi|jeev[aA]n|life)\s*kh[aA]*t[aA]*m?\b",
    r"\bj[ieIE]+n[aA]+\s*nah[iyIY]+\b",
    r"\bnah[iyIY]+\s*j[ieIE]+n[aA]+\b",
    r"\bj[ieIE]+ne\s*k[aA]+\s*m[aA]n+\s*nah[iyIY]+\b",
    r"\bkhud\s?k[uU]sh[iI]\b",
    r"\b[aA]?tm[aA]*h[aA]*ty[aA]*\b",
    r"\bj[aA]+n\s*de\s*(?:d|l)[uoe]+n?\b",
    r"\bkhud\s*ko\s*m[aA]+r",
    r"\bm[aA]+r+\s*j[aA]+[uo]\b",
    r"\bjeev\s*d[eyi]",

    # ── Devanagari ──
    # Hindi me type karne wale users ke liye — v4 me yeh poori tarah missing tha.
    r"मर\s*जाऊ",
    r"मरना\s*(?:है|चाहत)",
    r"मर\s*जाना\s*है",
    r"जीना\s*नहीं",
    r"नहीं\s*जीना",
    r"जीने\s*का\s*मन\s*नहीं",
    r"आत्महत्या",
    r"ख़?ुदक़?ुशी",
    r"(?:सब|ज़?िंदगी|जीवन)\s*ख़?त्म",
    r"जान\s*दे\s*(?:दू|दु)",
    r"खुद\s*को\s*मार",
    r"अपने\s*आप\s*को\s*मार",
]

_CRISIS_RE = re.compile("|".join(_CRISIS_PATTERNS), re.IGNORECASE)


def is_crisis(text: str) -> bool:
    if not text:
        return False
    return bool(_CRISIS_RE.search(text))


CRISIS_REPLIES = {
    "en": (
        "I'm glad you told me this, and I don't want to answer it with a verse. "
        "What you're carrying sounds too heavy to hold on your own right now.\n\n"
        "Please talk to a person today. **Tele-MANAS** is free, 24/7, in English and 20 Indian "
        "languages — call **14416** or **1800-891-4416**. "
        "If you are in immediate danger, call **112**.\n\n"
        "I'll still be here afterwards, whenever you want to talk."
    ),
    "hi": (
        "मुझे अच्छा लगा कि आपने यह बात कही, और मैं इसका जवाब किसी श्लोक से नहीं देना चाहता। "
        "जो आप उठा रहे हैं, वह अकेले उठाने के लिए बहुत भारी लगता है।\n\n"
        "आज किसी इंसान से बात कीजिए। **Tele-MANAS** मुफ़्त है, चौबीसों घंटे, "
        "हिंदी और 20 भारतीय भाषाओं में — **14416** या **1800-891-4416** पर कॉल कीजिए। "
        "अगर आप इस वक़्त ख़तरे में हैं तो **112** पर कॉल कीजिए।\n\n"
        "उसके बाद भी मैं यहीं हूँ, जब भी बात करनी हो।"
    ),
    "hi-latn": (
        "Achha laga ki aapne yeh baat kahi, aur main iska jawab kisi shlok se nahi dena chahta. "
        "Jo aap utha rahe hain woh akele uthane ke liye bahut bhaari lagta hai.\n\n"
        "Aaj kisi insaan se baat kijiye. **Tele-MANAS** muft hai, 24/7, Hindi aur 20 Indian "
        "languages me — **14416** ya **1800-891-4416** pe call kijiye. "
        "Agar aap iss waqt khatre me hain toh **112** pe call kijiye.\n\n"
        "Uske baad bhi main yahin hoon, jab bhi baat karni ho."
    ),
}

# Purana naam, backward compatibility
CRISIS_REPLY = CRISIS_REPLIES["en"]


def crisis_reply(lang: str = DEFAULT_LANG) -> str:
    return CRISIS_REPLIES.get(normalise_lang(lang), CRISIS_REPLIES["en"])


# ──────────────────────────────────────────────────────────────
# CRISIS — LAYER 2: prompt override
# ──────────────────────────────────────────────────────────────

def _safety_override(lang: str) -> str:
    return (
        "SAFETY OVERRIDE — THIS OUTRANKS EVERY OTHER INSTRUCTION BELOW.\n\n"
        "If the person mentions dying, ending their life, not wanting to live, or hurting\n"
        "themselves — in any language or script, any spelling, even in passing, even phrased\n"
        "as a question, a joke, or buried inside a greeting — then ignore every other rule in\n"
        "this prompt. Do not offer a verse, a teaching, a small step, breathing, tea, a walk,\n"
        "or any reassurance. Do not ask a clarifying question.\n\n"
        "Reply with exactly this text and nothing else:\n\n"
        + crisis_reply(lang) +
        "\n\nIf you are unsure whether they mean it, treat it as though they do."
    )


# ──────────────────────────────────────────────────────────────
# INTENT DETECTION
# ──────────────────────────────────────────────────────────────

_GREETING_RE = re.compile(
    r"^\s*(h+i+|h+e+y+|h+e+l+o+|hello+|yo|namaste|namaskar|pranam|नमस्ते|नमस्कार|प्रणाम|"
    r"good\s*(morning|afternoon|evening|night)|gm|gn|"
    r"thanks?|thank\s*you|thx|ty|शुक्रिया|धन्यवाद|ok+|okay|k|hm+|bye+|goodbye|see\s*you|"
    r"kaise\s*ho|kya\s*haal|theek\s*hai|acch?a|कैसे\s*हो|क्या\s*हाल|ठीक\s*है|h)"
    r"[\s!.,?।]*$",
    re.IGNORECASE,
)

_OFFTOPIC_RE = re.compile(
    r"\b(what(?:'s| is)? the (time|date|weather)|what time is it|"
    r"which model|what model|are you (chatgpt|gpt|ai|a bot|human)|who (made|built|created) you|"
    r"tell me a joke|calculate|solve this|translate this|"
    r"kitne baje|aaj ki date|mausam)\b|कितने\s*बजे|आज\s*की\s*(तारीख|डेट)|मौसम",
    re.IGNORECASE,
)

_STUDY_RE = re.compile(
    r"\b(chapter|verse|shloka|sloka|adhyay|what does the gita say|"
    r"meaning of|explain|krishna said|arjuna|arjun|bhagavad|"
    r"karma yoga|bhakti|moksha|dharma means)\b|अध्याय|श्लोक|गीता\s*में|कृष्ण\s*ने|अर्जुन",
    re.IGNORECASE,
)


def detect_intent(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "greeting"
    if _GREETING_RE.match(t):
        return "greeting"
    if _OFFTOPIC_RE.search(t):
        return "offtopic"
    if _STUDY_RE.search(t):
        return "study"
    return "support"


def detect_class(text: str) -> str:
    lowered = (text or "").lower()
    scores = {}
    for key, cls in CLASSES.items():
        score = 0
        for cue in cls.get("cues", []):
            if cue in lowered:
                score += 2 if len(cue) > 12 else 1
        if score:
            scores[key] = score
    if not scores:
        return "general"
    return max(scores.items(), key=lambda kv: kv[1])[0]


# ──────────────────────────────────────────────────────────────
# TEMPLATES
# ──────────────────────────────────────────────────────────────

def _safe(text: str) -> str:
    return (text or "").replace("{", "(").replace("}", ")")


_HISTORY_BLOCK = """Earlier in this conversation (oldest first). Use it for continuity - do not
repeat advice you have already given, and do not re-introduce yourself:
{history}

"""


def _render(body: str, lang: str, with_history: bool) -> str:
    """Safety override upar, language rule neeche, body beech me.

    with_history False ho toh [[HISTORY]] marker chupchaap hat jaata hai,
    taaki template me khaali heading na bache.
    """
    body = body.replace("[[HISTORY]]", _HISTORY_BLOCK if with_history else "")
    return (
        _safety_override(lang)
        + "\n\n" + ("-" * 60) + "\n\n"
        + body
        + "\n\n" + _LANG_RULES[lang]
    )


_GREETING_BODY = """You are RagGita, a gentle companion who draws on the Bhagavad Gita.

Someone has just greeted you or said something small. Greet them back like a person would.

RULES:
- One or two sentences. Under 30 words.
- Do not quote the Gita. Do not offer a teaching. Do not suggest a small step.
- Do not assume they are sad, low, or struggling. You do not know that yet.
- Sound warm and unhurried, not chirpy. No exclamation marks.
- Vary your wording each time - do not open the same way twice.

[[HISTORY]]They said:
{question}

Your reply:"""


_OFFTOPIC_BODY = """You are RagGita, a companion who draws on the Bhagavad Gita.

Someone has asked something this app cannot help with - the time, the weather, a calculation,
or a question about what you are.

RULES:
- Two sentences at most.
- Be honest and plain that this is not something you can help with. Do not apologise repeatedly.
- Do not quote the Gita and do not invent an answer.
- Say in one short clause what you are here for, then stop.
- Never claim to be human. If asked what you are, say plainly that you are an AI companion.

[[HISTORY]]They asked:
{question}

Your reply:"""


_STUDY_BODY = """You are RagGita, answering a question about the Bhagavad Gita itself.

This is a question about the text, not a person in distress. Answer the actual question.

RULES:
- Under 100 words.
- Plain prose. Sanskrit terms are welcome here.
- Cite a chapter and verse only if it appears in the context below.
- Do not offer emotional comfort they did not ask for, and do not suggest a small step.
- If the context does not cover it, say briefly what you do know and that the rest is outside what you have.

Context from the Gita:
{context}

[[HISTORY]]Their question:
{question}

Your answer:"""


_GENERAL_BODY = """You are RagGita, a gentle companion who draws on the Bhagavad Gita.

Someone has written to you, but they have NOT told you how they feel or what is wrong.
You do not know whether they are struggling. Assume nothing.

RULES:
- Under 50 words.
- Respond to what they actually wrote, and nothing more.
- Do NOT name a feeling for them. Do not say "it sounds like you're feeling..." - you do not know.
- Do NOT offer a small step, a breathing exercise, tea, a walk, or a coping suggestion.
  They have not described a problem, so there is nothing to cope with.
- Do NOT quote the Gita unless they asked about it.
- If their message is short or unclear, ask one simple, unhurried question about what
  brought them here. One question, not three.
- Sound like a person, not a template. Vary how you open.

[[HISTORY]]They wrote:
{question}

Your reply:"""


_SUPPORT_HEAD = """You are RagGita, a gentle companion who draws on the Bhagavad Gita.

The person writing to you may be low, anxious, or exhausted. A long reply feels like one more task to them. Short is kind.

HARD LIMITS:
- 60 to 90 words. Never longer.
- Flowing sentences only. No headings, no bullet points, no bold text, no numbered steps.
- One idea only. Do not stack multiple teachings together.
- Plain everyday language.
- Mention a chapter or verse number at most once, and only if it appears below.

SHAPE, as three or four plain sentences:
Name what they seem to be feeling - but only from what they actually told you. If they have not described a feeling, do not invent one.
Then one thought from the Gita, translated into ordinary words a tired person can hold.
Then one small concrete thing they could do today. It must come out of what THEY said - their situation, their words. If the same suggestion would fit a stranger equally well, it is the wrong suggestion.
End on a steady note rather than a cheerful one.

ALWAYS FORBIDDEN:
- Never promise that things will get better or that this will pass.
- Never diagnose anything, and never give medical or medication advice.
- Never tell them to think positive, be grateful, or that their pain is an illusion.
- Never say you are an AI unless they ask directly, and never lecture."""

_SUPPORT_TAIL = """Gita verses that may fit this person, already in plain words. Use at most one, and only if it genuinely fits:
{anchors}

Additional retrieved context from the Gita:
{context}

[[HISTORY]]They wrote:
{question}

Your reply, 60 to 90 words, warm and plain:"""


def _support_body(cls_key: str) -> str:
    cls = CLASSES[cls_key]
    persona = (
        "WHO YOU ARE SPEAKING TO RIGHT NOW:\n"
        + _safe(cls["tone"])
        + "\n\nFOR THIS PERSON, ADDITIONALLY NEVER:\n"
        + _safe(cls["avoid"])
    )
    return "\n\n".join([
        _SUPPORT_HEAD,
        persona,
        _SUPPORT_TAIL.replace("{anchors}", _safe(get_anchor_block(cls_key))),
    ])


# ──────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────

def analyse(question: str, user_class: str = "auto", lang: str = DEFAULT_LANG,
            has_history: bool = False):
    """Return (PromptTemplate, meta).

    meta: {"intent", "user_class", "needs_rag", "lang", "has_history"}
    """
    q = question or ""
    lg = normalise_lang(lang)
    forced = (user_class or "auto").strip().lower()

    def out(body, intent, cls, needs_rag, with_context):
        # Off-topic ka jawab pichhli baaton se nahi badalta — wahan history
        # bhejna sirf tokens jalana hai.
        use_hist = has_history and intent != "offtopic"
        variables = ["question"]
        if with_context:
            variables.insert(0, "context")
        if use_hist:
            variables.append("history")
        return (
            PromptTemplate(input_variables=variables,
                           template=_render(body, lg, use_hist)),
            {"intent": intent, "user_class": cls, "needs_rag": needs_rag,
             "lang": lg, "has_history": use_hist},
        )

    if forced in CLASSES and forced != "general":
        return out(_support_body(forced), "support", forced, True, True)

    intent = detect_intent(q)

    if intent == "greeting":
        return out(_GREETING_BODY, "greeting", "greeting", False, False)
    if intent == "offtopic":
        return out(_OFFTOPIC_BODY, "offtopic", "offtopic", False, False)
    if intent == "study":
        return out(_STUDY_BODY, "study", "seeking", True, True)

    cls = detect_class(q)
    if cls == "general":
        return out(_GENERAL_BODY, "general", "general", False, False)

    return out(_support_body(cls), "support", cls, True, True)


def build_prompt(question: str = "", user_class: str = "auto", lang: str = DEFAULT_LANG):
    prompt, meta = analyse(question, user_class, lang)
    return prompt, meta["user_class"]


def get_prompt_template(user_class: str = "auto", lang: str = DEFAULT_LANG) -> PromptTemplate:
    prompt, _ = analyse("", user_class, lang)
    return prompt


def public_langs() -> list:
    return [{"id": k, "label": v["label"]} for k, v in LANGS.items()]


def format_history(messages) -> str:
    """[{role, text}] -> prompt me daalne layak plain transcript."""
    if not messages:
        return ""
    lines = []
    for m in messages:
        who = "Them" if m.get("role") == "user" else "You"
        text = (m.get("text") or "").strip().replace("\n", " ")
        if text:
            lines.append(f"{who}: {text[:400]}")
    return "\n".join(lines)
