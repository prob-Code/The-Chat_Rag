"""
RagGita — Firebase ID token verification.

Client (web ya Expo) Firebase se sign-in karta hai aur ek ID token paata hai —
ek RS256 JWT jo ek ghante me expire hota hai aur SDK khud refresh karta rehta hai.
Woh token `Authorization: Bearer <token>` me aata hai; yahan verify hota hai.

Koi Firebase Admin SDK nahi, koi service account JSON nahi. Sirf Google ki
public certs se signature check — jo ek network call hai, per cold start,
cached. Iska matlab Lambda me koi secret rakhna hi nahi padta.

Jo cheezein check hoti hain (sab zaroori hain):
  - signature    Google ki current signing key se
  - exp / iat    token ab valid hai
  - aud          tumhare Firebase project ka id
  - iss          https://securetoken.google.com/<projectId>
  - sub          khali nahi

`aud` aur `iss` check chhodna sabse aam galti hai — unke bina kisi
DOOSRE Firebase project ka token bhi tumhare app me chal jaata hai.
"""

import os
import time
import logging

logger = logging.getLogger(__name__)

CERT_URL = ("https://www.googleapis.com/robot/v1/metadata/x509/"
            "securetoken@system.gserviceaccount.com")

_certs = {}
_certs_expire_at = 0.0


class AuthError(Exception):
    """Token galat hai. Message client ko dikhane layak hai."""


def project_id() -> str:
    return os.getenv("FIREBASE_PROJECT_ID", "").strip()


def enabled() -> bool:
    if not project_id():
        return False
    try:
        import jwt  # noqa: F401
        return True
    except ImportError:
        logger.warning("FIREBASE_PROJECT_ID set hai par PyJWT nahi mila — "
                       "pip install 'pyjwt[crypto]'")
        return False


def _load_certs(force=False):
    """Google ki public certs, cached. Woh roz rotate hoti hain."""
    global _certs, _certs_expire_at

    if _certs and not force and time.time() < _certs_expire_at:
        return _certs

    import requests
    r = requests.get(CERT_URL, timeout=5)
    r.raise_for_status()
    _certs = r.json()

    # Cache-Control ka max-age maano; na mile toh ek ghanta
    ttl = 3600
    cc = r.headers.get("cache-control", "")
    for part in cc.split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                ttl = max(300, int(part.split("=", 1)[1]))
            except ValueError:
                pass
    _certs_expire_at = time.time() + ttl
    logger.info("Firebase certs loaded (%d keys, ttl %ds)", len(_certs), ttl)
    return _certs


def verify_firebase_claims(token: str) -> dict:
    """Token verify karo aur poore claims return karo.

    Fail hone pe AuthError uthata hai. Kabhi chupchaap pass nahi karta —
    auth me "shayad theek hai" ka koi matlab nahi.

    Claims me `firebase.sign_in_provider` hota hai ("google.com",
    "anonymous", waghairah) — hard login gate ke liye wahi dekhna padta
    hai, kyunki anonymous ka token bhi poori tarah valid hota hai.
    """
    if not token:
        raise AuthError("No token provided.")

    pid = project_id()
    if not pid:
        raise AuthError("Server is not configured for sign-in.")

    try:
        import jwt
        from cryptography.x509 import load_pem_x509_certificate
        from cryptography.hazmat.backends import default_backend
    except ImportError as e:
        raise AuthError("Sign-in is unavailable on the server.") from e

    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        raise AuthError("Malformed token.") from e

    kid = header.get("kid")
    if not kid:
        raise AuthError("Token is missing a key id.")

    certs = _load_certs()
    pem = certs.get(kid)
    if pem is None:
        certs = _load_certs(force=True)   # keys rotate roz
        pem = certs.get(kid)
    if pem is None:
        raise AuthError("Unrecognised signing key. Please sign in again.")

    try:
        cert = load_pem_x509_certificate(pem.encode(), default_backend())
        public_key = cert.public_key()
    except Exception as e:
        raise AuthError("Could not read the signing certificate.") from e

    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=pid,
            issuer=f"https://securetoken.google.com/{pid}",
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except Exception as e:
        # jwt ke exception ka naam hi kaafi batata hai (ExpiredSignatureError,
        # InvalidAudienceError waghairah) — client ko woh dikhana theek hai.
        raise AuthError(f"{type(e).__name__}: {str(e)[:120]}") from e

    if not (claims.get("sub") or ""):
        raise AuthError("Token has no subject.")

    return claims


def verify_firebase_token(token: str) -> str:
    """Sirf uid chahiye ho toh. (Purana naam — jahan claims ki zaroorat
    nahi wahan yahi kaafi hai.)"""
    return verify_firebase_claims(token)["sub"]


def sign_in_provider(claims: dict) -> str:
    """"google.com" / "anonymous" / "password" ... na mile toh khali."""
    return (claims.get("firebase") or {}).get("sign_in_provider", "") or ""


def is_anonymous(claims: dict) -> bool:
    return sign_in_provider(claims) == "anonymous"


def display_name(claims: dict) -> str:
    """Log me daalne ke liye NAHI. Sirf /whoami jaisa response banane ke
    liye, jahan user apni hi baat dekh raha hota hai."""
    return (claims.get("name") or claims.get("email") or "").strip()
