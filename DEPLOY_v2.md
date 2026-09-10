# RagGita v2 — deploy checklist

## 1. Files

| File | Kahan jaayega | Naya ya replace |
|---|---|---|
| `gita_map.py` | `rag_core/gita_map.py` | **naya** |
| `prompts.py` | `rag_core/prompts.py` | **replace** (v1 wala overwrite kar do) |
| `config.py` | `rag_core/config.py` | replace |
| `api.py` | `api.py` | replace |
| `index.html` | `static/index.html` | replace |

`requirements.txt` me kuch add nahi karna — `openai` package already `langchain-openai` ke saath aata hai.

## 2. Space variables

Jo pehle se hain unke alawa yeh add karo (Settings → Variables and secrets):

| Type | Name | Value |
|---|---|---|
| Variable | `LLM_MAX_TOKENS` | `220` |
| Variable | `MAX_CONTEXT_CHARS` | `2500` |
| Variable | `FAST_TOP_K` | `3` |
| Variable | `LLM_TEMPERATURE` | `0.6` |
| Variable | `ENABLE_TTS` | `true` |
| Variable | `TTS_VOICE` | `sage` |
| Variable | `TTS_MODEL` | `gpt-4o-mini-tts` |

Voice change karni ho toh `TTS_VOICE` me: `alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar`.
Tone badalni ho toh `TTS_INSTRUCTIONS` variable add kar do — plain English me likho, model follow karta hai.

## 3. Test karo

**Class routing** — chip "Auto" pe rakh ke yeh type karo, har ek alag persona hit karna chahiye:

| Type this | Expected class |
|---|---|
| `I can't get out of bed, nothing matters` | low |
| `so anxious about my placement interview` | anxious |
| `my father passed away last month` | grief |
| `nobody cares about me` | lonely |
| `he betrayed me, I'm furious` | angry |
| `everyone else is ahead of me` | lost |
| `what does chapter 3 say about karma` | seeking |

Response me `user_class` field aata hai — `/docs` pe check kar sakte ho kaunsa class laga.

**Crisis guard** — `I want to end my life` bhejo. LLM call honi hi nahi chahiye (logs me "Crisis guard triggered"), aur helpline wala green bubble aana chahiye.

**Voice** — mic button dabao, bolo, auto-send hoga aur reply bol ke sunayega. Speaker icon on karoge toh typed questions ke replies bhi bolega.

## 4. Endpoints (naye)

- `GET /classes` → chip list + `tts_enabled` flag
- `POST /tts` → `{"text": "..."}` → mp3 bytes
- `POST /chat` ab `{"question": "...", "user_class": "anxious"}` leta hai; `user_class` optional hai, default `auto`
