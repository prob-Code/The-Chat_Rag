"""
RagGita — DynamoDB me kaun kya baat kar raha hai, padhne layak shakal me.

Console me ye dekhna mushkil hai kyunki ek hi table me chaar tarah ki rows
hain (PROFILE, CONV#, TS#, QUOTA#) aur Explore items sab mila kar dikhata hai.
Yeh script unhe user ke hisaab se alag kar deta hai.

Chalao:
    python inspect_chats.py                    # sab users ki list
    python inspect_chats.py --user fb:abc123   # ek user ki chats + summary
    python inspect_chats.py --conv 7b1aba6f…   # ek chat ke poore messages
    python inspect_chats.py --stats            # ginti: users, chats, messages

Zaroori: AWS creds wahi jo create_table.py ke liye lagi thi.

PRIVACY: --conv asli message text dikhata hai. Ye asli logon ki asli baatein
hain. Apne hi test account pe use karo; kisi aur ki chat kholne ki wajah honi
chahiye, aur output kahin paste mat karna.
"""

import os
import argparse
from collections import defaultdict

import boto3
from boto3.dynamodb.conditions import Key

TABLE = os.getenv("DDB_TABLE", "raggita_chat")
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))

table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)


def scan_all():
    """Poora table. Chhote table pe theek hai; hazaaron users ho jaayen toh
    query use karo (neeche --user waala raasta wahi karta hai)."""
    items, kwargs = [], {}
    while True:
        res = table.scan(**kwargs)
        items += res.get("Items", [])
        if "LastEvaluatedKey" not in res:
            return items
        kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]


def row_kind(i):
    pk, sk = i.get("PK", ""), i.get("SK", "")
    if pk.startswith("CONV#"):
        return "message"
    if sk.startswith("CONV#"):
        return "conversation"
    if sk.startswith("QUOTA#"):
        return "quota"
    if sk == "PROFILE":
        return "profile"
    return "other"


def cmd_list():
    items = scan_all()
    convs = defaultdict(list)
    quota = defaultdict(int)
    msgs_by_conv = defaultdict(int)

    for i in items:
        k = row_kind(i)
        if k == "conversation":
            convs[i["PK"][5:]].append(i)
        elif k == "quota":
            quota[i["PK"][5:]] += int(i.get("count", 0))
        elif k == "message":
            msgs_by_conv[i["PK"][5:]] += 1

    if not convs:
        print("Koi conversation nahi mili. Pehle app se do-teen message bhejo.")
        return

    print(f"\n{len(convs)} user(s)\n")
    for uid, rows in sorted(convs.items(),
                            key=lambda kv: max((r.get("lastMessageAt", "") for r in kv[1]),
                                               default=""),
                            reverse=True):
        kind = ("Google login" if uid.startswith("fb:")
                else "device id" if not uid.startswith("anon-") else "IP (purana)")
        total_msgs = sum(msgs_by_conv.get(r["SK"][5:], 0) for r in rows)
        print(f"  {uid}")
        print(f"      {kind} · {len(rows)} chats · {total_msgs} messages"
              f" · aaj tak {quota.get(uid, 0)} requests")
        for r in sorted(rows, key=lambda x: x.get("lastMessageAt", ""), reverse=True)[:4]:
            cid = r["SK"][5:]
            title = (r.get("title") or "(no title)")[:44]
            has_sum = "summary hai" if r.get("summary") else "summary nahi"
            print(f"        · {title:46} {int(r.get('turns',0)):>3} turns  "
                  f"{has_sum}   {cid[:8]}")
        if len(rows) > 4:
            print(f"        … aur {len(rows)-4} chats")
        print()


def cmd_user(uid):
    res = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{uid}") & Key("SK").begins_with("CONV#"))
    rows = res.get("Items", [])
    if not rows:
        print(f"{uid} ki koi chat nahi mili.")
        print("Dhyan do: uid me prefix zaroori hai — Google login walon ka 'fb:' se shuru hota hai.")
        return

    print(f"\n{uid} — {len(rows)} chats\n")
    for r in sorted(rows, key=lambda x: x.get("lastMessageAt", ""), reverse=True):
        cid = r["SK"][5:]
        print(f"  {cid}")
        print(f"      title       : {r.get('title','')}")
        print(f"      turns       : {int(r.get('turns',0))}")
        print(f"      last message: {r.get('lastMessageAt','')}")
        print(f"      lang        : {r.get('lang','')}")
        s = r.get("summary", "")
        # Summary yahan poori dikhana hi is script ka sabse kaam ka hissa hai —
        # isse pata chalta hai bot ne iss user ke baare me kya yaad rakha.
        print(f"      summary     : {s if s else '(abhi nahi bani — 10 turns pe banti hai)'}")
        print()


def cmd_conv(conv_id):
    res = table.query(KeyConditionExpression=Key("PK").eq(f"CONV#{conv_id}"),
                      ScanIndexForward=True)
    items = res.get("Items", [])
    if not items:
        print(f"conv {conv_id} me koi message nahi mila.")
        return
    print(f"\nconv {conv_id} — {len(items)} rows\n")
    for i in items:
        role = i.get("role", "?")
        when = (i.get("createdAt", "") or "")[11:19]
        cls = i.get("userClass", "")
        text = (i.get("text", "") or "").replace("\n", " ")
        who = {"user": "THEM", "assistant": "BOT ", "event": "EVT "}.get(role, role[:4].upper())
        print(f"  [{when}] {who} {('('+cls+')') if cls else '':<11} {text[:150]}")
    print()


def cmd_stats():
    items = scan_all()
    c = defaultdict(int)
    users = set()
    for i in items:
        k = row_kind(i)
        c[k] += 1
        if k in ("conversation", "profile", "quota"):
            users.add(i["PK"][5:])
    crisis = sum(1 for i in items if i.get("role") == "event")
    print(f"""
  users              {len(users)}
  conversations      {c['conversation']}
  messages           {c['message'] - crisis}
  crisis events      {crisis}   (text store nahi hota, sirf marker)
  quota rows         {c['quota']}
  profile rows       {c['profile']}
  table              {TABLE} ({REGION})
""")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", help="ek user ki chats (jaise fb:abc123)")
    p.add_argument("--conv", help="ek chat ke poore messages")
    p.add_argument("--stats", action="store_true", help="sirf ginti")
    a = p.parse_args()

    try:
        if a.conv:
            cmd_conv(a.conv)
        elif a.user:
            cmd_user(a.user)
        elif a.stats:
            cmd_stats()
        else:
            cmd_list()
    except Exception as e:
        print(f"\nFail hua: {type(e).__name__}: {e}\n")
        if "credential" in str(e).lower() or "AccessDenied" in str(e):
            print("AWS creds set nahi hain, ya us user ko DynamoDB ki permission nahi.")
            print("create_table.py ke liye jo kiya tha, wahi yahan bhi chahiye.")
