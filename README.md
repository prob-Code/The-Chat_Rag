

<div align="center">

# 🕉️ RagGita

### Your Compassionate Spiritual Guide

*A RAG-powered AI chatbot that shares the timeless wisdom of the Bhagavad Gita with empathy and clarity.*

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-Hugging_Face-yellow?style=for-the-badge)](https://huggingface.co/spaces/AgentCrafter/RAg_gita)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com)

</div>

---

## ✨ Features

| Feature | Description |
| :--- | :--- |
| 📚 **Semantic Search** | Searches through Bhagavad Gita verses using FAISS vector similarity |
| 🤖 **AI-Powered Answers** | Generates compassionate, context-aware responses via Groq (Llama 3.1) |
| 💬 **Premium Chat UI** | Dark glassmorphism interface with Markdown rendering |
| ⚡ **Streaming Responses** | Real-time token-by-token streaming via Server-Sent Events |
| 🌐 **REST API** | Clean JSON API — easily integrable into any website or app |
| 🐳 **Dockerized** | One-command deployment with Docker |

---

## 🖥️ Live Demo

The app is deployed on **Hugging Face Spaces** and accessible at:

> 🔗 **[https://agentcrafter-rag-gita.hf.space](https://agentcrafter-rag-gita.hf.space)**

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- A free [Groq API Key](https://console.groq.com/keys)

### 1. Clone & Install

```bash
git clone https://github.com/prob-Code/The-Chat_Rag.git
cd The-Chat_Rag

python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # macOS/Linux

pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your-groq-api-key
OPENAI_API_KEY=your-groq-api-key
LLM_MODEL=llama-3.1-8b-instant
OPENAI_API_BASE=https://api.groq.com/openai/v1
OPENAI_BASE_URL=https://api.groq.com/openai/v1

# Use HuggingFace Inference API for embeddings (saves ~400MB RAM)
USE_REMOTE_EMBEDDINGS=true
```

### 3. Run the Server

```bash
# Option 1: Startup script
python start_server.py

# Option 2: Uvicorn directly
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The app will be available at: **http://localhost:8000**

---

## 📡 API Reference

### Endpoints

| Method | Endpoint | Description |
| :---: | :--- | :--- |
| `GET` | `/` | Serves the chat UI |
| `GET` | `/health` | Health check (returns 503 until models are loaded) |
| `GET` | `/docs` | Swagger UI (interactive API docs) |
| `POST` | `/chat` | Send a question, get a response |
| `POST` | `/chat_fast` | Optimized endpoint with cached embeddings |
| `GET` | `/chat/stream?question=...` | Stream response tokens via SSE |

### Example — Chat Request

```bash
curl -X POST https://agentcrafter-rag-gita.hf.space/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How can I find inner peace?"}'
```

### Example — Response

```json
{
  "answer": "I hear you, and I want you to know that seeking peace is one of the bravest things...",
  "sources": []
}
```

### Example — JavaScript Integration

```javascript
const response = await fetch('https://agentcrafter-rag-gita.hf.space/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question: 'What does the Gita say about anxiety?' })
});

const data = await response.json();
console.log(data.answer);
```

---

## 🏗️ Architecture

```
User Question
     │
     ▼
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│   FastAPI     │────▶│  FAISS Vector   │────▶│  Top-K Gita  │
│   Server      │     │  Database       │     │  Passages     │
└──────────────┘     └─────────────────┘     └──────┬───────┘
                                                     │
                                                     ▼
                                              ┌──────────────┐
                                              │  Groq LLM    │
                                              │  (Llama 3.1) │
                                              └──────┬───────┘
                                                     │
                                                     ▼
                                              Compassionate
                                              AI Response
```

---

## 📁 Project Structure

```
RagGita/
├── api.py                  # FastAPI application (main entry point)
├── chat.py                 # Interactive CLI chat interface
├── ingest.py               # Script to build vector DB from PDF
├── start_server.py         # Server startup helper
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker container config
├── render.yaml             # Render.com deployment config
├── .env                    # Environment variables (not committed)
│
├── rag_core/               # Core RAG engine
│   ├── config.py           # LLM & embedding configuration
│   ├── bytez_llm.py        # Bytez LLM wrapper (fallback)
│   ├── streaming.py        # Token streaming callback handler
│   ├── prompts.py          # Prompt templates
│   └── gita_map.py         # Gita chapter/verse mapping
│
├── static/
│   └── index.html          # Premium dark-theme chat UI
│
├── gita_vector_db/         # Pre-built FAISS vector index
│   ├── index.faiss         # Vector index (~796 KB)
│   └── index.pkl           # Document chunks & metadata (~440 KB)
│
├── data/
│   └── bgita.pdf           # Source: Bhagavad Gita text
│
└── .github/workflows/
    ├── sync_to_hf_space.yml # Auto-sync GitHub → Hugging Face
    └── deploy.yml           # CI/CD pipeline
```

---

## 🛠️ Tech Stack

| Component | Technology |
| :--- | :--- |
| **Backend Framework** | FastAPI + Uvicorn |
| **LLM** | Groq — Llama 3.1 8B Instant |
| **Embeddings** | HuggingFace `all-MiniLM-L6-v2` (384-dim) |
| **Vector Store** | FAISS (Facebook AI Similarity Search) |
| **Orchestration** | LangChain |
| **Frontend** | Vanilla HTML/CSS/JS with Glassmorphism UI |
| **Deployment** | Docker → Hugging Face Spaces |
| **CI/CD** | GitHub Actions → HF Hub Sync |

---

## ☁️ Deployment

### Hugging Face Spaces (Recommended — Free)

The repository automatically syncs to Hugging Face Spaces via GitHub Actions on every push to `main`.

1. Fork this repo
2. Add `HF_TOKEN` secret in GitHub repo → Settings → Secrets
3. Push to `main` — the workflow handles the rest

### Docker (Self-hosted)

```bash
docker build -t raggita .
docker run -p 8000:8000 --env-file .env raggita
```

---

## 🔑 Environment Variables

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `GROQ_API_KEY` | ✅ | — | Groq API key for LLM inference |
| `LLM_MODEL` | ❌ | `llama-3.1-8b-instant` | Model identifier |
| `OPENAI_API_BASE` | ❌ | `https://api.groq.com/openai/v1` | OpenAI-compatible endpoint |
| `USE_REMOTE_EMBEDDINGS` | ❌ | `true` | Use HF Inference API for embeddings |
| `HF_TOKEN` | ❌ | — | HuggingFace token (for remote embeddings) |
| `PORT` | ❌ | `8000` | Server port |

---

## 💬 Sample Questions

> *"I'm feeling anxious about my future. What does the Gita say?"*
>
> *"How do I deal with stress at work?"*
>
> *"What is the meaning of karma?"*
>
> *"How to handle difficult relationships?"*
>
> *"What does Krishna say about duty and purpose?"*

---

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ and the wisdom of the Bhagavad Gita**

*🙏 Namaste*

</div>
