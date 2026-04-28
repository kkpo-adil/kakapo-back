from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import require_api_key
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.publisher import Publisher
from app.models.publisher_balance import PublisherBalance
from app.schemas.publisher import PublisherCreate, PublisherUpdate, PublisherRead, PublisherBalanceRead
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/publishers", tags=["Publishers"])


@router.post("", response_model=PublisherRead, status_code=status.HTTP_201_CREATED)
def create_publisher(payload: PublisherCreate, db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    existing = db.query(Publisher).filter(Publisher.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already exists")
    publisher = Publisher(
        id=uuid.uuid4(),
        name=payload.name,
        slug=payload.slug,
        contract_type=payload.contract_type,
        revenue_share_pct=payload.revenue_share_pct,
        kpt_unit_cost=payload.kpt_unit_cost,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    balance = PublisherBalance(
        id=uuid.uuid4(),
        publisher_id=publisher.id,
    )
    db.add(publisher)
    db.add(balance)
    db.commit()
    db.refresh(publisher)
    return publisher


@router.get("", response_model=list[PublisherRead])
def list_publishers(db: Session = Depends(get_db)):
    return db.query(Publisher).all()


@router.get("/{publisher_id}", response_model=PublisherRead)
def get_publisher(publisher_id: uuid.UUID, db: Session = Depends(get_db)):
    publisher = db.query(Publisher).filter(Publisher.id == publisher_id).first()
    if not publisher:
        raise HTTPException(status_code=404, detail="Publisher not found")
    return publisher


@router.patch("/{publisher_id}", response_model=PublisherRead)
def update_publisher(publisher_id: uuid.UUID, payload: PublisherUpdate, db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    publisher = db.query(Publisher).filter(Publisher.id == publisher_id).first()
    if not publisher:
        raise HTTPException(status_code=404, detail="Publisher not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(publisher, field, value)
    publisher.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(publisher)
    return publisher


@router.get("/{publisher_id}/balance", response_model=PublisherBalanceRead)
def get_balance(publisher_id: uuid.UUID, db: Session = Depends(get_db)):
    balance = db.query(PublisherBalance).filter(PublisherBalance.publisher_id == publisher_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    return balance

@router.get("/me/dashboard")
def get_publisher_dashboard(db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    from app.models.publication import Publication
    from app.models.kpt import KPT
    from app.models.integrity_check_log import IntegrityCheckLog
    from app.models.query_log import QueryLog
    from sqlalchemy import func

    publishers = db.query(Publisher).filter(Publisher.status == "active").all()
    if not publishers:
        raise HTTPException(status_code=404, detail="No active publisher found")
    publisher = publishers[0]

    balance = db.query(PublisherBalance).filter(
        PublisherBalance.publisher_id == publisher.id
    ).first()

    total_kpts = db.query(KPT).count()
    active_kpts = db.query(KPT).filter(KPT.status == "active").count()

    total_queries = db.query(QueryLog).count()

    revenue_share = float(publisher.revenue_share_pct) / 100
    estimated_revenue = total_queries * 0.002 * revenue_share

    monthly_queries = db.query(QueryLog).filter(
        func.date_trunc("month", QueryLog.queried_at) == func.date_trunc("month", func.now())
    ).count()

    monthly_revenue = monthly_queries * 0.002 * revenue_share

    return {
        "publisher": {
            "id": str(publisher.id),
            "name": publisher.name,
            "slug": publisher.slug,
            "status": publisher.status,
            "contract_type": publisher.contract_type,
            "revenue_share_pct": float(publisher.revenue_share_pct),
        },
        "balance": {
            "total_earned": float(balance.total_earned) if balance else 0,
            "total_paid_out": float(balance.total_paid_out) if balance else 0,
            "pending_payout": float(balance.pending_payout) if balance else 0,
        },
        "stats": {
            "total_kpts": total_kpts,
            "active_kpts": active_kpts,
            "total_queries": total_queries,
            "monthly_queries": monthly_queries,
            "estimated_total_revenue": round(estimated_revenue, 2),
            "estimated_monthly_revenue": round(monthly_revenue, 2),
        },
    }
