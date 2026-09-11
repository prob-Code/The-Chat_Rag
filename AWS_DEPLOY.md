# RagGita → AWS Lambda

## Jawab: nahi, sirf woh ek line kaafi nahi

Woh `COPY --from=...` line zaroori hai, but woh pandrah me se ek step hai.
Uske bina bhi nahi hota, aur usse akele bhi nahi hota.

Teen aur cheezein chahiye, aur teenon chhoot jaana aam hai:

| Cheez | Bina iske kya hoga |
|---|---|
| `AWS_LWA_PORT=8000` | Adapter 8080 pe dhoondta hai, tumhara app 8000 pe hai → har request timeout |
| `AWS_LWA_INVOKE_MODE=response_stream` | `/chat/stream` chupchaap buffer ho jayega, streaming ka fayda khatam |
| `--platform linux/amd64` build pe | Windows/Mac pe bani image Lambda pe `exec format error` degi |

Sab kuch `Dockerfile` aur `deploy_lambda.sh` me daal diya hai.

---

## Steps

### 1. Prerequisites

```bash
aws configure          # credentials
docker --version       # Docker Desktop chalu ho
```

### 2. API key export karo — file me mat likhna

```bash
export OPENAI_API_KEY=sk-...
```

Script isse Lambda env var me bhejti hai. **`deploy_lambda.sh` me hardcode mat karna** — woh git me jaati hai.

### 3. Deploy

```bash
chmod +x deploy_lambda.sh
./deploy_lambda.sh
```

Windows pe Git Bash ya WSL me chalao.

Pehli baar ~5-8 min lagega (image build + push). Baad me ~2 min.

Script yeh sab karti hai: IAM role → ECR repo → build+push → Lambda function → reserved concurrency → Function URL with response streaming.

### 4. Verify

```bash
curl https://<your-url>.lambda-url.ap-south-1.on.aws/health
curl https://<your-url>.lambda-url.ap-south-1.on.aws/classes
```

Logs:
```bash
aws logs tail /aws/lambda/raggita --follow --region ap-south-1
```

---

## Settings jo maine chuni, aur kyun

| Setting | Value | Wajah |
|---|---|---|
| Region | `ap-south-1` (Mumbai) | Tumhare users India me hain — sabse kam latency |
| Memory | 1024 MB | Lambda pe CPU memory ke saath badhta hai; isse kam pe cold start aur bura |
| Timeout | 60s | OpenAI 3-5s leta hai, retries ki gunjaish chahiye |
| Reserved concurrency | 20 | **Sabse important setting.** Iske bina Lambda 1000 parallel tak jaayega aur OpenAI 429 ki barish kar dega |
| Invoke mode | RESPONSE_STREAM | SSE ke liye; payload limit bhi 6 MB se 200 MB ho jaata hai |
| Auth type | NONE | Public app hai. Iska matlab endpoint khula hai — neeche padho |

---

## Deploy se pehle yeh kar lo

**OpenAI dashboard me hard spend cap lagao.** Settings → Limits → monthly budget.

Function URL `auth-type NONE` ka matlab hai koi bhi tumhara endpoint call kar sakta hai. App ka rate limiter madad karta hai, but Lambda pe woh counters per-container hote hain — 20 concurrent executions matlab 20 alag counters, yani effective limit 20x dheeli.

Spend cap hi woh ek cheez hai jo chahe kuch bhi ho jaaye, bill ko rok deti hai. 2 minute lagte hain.

---

## Cold start

Pehli request ke baad function ~10-15 min tak warm rehta hai. Uske baad agli request cold hogi — LangChain imports ke saath ~4-8s.

Demo ke liye teen options:

1. **Demo se 5 min pehle ek dummy request maar do** — sabse simple, free
2. **Provisioned concurrency 1** — hamesha ek warm instance, ~$4/mo
3. **LangChain hot path se hatao** — tum use sirf `PromptTemplate` (string formatting) aur `ChatOpenAI` (openai SDK wrapper) ke liye use kar rahe ho. Dono seedhe replace ho sakte hain, import time kaafi girega

Demo ke din option 1 kaafi hai. Option 3 permanent fix hai.

---

## Frontend kahan se aayega

Abhi static files Lambda se hi serve ho rahe hain — chalta hai, but har page load pe Lambda invoke hota hai. Traffic badhe toh `static/` S3 + CloudFront pe daal do aur `API_BASE` ko Lambda URL pe point kar do. Abhi zaroorat nahi.

---

## Render ka kya karein

`render.yaml` fix kar diya hai (OpenAI + naye env vars), aur `requirements.txt` se torch nikal gaya hai, toh build ab pass hona chahiye.

But seedhi baat: **teen deployment targets ek student project ke liye zyada hain.** HF Space, Render, aur Lambda — teeno maintain karne ka koi fayda nahi. Ek chuno:

- **Lambda** — spiky traffic, idle pe $0, cold start ki keemat
- **HF Space** — abhi chal raha hai, free, demo ke liye theek
- **Render** — free tier sleep hota hai, cold start Lambda jitna hi bura

Render nahi chahiye toh `render.yaml` me `autoDeploy: false` kar do, ya GitHub → Settings → Environments me `main - raggita-api` delete kar do. Red X ki barish band ho jayegi.
