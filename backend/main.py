"""
HIREBLOCK Early Access API
Stores hashes only. Issues JWTs. New accounts are waitlisted until public launch (TBD).
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func

SECRET_KEY = os.getenv("HIREBLOCK_SECRET", "hireblock-dev-only-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 14
PUBLIC_LAUNCH = os.getenv("HIREBLOCK_PUBLIC_LAUNCH", "TBD")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hireblock.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

ADJECTIVES = [
    "ancient", "bold", "calm", "daring", "eager", "fierce", "gentle", "happy",
    "inventive", "joyful", "keen", "lively", "mighty", "noble", "optimistic",
    "peaceful", "quick", "radiant", "strong", "trusty", "unique", "vivid",
    "wise", "youthful", "zealous", "brave", "clever", "dynamic", "elegant",
    "fearless", "graceful", "heroic", "insightful",
]
NOUNS = [
    "eagle", "falcon", "griffin", "hawk", "lion", "phoenix", "raven", "tiger",
    "wolf", "bear", "dragon", "fox", "horse", "jaguar", "knight", "leopard",
    "owl", "panther", "raptor", "shark", "turtle", "unicorn", "viper", "walrus",
    "zebra", "arrow", "blade", "crown", "echo", "flame", "glacier", "harbor",
]

ALLOWED_ID_TYPES = {"dl", "fein", "ssn", "address"}
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

app = FastAPI(title="HIREBLOCK Early Access API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(120), unique=True, index=True, nullable=False)
    user_type = Column(String(20), nullable=False)
    final_hash = Column(String(64), nullable=False)
    id_type = Column(String(20), nullable=False)
    access_tier = Column(String(30), default="early_access")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reveal_consents = relationship("RevealConsent", back_populates="user", cascade="all, delete-orphan")


class RevealConsent(Base):
    __tablename__ = "reveal_consents"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_username = Column(String(120), index=True, nullable=False)
    revealed_email = Column(Boolean, default=False)
    revealed_phone = Column(Boolean, default=False)
    revealed_full = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user = relationship("User", back_populates="reveal_consents")


Base.metadata.create_all(bind=engine)


class PIIPayload(BaseModel):
    first_name: str
    middle_name: Optional[str] = ""
    last_name: str
    dob: str
    id_type: str
    id_value: str
    entity_name: Optional[str] = ""


class SignupRequest(BaseModel):
    user_type: str = Field(pattern="^(employer|professional)$")
    pii: PIIPayload


class LoginRequest(BaseModel):
    username: str
    user_type: str
    pii: PIIPayload


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_type: str
    access_tier: str
    public_launch: str
    notice: str


class MatchOut(BaseModel):
    match_username: str
    match_type: str
    title: str
    reveal_status: Dict[str, bool]


class RevealRequest(BaseModel):
    step: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def norm(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_pii(pii: PIIPayload) -> None:
    if len(pii.first_name.strip()) < 2 or len(pii.last_name.strip()) < 2:
        raise HTTPException(400, "First and last name are required.")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", pii.dob):
        raise HTTPException(400, "Birth date must be YYYY-MM-DD.")
    id_type = pii.id_type.lower().strip()
    if id_type not in ALLOWED_ID_TYPES:
        raise HTTPException(400, "id_type must be dl, fein, ssn, or address.")
    val = pii.id_value.strip()
    if id_type == "fein" and not re.match(r"^\d{2}-\d{7}$", val):
        raise HTTPException(400, "FEIN must be XX-XXXXXXX.")
    if id_type == "ssn" and not re.match(r"^(\d{3}-\d{2}-\d{4}|\d{9})$", val):
        raise HTTPException(400, "SSN must be XXX-XX-XXXX.")
    if id_type == "dl" and not re.match(r"^[A-Za-z0-9-]{5,20}$", val):
        raise HTTPException(400, "Driver license must be 5-20 letters or numbers.")
    if id_type == "address" and len(val) < 10:
        raise HTTPException(400, "Address is too short to use as an identifier.")


def compute_final_hash(pii: PIIPayload) -> str:
    validate_pii(pii)
    parts = [
        norm(pii.first_name),
        norm(pii.middle_name or ""),
        norm(pii.last_name),
        norm(pii.dob),
        norm(pii.id_type),
        norm(pii.id_value),
    ]
    combined = "".join(sha(part) for part in parts)
    return sha(combined)


def generate_username(user_type: str, final_hash: str) -> str:
    adj1 = ADJECTIVES[int(final_hash[0:8], 16) % len(ADJECTIVES)]
    noun = NOUNS[int(final_hash[8:16], 16) % len(NOUNS)]
    adj2 = ADJECTIVES[int(final_hash[16:24], 16) % len(ADJECTIVES)]
    prefix = "co" if user_type == "employer" else "pro"
    return f"{prefix}-{adj1}-{noun}-{adj2}"


def create_access_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise JWTError()
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired key.")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found.")
    return user


def notice_text() -> str:
    return (
        f"Early access only. Your anonymous key is saved. "
        f"Matching and full reveal go live on public launch ({PUBLIC_LAUNCH})."
    )


@app.get("/")
def root():
    return {
        "product": "HIREBLOCK",
        "status": "early_access",
        "public_launch": PUBLIC_LAUNCH,
        "docs": "/docs",
    }


@app.post("/api/signup", response_model=TokenResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    final_hash = compute_final_hash(req.pii)
    username = generate_username(req.user_type, final_hash)
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "This identity already has a key. Use Login.")
    user = User(
        username=username,
        user_type=req.user_type,
        final_hash=final_hash,
        id_type=req.pii.id_type.lower().strip(),
        access_tier="early_access",
    )
    db.add(user)
    db.commit()
    return TokenResponse(
        access_token=create_access_token(username),
        username=username,
        user_type=req.user_type,
        access_tier="early_access",
        public_launch=PUBLIC_LAUNCH,
        notice=notice_text(),
    )


@app.post("/api/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username.strip()).first()
    if not user:
        raise HTTPException(404, "Username not found.")
    computed = compute_final_hash(req.pii)
    if computed != user.final_hash or req.user_type != user.user_type:
        raise HTTPException(
            401,
            "Identity mismatch. First/middle/last name, birth date, and identifier must match signup exactly.",
        )
    return TokenResponse(
        access_token=create_access_token(user.username),
        username=user.username,
        user_type=user.user_type,
        access_tier=user.access_tier,
        public_launch=PUBLIC_LAUNCH,
        notice=notice_text(),
    )


@app.get("/api/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "user_type": current_user.user_type,
        "access_tier": current_user.access_tier,
        "public_launch": PUBLIC_LAUNCH,
        "notice": notice_text(),
    }


MOCK_MATCHES = [
    {"match_username": "co-wise-fox-brave", "match_type": "employer", "title": "Preview: Healthcare Regulatory Counsel"},
    {"match_username": "pro-calm-lion-daring", "match_type": "professional", "title": "Preview: Senior IP Attorney"},
    {"match_username": "co-strong-eagle-quick", "match_type": "employer", "title": "Preview: Clinical Lab Scientists"},
]


@app.get("/api/matches", response_model=List[MatchOut])
def matches(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for m in MOCK_MATCHES:
        row = (
            db.query(RevealConsent)
            .filter(
                RevealConsent.user_id == current_user.id,
                RevealConsent.match_username == m["match_username"],
            )
            .first()
        )
        out.append(
            MatchOut(
                match_username=m["match_username"],
                match_type=m["match_type"],
                title=m["title"] + " — live matching TBD",
                reveal_status={
                    "email": bool(row and row.revealed_email),
                    "phone": bool(row and row.revealed_phone),
                    "full": bool(row and row.revealed_full),
                },
            )
        )
    return out


@app.post("/api/reveal/{match_username}")
def reveal(
    match_username: str,
    req: RevealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.step not in {"email", "phone", "full"}:
        raise HTTPException(400, "step must be email, phone, or full")
    row = (
        db.query(RevealConsent)
        .filter(
            RevealConsent.user_id == current_user.id,
            RevealConsent.match_username == match_username,
        )
        .first()
    )
    if not row:
        row = RevealConsent(user_id=current_user.id, match_username=match_username)
        db.add(row)
    if req.step == "email":
        row.revealed_email = True
    elif req.step == "phone":
        row.revealed_phone = True
    else:
        row.revealed_full = True
    db.commit()
    return {
        "match_username": match_username,
        "revealed_email": row.revealed_email,
        "revealed_phone": row.revealed_phone,
        "revealed_full": row.revealed_full,
        "notice": "Consent recorded. Counterparty identity stays sealed until public launch (TBD).",
    }
