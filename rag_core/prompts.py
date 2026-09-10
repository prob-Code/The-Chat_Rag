"""
RagGita — prompt layer (v2).

Ek hi jagah pe: response length/tone, per-class dynamic prompting,
emotion auto-detection, aur crisis safety guard.

Usage in api.py:
    from rag_core.prompts import (
        build_prompt, detect_class, is_crisis, CRISIS_REPLY,
    )
"""

import re
from langchain_core.prompts import PromptTemplate

from rag_core.gita_map import (
    CLASSES,
    DEFAULT_CLASS,
    get_anchor_block,
)


# ──────────────────────────────────────────────────────────────
# BASE RULES — har class pe lagte hain
# ──────────────────────────────────────────────────────────────
# NOTE: final template me sirf {context} aur {question} placeholders bachne chahiye.
# Isliye persona/anchor text insert karne se pehle _safe() se braces strip karte hain.

_BASE_HEAD = """You are RagGita, a gentle companion who draws on the Bhagavad Gita.

The person writing to you may be depressed, anxious, or exhausted. A long reply feels like one more task to them. Short is kind.

HARD LIMITS:
- 60 to 90 words. Never longer.
- Flowing sentences only. No headings, no bullet points, no bold text, no numbered steps.
- One idea only. Do not stack multiple teachings together.
- Plain everyday language. No Sanskrit words unless the person used them first.
- Mention a chapter or verse number at most once, and only if it appears below.

WHAT TO WRITE, as three or four plain sentences:
First, name what they seem to be feeling, simply and without judgement.
Then one thought from the Gita, translated into ordinary words a tired person can actually hold.
Then one small concrete thing they could do today, something that takes under ten minutes.
End on a steady note rather than a cheerful one.

ALWAYS FORBIDDEN:
- Never promise that things will get better or that this will pass.
- Never diagnose anything, and never give medical or medication advice.
- Never tell them to think positive, be grateful, or that their pain is an illusion.
- Never say you are an AI, and never lecture."""

_BASE_TAIL = """Gita verses most relevant to this person right now, already in plain words. Prefer these, and use at most one:
{anchors}

Additional retrieved context from the Gita:
{context}

They wrote:
{question}

Your reply, 60 to 90 words, warm and plain:"""


def _safe(text: str) -> str:
    """Curly braces hata do, warna PromptTemplate unhe placeholder samjhega."""
    return (text or "").replace("{", "(").replace("}", ")")


# ──────────────────────────────────────────────────────────────
# AUTO-DETECT
# ──────────────────────────────────────────────────────────────

def detect_class(text: str) -> str:
    """Message se emotion class guess karo. Cheap keyword scoring — no extra LLM call.

    Tie ya kuch match na ho toh DEFAULT_CLASS.
    """
    if not text:
        return DEFAULT_CLASS

    lowered = text.lower()
    scores = {}

    for key, cls in CLASSES.items():
        score = 0
        for cue in cls.get("cues", []):
            if cue in lowered:
                # Lambe cues zyada specific hote hain, unhe zyada weight
                score += 2 if len(cue) > 12 else 1
        if score:
            scores[key] = score

    if not scores:
        return DEFAULT_CLASS

    return max(scores.items(), key=lambda kv: kv[1])[0]


def resolve_class(user_class: str, question: str) -> str:
    """UI se aayi class ko normalize karo. 'auto' ya unknown -> detect."""
    key = (user_class or "auto").strip().lower()
    if key in CLASSES:
        return key
    return detect_class(question)


# ──────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ──────────────────────────────────────────────────────────────

def build_prompt(question: str = "", user_class: str = "auto"):
    """Return (PromptTemplate, resolved_class).

    `question` sirf detection ke liye padha jaata hai — template me embed nahi hota,
    woh {question} placeholder hi rehta hai (user input se prompt injection na ho).
    """
    resolved = resolve_class(user_class, question)
    cls = CLASSES[resolved]

    persona_block = (
        "WHO YOU ARE SPEAKING TO RIGHT NOW:\n"
        + _safe(cls["tone"])
        + "\n\nFOR THIS PERSON, ADDITIONALLY NEVER:\n"
        + _safe(cls["avoid"])
    )

    template = "\n\n".join([
        _BASE_HEAD,
        persona_block,
        _BASE_TAIL.replace("{anchors}", _safe(get_anchor_block(resolved))),
    ])

    return PromptTemplate(
        input_variables=["context", "question"],
        template=template,
    ), resolved


def get_prompt_template(user_class: str = "auto") -> PromptTemplate:
    """Backward-compatible helper (streaming endpoint isko use karta hai)."""
    tmpl, _ = build_prompt("", user_class)
    return tmpl


# ──────────────────────────────────────────────────────────────
# CRISIS GUARD
# ──────────────────────────────────────────────────────────────
# Depression-facing app hai, so yeh non-negotiable hai.
# Deliberately BROAD — false positive chalega, false negative nahi.

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
    """True agar message me self-harm / suicide ka signal hai."""
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
