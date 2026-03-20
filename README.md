# RagGita - Bhagavad Gita AI Assistant

A RAG (Retrieval Augmented Generation) application that answers questions based on the Bhagavad Gita using AI.

## Quick Links

- [Local Development](#local-development)
- [Deployment Guide](#deployment-to-render--hugging-face)

## Features
- 📚 Semantic search through Bhagavad Gita verses
- 🤖 AI-powered answers using Bytez GPT-5.1
- 💬 Interactive chat interface
- 🎯 Modern, practical interpretations
- 🚀 Deployable FastAPI backend

## Local Development

### 1. Install Dependencies
```bash
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Get Bytez API Key (Free)
1. Go to [bytez.com](https://bytez.com)
2. Sign up for an account
3. Get your API key
4. Set it as environment variable: `BYTEZ_API_KEY`

### 3. Configure Environment
Create a `.env` file:
```env
BYTEZ_API_KEY=your-api-key-here
BYTEZ_MODEL=openai/gpt-5.1
```

### 4. Create Vector Database (Already Done!)
The vector database has been created from the Gita PDF. If you need to recreate it:
```bash
python ingest.py
```

### 5. Run the API Server
```bash
# Option 1: Using the startup script
python start_server.py

# Option 2: Using uvicorn directly
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: http://localhost:8000

### 6. Test the API
```bash
# Using curl
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How can I find inner peace?"}'

# Or use the test script
python test_api.py --url http://localhost:8000
```

### 7. Run Interactive Chat (CLI)
```bash
python chat.py
```

## Deployment to Render / Hugging Face

### Option 1: Render (Recommended - Free Tier)

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
   - `BYTEZ_API_KEY`: Your Bytez API key
6. Click "Create Web Service"

Your API will be live at: `https://raggita-api.onrender.com`

### Option 2: Hugging Face Spaces

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Configure:
   - **Space name**: raggita-api
   - **Space SDK**: Docker
   - **Space hardware**: Free (CPU basic)
4. Upload your files or connect GitHub repo
5. Deploy!

Your API will be live at: `https://YOUR_USERNAME-raggita-api.hf.space`

## API Documentation

Once running, visit:
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | Detailed health check |
| `/chat` | POST | Chat with Gita RAG bot |

### Example Request
```bash
curl -X POST https://your-api-url.com/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How can I find inner peace?"}'
```

### Example Response
```json
{
  "answer": "I understand you're seeking inner peace...",
  "sources": []
}
```

## Usage
Once the application starts, you can ask questions like:
- "How to deal with stress at work?"
- "What does Gita say about duty?"
- "How to handle difficult relationships?"
- "What is the meaning of karma?"

Type `exit` to quit the CLI application.

## Project Structure
- `data/bgita.pdf` - Bhagavad Gita PDF (368 KB)
- `ingest.py` - Creates vector database from PDF
- `chat.py` - Interactive chat interface (CLI)
- `api.py` - FastAPI web server
- `start_server.py` - Server startup script
- `test_api.py` - API testing script
- `gita_vector_db/` - Vector database storage (generated)
  - `index.faiss` - FAISS vector index (~796 KB)
  - `index.pkl` - Metadata and document chunks (~440 KB)
- `requirements.txt` - Python dependencies
- `render.yaml` - Render deployment configuration
- `Dockerfile` - Docker configuration
- `README.md` - This file
- `README_DEPLOY.md` - Detailed deployment guide

### 📁 Vector Database Location
The vector database is stored in the `gita_vector_db/` folder and contains:
- **index.faiss** - The FAISS vector index for fast similarity search
- **index.pkl** - Pickled metadata including the original text chunks

Total size: ~1.2 MB

## Technologies Used
- **FastAPI** - Modern, fast web framework
- **LangChain** - RAG framework
- **Bytez GPT-5.1** - Fast, cloud-based LLM
- **FAISS** - Vector similarity search
- **HuggingFace Embeddings** - Text embeddings
- **PyPDF** - PDF processing
- **Uvicorn** - ASGI server

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BYTEZ_API_KEY` | Yes | - | Bytez API key |
| `BYTEZ_MODEL` | No | openai/gpt-5.1 | Model ID |
| `PORT` | No | 8000 | Server port |

## Notes
- The vector database has already been created
- Bytez API is free to use with rate limits
- No local LLM installation required
- Fast response times with cloud-based inference

## Troubleshooting

### Models Not Loaded Yet Error
On first startup, the API takes ~30-60 seconds to load. The `/health` endpoint will return 503 until ready.

### API Key Issues
Make sure your `BYTEZ_API_KEY` is valid and set as an environment variable.

### Model Not Found Error
If you see model errors, verify the `BYTEZ_MODEL` environment variable is set correctly.

### Deployment Issues
- Check `README_DEPLOY.md` for detailed troubleshooting
- View logs in Render/Hugging Face dashboard
- Make sure `gita_vector_db/` folder is included in deployment
