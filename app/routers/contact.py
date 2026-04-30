import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.contact_request import ContactRequest

router = APIRouter(prefix="/contact", tags=["Contact"])
logger = logging.getLogger(__name__)

ALLOWED_SEGMENTS = {"llm", "pharma", "legal-finance", "institutions", "publisher", "other"}
RATE_LIMIT: dict[str, datetime] = {}
RATE_LIMIT_SECONDS = 300


class ContactPayload(BaseModel):
    segment: str
    payload: dict
    rgpd_consent: bool


@router.post("")
def submit_contact(data: ContactPayload, request: Request, db: Session = Depends(get_db)):
    if data.segment not in ALLOWED_SEGMENTS:
        raise HTTPException(status_code=400, detail="Segment invalide")

    if not data.rgpd_consent:
        raise HTTPException(status_code=400, detail="Le consentement RGPD est requis")

    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{data.segment}"
    now = datetime.now(timezone.utc)
    last = RATE_LIMIT.get(rate_key)
    if last and (now - last).total_seconds() < RATE_LIMIT_SECONDS:
        raise HTTPException(status_code=429, detail="Merci de patienter avant de soumettre à nouveau.")

    RATE_LIMIT[rate_key] = now

    email = data.payload.get("email", "")

    contact = ContactRequest(
        segment=data.segment,
        email=email,
        payload=json.dumps(data.payload, ensure_ascii=False),
    )
    db.add(contact)
    db.commit()

    logger.info(
        f"[CONTACT] segment={data.segment} email={email} payload={json.dumps(data.payload)}"
    )

    return {"status": "ok", "message": "Votre demande a bien été reçue. Notre équipe revient vers vous sous 48h."}
