import os
import httpx
from datetime import datetime, timezone, timedelta
from jose import jwt
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

def get_orcid_client_id(): return os.environ.get("ORCID_CLIENT_ID", "")
def get_orcid_client_secret(): return os.environ.get("ORCID_CLIENT_SECRET", "")
def get_jwt_secret(): return os.environ.get("JWT_SECRET", "")
def get_frontend_url(): return os.environ.get("FRONTEND_URL", "https://kakapo-front.vercel.app")

ORCID_AUTH_URL = "https://orcid.org/oauth/authorize"
ORCID_TOKEN_URL = "https://orcid.org/oauth/token"

def get_redirect_uri(request: Request) -> str:
    return "https://kakapo-back-production.up.railway.app/auth/orcid/callback"

def create_jwt(data: dict) -> str:
    payload = {
        **data,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def decode_jwt(token: str) -> dict:
    return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])

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
    ORCID_CLIENT_ID = get_orcid_client_id()
    ORCID_CLIENT_ID = get_orcid_client_id()
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
                "client_id": get_orcid_client_id(),
                "client_secret": get_orcid_client_secret(),
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
    return RedirectResponse(f"{get_frontend_url()}/auth/callback?token={jwt_token}")

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



class ProfileUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    bio: str | None = None
    primary_domain: str | None = None
    affiliation_raw: str | None = None
    institution_ror: str | None = None


@router.patch("/me", response_model=dict)
def update_me(payload: ProfileUpdate, request: Request, db: Session = Depends(get_db)):
    jwt_payload = get_current_user(request)
    from app.models.scientist_profile import ScientistProfile
    profile = db.query(ScientistProfile).filter(
        ScientistProfile.id == jwt_payload["sub"]
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return {
        "id": str(profile.id),
        "display_name": profile.display_name,
        "email": profile.email,
        "bio": profile.bio,
        "primary_domain": profile.primary_domain,
        "affiliation_raw": profile.affiliation_raw,
        "institution_ror": profile.institution_ror,
        "orcid_id": profile.orcid_id,
        "is_verified": profile.is_verified,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


@router.get("/dashboard")
def get_dashboard(request: Request, db: Session = Depends(get_db)):
    from app.routers.auth import get_current_user
    from app.models.scientist_profile import ScientistProfile
    from app.models.publication import Publication
    from app.models.kpt import KPT
    from app.models.integrity_check_log import IntegrityCheckLog
    from app.models.query_log import QueryLog
    from app.services.kpt_quota_service import KPTQuotaService
    from sqlalchemy import func

    payload = get_current_user(request)
    profile = db.query(ScientistProfile).filter(ScientistProfile.id == payload["sub"]).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    active_kpts = db.query(KPT).filter(KPT.status == "active").all()
    active_pub_ids = [k.publication_id for k in active_kpts]
    publications = db.query(Publication).filter(Publication.id.in_(active_pub_ids)).all()

    pub_ids = [str(p.id) for p in publications]

    kpts = db.query(KPT).filter(KPT.publication_id.in_(pub_ids)).all()
    kpt_ids = [k.id for k in kpts]

    total_verifications = db.query(IntegrityCheckLog).filter(
        IntegrityCheckLog.kpt_id.in_(kpt_ids)
    ).count()

    total_ai_queries = db.query(QueryLog).filter(
        QueryLog.doi_queried.in_([k.doi for k in kpts])
    ).count()

    quota_service = KPTQuotaService()
    quota_status = quota_service.get_status(profile)

    pub_stats = []
    for pub in publications:
        pub_kpts = [k for k in kpts if str(k.publication_id) == str(pub.id)]
        active_kpt = next((k for k in pub_kpts if k.status == "active"), None)
        kpt_ids_for_pub = [k.id for k in pub_kpts]
        verif_count = db.query(IntegrityCheckLog).filter(
            IntegrityCheckLog.kpt_id.in_(kpt_ids_for_pub)
        ).count()
        ai_count = db.query(QueryLog).filter(
            QueryLog.doi_queried == pub.doi
        ).count() if pub.doi else 0
        pub_stats.append({
            "id": str(pub.id),
            "title": pub.title,
            "doi": pub.doi,
            "source": pub.source,
            "submitted_at": pub.submitted_at.isoformat() if pub.submitted_at else None,
            "kpt_id": active_kpt.kpt_id if active_kpt else None,
            "kpt_status": active_kpt.status if active_kpt else None,
            "verifications": verif_count,
            "ai_queries": ai_count,
        })

    return {
        "profile": {
            "display_name": profile.display_name,
            "orcid_id": profile.orcid_id,
            "is_verified": profile.is_verified,
        },
        "quota": {
            "monthly_quota": quota_status.quota,
            "used": quota_status.used,
            "remaining": quota_status.remaining,
            "period_end": quota_status.period_end.isoformat(),
        },
        "stats": {
            "total_publications": len(publications),
            "total_kpts": len(kpts),
            "total_verifications": total_verifications,
            "total_ai_queries": total_ai_queries,
        },
        "publications": pub_stats,
    }
