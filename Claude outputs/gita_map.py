"""
RagGita — emotion ↔ shloka mapping.

Har verse holy-bhagavad-gita.org se manually verify kiya gaya hai (Sept 2026).
Gloss deliberately plain hai — depressed user ke liye "translated", not "quoted".

Yeh file akeli source of truth hai. Naya verse add karna ho toh:
  1. VERSES me entry daalo (ref, sanskrit, translation, gloss)
  2. CLASSES ke anchors list me ref add kar do
api.py / prompts.py ko chhune ki zaroorat nahi.
"""

# ──────────────────────────────────────────────────────────────
# VERSE BANK
# ──────────────────────────────────────────────────────────────
# gloss = ek line, everyday English, jo ek thake hue insaan ko samajh aaye.

VERSES = {
    "2.14": {
        "sanskrit": "mātrā-sparśhās tu kaunteya śhītoṣhṇa-sukha-duḥkha-dāḥ",
        "translation": "Contact with the world gives fleeting cold and heat, pleasure and pain. These come and go like seasons; learn to bear them.",
        "gloss": "What you feel right now arrived, and it moves. It is weather passing through you, not the whole of who you are.",
    },
    "2.22": {
        "sanskrit": "vāsānsi jīrṇāni yathā vihāya navāni gṛihṇāti naro 'parāṇi",
        "translation": "As a person sheds worn-out garments and puts on new ones, so the soul casts off a worn-out body.",
        "gloss": "What was truly them was never the body that wore out. Something was set down, not lost.",
    },
    "2.47": {
        "sanskrit": "karmaṇy-evādhikāras te mā phaleṣhu kadāchana",
        "translation": "You have a right to your work, but never to its fruits. Do not be the cause of results, nor be attached to inaction.",
        "gloss": "The doing is yours. The outcome was never in your hands. Do the next honest thing and put the result down.",
    },
    "2.56": {
        "sanskrit": "duḥkheṣhv-anudvigna-manāḥ sukheṣhu vigata-spṛihaḥ",
        "translation": "One whose mind is undisturbed in sorrow, who does not crave pleasure, free from attachment, fear and anger, is steady in wisdom.",
        "gloss": "Steadiness is not feeling nothing. It is not being dragged off by every wave that comes.",
    },
    "2.62": {
        "sanskrit": "dhyāyato viṣhayān puṁsaḥ saṅgas teṣhūpajāyate",
        "translation": "Dwelling on objects breeds attachment; from attachment comes desire; from desire comes anger.",
        "gloss": "Anger rarely starts as anger. It starts as replaying something in your head until it hardens.",
    },
    "2.70": {
        "sanskrit": "āpūryamāṇam achala-pratiṣhṭhaṁ samudram āpaḥ praviśhanti yadvat",
        "translation": "As rivers pour endlessly into the ocean and it remains still, so peace comes to one who is unmoved by the flow of desires.",
        "gloss": "Rivers keep pouring in; the ocean stays level. You can let things reach you without being flooded by them.",
    },
    "3.35": {
        "sanskrit": "śhreyān swa-dharmo viguṇaḥ para-dharmāt sv-anuṣhṭhitāt",
        "translation": "Better one's own duty done imperfectly than another's duty done well.",
        "gloss": "Your own path walked badly beats someone else's walked perfectly. The comparison itself is the wrong measure.",
    },
    "6.5": {
        "sanskrit": "uddhared ātmanātmānaṁ nātmānam avasādayet",
        "translation": "Elevate yourself by your own mind; do not degrade yourself. The mind can be the friend and also the enemy of the self.",
        "gloss": "The same mind can lift you or bury you. Right now it may be running as your enemy — that is a setting, not a verdict on you.",
    },
    "6.16": {
        "sanskrit": "nātyaśhnatastu yogo 'sti na chaikāntam anaśhnataḥ",
        "translation": "Those who eat too much or too little, sleep too much or too little, cannot attain success in yoga.",
        "gloss": "Too much sleep or too little, too much food or none — the extremes make steadiness impossible. This is not a moral failing, it is mechanics.",
    },
    "6.17": {
        "sanskrit": "yuktāhāra-vihārasya yukta-cheṣhṭasya karmasu ... yogo bhavati duḥkha-hā",
        "translation": "For one measured in eating and rest, balanced in work and regulated in sleep, yoga becomes the destroyer of sorrow.",
        "gloss": "Measured food, measured rest, measured work — the Gita calls this the destroyer of sorrow. Small ordinary order, not grand effort.",
    },
    "6.26": {
        "sanskrit": "yato yato niśhcharati manaśh chañchalam asthiram",
        "translation": "Wherever the restless, unsteady mind wanders, bring it back and steady it again.",
        "gloss": "The mind wanders off. You bring it back. It wanders again. Bringing it back *is* the practice — not a sign you are failing at it.",
    },
    "6.32": {
        "sanskrit": "ātmaupamyena sarvatra samaṁ paśhyati yo 'rjuna",
        "translation": "The highest yogi sees all beings as equal to the self, and feels their joy and sorrow as their own.",
        "gloss": "You are asked to treat others' pain as your own. That instruction points both ways — you are one of the beings owed that kindness.",
    },
    "6.35": {
        "sanskrit": "asanśhayaṁ mahā-bāho mano durnigrahaṁ chalam / abhyāsena tu kaunteya vairāgyeṇa cha gṛihyate",
        "translation": "Undoubtedly the mind is restless and hard to restrain; but by practice and detachment it can be held.",
        "gloss": "Krishna does not argue that it is easy. He agrees it is hard, then says it still yields — slowly, by repetition.",
    },
    "9.22": {
        "sanskrit": "teṣhāṁ nityābhiyuktānāṁ yoga-kṣhemaṁ vahāmyaham",
        "translation": "To those constantly devoted, I provide what they lack and preserve what they have.",
        "gloss": "What you cannot carry right now, you are not the only one carrying. Something holds the part you have dropped.",
    },
    "12.13": {
        "sanskrit": "adveṣhṭā sarva-bhūtānāṁ maitraḥ karuṇa eva cha ... kṣhamī",
        "translation": "Free from malice, friendly, compassionate, without egotism, even in pain and pleasure, and ever-forgiving — such a one is dear to Me.",
        "gloss": "Forgiving is listed as a quality worth having. Nobody said the list excludes forgiving yourself.",
    },
    "18.58": {
        "sanskrit": "mach-chittaḥ sarva-durgāṇi mat-prasādāt tariṣhyasi",
        "translation": "Fixing your mind on Me, you shall cross over all difficulties by My grace.",
        "gloss": "You are not asked to remove the hard passage. You are told it can be crossed.",
    },
}


# ──────────────────────────────────────────────────────────────
# CLASSES — yeh hi tumhare "multiple interfaces" hain
# ──────────────────────────────────────────────────────────────
# label      : UI chip pe kya dikhega
# emoji      : chip icon
# anchors    : iss class ke liye preferred verses (prompt me inject honge)
# tone       : persona instruction, prompt me literally jaata hai
# avoid      : negative constraints — depressed user ke liye yeh critical hai
# cues       : auto-detect keywords (user "Auto" chune toh)

CLASSES = {
    "low": {
        "label": "Feeling low",
        "emoji": "🌑",
        "anchors": ["6.5", "6.16", "6.17", "6.35", "2.14"],
        "tone": (
            "They are flat, heavy, or empty. Energy is the scarce resource, not insight. "
            "Match their register - quiet and level, never bright or motivating. "
            "Your one suggestion must be almost embarrassingly small: something that takes "
            "under a minute, needs no decision and no leaving the room. "
            "Build it out of the specific thing they described. "
            "Do not fall back on a stock suggestion - if it would fit any stranger equally "
            "well, it is the wrong one."
        ),
        "avoid": (
            "Do not encourage them to be strong, to fight, or to push through. "
            "Do not mention gratitude or silver linings. Do not call this a lesson or a test."
        ),
        "cues": [
            "empty", "numb", "nothing matters", "no energy", "tired all the time",
            "feel low", "feeling low", "feel down", "feeling down", "feel heavy",
            "udaas", "mann bhari", "dil bhari", "उदास", "मन नहीं", "कुछ अच्छा नहीं",
            "out of bed", "pointless", "worthless", "hate myself", "burden",
            "kuch acha nahi", "mann nahi", "thak gaya", "bekar", "bekaar",
        ],
    },
    "anxious": {
        "label": "Anxious",
        "emoji": "🌀",
        "anchors": ["2.47", "6.26", "6.35", "2.70"],
        "tone": (
            "Their mind is racing ahead into outcomes that have not happened. "
            "Speak slowly and concretely. Bring them back to the one action in front of them today, "
            "and separate that action from its result."
        ),
        "avoid": (
            "Do not tell them to relax or stop worrying. Do not list breathing techniques as a lecture. "
            "Do not predict that the outcome will be fine - you do not know that."
        ),
        "cues": [
            "anxious", "anxiety", "panic", "worried", "worry", "overthink",
            "what if", "exam", "interview", "result", "future", "scared of failing",
            "tension", "ghabra", "dar lag",
        ],
    },
    "grief": {
        "label": "Grief / loss",
        "emoji": "🕯️",
        "anchors": ["2.22", "2.14", "12.13"],
        "tone": (
            "Someone or something is gone. Stay with them in it. "
            "Grief is not a problem to be solved, so do not solve it. "
            "Your small step should be an act of remembering, not of moving on."
        ),
        "avoid": (
            "Never say they should not grieve, that the soul is eternal so this does not matter, "
            "that it was meant to be, or that they are in a better place. "
            "Do not rush them toward acceptance."
        ),
        "cues": [
            "died", "death", "passed away", "lost my", "funeral", "miss them",
            "miss him", "miss her", "grief", "breakup", "broke up", "left me",
            "guzar gaye", "nahi rahe", "chala gaya",
        ],
    },
    "lonely": {
        "label": "Lonely",
        "emoji": "🌊",
        "anchors": ["9.22", "12.13", "6.32"],
        "tone": (
            "They feel unseen or alone. Do not perform closeness or claim to be their friend. "
            "Acknowledge the isolation plainly, then point at one small real-world thread - "
            "a message they could send, a person they could sit near."
        ),
        "avoid": (
            "Do not say you are always here for them or imply you can replace human contact. "
            "Do not tell them to just reach out, as if that were easy."
        ),
        "cues": [
            "lonely", "alone", "no one", "nobody", "no friends", "isolated",
            "nobody cares", "unseen", "akela", "koi nahi",
        ],
    },
    "angry": {
        "label": "Angry",
        "emoji": "🔥",
        "anchors": ["2.62", "2.56", "6.26"],
        "tone": (
            "There is heat here, and often hurt underneath it. Do not moralise about anger. "
            "Name it as legitimate first, then show the chain the Gita describes - "
            "replaying, attachment, craving, anger - so they can see the mechanism rather than be scolded for it."
        ),
        "avoid": (
            "Do not tell them anger is wrong, sinful, or beneath them. "
            "Do not ask them to forgive anyone today."
        ),
        "cues": [
            "angry", "anger", "furious", "hate", "unfair", "betrayed", "cheated",
            "resent", "revenge", "gussa", "dhokha",
        ],
    },
    "lost": {
        "label": "Lost / no direction",
        "emoji": "🧭",
        "anchors": ["3.35", "2.47", "18.58"],
        "tone": (
            "They cannot see a path, or they are measuring themselves against other people. "
            "This is Arjuna's actual situation at the start of the Gita, so treat it as a normal place to be, not a failure. "
            "Point at their own next step, not at a five-year plan."
        ),
        "avoid": (
            "Do not tell them to follow their passion or that everything happens for a reason. "
            "Do not compare them favourably to others - that keeps the same measuring stick."
        ),
        "cues": [
            "lost", "no direction", "confused", "don't know what", "dont know what",
            "purpose", "meaning", "career", "everyone else", "behind", "comparison",
            "samajh nahi", "kya karu", "kya karoon",
            # comparison-with-peers phrasings (live testing me yeh miss ho rahe the)
            "everyone in my", "everyone has", "everybody has", "already has",
            "already got", "i have nothing", "nothing to show", "falling behind",
            "left behind", "compared to", "ahead of me", "sabke paas",
            "mere paas kuch nahi", "peeche reh",
        ],
    },
    "general": {
        "label": "Just talking",
        "emoji": "🌿",
        "anchors": ["2.14", "6.26", "2.47"],
        "tone": (
            "You do not yet know what they are carrying, and they have not told you. "
            "Respond to what they actually said and nothing more. "
            "If their message is unclear or very short, it is better to ask one simple, "
            "unhurried question than to guess at a feeling. "
            "Stay warm and level."
        ),
        "avoid": (
            "Do not assume they are sad, low, anxious or struggling - you have no evidence of that. "
            "Do not name a feeling they did not describe. "
            "Do not offer a coping step for a problem they have not mentioned."
        ),
        "cues": [],
    },
    "seeking": {
        "label": "Just curious",
        "emoji": "📖",
        "anchors": [],
        "tone": (
            "This is a question about the text itself, not a cry for help. "
            "You may be a little more expansive and precise here, and Sanskrit terms are welcome. "
            "Answer the actual question asked."
        ),
        "avoid": (
            "Do not assume they are in distress and do not offer emotional comfort they did not ask for."
        ),
        "cues": [
            "what does the gita say", "which chapter", "explain", "meaning of",
            "krishna said", "arjuna", "verse", "shloka", "sloka", "chapter",
        ],
    },
}

DEFAULT_CLASS = "low"


def get_anchor_block(user_class: str) -> str:
    """Prompt me daalne layak formatted anchor verses."""
    cls = CLASSES.get(user_class, CLASSES[DEFAULT_CLASS])
    refs = cls.get("anchors", [])
    if not refs:
        return "(none - rely on the retrieved context below)"

    lines = []
    for ref in refs:
        v = VERSES.get(ref)
        if not v:
            continue
        lines.append(f"- Gita {ref}: {v['gloss']}")
    return "\n".join(lines) if lines else "(none)"


def public_classes() -> list:
    """Frontend ke liye — tone/avoid/cues expose nahi karte."""
    return [
        {"id": key, "label": val["label"], "emoji": val["emoji"]}
        for key, val in CLASSES.items()
    ]
