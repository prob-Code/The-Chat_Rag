# Dockerfile for Render/Cloud Deployment
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api.py .
COPY start_server.py .
COPY rag_core/ ./rag_core/
COPY static/ ./static/

# Copy pre-built vector database (built with HuggingFace all-MiniLM-L6-v2)
COPY gita_vector_db/ ./gita_vector_db/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
