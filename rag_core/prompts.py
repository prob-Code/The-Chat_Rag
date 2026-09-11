"""
RagGita — prompt layer (v3).

v2 me ek badi galti thi: har input therapeutic saanche me chala jaata tha.
"hi" ka jawab bhi "It sounds like you're feeling heavy and empty..." aata tha,
kyunki:
  1. DEFAULT_CLASS "low" tha — jo match na ho woh depression persona me girta tha
  2. persona me literal examples likhe the ("a glass of water") — model copy karta tha
  3. base prompt har message pe ek hi 4-hisse ka shape thopta tha

v3 me class decide karne se PEHLE intent decide hota hai. Therapeutic shape
sirf tab lagta hai jab sach me emotional signal ho.

    crisis    -> helpline, koi model call nahi
    greeting  -> chhota warm jawab, na verse na step, RAG bhi nahi
    offtopic  -> imaandar redirect, RAG nahi
    study     -> Gita ke baare me sawaal, seedha jawab
    support   -> class detection + therapeutic shape (v2 wala behaviour)

api.py sirf analyse() bulata hai.
"""

import re
from langchain_core.prompts import PromptTemplate

from rag_core.gita_map import CLASSES, get_anchor_block


# ──────────────────────────────────────────────────────────────
# INTENT DETECTION
# ──────────────────────────────────────────────────────────────

_GREETING_RE = re.compile(
    r"^\s*(hi+|hey+|hello+|yo|namaste|namaskar|pranam|hii+|helo+|"
    r"good\s*(morning|afternoon|evening|night)|"
    r"thanks?|thank\s*you|thx|ok|okay|k|hmm+|bye|goodbye|see\s*you|"
    r"gn|gm|kaise\s*ho|kya\s*haal|theek\s*hai|accha|acha)"
    r"[\s!.,?]*$",
    re.IGNORECASE,
)

# Sawaal jo iss app ke liye hain hi nahi
_OFFTOPIC_RE = re.compile(
    r"\b(what(?:'s| is)? the (time|date|weather)|what time is it|"
    r"which model|what model|are you (chatgpt|gpt|ai|a bot|human)|who (made|built|created) you|"
    r"tell me a joke|calculate|solve this|translate this|"
    r"kitne baje|aaj ki date|mausam)\b",
    re.IGNORECASE,
)

# Gita ke text ke baare me sawaal
_STUDY_RE = re.compile(
    r"\b(chapter|verse|shloka|sloka|adhyay|what does the gita say|"
    r"meaning of|explain|krishna said|arjuna|arjun|bhagavad|"
    r"karma yoga|bhakti|moksha|dharma means)\b",
    re.IGNORECASE,
)


def _has_emotional_signal(text: str) -> bool:
    """Kya iss message me kisi bhi class ka cue hai?"""
    lowered = (text or "").lower()
    for cls in CLASSES.values():
        for cue in cls.get("cues", []):
            if cue in lowered:
                return True
    return False


def detect_intent(text: str) -> str:
    """greeting | offtopic | study | support"""
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
    """Emotion class. Koi cue na mile toh 'general' — 'low' NAHI.

    Yeh v2 ka sabse bada bug tha: bina kisi signal ke bhi app maan leta tha
    ki saamne wala depressed hai.
    """
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


# — Light templates: koi Gita context nahi, koi thopa hua shape nahi —

GREETING_TEMPLATE = """You are RagGita, a gentle companion who draws on the Bhagavad Gita.

Someone has just greeted you or said something small. Greet them back like a person would.

RULES:
- One or two sentences. Under 30 words.
- Do not quote the Gita. Do not offer a teaching. Do not suggest a small step.
- Do not assume they are sad, low, or struggling. You do not know that yet.
- Sound warm and unhurried, not chirpy. No exclamation marks.
- Leave the door open without pressing. Vary your wording each time.

They said:
{question}

Your reply:"""


OFFTOPIC_TEMPLATE = """You are RagGita, a companion who draws on the Bhagavad Gita.

Someone has asked something this app cannot help with - the time, the weather, a calculation,
or a question about what you are.

RULES:
- Two sentences at most.
- Be honest and plain that this is not something you can help with. Do not apologise repeatedly.
- Do not quote the Gita and do not invent an answer.
- Say in one short clause what you are here for, then stop.
- Never claim to be human. If asked what you are, say plainly that you are an AI companion.

They asked:
{question}

Your reply:"""


STUDY_TEMPLATE = """You are RagGita, answering a question about the Bhagavad Gita itself.

This is a question about the text, not a person in distress. Answer the actual question.

RULES:
- Under 100 words.
- Plain prose. Sanskrit terms are welcome here.
- Cite a chapter and verse only if it appears in the context below.
- Do not offer emotional comfort they did not ask for, and do not suggest a small step.
- If the context below does not cover it, say what you do know briefly and say the rest is outside what you have.

Context from the Gita:
{context}

Their question:
{question}

Your answer:"""


# — Support template: therapeutic shape, sirf yahan —

_SUPPORT_HEAD = """You are RagGita, a gentle companion who draws on the Bhagavad Gita.

The person writing to you may be low, anxious, or exhausted. A long reply feels like one more task to them. Short is kind.

HARD LIMITS:
- 60 to 90 words. Never longer.
- Flowing sentences only. No headings, no bullet points, no bold text, no numbered steps.
- One idea only. Do not stack multiple teachings together.
- Plain everyday language. No Sanskrit words unless the person used them first.
- Mention a chapter or verse number at most once, and only if it appears below.

SHAPE, as three or four plain sentences:
Name what they seem to be feeling, simply and without judgement - but only if they have actually told you something about how they feel. If they have not, do not invent a feeling for them.
Then one thought from the Gita, translated into ordinary words a tired person can hold.
Then one small concrete thing they could do today. It must come out of what THEY said - their situation, their day, their words. Never reach for a generic suggestion.
End on a steady note rather than a cheerful one.

ALWAYS FORBIDDEN:
- Never promise that things will get better or that this will pass.
- Never diagnose anything, and never give medical or medication advice.
- Never tell them to think positive, be grateful, or that their pain is an illusion.
- Never say you are an AI unless they ask directly, and never lecture.
- Never reuse a suggestion you would give to anyone. If the step would fit a stranger equally well, it is the wrong step."""

_SUPPORT_TAIL = """Gita verses that may fit this person, already in plain words. Use at most one, and only if it genuinely fits:
{anchors}

Additional retrieved context from the Gita:
{context}

They wrote:
{question}

Your reply, 60 to 90 words, warm and plain:"""


def _support_template(cls_key: str) -> str:
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
# SINGLE ENTRY POINT
# ──────────────────────────────────────────────────────────────

def analyse(question: str, user_class: str = "auto"):
    """Return (PromptTemplate, meta dict).

    meta: {"intent": ..., "user_class": ..., "needs_rag": bool}

    api.py isse ek hi baar bulata hai. Agar needs_rag False hai toh
    retrieval skip karo — embedding call aur FAISS search dono bach jaate hain,
    aur model ko woh verses milte hi nahi jinhe woh zabardasti ghusa deta.
    """
    q = question or ""
    forced = (user_class or "auto").strip().lower()

    # User ne UI me khud class chuni hai -> use respect karo, intent skip
    if forced in CLASSES:
        return (
            PromptTemplate(input_variables=["context", "question"],
                           template=_support_template(forced)),
            {"intent": "support", "user_class": forced, "needs_rag": True},
        )

    intent = detect_intent(q)

    if intent == "greeting":
        return (
            PromptTemplate(input_variables=["question"], template=GREETING_TEMPLATE),
            {"intent": "greeting", "user_class": "greeting", "needs_rag": False},
        )

    if intent == "offtopic":
        return (
            PromptTemplate(input_variables=["question"], template=OFFTOPIC_TEMPLATE),
            {"intent": "offtopic", "user_class": "offtopic", "needs_rag": False},
        )

    if intent == "study":
        return (
            PromptTemplate(input_variables=["context", "question"], template=STUDY_TEMPLATE),
            {"intent": "study", "user_class": "seeking", "needs_rag": True},
        )

    cls = detect_class(q)
    return (
        PromptTemplate(input_variables=["context", "question"],
                       template=_support_template(cls)),
        {"intent": "support", "user_class": cls, "needs_rag": True},
    )


# Purana naam, taaki /chat/stream na toote
def build_prompt(question: str = "", user_class: str = "auto"):
    prompt, meta = analyse(question, user_class)
    return prompt, meta["user_class"]


def get_prompt_template(user_class: str = "auto") -> PromptTemplate:
    prompt, _ = analyse("", user_class)
    return prompt


# ──────────────────────────────────────────────────────────────
# CRISIS GUARD  (v2 se badla nahi)
# ──────────────────────────────────────────────────────────────

_CRISIS_PATTERNS = [
    r"\bkill (?:myself|me)\b",
    r"\bkilling myself\b",
    r"\bend (?:my life|it all|myself)\b",
    r"\bsuicid",
    r"\bwant to die\b",
    r"\bwanna die\b",
    r"\bbetter off dead\b",
    r"\bno reason to live\b",
    r"\bdon'?t want to (?:live|be here|wake up|exist)\b",
    r"\bcut(?:ting)? myself\b",
    r"\bhurt(?:ing)? myself\b",
    r"\bself[- ]harm\b",
    r"\boverdose\b",
    r"\bjump off\b",
    r"\bhang myself\b",
    r"\bmar jau", r"\bmarna hai\b", r"\bjeena nahi\b", r"\bjeene ka mann nahi\b",
    r"\bkhudkushi\b", r"\batmahatya\b", r"\bzindagi khatam\b",
]

_CRISIS_RE = re.compile("|".join(_CRISIS_PATTERNS), re.IGNORECASE)


def is_crisis(text: str) -> bool:
    if not text:
        return False
    return bool(_CRISIS_RE.search(text))


CRISIS_REPLY = (
    "I'm glad you told me this, and I don't want to answer it with a verse. "
    "What you're carrying sounds too heavy to hold on your own right now.\n\n"
    "Please talk to a person today. **Tele-MANAS** is free, 24/7, in English and 20 Indian "
    "languages — call **14416** or **1800-891-4416**. "
    "If you are in immediate danger, call **112**.\n\n"
    "I'll still be here afterwards, whenever you want to talk."
)
