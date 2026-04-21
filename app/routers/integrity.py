from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.kpt import KPT
from app.models.integrity_check_log import IntegrityCheckLog, IntegrityResult
from app.schemas.integrity import IntegrityVerifyRequest, IntegrityVerifyResponse
from datetime import datetime, timezone

router = APIRouter(prefix="/integrity", tags=["Integrity"])


@router.post("/verify", response_model=IntegrityVerifyResponse)
def verify_integrity(payload: IntegrityVerifyRequest, request: Request, db: Session = Depends(get_db)):
    ip = payload.ip_address or request.client.host

    kpt = db.query(KPT).filter(
        KPT.doi == payload.doi,
        KPT.status.in_(["active", "active_preprint"]),
    ).first()

    if kpt is None:
        log = IntegrityCheckLog(
            submitted_hash=payload.content_hash,
            result=IntegrityResult.not_found,
            checked_at=datetime.now(timezone.utc),
            ip_address=ip,
        )
        db.add(log)
        db.commit()
        return IntegrityVerifyResponse(
            status=IntegrityResult.not_found,
            message="Aucun KPT actif trouvé pour ce DOI",
        )

    result = IntegrityResult.match if kpt.content_hash == payload.content_hash else IntegrityResult.mismatch

    log = IntegrityCheckLog(
        kpt_id=kpt.id,
        requester_id=payload.requester_id,
        submitted_hash=payload.content_hash,
        expected_hash=kpt.content_hash,
        result=result,
        checked_at=datetime.now(timezone.utc),
        ip_address=ip,
    )
    db.add(log)
    db.commit()

    if result == IntegrityResult.mismatch:
        return IntegrityVerifyResponse(
            status=IntegrityResult.mismatch,
            message="Le contenu soumis ne correspond pas à la publication certifiée",
            kpt_id=kpt.id,
            certified_at=kpt.certified_at,
            score=0,
        )

    return IntegrityVerifyResponse(
        status=IntegrityResult.match,
        message="Intégrité vérifiée",
        kpt_id=kpt.id,
        version=kpt.version,
        score=kpt.score,
        certified_at=kpt.certified_at,
    )
