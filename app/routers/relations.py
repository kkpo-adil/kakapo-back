import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.publication import Publication
from app.models.publication_relation import PublicationRelation
from app.models.trust_score import TrustScore
from app.schemas.publication_relation import RelationCreate, RelationRead, RelatedPublication

router = APIRouter(prefix="/publications", tags=["Relations"])


@router.post(
    "/{publication_id}/relations",
    response_model=RelationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Déclarer une relation de citation vers une autre publication",
)
def add_relation(
    publication_id: uuid.UUID,
    body: RelationCreate,
    db: Session = Depends(get_db),
):
    source = db.query(Publication).filter(Publication.id == publication_id).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"Publication {publication_id} not found")

    allowed = {"cites", "extends", "contradicts", "replicates"}
    if body.relation_type not in allowed:
        raise HTTPException(status_code=422, detail=f"relation_type must be one of {allowed}")

    target_id    = body.target_id or uuid.uuid4()
    target_certified = False

    if body.target_id:
        target_pub = db.query(Publication).filter(Publication.id == body.target_id).first()
        target_certified = target_pub is not None

    relation = PublicationRelation(
        source_id=publication_id,
        target_id=target_id,
        target_doi=body.target_doi,
        target_title=body.target_title,
        relation_type=body.relation_type,
        target_certified=target_certified,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


@router.get(
    "/{publication_id}/related",
    response_model=list[RelatedPublication],
    summary="Récupérer les publications liées avec leurs scores (context_depth V1)",
)
def get_related(
    publication_id: uuid.UUID,
    context_depth: int = Query(0, ge=0, le=2, description="0=none, 1=direct links, 2=two hops"),
    db: Session = Depends(get_db),
):
    if context_depth == 0:
        return []

    relations = (
        db.query(PublicationRelation)
        .filter(PublicationRelation.source_id == publication_id)
        .all()
    )

    result: list[RelatedPublication] = []

    for rel in relations:
        trust_score = None
        title       = rel.target_title
        doi         = rel.target_doi

        if rel.target_certified:
            target_pub = db.query(Publication).filter(Publication.id == rel.target_id).first()
            if target_pub:
                title = target_pub.title
                doi   = target_pub.doi
                score_row = (
                    db.query(TrustScore)
                    .filter(TrustScore.publication_id == rel.target_id)
                    .order_by(TrustScore.scored_at.desc())
                    .first()
                )
                if score_row:
                    trust_score = score_row.score

        result.append(RelatedPublication(
            id=str(rel.target_id),
            title=title,
            doi=doi,
            relation_type=rel.relation_type,
            certified=rel.target_certified,
            trust_score=trust_score,
        ))

    return result
