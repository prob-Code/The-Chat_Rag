"""
RagGita — "chat sach me behtar ho rahi hai ya nahi" ka asli test.

"Behtar lag raha hai" koi test nahi hota. Isliye yeh script wahi ek
conversation DO tareeke se chalata hai aur farak naapta hai:

    MEMORY ON   ek hi conversation_id — bot ko pichhli baatein yaad hain
    MEMORY OFF  har turn naya conversation — bot ko kuch yaad nahi

Dono ko bilkul wahi messages jaate hain. Agar memory + pace layer kaam kar
raha hai toh ON waale me:

  1. sawaal ghat jaate hain      turn 3+ pe bot poochna band kar deta hai
  2. continuity aati hai         reply me wo cheez aati hai jo user ne
                                 PICHHLE turn me kahi thi, iss turn me nahi
  3. class chipakti hai          "haan" jaise khali message pe bhi sahi class
  4. dohraav ghatta hai          wahi suggestion dobara nahi

OFF waale me teeno nahi hone chahiye. Agar dono taraf ek jaisa aaya, toh
memory kaam NAHI kar rahi — chahe reply kitna bhi accha lage.

Chalao:
    set RAGGITA_URL=https://xxxx.lambda-url.ap-south-1.on.aws
    set RAGGITA_TOKEN=<ID token>
    python test_conversation.py

Token kahan se milega (login gate on hai isliye zaroori hai):
    App kholo, sign in karo, F12 -> Console, ye chalao:
        await window.RagAuth.idToken()
    Jo string aaye wahi. Ek ghante me expire hoti hai.
    Token kisi ko bhejna nahi — wo tumhare account ka pass hai.
"""

import os
import re
import sys
import json
import time
import urllib.request
import urllib.error

URL = os.getenv("RAGGITA_URL", "").rstrip("/")
TOKEN = os.getenv("RAGGITA_TOKEN", "").strip()
LANG = os.getenv("RAGGITA_LANG", "hi-latn")

# Ek asli-jaisi baat. Turn 4 aur 5 jaan-boojh ke khali hain ("haan",
# "pata nahi") — yahi wo jagah hai jahan purana bot patri se utar jaata tha.
SCRIPT = [
    "yaar bahut low feel kar raha hoon aaj kal",
    "placement ka pressure hai, mere batch ke sabko offer aa gaya",
    "2 months se aisa hi chal raha hai",
    "haan",
    "pata nahi",
    "kuch samajh nahi aa raha aage kya karu",
]

# Turn 2 me ye cheezein user ne kahi thi. Baad ke replies me inka zikr
# aana = bot ko yaad hai. Iss list me sirf wo shabd hain jo BAAD ke
# user-messages me nahi aate, warna cheating ho jaati.
CONTINUITY_CUES = ["placement", "batch", "offer", "2 month", "do mahine",
                   "months", "mahine"]


def post(path, payload):
    req = urllib.request.Request(
        URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": "Bearer " + TOKEN} if TOKEN else {})},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        if e.code == 401:
            print("\n  401 — token nahi chala. Expire ho gaya hoga (1 ghanta), "
                  "ya REQUIRE_AUTH on hai aur token diya nahi.")
            print("  Naya token: app me sign in karke console me "
                  "`await window.RagAuth.idToken()`")
            sys.exit(1)
        raise SystemExit(f"\n  HTTP {e.code}: {body}")


def ends_with_question(t):
    t = (t or "").strip()
    # Aakhri do sentence dekhte hain — beech me sawaal hona alag baat hai,
    # reply KHATAM sawaal pe karna wo behaviour hai jo hume rokna tha.
    return t.endswith("?") or bool(re.search(r"\?[\s\"'*_]*$", t))


def question_count(t):
    return (t or "").count("?")


def continuity_hits(reply, current_msg):
    """Reply me wo cheezein jo user ne PEHLE kahi thi, ab nahi."""
    r, c = (reply or "").lower(), (current_msg or "").lower()
    return [q for q in CONTINUITY_CUES if q in r and q not in c]


# Suggestion nikalna mushkil hai, toh proxy: content words ka overlap.
_STOP = set("""the a an and or but is are was were be been being to of in on at for
with from by as that this these those it its you your they them their i me my we us our
he she his her not no yes so if then than too very just can could would should may might
will shall do does did done have has had he'll hai hain ho hoon hun tha thi the ka ki ke
ko se me mein aur ya par lekin nahi na jo wo yeh ye is us bhi hi kuch sab kar karo karna
ek do teen liye bina agar toh tum tumhara tumhare mera mere apna apne""".split())


def content_words(t):
    ws = re.findall(r"[a-zA-Zऀ-ॿ]{4,}", (t or "").lower())
    return {w for w in ws if w not in _STOP}


def repeat_overlap(reply, previous_replies):
    """Pichhle kisi reply ke saath sabse zyada overlap (0..1)."""
    cur = content_words(reply)
    if not cur or not previous_replies:
        return 0.0
    best = 0.0
    for p in previous_replies:
        prev = content_words(p)
        if prev:
            best = max(best, len(cur & prev) / len(cur))
    return best


def run(memory_on):
    label = "MEMORY ON " if memory_on else "MEMORY OFF"
    print(f"\n{'='*74}\n  {label}   "
          f"({'ek hi conversation' if memory_on else 'har turn naya conversation'})\n{'='*74}")
    conv = ""
    rows, replies = [], []

    for n, msg in enumerate(SCRIPT):
        payload = {"question": msg, "lang": LANG, "user_class": "auto"}
        if memory_on and conv:
            payload["conversation_id"] = conv

        t0 = time.time()
        d = post("/chat", payload)
        ms = int((time.time() - t0) * 1000)

        if memory_on:
            conv = d.get("conversation_id", conv)
        ans = d.get("answer", "")
        replies_before = list(replies)
        replies.append(ans)

        row = {
            "turn": n,
            "msg": msg,
            "cls": d.get("user_class", "?"),
            "crisis": d.get("crisis", False),
            "q_end": ends_with_question(ans),
            "q_all": question_count(ans),
            "words": len(ans.split()),
            "cont": continuity_hits(ans, msg),
            "rep": repeat_overlap(ans, replies_before),
            "ms": ms,
        }
        rows.append(row)

        print(f"\n  turn {n} · THEM: {msg}")
        print(f"           class={row['cls']:8} "
              f"ends-with-?={'YES' if row['q_end'] else 'no ':3}  "
              f"words={row['words']:3}  "
              f"repeat={row['rep']:.2f}  {ms}ms")
        if row["cont"]:
            print(f"           yaad hai: {', '.join(row['cont'])}")
        print(f"           BOT : {ans[:300]}")
        if row["crisis"]:
            print("           >>> CRISIS reply (script me crisis nahi tha — "
                  "false positive dekho)")
    return rows


def summarise(rows, label):
    late = [r for r in rows if r["turn"] >= 3]
    return {
        "label": label,
        "q_end_total": sum(1 for r in rows if r["q_end"]),
        "q_end_late": sum(1 for r in late if r["q_end"]),
        "cont_turns": sum(1 for r in rows if r["cont"]),
        "general": sum(1 for r in rows if r["cls"] in ("general", "auto")),
        "avg_words": round(sum(r["words"] for r in rows) / max(1, len(rows))),
        "max_repeat": round(max((r["rep"] for r in rows), default=0), 2),
        "avg_ms": round(sum(r["ms"] for r in rows) / max(1, len(rows))),
    }


def verdict(on, off):
    print(f"\n\n{'='*74}\n  NATIJA\n{'='*74}\n")
    print(f"  {'':34}{'MEMORY ON':>12}{'MEMORY OFF':>13}")
    rowsdef = [
        ("reply sawaal pe khatam (kul 6)",     "q_end_total", "kam behtar"),
        ("   usme se turn 3+ pe",              "q_end_late",  "0 hona chahiye"),
        ("pichhli baat yaad aayi (turns)",     "cont_turns",  "zyada behtar"),
        ("class 'general' pe gira",            "general",     "kam behtar"),
        ("sabse zyada dohraav (0-1)",          "max_repeat",  "kam behtar"),
        ("average words",                      "avg_words",   ""),
        ("average latency ms",                 "avg_ms",      ""),
    ]
    for name, key, note in rowsdef:
        print(f"  {name:34}{str(on[key]):>12}{str(off[key]):>13}   {note}")

    print()
    checks = [
        ("turn 3+ pe sawaal band ho gaye",
         on["q_end_late"] == 0,
         f"ON me turn 3+ pe {on['q_end_late']} reply sawaal pe khatam — "
         "pace layer ka LAND nahi lag raha"),
        ("memory se continuity aa rahi hai",
         on["cont_turns"] > off["cont_turns"],
         f"ON me {on['cont_turns']} turns, OFF me {off['cont_turns']} — "
         "history prompt me ja hi nahi rahi, ya DynamoDB off hai"),
        ("class chipak rahi hai (general pe nahi gir rahi)",
         on["general"] <= off["general"],
         "ON me bhi general pe gir raha hai — sticky class kaam nahi kar rahi"),
        ("dohraav ON me OFF se zyada nahi",
         on["max_repeat"] <= off["max_repeat"] + 0.15,
         f"ON ka dohraav {on['max_repeat']} vs OFF {off['max_repeat']} — "
         "bot wahi baat ghuma kar bol raha hai"),
    ]
    ok = 0
    for name, passed, why in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        if not passed:
            print(f"        -> {why}")
        ok += bool(passed)

    print(f"\n  {ok}/{len(checks)} pass\n")
    if ok < len(checks):
        print("  Kuch fail hai toh CloudWatch me `turn=` aur `pace=` waali line dekho.")
        print("  pace=open dikhta rahe har turn pe = turn count nahi badh raha")
        print("  (DynamoDB se history load nahi ho rahi).\n")
    return ok == len(checks)


if __name__ == "__main__":
    if not URL:
        raise SystemExit("RAGGITA_URL set karo.\n"
                         "  set RAGGITA_URL=https://xxxx.lambda-url.ap-south-1.on.aws")
    if not TOKEN:
        print("\n  Warning: RAGGITA_TOKEN nahi diya. REQUIRE_AUTH on hai toh 401 aayega.\n")

    print(f"\n  target : {URL}\n  lang   : {LANG}\n  turns  : {len(SCRIPT)}")

    on = summarise(run(memory_on=True), "on")
    off = summarise(run(memory_on=False), "off")
    sys.exit(0 if verdict(on, off) else 1)
