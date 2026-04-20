import uuid
import json
from pathlib import Path
from datetime import datetime, timezone

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.publication import Publication
from app.schemas.publication import PublicationRead, PublicationList
from app.services.hash_service import compute_sha256_file
from app.services.kpt_service import issue_kpt
from app.services.trust_engine import compute_trust_score
from app.schemas.kpt import KPTIssueRequest

router = APIRouter(prefix="/publications", tags=["Publications"])


@router.post(
    "/upload",
    response_model=PublicationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF and create a publication with its KPT and Trust Score",
)
async def upload_publication(
    file: UploadFile = File(..., description="PDF file"),
    title: str = Form(..., min_length=1, max_length=512),
    abstract: str | None = Form(None),
    source: str | None = Form(None, description="hal | arxiv | direct | other"),
    doi: str | None = Form(None),
    authors_raw: str | None = Form(None, description="JSON string: [{name, orcid?}]"),
    institution_raw: str | None = Form(None),
    submitted_at: str | None = Form(None, description="ISO 8601 datetime"),
    orcid_authors: str | None = Form(None, description="JSON array of ORCID URIs"),
    ror_institution: str | None = Form(None),
    dataset_hashes: str | None = Form(None, description="JSON array of SHA-256 strings"),
    db: Session = Depends(get_db),
):
    # --- Validate file type ---
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are accepted",
        )

    # --- Validate file size ---
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # --- Validate source ---
    allowed_sources = {"hal", "arxiv", "direct", "other", None}
    if source not in allowed_sources:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source must be one of: hal, arxiv, direct, other",
        )

    # --- Parse optional JSON fields ---
    parsed_orcid = None
    if orcid_authors:
        try:
            parsed_orcid = json.loads(orcid_authors)
            if not isinstance(parsed_orcid, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="orcid_authors must be a valid JSON array",
            )

    parsed_dataset_hashes = None
    if dataset_hashes:
        try:
            parsed_dataset_hashes = json.loads(dataset_hashes)
            if not isinstance(parsed_dataset_hashes, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="dataset_hashes must be a valid JSON array",
            )

    parsed_submitted_at = None
    if submitted_at:
        try:
            parsed_submitted_at = datetime.fromisoformat(submitted_at)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="submitted_at must be a valid ISO 8601 datetime",
            )

    # --- Persist file ---
    pub_id = uuid.uuid4()
    upload_dir: Path = settings.upload_path / str(pub_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = Path(file.filename).name if file.filename else "document.pdf"
    dest_path = upload_dir / safe_filename

    async with aiofiles.open(dest_path, "wb") as out_file:
        while chunk := await file.read(65536):
            await out_file.write(chunk)

    # --- Compute hash ---
    file_hash = compute_sha256_file(dest_path)

    # --- Create Publication ---
    publication = Publication(
        id=pub_id,
        title=title,
        abstract=abstract,
        source=source,
        file_path=str(dest_path),
        file_hash=file_hash,
        doi=doi,
        authors_raw=authors_raw,
        institution_raw=institution_raw,
        submitted_at=parsed_submitted_at,
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)

    # --- Issue KPT ---
    kpt_request = KPTIssueRequest(
        publication_id=publication.id,
        orcid_authors=parsed_orcid,
        ror_institution=ror_institution,
        dataset_hashes=parsed_dataset_hashes,
    )
    issue_kpt(db, kpt_request)

    # --- Compute Trust Score ---
    compute_trust_score(db, publication, dataset_hashes=parsed_dataset_hashes)

    db.refresh(publication)
    return publication


@router.get(
    "/",
    response_model=PublicationList,
    summary="List all publications with pagination",
)
def list_publications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    source: str | None = Query(None, description="Filter by source"),
    db: Session = Depends(get_db),
):
    query = db.query(Publication)
    if source:
        query = query.filter(Publication.source == source)

    total = query.count()
    items = query.order_by(Publication.created_at.desc()).offset(skip).limit(limit).all()

    return PublicationList(total=total, items=items)


@router.get(
    "/{publication_id}",
    response_model=PublicationRead,
    summary="Get a publication by ID",
)
def get_publication(
    publication_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if not publication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publication {publication_id} not found",
        )
    return publication
