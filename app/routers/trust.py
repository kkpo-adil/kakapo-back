import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.publication import Publication
from app.models.trust_score import TrustScore
from app.schemas.trust_score import TrustScoreRead
from app.services.trust_engine import compute_trust_score, get_latest_trust_score

router = APIRouter(prefix="/trust", tags=["Trust Engine"])


@router.get(
    "/score/{publication_id}",
    response_model=TrustScoreRead,
    summary="Get the latest Trust Score for a publication",
)
def get_trust_score(
    publication_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    score = get_latest_trust_score(db, publication_id)
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No trust score found for publication {publication_id}",
        )
    return score


@router.post(
    "/score/{publication_id}",
    response_model=TrustScoreRead,
    status_code=status.HTTP_201_CREATED,
    summary="Recompute and persist a new Trust Score for a publication",
    description=(
        "Triggers a fresh scoring pass on the publication using the current Trust Engine version. "
        "Previous scores are preserved in history."
    ),
)
def rescore_publication(
    publication_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if not publication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publication {publication_id} not found",
        )

    score = compute_trust_score(db, publication)
    return score


@router.get(
    "/history/{publication_id}",
    response_model=list[TrustScoreRead],
    summary="Get the full scoring history for a publication",
)
def get_score_history(
    publication_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if not publication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publication {publication_id} not found",
        )

    scores = (
        db.query(TrustScore)
        .filter(TrustScore.publication_id == publication_id)
        .order_by(TrustScore.scored_at.desc())
        .all()
    )
    return scores
