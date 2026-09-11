#!/usr/bin/env bash
# RagGita -> AWS Lambda (container image + Web Adapter + Function URL)
#
# Windows pe Git Bash ya WSL me chalao.
#
# CHALANE SE PEHLE:
#   1. aws configure         (credentials set ho)
#   2. Docker Desktop chalu ho
#   3. OPENAI_API_KEY apne shell me export karo -- ISS FILE ME MAT LIKHNA,
#      yeh git me jaati hai.
#
#      export OPENAI_API_KEY=sk-...
#
# Usage:  ./deploy_lambda.sh

set -euo pipefail

# ── Config ───────────────────────────────────────────────────
REGION="${AWS_REGION:-ap-south-1}"          # Mumbai — India users ke liye sabse kam latency
FUNCTION_NAME="raggita"
ECR_REPO="raggita"
ROLE_NAME="raggita-lambda-role"

MEMORY_MB=1024      # CPU memory ke saath badhta hai; 1024 cold start ke liye theek hai
TIMEOUT_SEC=60      # OpenAI ko 3-5s lagta hai; 60 me retries ki gunjaish hai
RESERVED_CONCURRENCY=20   # OpenAI rate limit ke against asli bachaav

: "${OPENAI_API_KEY:?OPENAI_API_KEY set nahi hai. 'export OPENAI_API_KEY=sk-...' chalao}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"

echo "==> Account ${ACCOUNT_ID}, region ${REGION}"

# ── 1. Execution role ────────────────────────────────────────
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "==> Creating IAM role ${ROLE_NAME}"
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]
    }' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "==> Role bani. IAM propagate hone ke liye 10s ruk rahe hain..."
  sleep 10
fi
ROLE_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)"

# ── 2. ECR repo ──────────────────────────────────────────────
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$ECR_REPO" --region "$REGION" >/dev/null

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# ── 3. Build + push ──────────────────────────────────────────
# --platform zaroori hai: Windows/Mac pe build karke Lambda pe bhejna hai,
# aur Lambda ko linux/amd64 chahiye. Yeh bhoolne pe "exec format error" aata hai.
echo "==> Building image (linux/amd64)"
docker build --platform linux/amd64 -t "${ECR_REPO}:latest" .
docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"

# ── 4. Lambda function ───────────────────────────────────────
ENV_VARS="Variables={\
OPENAI_API_KEY=${OPENAI_API_KEY},\
OPENAI_API_BASE=https://api.openai.com/v1,\
LLM_MODEL=gpt-4o-mini,\
LLM_MAX_TOKENS=220,\
LLM_TEMPERATURE=0.6,\
MAX_CONTEXT_CHARS=2500,\
FAST_TOP_K=3,\
USE_REMOTE_EMBEDDINGS=true,\
USE_BYTEZ=false,\
ENABLE_TTS=true,\
TTS_MODEL=gpt-4o-mini-tts,\
TTS_VOICE=sage,\
GUARD_ENABLED=true,\
RATE_LIMIT_PER_MIN=8,\
RATE_LIMIT_PER_HOUR=80,\
DAILY_REQUEST_BUDGET=3000,\
OPENAI_MAX_RETRIES=3\
}"

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "==> Updating existing function"
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" --image-uri "${ECR_URI}:latest" --region "$REGION" >/dev/null
  aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" --memory-size "$MEMORY_MB" --timeout "$TIMEOUT_SEC" \
    --environment "$ENV_VARS" --region "$REGION" >/dev/null
else
  echo "==> Creating function"
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --package-type Image \
    --code ImageUri="${ECR_URI}:latest" \
    --role "$ROLE_ARN" \
    --memory-size "$MEMORY_MB" \
    --timeout "$TIMEOUT_SEC" \
    --environment "$ENV_VARS" \
    --region "$REGION" >/dev/null
fi

aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"

# ── 5. Concurrency ceiling ───────────────────────────────────
# Lambda 1000 parallel tak jaa sakta hai. OpenAI itna nahi jhelega —
# yeh cap hi tumhe 429 ki barish se bachata hai.
aws lambda put-function-concurrency \
  --function-name "$FUNCTION_NAME" \
  --reserved-concurrent-executions "$RESERVED_CONCURRENCY" \
  --region "$REGION" >/dev/null

# ── 6. Function URL (SSE ke liye response streaming) ─────────
if ! aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  aws lambda create-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --auth-type NONE \
    --invoke-mode RESPONSE_STREAM \
    --region "$REGION" >/dev/null

  aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE \
    --region "$REGION" >/dev/null
fi

URL="$(aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --region "$REGION" --query FunctionUrl --output text)"

echo
echo "================================================"
echo " Deployed: ${URL}"
echo "================================================"
echo
echo "Test karo:"
echo "  curl ${URL}health"
echo "  curl ${URL}classes"
echo
echo "Logs:"
echo "  aws logs tail /aws/lambda/${FUNCTION_NAME} --follow --region ${REGION}"
