# 🚀 Quick Start Guide - RagGita

## ✅ FIXED: Model Error Resolved!

**Problem:** `models/gemini-pro is not found`  
**Solution:** Updated to use `gemini-1.5-flash` ✓

---

## 🎯 Current Status: READY TO USE!

The application is **running and waiting for your questions**.

---

## 📝 How to Use

### Start the Application
```bash
.\.venv\Scripts\Activate.ps1
python chat.py
```

### Ask Questions
Examples:
- "How to deal with stress at work?"
- "What does Gita say about karma?"
- "How to handle difficult relationships?"
- "What is dharma in modern context?"

### Exit
Type: `exit`

---

## 📁 Vector Database Location

**Path:** `d:\RagGita\gita_vector_db\`

**Contents:**
- `index.faiss` (796 KB) - Vector embeddings
- `index.pkl` (440 KB) - Text chunks & metadata

**Total:** ~1.2 MB

---

## 🔧 Configuration

### API Key
**File:** `chat.py` (line 8)
```python
os.environ["GOOGLE_API_KEY"] = "AIzaSyDTZeygRMA4MdNt-vx4H1e6C_lMgcs1s3g"
```

### Model
**File:** `chat.py` (line 25)
```python
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
```

---

## 🛠️ Tech Stack

- **LangChain** - RAG orchestration
- **Google Gemini 1.5 Flash** - LLM (fast & free)
- **FAISS** - Vector search
- **HuggingFace** - Embeddings
- **PyPDF** - PDF processing

---

## ⚡ Performance

- **Response Time:** ~2-5 seconds
- **Retrieval:** Top 4 relevant verses
- **Model:** Cloud-based (no local GPU needed)
- **Cost:** Free (with rate limits)

---

## 📊 How It Works

1. **User asks question** → 
2. **FAISS finds relevant Gita verses** → 
3. **Combines context + question** → 
4. **Gemini generates answer** → 
5. **Returns modern interpretation**

---

## ✨ Features

✅ Semantic search through Bhagavad Gita  
✅ AI-powered contextual answers  
✅ Modern, practical interpretations  
✅ Fast cloud-based processing  
✅ No local model installation needed  

---

## 🎓 Example Interaction

**Q:** "How to deal with stress at work?"

**A:** The Gita will provide relevant verses about:
- Karma Yoga (action without attachment)
- Equanimity in success and failure
- Focus on duty, not results
- Modern application to workplace stress

---

**Ready to explore the wisdom of the Gita! 🙏**
