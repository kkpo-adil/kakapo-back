from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from app.database import get_db
from app.models.vo_transaction import VOTransaction
from app.models.publication import Publication

router = APIRouter(prefix="/earnings", tags=["Earnings"])


@router.get("/kakapo/stats")
def kakapo_stats(db: Session = Depends(get_db)):
    total_vo = db.query(sqlfunc.count(VOTransaction.id)).scalar() or 0
    total_kakapo = float(db.query(sqlfunc.sum(VOTransaction.kakapo_amount_usd)).scalar() or 0)
    total_party = float(db.query(sqlfunc.sum(VOTransaction.party_amount_usd)).scalar() or 0)
    by_segment = db.query(
        VOTransaction.consumer_segment,
        sqlfunc.count(VOTransaction.id),
        sqlfunc.sum(VOTransaction.kakapo_amount_usd),
    ).group_by(VOTransaction.consumer_segment).all()
    recent = db.query(VOTransaction).order_by(VOTransaction.created_at.desc()).limit(10).all()
    return {
        "total_vo": total_vo,
        "kakapo_revenue_usd": round(total_kakapo, 4),
        "party_revenue_usd": round(total_party, 4),
        "total_revenue_usd": round(total_kakapo + total_party, 4),
        "kakapo_share_pct": 40,
        "party_share_pct": 60,
        "by_segment": [
            {"segment": r[0], "vo_count": r[1], "kakapo_usd": round(float(r[2] or 0), 4)}
            for r in by_segment
        ],
        "recent_transactions": [
            {
                "kpt_id": t.kpt_id,
                "question": t.question[:80],
                "total_usd": float(t.total_amount_usd),
                "kakapo_usd": float(t.kakapo_amount_usd),
                "party_usd": float(t.party_amount_usd),
                "segment": t.consumer_segment,
                "created_at": t.created_at.isoformat(),
            }
            for t in recent
        ],
    }


@router.get("/publication/{publication_id}")
def publication_earnings(publication_id: str, db: Session = Depends(get_db)):
    from app.models.kpt import KPT
    import uuid
    from fastapi import HTTPException
    try:
        pub_uuid = uuid.UUID(publication_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    pub = db.query(Publication).filter(Publication.id == pub_uuid).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    kpt = db.query(KPT).filter(KPT.publication_id == pub_uuid).first()
    total_vo = db.query(sqlfunc.count(VOTransaction.id)).filter(
        VOTransaction.publication_id == pub_uuid
    ).scalar() or 0
    total_party = float(db.query(sqlfunc.sum(VOTransaction.party_amount_usd)).filter(
        VOTransaction.publication_id == pub_uuid
    ).scalar() or 0)
    total_kakapo = float(db.query(sqlfunc.sum(VOTransaction.kakapo_amount_usd)).filter(
        VOTransaction.publication_id == pub_uuid
    ).scalar() or 0)
    return {
        "publication_id": publication_id,
        "title": pub.title,
        "kpt_id": kpt.kpt_id if kpt else None,
        "kpt_status": pub.kpt_status,
        "total_vo": total_vo,
        "party_earnings_usd": round(total_party, 4),
        "kakapo_earnings_usd": round(total_kakapo, 4),
    }
