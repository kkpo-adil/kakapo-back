import uuid
import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys
sys.path.insert(0, "/app")

from app.models.publication import Publication
from app.models.kpt import KPT
from app.models.trust_score import TrustScore

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

def make_hash(content):
    return hashlib.sha256(content.encode()).hexdigest()

publications_data = [
    {
        "title": "Attention Is All You Need",
        "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer, a model architecture based solely on attention mechanisms.",
        "source": "arxiv",
        "doi": "10.48550/arXiv.1706.03762",
        "authors_raw": json.dumps([{"name": "Vaswani, A."}, {"name": "Shazeer, N."}]),
        "institution_raw": "Google Brain",
    },
    {
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "abstract": "We introduce BERT, a new language representation model designed to pre-train deep bidirectional representations from unlabeled text.",
        "source": "arxiv",
        "doi": "10.48550/arXiv.1810.04805",
        "authors_raw": json.dumps([{"name": "Devlin, J."}, {"name": "Chang, M."}]),
        "institution_raw": "Google AI Language",
    },
    {
        "title": "Deep Residual Learning for Image Recognition",
        "abstract": "We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously.",
        "source": "arxiv",
        "doi": "10.48550/arXiv.1512.03385",
        "authors_raw": json.dumps([{"name": "He, K."}, {"name": "Zhang, X."}]),
        "institution_raw": "Microsoft Research",
    },
]

for data in publications_data:
    existing = db.query(Publication).filter(Publication.doi == data["doi"]).first()
    if existing:
        print(f"Skip: {data['doi']}")
        continue
    pub = Publication(
        id=uuid.uuid4(),
        title=data["title"],
        abstract=data["abstract"],
        source=data["source"],
        doi=data["doi"],
        authors_raw=data["authors_raw"],
        institution_raw=data["institution_raw"],
        file_hash=make_hash(data["title"] + data["doi"]),
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(pub)
    db.flush()
    pub_short = str(pub.id).replace("-", "")[:8].upper()
    suffix = str(uuid.uuid4()).replace("-", "")[:8].upper()
    kpt = KPT(
        id=uuid.uuid4(),
        kpt_id=f"KPT-{pub_short}-v1-{suffix}",
        publication_id=pub.id,
        content_hash=pub.file_hash,
        version=1,
        status="active",
        metadata_json={
            "doi": pub.doi,
            "source": pub.source,
            "title": pub.title,
            "orcid_authors": [],
            "dataset_hashes": [],
            "ror_institution": None,
            "trust_fields": {
                "has_doi": True,
                "has_abstract": True,
                "has_authors": True,
                "has_institution": True,
                "has_dataset": False,
            },
        },
    )
    db.add(kpt)
    db.flush()
    score = TrustScore(
        id=uuid.uuid4(),
        publication_id=pub.id,
        kpt_id=kpt.id,
        score=82,
        source_score=85,
        completeness_score=90,
        freshness_score=75,
        citation_score=80,
        dataset_score=60,
    )
    db.add(score)
    print(f"Created: {data['title'][:50]}")

db.commit()
db.close()
print("Seed complete")
