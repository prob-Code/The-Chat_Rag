"""
RagGita — abuse guard.

Teen layers:
  1. Per-IP sliding-window rate limit (minute + hour)
  2. Global daily request budget — credit drain ke against last line
  3. Gentle 429s, kyunki yeh mental-health app hai

IMPORTANT DESIGN CALL:
Crisis messages kabhi rate-limit nahi hote. Woh LLM call karte hi nahi
(fixed helpline reply hai), toh unka cost zero hai — aur jo insaan limit
tak pahunch gaya ho usse helpline rokna sabse bura outcome hoga.

LAMBDA NOTE:
Yeh counters in-memory hain, matlab per-container. Lambda pe jab 50 concurrent
executions chalti hain toh har ek ka apna counter hoga — yani effective limit
50x dheeli ho jayegi. Isliye yeh app-level guard *akela kaafi nahi* hai.
Asli protection: API Gateway throttling + Lambda reserved concurrency +
OpenAI dashboard me hard spend cap. Yeh uske upar ka backstop hai.
DynamoDB-backed shared counter chahiye toh RateLimiter ko swap kar dena.
"""

import os
import time
import threading
from collections import deque

from fastapi import Request, HTTPException, status


# ──────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────
# Limits jaan-boojh ke udaar hain. Ek pareshaan insaan 20 min me 15 message
# bhej sakta hai — woh abuse nahi hai, woh bura din hai.

RATE_PER_MIN    = int(os.getenv("RATE_LIMIT_PER_MIN", "8"))
RATE_PER_HOUR   = int(os.getenv("RATE_LIMIT_PER_HOUR", "80"))
DAILY_BUDGET    = int(os.getenv("DAILY_REQUEST_BUDGET", "3000"))
GUARD_ENABLED   = os.getenv("GUARD_ENABLED", "true").strip().lower() in ("1", "true", "yes", "y")

_TRUSTED_PROXY  = os.getenv("TRUST_FORWARDED_FOR", "true").strip().lower() in ("1", "true", "yes", "y")


# ──────────────────────────────────────────────────────────────
# CLIENT IDENTITY
# ──────────────────────────────────────────────────────────────

def client_ip(request: Request) -> str:
    """Caller ka IP nikalo.

    HF Spaces, API Gateway, ALB — sab X-Forwarded-For lagate hain, usme
    pehla entry asli client hota hai. Yeh header spoof ho sakta hai, isliye
    ise identification samjho, authentication nahi.
    """
    if _TRUSTED_PROXY:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            first = fwd.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else "unknown"


# ──────────────────────────────────────────────────────────────
# SLIDING WINDOW LIMITER
# ──────────────────────────────────────────────────────────────

class RateLimiter:
    """Per-key sliding window. Thread-safe, memory-bounded."""

    def __init__(self, max_keys: int = 10000):
        self._hits = {}          # key -> deque[timestamp]
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def _prune(self, now: float):
        """Purane keys hata do taaki memory na badhe."""
        if len(self._hits) <= self._max_keys:
            return
        cutoff = now - 3600
        dead = [k for k, dq in self._hits.items() if not dq or dq[-1] < cutoff]
        for k in dead:
            self._hits.pop(k, None)

    def check(self, key: str):
        """Return (allowed: bool, retry_after_seconds: int)."""
        now = time.time()

        with self._lock:
            dq = self._hits.get(key)
            if dq is None:
                dq = deque()
                self._hits[key] = dq

            # Ek ghante se purane hits bahar
            while dq and dq[0] < now - 3600:
                dq.popleft()

            in_last_min = sum(1 for t in dq if t >= now - 60)

            if in_last_min >= RATE_PER_MIN:
                oldest_in_min = next(t for t in dq if t >= now - 60)
                return False, max(1, int(60 - (now - oldest_in_min)))

            if len(dq) >= RATE_PER_HOUR:
                return False, max(1, int(3600 - (now - dq[0])))

            dq.append(now)
            self._prune(now)
            return True, 0


# ──────────────────────────────────────────────────────────────
# DAILY BUDGET
# ──────────────────────────────────────────────────────────────

class DailyBudget:
    """Poore process ka daily request counter. UTC midnight pe reset."""

    def __init__(self, limit: int):
        self.limit = limit
        self._day = None
        self._count = 0
        self._lock = threading.Lock()

    def _today(self) -> int:
        return int(time.time() // 86400)

    def check_and_increment(self) -> bool:
        with self._lock:
            today = self._today()
            if today != self._day:
                self._day = today
                self._count = 0
            if self._count >= self.limit:
                return False
            self._count += 1
            return True

    def snapshot(self) -> dict:
        with self._lock:
            return {"used": self._count, "limit": self.limit}


_limiter = RateLimiter()
_budget = DailyBudget(DAILY_BUDGET)


# ──────────────────────────────────────────────────────────────
# MESSAGES — yeh error strings user ko dikhte hain
# ──────────────────────────────────────────────────────────────
# Tone jaan-boojh ke narm hai. "Rate limit exceeded" ek pareshaan insaan ko
# darwaza band hone jaisa lagta hai. Yeh rukne ko kehta hai, bhagane ko nahi.

TOO_FAST_MESSAGE = (
    "Let's slow down together for a moment. I'm still here — "
    "try again in a few seconds."
)

BUDGET_MESSAGE = (
    "I've reached my limit for today and can't answer properly right now. "
    "If something feels urgent, please talk to someone — Tele-MANAS is free "
    "and open all night at 14416."
)


def enforce(request: Request, is_crisis_message: bool = False) -> None:
    """Guard chalao. Block karna ho toh HTTPException raise karta hai.

    Crisis messages hamesha guzar jaate hain — woh LLM call karte hi nahi,
    aur unhe rokna iss app ka sabse bura failure mode hoga.
    """
    if is_crisis_message or not GUARD_ENABLED:
        return

    if not _budget.check_and_increment():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=BUDGET_MESSAGE,
        )

    allowed, retry_after = _limiter.check(client_ip(request))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=TOO_FAST_MESSAGE,
            headers={"Retry-After": str(retry_after)},
        )


def budget_status() -> dict:
    return _budget.snapshot()
