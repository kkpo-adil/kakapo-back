from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.publisher import Publisher
from app.models.publisher_balance import PublisherBalance
from app.schemas.publisher import PublisherCreate, PublisherUpdate, PublisherRead, PublisherBalanceRead
import uuid
from datetime import datetime

router = APIRouter(prefix="/publishers", tags=["Publishers"])


@router.post("", response_model=PublisherRead, status_code=status.HTTP_201_CREATED)
def create_publisher(payload: PublisherCreate, db: Session = Depends(get_db)):
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
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
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
def update_publisher(publisher_id: uuid.UUID, payload: PublisherUpdate, db: Session = Depends(get_db)):
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
