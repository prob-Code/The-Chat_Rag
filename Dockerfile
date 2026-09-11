# RagGita — ek hi Dockerfile, teen jagah chalti hai.
#
#   AWS Lambda      -> Web Adapter extension isko HTTP server ki tarah chalata hai
#   App Runner/ECS  -> normal container
#   Local           -> docker run -p 8000:8000 raggita
#
# Web Adapter Lambda ke bahar inert rehta hai, isliye alag Dockerfile.lambda
# rakhne ki zaroorat nahi. Ek image, sab targets.

FROM python:3.11-slim

WORKDIR /app

# ── AWS Lambda Web Adapter ──────────────────────────────────
# Yeh extension Lambda Runtime API ko handle karta hai aur invocations
# ko tumhare uvicorn server pe proxy kar deta hai. Isi wajah se api.py
# me ek line bhi badalni nahi padti.
# Version pin kiya hua hai — "latest" mat karna, silently toot sakta hai.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.0.1 /lambda-adapter /opt/extensions/lambda-adapter

# gcc chahiye kuch wheels ke liye; build ke baad hata dete hain
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc && apt-get autoremove -y

# Application code
COPY api.py .
COPY rag_core/ ./rag_core/
COPY static/ ./static/
COPY gita_vector_db/ ./gita_vector_db/

# ── Lambda Web Adapter config ───────────────────────────────
# Yeh env vars Lambda ke bahar bilkul ignore ho jaate hain.
ENV AWS_LWA_PORT=8000
# Readiness /health pe hai: woh models load hone tak 503 deta hai,
# toh adapter tab tak intezaar karega jab tak FAISS taiyar na ho.
ENV AWS_LWA_READINESS_CHECK_PATH=/health
# SSE (/chat/stream) ke liye zaroori. Python runtimes me native response
# streaming nahi hai — adapter hi woh kaam karta hai.
ENV AWS_LWA_INVOKE_MODE=response_stream

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
