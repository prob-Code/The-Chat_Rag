# RagGita Deployment Summary

## Files Created/Updated

### Core API Files
| File | Purpose |
|------|---------|
| `api.py` | FastAPI backend server - main entry point |
| `requirements.txt` | Python dependencies |
| `start_server.py` | Local development startup script |
| `test_api.py` | API testing script |

### Frontend
| File | Purpose |
|------|---------|
| `static/index.html` | Beautiful chat UI for testing the API |

### Deployment Configuration
| File | Purpose |
|------|---------|
| `render.yaml` | Render.com deployment blueprint |
| `Dockerfile` | Docker container configuration |
| `.dockerignore` | Docker build exclusions |
| `.github/workflows/deploy.yml` | GitHub Actions CI/CD |

### Documentation
| File | Purpose |
|------|---------|
| `README.md` | Updated with deployment instructions |
| `README_DEPLOY.md` | Detailed deployment guide |
| `DEPLOYMENT_SUMMARY.md` | This file |

---

## Quick Start

### 1. Local Testing

```bash
# Start the server
python start_server.py

# Or directly with uvicorn
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### 2. Open Browser

- **Frontend UI**: http://localhost:8000/
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 3. Test API

```bash
# Using curl
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How can I find inner peace?"}'

# Using Python test script
python test_api.py --url http://localhost:8000
```

---

## Deploy to Render (Recommended)

### Option A: Blueprint Deploy (Easiest)

1. Push code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New" → "Blueprint"
4. Connect your GitHub repo
5. Render auto-detects `render.yaml` and deploys

### Option B: Manual Deploy

1. Push code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New" → "Web Service"
4. Configure:
   - **Name**: raggita-api
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1`
5. Add Environment Variable:
   - `BYTEZ_API_KEY`: your-api-key-here
6. Deploy!

---

## Deploy to Hugging Face Spaces

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Configure:
   - **Space name**: raggita-api
   - **Space SDK**: Docker
   - **Space hardware**: Free (CPU basic)
4. Upload files or connect GitHub repo
5. Deploy!

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | HTML Frontend (chat UI) |
| GET | `/api` | API info JSON |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger API documentation |
| POST | `/chat` | Chat with Gita bot |
| POST | `/ask` | Alias for /chat |

### Example Request

```bash
curl -X POST https://your-api.render.com/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the purpose of life?"}'
```

### Example Response

```json
{
  "answer": "According to the Bhagavad Gita...",
  "sources": []
}
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BYTEZ_API_KEY` | Yes | - | Bytez API key (get from bytez.com) |
| `BYTEZ_MODEL` | No | openai/gpt-5.1 | Model to use |
| `PORT` | No | 8000 | Server port |

---

## Important Files to Deploy

These must be included in your deployment:

```
✅ api.py              # Main API file
✅ requirements.txt    # Dependencies
✅ gita_vector_db/     # Vector database (CRITICAL)
│   ├── index.faiss
│   └── index.pkl
✅ lightrag/            # Custom LLM wrapper
│   └── bytez_llm.py
✅ static/             # Frontend UI
│   └── index.html
✅ data/               # Source document
│   └── bgita.pdf
```

---

## Troubleshooting

### API Returns "Models not loaded yet"

The API takes 30-60 seconds to load on first startup. Wait for the `/health` endpoint to return 200.

### Hugging Face Model Download Fails

On free tiers, model downloads may timeout. Solutions:
1. Use a paid plan
2. Pre-download in build step
3. Use Docker with cached layers

### Out of Memory

Reduce memory by:
1. Using smaller embedding model
2. Reducing `k` in retriever (api.py line 59)
3. Upgrading to paid plan

---

## Next Steps

1. **Get Bytez API Key**: Sign up at [bytez.com](https://bytez.com)
2. **Push to GitHub**: `git add . && git commit -m "Deployment ready" && git push`
3. **Deploy to Render**: Follow steps above
4. **Share your API**: Give others your URL

---

## Support

- **API Issues**: Check Render/HF logs
- **Bytez API**: Visit [bytez.com/docs](https://bytez.com)
- **FastAPI**: Visit [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
