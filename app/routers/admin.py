from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.publication import Publication
from app.models.kpt import KPT
from app.models.trust_score import TrustScore
import uuid, hashlib, json
from datetime import datetime, timezone

router = APIRouter(prefix="/admin", tags=["Admin"])

def make_hash(content):
    return hashlib.sha256(content.encode()).hexdigest()

@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    publications_data = [
        {"title": "Attention Is All You Need", "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer, a model architecture based solely on attention mechanisms.", "source": "arxiv", "doi": "10.48550/arXiv.1706.03762", "authors_raw": json.dumps([{"name": "Vaswani, A."}, {"name": "Shazeer, N."}]), "institution_raw": "Google Brain"},
        {"title": "BERT: Pre-training of Deep Bidirectional Transformers", "abstract": "We introduce BERT, a new language representation model designed to pre-train deep bidirectional representations from unlabeled text.", "source": "arxiv", "doi": "10.48550/arXiv.1810.04805", "authors_raw": json.dumps([{"name": "Devlin, J."}, {"name": "Chang, M."}]), "institution_raw": "Google AI Language"},
        {"title": "Deep Residual Learning for Image Recognition", "abstract": "We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously.", "source": "arxiv", "doi": "10.48550/arXiv.1512.03385", "authors_raw": json.dumps([{"name": "He, K."}, {"name": "Zhang, X."}]), "institution_raw": "Microsoft Research"},
    ]
    created = []
    for data in publications_data:
        if db.query(Publication).filter(Publication.doi == data["doi"]).first():
            continue
        pub = Publication(id=uuid.uuid4(), title=data["title"], abstract=data["abstract"], source=data["source"], doi=data["doi"], authors_raw=data["authors_raw"], institution_raw=data["institution_raw"], file_hash=make_hash(data["title"] + data["doi"]), submitted_at=datetime.now(timezone.utc))
        db.add(pub)
        db.flush()
        pub_short = str(pub.id).replace("-", "")[:8].upper()
        suffix = str(uuid.uuid4()).replace("-", "")[:8].upper()
        kpt = KPT(id=uuid.uuid4(), kpt_id=f"KPT-{pub_short}-v1-{suffix}", publication_id=pub.id, content_hash=pub.file_hash, version=1, status="active", metadata_json={"doi": pub.doi, "source": pub.source, "title": pub.title, "orcid_authors": [], "dataset_hashes": [], "ror_institution": None, "trust_fields": {"has_doi": True, "has_abstract": True, "has_authors": True, "has_institution": True, "has_dataset": False}})
        db.add(kpt)
        db.flush()
        score = TrustScore(id=uuid.uuid4(), publication_id=pub.id, score=0.82, source_score=0.85, completeness_score=0.90, freshness_score=0.75, citation_score=0.80, dataset_score=0.60)
        db.add(score)
        created.append(pub.title)
    db.commit()
    return {"created": created}
