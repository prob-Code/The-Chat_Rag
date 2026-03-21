# RagGita Deployment Guide

A FastAPI backend for the RagGita spiritual guide chatbot.

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Or use the startup script
python start_server.py
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Deployment Options

### Option 1: Render (Recommended - Free Tier Available)

#### Method A: Deploy via Blueprint (Easiest)

1. Fork this repository to your GitHub account
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New" → "Blueprint"
4. Connect your GitHub repo
5. Render will automatically detect `render.yaml` and deploy

#### Method B: Manual Deploy

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New" → "Web Service"
3. Connect your GitHub repo
4. Configure:
   - **Name**: raggita-api
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1`
5. Add Environment Variables:
   - `BYTEZ_API_KEY`: Your Bytez API key (get from [bytez.com](https://bytez.com))
6. Click "Create Web Service"

Your API will be live at: `https://raggita-api.onrender.com`

---

### Option 2: Hugging Face Spaces

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Configure:
   - **Space name**: raggita-api
   - **License**: Apache-2.0
   - **Space SDK**: Docker
   - **Space hardware**: Free (CPU basic)
4. Clone the repository:
   ```bash
   git clone https://huggingface.co/spaces/YOUR_USERNAME/raggita-api
   cd raggita-api
   ```
5. Copy your project files to this repo
6. Commit and push:
   ```bash
   git add .
   git commit -m "Initial deployment"
   git push
   ```

Your API will be live at: `https://YOUR_USERNAME-raggita-api.hf.space`

---

### Option 3: Railway

1. Go to [Railway](https://railway.app/)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway will auto-detect the Python app
5. Add environment variable: `BYTEZ_API_KEY`
6. Deploy!

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BYTEZ_API_KEY` | Yes | API key for Bytez LLM service |
| `BYTEZ_MODEL` | No | Model ID (default: `openai/gpt-5.1`) |
| `PORT` | No | Server port (default: 8000) |

---

## API Endpoints

### POST /chat
Send a question and get a spiritual response.

**Request:**
```json
{
  "question": "I'm feeling anxious about my future. What does the Gita say?"
}
```

**Response:**
```json
{
  "answer": "I understand you're feeling anxious about the future...",
  "sources": []
}
```

### GET /health
Check if the API is healthy and ready.

**Response:**
```json
{
  "status": "healthy",
  "message": "All systems operational",
  "version": "1.0.0"
}
```

### GET /
Root endpoint - basic health check.

---

## Testing the API

### Using cURL

```bash
# Test health
curl https://YOUR-URL/health

# Test chat
curl -X POST https://YOUR-URL/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How can I find inner peace?"}'
```

### Using Python

```python
import requests

response = requests.post(
    "https://YOUR-URL/chat",
    json={"question": "How can I find inner peace?"}
)
print(response.json())
```

### Using JavaScript/Fetch

```javascript
const response = await fetch('https://YOUR-URL/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    question: "How can I find inner peace?"
  }),
});

const data = await response.json();
console.log(data.answer);
```

---

## Troubleshooting

### Issue: "Models not loaded yet"

The API takes ~30-60 seconds to load on first startup. The `/health` endpoint will return 503 until ready.

### Issue: Hugging Face model download fails

On free tiers, model downloads may timeout. Solutions:
1. Use a paid plan with more resources
2. Pre-download models in build step
3. Use Docker with cached layers

### Issue: Out of memory

Reduce memory usage by:
1. Using smaller embedding model
2. Reducing `k` (retrieval count) in api.py
3. Upgrading to a paid plan

---

## Project Structure

```
RagGita/
├── api.py              # FastAPI application
├── requirements.txt    # Python dependencies
├── render.yaml        # Render deployment config
├── Dockerfile         # Docker configuration
├── gita_vector_db/    # Pre-built FAISS database
│   ├── index.faiss
│   └── index.pkl
├── lightrag/          # Custom LLM wrapper
│   └── bytez_llm.py
└── data/
    └── bgita.pdf      # Source document
```

---

## Support

For issues with:
- **API/Deployment**: Check Render logs or Hugging Face build logs
- **Bytez API**: Contact [bytez.com](https://bytez.com) support
- **Models**: Visit Hugging Face forums
