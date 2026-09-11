# RagGita — ek hi Dockerfile, teen jagah chalti hai.
#
#   AWS Lambda      -> Web Adapter extension isko HTTP server ki tarah chalata hai
#   App Runner/ECS  -> normal container
#   Local           -> docker run -p 8000:8000 raggita
#
# Web Adapter Lambda ke bahar inert rehta hai, isliye alag Dockerfile.lambda
# rakhne ki zaroorat nahi. Ek image, sab targets.

# ── AWS Lambda Web Adapter ──────────────────────────────────
# Yeh extension Lambda Runtime API handle karta hai aur invocations ko
# tumhare uvicorn server pe proxy karta hai — isi wajah se api.py me ek
# line bhi badalni nahi padti.
#
# --platform DONO jagah pin kiya hua hai (yahan aur neeche base image pe).
# Adapter image multi-arch hai; bina pin ke builder kabhi arm64 binary
# utha leta hai, aur phir Lambda pe yeh error aata hai:
#   Extension.LaunchError / ProcessSpawnFailed
# Lambda function ka architecture bhi x86_64 hi hona chahiye.
FROM --platform=linux/amd64 public.ecr.aws/awsguru/aws-lambda-adapter:1.0.1 AS adapter

FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

COPY --from=adapter /lambda-adapter /opt/extensions/lambda-adapter

# NOTE: gcc yahan jaan-boojh ke install NAHI hota.
# Saari dependencies (faiss-cpu, numpy, pydantic, uvloop, tokenizers)
# prebuilt manylinux wheels me aati hain — kuch compile nahi hota.
# Pehle gcc install kar rahe the, aur wahi 40s ka step Docker Desktop ko
# memory pe maar raha tha. Agar kabhi koi package sach me compile maange,
# error saaf "gcc not found" bolega — tab yeh wapas add kar dena:
#   RUN apt-get update && apt-get install -y --no-install-recommends gcc \
#       && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
