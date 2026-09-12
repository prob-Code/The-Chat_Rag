"""
RagGita — DynamoDB storage layer.

Ek hi table, teen item shapes. Keys iss tarah bante hain ki dono screen
ek-ek query me ban jaayein:

    PK                  SK                    kya hai
    ------------------  --------------------  ----------------------------------
    USER#<uid>          PROFILE               longTermSummary, createdAt
    USER#<uid>          CONV#<convId>         title, lastMessageAt, summary, turns
    USER#<uid>          QUOTA#<yyyy-mm-dd>    count (+ ttl, khud expire hota hai)
    CONV#<convId>       TS#<iso>#<seq>        role, text, userClass, lang

Messages CONV# ke neeche hain, USER# ke neeche NAHI — warna chat list kholne
ke liye har purana message scan karna padta. Iss tarah 400 message wali chat
bhi list screen ko dheema nahi karti.

Sab kuch best-effort hai: DynamoDB gir jaye toh chat chalti rehni chahiye,
sirf history nahi banegi. Ek pareshaan insaan ko "database error" dikhana
sabse bekaar outcome hai.
"""

import os
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

TABLE_NAME = os.getenv("DDB_TABLE", "raggita_chat")
REGION = os.getenv("AWS_REGION", "ap-south-1")

MEMORY_TURNS = int(os.getenv("MEMORY_TURNS", "8"))        # kitne message jaise ke waise
SUMMARISE_EVERY = int(os.getenv("SUMMARISE_EVERY", "10"))  # kitne turns pe summary refresh
QUOTA_PER_DAY = int(os.getenv("USER_QUOTA_PER_DAY", "200"))

_table = None
_unavailable_logged = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def table():
    """Lazy table handle. boto3 na ho ya table na mile toh None."""
    global _table, _unavailable_logged
    if _table is not None:
        return _table
    try:
        import boto3
        _table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
        _table.load()
        logger.info("DynamoDB table %s ready", TABLE_NAME)
        return _table
    except Exception as e:
        if not _unavailable_logged:
            logger.warning("DynamoDB unavailable (%s: %s) — running without history",
                           type(e).__name__, str(e)[:200])
            _unavailable_logged = True
        _table = None
        return None


def enabled() -> bool:
    return table() is not None


# ──────────────────────────────────────────────────────────────
# WRITES
# ──────────────────────────────────────────────────────────────

def new_conversation_id() -> str:
    return uuid.uuid4().hex[:16]


def save_turn(uid, conv_id, question, answer, user_class="auto", lang="en", crisis=False):
    """User ka message aur bot ka reply, dono ek saath likho.

    Return: naya turn count (ya None agar store off hai).
    Crisis messages ke liye sirf event likhte hain, text nahi — neeche dekho.
    """
    t = table()
    if t is None:
        return None

    try:
        ts = _now_iso()
        base = f"CONV#{conv_id}"

        if crisis:
            # Crisis ka text jaan-boojh ke store NAHI hota. App ko pata hona
            # chahiye ki guard chala, par kisi ki sabse buri raat ka database
            # banana zaroori nahi hai.
            t.put_item(Item={
                "PK": base, "SK": f"TS#{ts}#0",
                "role": "event", "text": "[crisis guard fired]",
                "userClass": "crisis", "lang": lang, "createdAt": ts,
            })
        else:
            with t.batch_writer() as bw:
                bw.put_item(Item={
                    "PK": base, "SK": f"TS#{ts}#0",
                    "role": "user", "text": question[:4000],
                    "userClass": user_class, "lang": lang, "createdAt": ts,
                })
                bw.put_item(Item={
                    "PK": base, "SK": f"TS#{ts}#1",
                    "role": "assistant", "text": answer[:4000],
                    "userClass": user_class, "lang": lang, "createdAt": ts,
                })

        # Conversation metadata — turns counter atomically badhao
        res = t.update_item(
            Key={"PK": f"USER#{uid}", "SK": f"CONV#{conv_id}"},
            UpdateExpression=(
                "SET lastMessageAt = :ts, lang = :lang, "
                "createdAt = if_not_exists(createdAt, :ts), "
                "title = if_not_exists(title, :title) "
                "ADD turns :one"
            ),
            ExpressionAttributeValues={
                ":ts": ts, ":lang": lang, ":one": 1,
                ":title": (question[:60] if not crisis else "…"),
            },
            ReturnValues="UPDATED_NEW",
        )
        return int(res.get("Attributes", {}).get("turns", 0))

    except Exception:
        logger.exception("save_turn failed (continuing without history)")
        return None


def update_summary(uid, conv_id, summary):
    t = table()
    if t is None:
        return
    try:
        t.update_item(
            Key={"PK": f"USER#{uid}", "SK": f"CONV#{conv_id}"},
            UpdateExpression="SET summary = :s, summarisedAt = :ts",
            ExpressionAttributeValues={":s": summary[:2000], ":ts": _now_iso()},
        )
    except Exception:
        logger.exception("update_summary failed")


# ──────────────────────────────────────────────────────────────
# READS
# ──────────────────────────────────────────────────────────────

def load_memory(uid, conv_id, turns=None):
    """Return (summary, [ {role, text}, ... ]) — sabse purana pehle."""
    t = table()
    if t is None or not conv_id:
        return "", []

    turns = turns or MEMORY_TURNS
    try:
        from boto3.dynamodb.conditions import Key

        meta = t.get_item(Key={"PK": f"USER#{uid}", "SK": f"CONV#{conv_id}"}).get("Item", {})
        summary = meta.get("summary", "") or ""

        # ScanIndexForward=False -> naye pehle; baad me ulta kar dete hain
        res = t.query(
            KeyConditionExpression=Key("PK").eq(f"CONV#{conv_id}"),
            ScanIndexForward=False,
            Limit=turns,
        )
        msgs = [
            {"role": i.get("role", "user"), "text": i.get("text", "")}
            for i in reversed(res.get("Items", []))
            if i.get("role") in ("user", "assistant")
        ]
        return summary, msgs
    except Exception:
        logger.exception("load_memory failed (continuing without history)")
        return "", []


def list_conversations(uid, limit=50):
    t = table()
    if t is None:
        return []
    try:
        from boto3.dynamodb.conditions import Key
        res = t.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{uid}") & Key("SK").begins_with("CONV#"),
            Limit=limit,
        )
        items = [{
            "conversation_id": i["SK"].split("#", 1)[1],
            "title": i.get("title", ""),
            "last_message_at": i.get("lastMessageAt", ""),
            "turns": int(i.get("turns", 0)),
            "lang": i.get("lang", "en"),
        } for i in res.get("Items", [])]
        items.sort(key=lambda x: x["last_message_at"], reverse=True)
        return items
    except Exception:
        logger.exception("list_conversations failed")
        return []


def get_messages(conv_id, limit=100):
    t = table()
    if t is None:
        return []
    try:
        from boto3.dynamodb.conditions import Key
        res = t.query(
            KeyConditionExpression=Key("PK").eq(f"CONV#{conv_id}"),
            ScanIndexForward=True,
            Limit=limit,
        )
        return [{
            "role": i.get("role"), "text": i.get("text", ""),
            "created_at": i.get("createdAt", ""), "user_class": i.get("userClass", ""),
        } for i in res.get("Items", [])]
    except Exception:
        logger.exception("get_messages failed")
        return []


# ──────────────────────────────────────────────────────────────
# DELETE  (DPDP ke under yeh optional nahi hai)
# ──────────────────────────────────────────────────────────────

def delete_conversation(uid, conv_id):
    t = table()
    if t is None:
        return 0
    try:
        from boto3.dynamodb.conditions import Key
        n = 0
        res = t.query(KeyConditionExpression=Key("PK").eq(f"CONV#{conv_id}"))
        with t.batch_writer() as bw:
            for i in res.get("Items", []):
                bw.delete_item(Key={"PK": i["PK"], "SK": i["SK"]})
                n += 1
        t.delete_item(Key={"PK": f"USER#{uid}", "SK": f"CONV#{conv_id}"})
        return n
    except Exception:
        logger.exception("delete_conversation failed")
        return 0


def delete_user(uid):
    """Sab kuch mita do — messages, conversations, profile, quota rows."""
    t = table()
    if t is None:
        return {"conversations": 0, "messages": 0}
    try:
        from boto3.dynamodb.conditions import Key
        convs = list_conversations(uid, limit=1000)
        msgs = 0
        for c in convs:
            msgs += delete_conversation(uid, c["conversation_id"])

        res = t.query(KeyConditionExpression=Key("PK").eq(f"USER#{uid}"))
        with t.batch_writer() as bw:
            for i in res.get("Items", []):
                bw.delete_item(Key={"PK": i["PK"], "SK": i["SK"]})
        return {"conversations": len(convs), "messages": msgs}
    except Exception:
        logger.exception("delete_user failed")
        return {"conversations": 0, "messages": 0}


# ──────────────────────────────────────────────────────────────
# PER-USER QUOTA
# ──────────────────────────────────────────────────────────────

def check_quota(uid, limit=None):
    """Atomic daily counter. Return (allowed, used).

    Yeh guard.py ke in-memory limiter ki jagah hai. Woh per-container tha,
    matlab Lambda pe 20 concurrent containers = 20 alag counters. Yeh
    DynamoDB pe hai, toh sab containers ke aar-paar sahi rehta hai.
    """
    t = table()
    if t is None:
        return True, 0

    limit = limit or QUOTA_PER_DAY
    try:
        ttl = int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp())
        res = t.update_item(
            Key={"PK": f"USER#{uid}", "SK": f"QUOTA#{_today()}"},
            UpdateExpression="ADD #c :one SET expiresAt = if_not_exists(expiresAt, :ttl)",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues={":one": 1, ":ttl": ttl},
            ReturnValues="UPDATED_NEW",
        )
        used = int(res.get("Attributes", {}).get("count", 0))
        return used <= limit, used
    except Exception:
        logger.exception("check_quota failed (allowing request)")
        return True, 0
