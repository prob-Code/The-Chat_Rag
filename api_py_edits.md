# api.py — 4 chhote edits

`api.py` bada hai (16 KB), isliye poori file replace mat karo. Sirf yeh 4 blocks badlo.
Har edit me **DHOONDO** wala text file me search karo, aur **BADLO** wale se replace karo.

---

## Edit 1 — import add karo

**DHOONDO** (line ~33 ke aas-paas):

```python
from rag_core.config import LightRAGConfig, get_llm
from rag_core.streaming import TokenQueueCallbackHandler
```

**BADLO:**

```python
from rag_core.config import LightRAGConfig, get_llm
from rag_core.streaming import TokenQueueCallbackHandler
from rag_core.prompts import get_prompt_template, is_crisis, CRISIS_REPLY
```

---

## Edit 2 — purana lamba prompt hatao

`lifespan()` ke andar `# 4. Create prompt template` comment se lekar us poore
`prompt_template = PromptTemplate(...)` block ke closing `)` tak — **sab delete karo**
(woh ~40 lines ka "You are a compassionate spiritual guide..." wala block).

Uski jagah sirf yeh 2 lines:

```python
        # 4. Create prompt template (short + gentle; personas rag_core/prompts.py me)
        prompt_template = get_prompt_template("default")
```

> Indentation dhyan se — `lifespan()` ke andar hai, so 8 spaces.

`PromptTemplate` ka import ab api.py me use nahi hoga, but usse chhodo — harmless hai.

---

## Edit 3 — crisis guard in `/chat`

**DHOONDO** (`chat_endpoint` ke andar):

```python
    try:
        # Retrieve relevant context
        docs = retriever.invoke(request.question)
```

**BADLO:**

```python
    try:
        # Safety first — self-harm signal pe verse nahi, help chahiye
        if is_crisis(request.question):
            return ChatResponse(answer=CRISIS_REPLY, sources=[])

        # Retrieve relevant context
        docs = retriever.invoke(request.question)
```

---

## Edit 4 — same guard in `/chat_fast`

**DHOONDO** (`chat_fast_endpoint` ke andar):

```python
    try:
        if not _llm_ping():
```

**BADLO:**

```python
    try:
        if is_crisis(request.question):
            return ChatResponse(answer=CRISIS_REPLY, sources=[])

        if not _llm_ping():
```

---

## Bonus — footer text (`static/index.html`)

**DHOONDO:**

```html
Powered by Bhagavad Gita Wisdom <span>•</span> Built with RAG + Groq
```

**BADLO:**

```html
Powered by Bhagavad Gita Wisdom <span>•</span> Built with RAG + OpenAI
```
