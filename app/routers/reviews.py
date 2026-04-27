import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.scientific_review import ScientificReview, ReviewFlag
from app.models.publication import Publication
from app.models.scientist_profile import ScientistProfile

router = APIRouter(prefix="/reviews", tags=["Reviews"])


class ReviewCreate(BaseModel):
    methodology_score: int = Field(..., ge=0, le=5)
    data_score: int = Field(..., ge=0, le=5)
    reproducibility_score: int = Field(..., ge=0, le=5)
    clarity_score: int = Field(..., ge=0, le=5)
    flag: ReviewFlag = ReviewFlag.none
    comment: str | None = Field(None, max_length=1000)


class ReviewRead(BaseModel):
    id: uuid.UUID
    publication_id: uuid.UUID
    reviewer_orcid: str
    reviewer_name: str
    methodology_score: int
    data_score: int
    reproducibility_score: int
    clarity_score: int
    global_score: float
    flag: ReviewFlag
    comment: str | None
    is_conflict_of_interest: bool
    is_same_institution: bool
    created_at: datetime
    model_config = {"from_attributes": True}


def get_current_scientist(request: Request, db: Session = Depends(get_db)) -> ScientistProfile:
    from app.routers.auth import get_current_user
    payload = get_current_user(request)
    profile = db.query(ScientistProfile).filter(ScientistProfile.id == payload["sub"]).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Scientist profile not found")
    return profile


@router.post("/{publication_id}", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def submit_review(
    publication_id: uuid.UUID,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    scientist: ScientistProfile = Depends(get_current_scientist),
):
    publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")

    existing = db.query(ScientificReview).filter(
        ScientificReview.publication_id == publication_id,
        ScientificReview.reviewer_orcid == scientist.orcid_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this publication")

    is_same_institution = bool(
        scientist.affiliation_raw
        and publication.institution_raw
        and scientist.affiliation_raw.lower().strip() == publication.institution_raw.lower().strip()
    )

    global_score = round(
        (payload.methodology_score + payload.data_score +
         payload.reproducibility_score + payload.clarity_score) / 20.0, 4
    )

    review = ScientificReview(
        publication_id=publication_id,
        reviewer_orcid=scientist.orcid_id,
        reviewer_name=scientist.display_name,
        reviewer_institution=scientist.affiliation_raw,
        methodology_score=payload.methodology_score,
        data_score=payload.data_score,
        reproducibility_score=payload.reproducibility_score,
        clarity_score=payload.clarity_score,
        global_score=global_score,
        flag=payload.flag,
        comment=payload.comment,
        is_same_institution=is_same_institution,
        is_conflict_of_interest=is_same_institution,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/{publication_id}", response_model=list[ReviewRead])
def get_reviews(publication_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(ScientificReview).filter(
        ScientificReview.publication_id == publication_id
    ).order_by(ScientificReview.created_at.desc()).all()
