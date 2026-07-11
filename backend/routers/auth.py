from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
import sys, os, hashlib, hmac, base64, json, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import User
from schemas import PINSetup, PINLogin, Token

router = APIRouter(prefix="/auth", tags=["auth"])


def _load_secret() -> bytes:
    """Token-signing secret. Priority: WEALTHOS_SECRET env var, then a
    generated backend/.secret file (git-ignored). Never hardcoded — a secret
    in the repo would let anyone forge session tokens."""
    env = os.environ.get("WEALTHOS_SECRET")
    if env:
        return env.encode()
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".secret")
    try:
        with open(path, "rb") as f:
            return f.read().strip()
    except FileNotFoundError:
        import secrets
        value = secrets.token_hex(32).encode()
        with open(path, "wb") as f:
            f.write(value)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return value


SECRET_KEY = _load_secret()
ACCESS_TOKEN_EXPIRE_DAYS = 30

# ── Login rate limiting (single-user app → one global counter) ────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
_failed = {"count": 0, "locked_until": 0.0}


def _check_lockout():
    remaining = _failed["locked_until"] - time.time()
    if remaining > 0:
        raise HTTPException(status_code=429,
                            detail=f"Too many wrong PINs. Try again in {int(remaining) + 1}s.")


def _record_failure():
    _failed["count"] += 1
    if _failed["count"] >= MAX_FAILED_ATTEMPTS:
        _failed["count"] = 0
        _failed["locked_until"] = time.time() + LOCKOUT_SECONDS


def _record_success():
    _failed["count"] = 0
    _failed["locked_until"] = 0.0


def hash_pin(pin: str) -> str:
    """PBKDF2-SHA256 PIN hash using Python stdlib only — no third-party deps"""
    salt = b"wealthos-static-salt-v1"
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 260000)
    return dk.hex()


def verify_pin(pin: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_pin(pin), stored_hash)


def create_token(user_id: int) -> str:
    payload = json.dumps({"sub": str(user_id), "exp": time.time() + ACCESS_TOKEN_EXPIRE_DAYS * 86400})
    data = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(SECRET_KEY, data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def verify_token(token: str) -> bool:
    try:
        data, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET_KEY, data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        payload = json.loads(base64.urlsafe_b64decode(data + "=="))
        return payload["exp"] > time.time()
    except Exception:
        return False


def require_auth(authorization: Optional[str] = Header(None)):
    """Dependency that gates every data router behind a valid bearer token."""
    if (
        not authorization
        or not authorization.lower().startswith("bearer ")
        or not verify_token(authorization.split(" ", 1)[1].strip())
    ):
        raise HTTPException(status_code=401, detail="Not authenticated")


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    user = db.query(User).first()
    return {"has_pin": user is not None}


@router.post("/setup", response_model=Token)
def setup_pin(data: PINSetup, db: Session = Depends(get_db)):
    existing = db.query(User).first()
    if existing:
        raise HTTPException(status_code=400, detail="PIN already set. Use /auth/login instead.")
    if len(data.pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")
    user = User(pin_hash=hash_pin(data.pin))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.post("/login", response_model=Token)
def login(data: PINLogin, db: Session = Depends(get_db)):
    _check_lockout()
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=404, detail="No PIN set. Please set up first.")
    if not verify_pin(data.pin, user.pin_hash):
        _record_failure()
        raise HTTPException(status_code=401, detail="Invalid PIN")
    _record_success()
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.post("/change-pin", response_model=Token)
def change_pin(data: PINSetup, db: Session = Depends(get_db)):
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found")
    if len(data.pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")
    user.pin_hash = hash_pin(data.pin)
    db.commit()
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.delete("/reset", dependencies=[Depends(require_auth)])
def reset_pin(db: Session = Depends(get_db)):
    """
    Reset PIN (requires a valid session token — otherwise anyone on the
    network could hijack the data by resetting the PIN and setting their own).
    Forgot the PIN entirely? Clear it straight from the local database:
    sqlite3 finance_tracker.db "DELETE FROM users;"
    """
    users = db.query(User).all()
    for u in users:
        db.delete(u)
    db.commit()
    return {"message": "PIN reset. Set a new PIN at /auth/setup"}
