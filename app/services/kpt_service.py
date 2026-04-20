import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.kpt import KPT
from app.models.publication import Publication
from app.schemas.kpt import KPTIssueRequest, KPTVerifyResponse
from app.services.hash_service import verify_file_hash, compute_sha256_file


def _build_kpt_id(publication: Publication, version: int) -> str:
    pub_short = str(publication.id).replace("-", "")[:8].upper()
    suffix = str(uuid.uuid4()).replace("-", "")[:8].upper()
    return f"KPT-{pub_short}-v{version}-{suffix}"


def issue_kpt(db: Session, request: KPTIssueRequest) -> KPT:
    publication = db.query(Publication).filter(
        Publication.id == request.publication_id
    ).first()

    if publication is None:
        raise ValueError(f"Publication {request.publication_id} not found")

    if publication.file_hash is None:
        raise ValueError("Publication has no file hash — upload a PDF first")

    existing_kpts = (
        db.query(KPT)
        .filter(KPT.publication_id == request.publication_id)
        .order_by(KPT.version.desc())
        .all()
    )

    if existing_kpts:
        last_version = existing_kpts[0].version
        for old_kpt in existing_kpts:
            if old_kpt.status == "active":
                old_kpt.status = "superseded"
        version = last_version + 1
    else:
        version = 1

    metadata = {
        "publication_id": str(publication.id),
        "title": publication.title,
        "source": publication.source,
        "doi": publication.doi,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "orcid_authors": request.orcid_authors or [],
        "ror_institution": request.ror_institution,
        "dataset_hashes": request.dataset_hashes or [],
        "trust_fields": {
            "has_doi": publication.doi is not None,
            "has_abstract": publication.abstract is not None,
            "has_authors": publication.authors_raw is not None,
            "has_institution": publication.institution_raw is not None,
            "has_dataset": bool(request.dataset_hashes),
        },
    }

    kpt = KPT(
        publication_id=publication.id,
        content_hash=publication.file_hash,
        version=version,
        status="active",
        metadata_json=metadata,
    )
    kpt.kpt_id = _build_kpt_id(publication, version)

    db.add(kpt)
    db.commit()
    db.refresh(kpt)
    return kpt


def get_kpt_by_kpt_id(db: Session, kpt_id: str) -> KPT | None:
    return db.query(KPT).filter(KPT.kpt_id == kpt_id).first()


def get_kpt_by_id(db: Session, kpt_uuid: uuid.UUID) -> KPT | None:
    return db.query(KPT).filter(KPT.id == kpt_uuid).first()


def verify_kpt(db: Session, kpt_id: str, file_path: str | None = None) -> KPTVerifyResponse:
    kpt = get_kpt_by_kpt_id(db, kpt_id)

    if kpt is None:
        return KPTVerifyResponse(
            valid=False, kpt_id=kpt_id, status="not_found",
            content_hash="", stored_hash="",
            message="KPT not found",
        )

    if kpt.status != "active":
        return KPTVerifyResponse(
            valid=False, kpt_id=kpt_id, status=kpt.status,
            content_hash=kpt.content_hash, stored_hash=kpt.content_hash,
            message=f"KPT is not active (status: {kpt.status})",
        )

    if file_path:
        if not verify_file_hash(file_path, kpt.content_hash):
            actual_hash = compute_sha256_file(file_path)
            return KPTVerifyResponse(
                valid=False, kpt_id=kpt_id, status=kpt.status,
                content_hash=actual_hash, stored_hash=kpt.content_hash,
                message="File hash mismatch — content has been altered",
            )

    return KPTVerifyResponse(
        valid=True, kpt_id=kpt_id, status=kpt.status,
        content_hash=kpt.content_hash, stored_hash=kpt.content_hash,
        message="KPT is valid and active",
    )


def update_kpt_status(db: Session, kpt_id: str, new_status: str) -> KPT:
    allowed = {"challenged", "revoked", "superseded"}
    if new_status not in allowed:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {allowed}")

    kpt = get_kpt_by_kpt_id(db, kpt_id)
    if kpt is None:
        raise ValueError(f"KPT {kpt_id} not found")

    kpt.status = new_status
    db.commit()
    db.refresh(kpt)
    return kpt


def list_kpts_for_publication(db: Session, publication_id: uuid.UUID) -> list[KPT]:
    return (
        db.query(KPT)
        .filter(KPT.publication_id == publication_id)
        .order_by(KPT.version.desc())
        .all()
    )
