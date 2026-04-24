import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.ai_client_profile import AIClientProfile, PlanType, PLAN_QUOTAS, PLAN_PRICES

router = APIRouter(prefix="/clients", tags=["AI Clients"])


class ClientRegisterRequest(BaseModel):
    organization_name: str
    contact_email: str
    plan_type: PlanType = PlanType.compliance_starter


class ClientRead(BaseModel):
    id: uuid.UUID
    organization_name: str
    contact_email: str
    plan_type: PlanType
    monthly_quota: int
    quota_used_current_month: int
    price_per_query: float
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ClientWithKey(ClientRead):
    api_key: str


def get_ai_client(request: Request, db: Session = Depends(get_db)) -> AIClientProfile:
    api_key = request.headers.get("X-Client-API-Key", "")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-Client-API-Key header")
    client = db.query(AIClientProfile).filter(
        AIClientProfile.api_key == api_key,
        AIClientProfile.is_active == True,
    ).first()
    if not client:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return client


@router.post("/register", response_model=ClientWithKey, status_code=status.HTTP_201_CREATED)
def register_client(payload: ClientRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(AIClientProfile).filter(
        AIClientProfile.contact_email == payload.contact_email
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    quota = PLAN_QUOTAS.get(payload.plan_type, 100_000)
    price = PLAN_PRICES.get(payload.plan_type, 0.002)
    client = AIClientProfile(
        organization_name=payload.organization_name,
        contact_email=payload.contact_email,
        api_key=AIClientProfile.generate_api_key(),
        plan_type=payload.plan_type,
        monthly_quota=quota,
        price_per_query=price,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/me", response_model=ClientRead)
def get_me(client: AIClientProfile = Depends(get_ai_client)):
    return client


@router.get("/me/usage")
def get_usage(client: AIClientProfile = Depends(get_ai_client)):
    quota = client.monthly_quota
    used = client.quota_used_current_month
    remaining = max(0, quota - used) if quota > 0 else -1
    return {
        "plan_type": client.plan_type,
        "monthly_quota": quota,
        "quota_used": used,
        "quota_remaining": remaining,
        "overage": max(0, used - quota) if quota > 0 else 0,
        "price_per_query": float(client.price_per_query),
    }


@router.post("/me/rotate-key", response_model=ClientWithKey)
def rotate_key(client: AIClientProfile = Depends(get_ai_client), db: Session = Depends(get_db)):
    client.api_key = AIClientProfile.generate_api_key()
    db.commit()
    db.refresh(client)
    return client
