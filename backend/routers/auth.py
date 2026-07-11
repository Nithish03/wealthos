from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import sys, os, hashlib, hmac, base64, json, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from models import User
from schemas import PINSetup, PINLogin, Token

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = b"wealthos-secret-key-2024-local"
ACCESS_TOKEN_EXPIRE_DAYS = 30


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
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=404, detail="No PIN set. Please set up first.")
    if not verify_pin(data.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="Invalid PIN")
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


@router.delete("/reset")
def reset_pin(db: Session = Depends(get_db)):
    """
    Emergency reset — deletes stored PIN so you can set a new one.
    Only works locally. Call: DELETE http://localhost:8000/auth/reset
    """
    users = db.query(User).all()
    for u in users:
        db.delete(u)
    db.commit()
    return {"message": "PIN reset. Set a new PIN at /auth/setup"}
