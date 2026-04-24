import os
import httpx
from datetime import datetime, timezone, timedelta
from jose import jwt
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])

ORCID_CLIENT_ID = os.environ.get("ORCID_CLIENT_ID", "")
ORCID_CLIENT_SECRET = os.environ.get("ORCID_CLIENT_SECRET", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://kakapo-front.vercel.app")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

ORCID_AUTH_URL = "https://orcid.org/oauth/authorize"
ORCID_TOKEN_URL = "https://orcid.org/oauth/token"

def get_redirect_uri(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/auth/orcid/callback"

def create_jwt(data: dict) -> str:
    payload = {
        **data,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ")[1]
    try:
        return decode_jwt(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/orcid/login")
def orcid_login(request: Request):
    redirect_uri = get_redirect_uri(request)
    from urllib.parse import urlencode
    params = {
        "client_id": ORCID_CLIENT_ID,
        "response_type": "code",
        "scope": "/authenticate",
        "redirect_uri": redirect_uri,
    }
    return RedirectResponse(f"{ORCID_AUTH_URL}?{urlencode(params)}")

@router.get("/orcid/callback")
async def orcid_callback(code: str, request: Request, db: Session = Depends(get_db)):
    redirect_uri = get_redirect_uri(request)
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            ORCID_TOKEN_URL,
            data={
                "client_id": ORCID_CLIENT_ID,
                "client_secret": ORCID_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="ORCID token exchange failed")
    token_data = token_response.json()
    orcid_id = token_data.get("orcid")
    name = token_data.get("name", "")
    access_token = token_data.get("access_token")
    if not orcid_id:
        raise HTTPException(status_code=400, detail="ORCID ID not returned")
    from app.models.scientist_profile import ScientistProfile
    profile = db.query(ScientistProfile).filter(
        ScientistProfile.orcid_id == orcid_id
    ).first()
    if not profile:
        profile = ScientistProfile(
            orcid_id=orcid_id,
            display_name=name,
            is_verified=True,
            orcid_access_token=access_token,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        profile.display_name = name
        profile.orcid_access_token = access_token
        db.commit()
    jwt_token = create_jwt({
        "sub": str(profile.id),
        "orcid": orcid_id,
        "name": name,
        "role": "scientist",
    })
    return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={jwt_token}")

@router.get("/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    payload = get_current_user(request)
    from app.models.scientist_profile import ScientistProfile
    profile = db.query(ScientistProfile).filter(
        ScientistProfile.id == payload["sub"]
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@router.get("/debug")
def debug_env():
    return {
        "client_id_set": bool(ORCID_CLIENT_ID),
        "client_id_length": len(ORCID_CLIENT_ID),
        "secret_set": bool(ORCID_CLIENT_SECRET),
        "jwt_set": bool(JWT_SECRET),
    }
