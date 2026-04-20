import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.kpt import KPTRead, KPTIssueRequest, KPTVerifyResponse, KPTStatusUpdate
from app.services import kpt_service

router = APIRouter(prefix="/kpt", tags=["KPT"])


# /issue et /publication/{id} AVANT /{kpt_id} pour éviter le shadowing FastAPI
@router.post(
    "/issue",
    response_model=KPTRead,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new KPT for an existing publication",
)
def issue_kpt(
    request: KPTIssueRequest,
    db: Session = Depends(get_db),
):
    try:
        kpt = kpt_service.issue_kpt(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return kpt


@router.get(
    "/publication/{publication_id}",
    response_model=list[KPTRead],
    summary="List all KPT versions for a publication",
)
def list_kpts_for_publication(
    publication_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return kpt_service.list_kpts_for_publication(db, publication_id)


# Routes avec paramètre dynamique {kpt_id} — après les routes statiques
@router.get(
    "/{kpt_id}",
    response_model=KPTRead,
    summary="Get a KPT by its human-readable identifier",
)
def get_kpt(
    kpt_id: str,
    db: Session = Depends(get_db),
):
    kpt = kpt_service.get_kpt_by_kpt_id(db, kpt_id)
    if not kpt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"KPT '{kpt_id}' not found")
    return kpt


@router.post(
    "/{kpt_id}/verify",
    response_model=KPTVerifyResponse,
    summary="Verify the integrity and status of a KPT",
)
def verify_kpt(
    kpt_id: str,
    verify_file: bool = Query(False, description="Recompute file hash and compare with stored hash"),
    db: Session = Depends(get_db),
):
    file_path = None
    if verify_file:
        kpt = kpt_service.get_kpt_by_kpt_id(db, kpt_id)
        if kpt and kpt.publication and kpt.publication.file_path:
            file_path = kpt.publication.file_path
    return kpt_service.verify_kpt(db, kpt_id, file_path=file_path)


@router.patch(
    "/{kpt_id}/status",
    response_model=KPTRead,
    summary="Update KPT status: challenged | revoked | superseded",
)
def update_kpt_status(
    kpt_id: str,
    body: KPTStatusUpdate,
    db: Session = Depends(get_db),
):
    allowed = {"challenged", "revoked", "superseded"}
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of: {', '.join(sorted(allowed))}",
        )
    try:
        return kpt_service.update_kpt_status(db, kpt_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
