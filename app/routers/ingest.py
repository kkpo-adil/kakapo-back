import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.publication import Publication
from app.models.kpt import KPT
from app.services.hal_ingestor import ingest_batch, IngestReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["Ingest"])

ADMIN_TOKEN = os.environ.get("KAKAPO_ADMIN_TOKEN", "")


def require_admin(x_admin_token: str = Header(...)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Admin token invalide")


class IngestRequest(BaseModel):
    query: str
    max_results: int = 1000
    domains: list[str] | None = None
    year_from: int | None = None
    year_to: int | None = None


class IngestReportResponse(BaseModel):
    total_fetched: int
    total_created: int
    total_skipped_existing: int
    total_failed: int
    errors: list[str]
    duration_seconds: float


@router.post("/hal", response_model=IngestReportResponse)
def ingest_hal(body: IngestRequest, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    report = ingest_batch(
        db=db,
        query=body.query,
        max_results=body.max_results,
        domains=body.domains,
        year_from=body.year_from,
        year_to=body.year_to,
    )
    return IngestReportResponse(**report.__dict__)


@router.get("/hal/status")
def ingest_status(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    total_indexed = db.query(func.count(Publication.id)).filter(Publication.kpt_status == "indexed").scalar()
    total_certified = db.query(func.count(Publication.id)).filter(Publication.kpt_status == "certified").scalar()

    domain_rows = (
        db.query(Publication.institution_raw, func.count(Publication.id))
        .filter(Publication.kpt_status == "indexed")
        .group_by(Publication.institution_raw)
        .order_by(func.count(Publication.id).desc())
        .limit(5)
        .all()
    )

    return {
        "total_indexed_publications": total_indexed,
        "total_certified_publications": total_certified,
        "last_ingestion_at": datetime.now(timezone.utc).isoformat(),
        "top_5_domains_indexed": [{"domain": r[0], "count": r[1]} for r in domain_rows],
    }

@router.post("/seed-certified")
def seed_certified_publications(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    import uuid, math
    from datetime import datetime, timezone
    from app.models.publication import Publication
    from app.models.kpt import KPT
    from app.models.trust_score import TrustScore
    from app.models.publication_relation import PublicationRelation

    PUBS = [
        {"id":"11111111-0001-0001-0001-000000000001","title":"Attention Is All You Need","abstract":"The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer, a model architecture relying entirely on an attention mechanism.","doi":"10.48550/arXiv.1706.03762","source":"arxiv","authors_raw":"Vaswani, A., Shazeer, N., Parmar, N.","institution_raw":"Google Brain","year":2017,"citations":90000},
        {"id":"11111111-0002-0002-0002-000000000002","title":"BERT: Pre-training of Deep Bidirectional Transformers","abstract":"We introduce BERT, designed to pre-train deep bidirectional representations from unlabeled text.","doi":"10.48550/arXiv.1810.04805","source":"arxiv","authors_raw":"Devlin, J., Chang, M., Lee, K.","institution_raw":"Google AI Language","year":2018,"citations":50000},
        {"id":"11111111-0003-0003-0003-000000000003","title":"Deep Residual Learning for Image Recognition","abstract":"We present a residual learning framework to ease the training of networks substantially deeper than those used previously.","doi":"10.48550/arXiv.1512.03385","source":"arxiv","authors_raw":"He, K., Zhang, X., Ren, S.","institution_raw":"Microsoft Research","year":2015,"citations":150000},
        {"id":"11111111-0004-0004-0004-000000000004","title":"Generative Adversarial Nets","abstract":"We propose a new framework for estimating generative models via an adversarial process.","doi":"10.48550/arXiv.1406.2661","source":"arxiv","authors_raw":"Goodfellow, I., Pouget-Abadie, J.","institution_raw":"Universite de Montreal","year":2014,"citations":60000},
        {"id":"11111111-0005-0005-0005-000000000005","title":"Dropout: A Simple Way to Prevent Neural Networks from Overfitting","abstract":"We describe dropout, a technique for addressing overfitting by randomly dropping units during training.","doi":"10.5555/2627435.2670313","source":"direct","authors_raw":"Srivastava, N., Hinton, G.","institution_raw":"University of Toronto","year":2014,"citations":40000},
        {"id":"11111111-0006-0006-0006-000000000006","title":"Adam: A Method for Stochastic Optimization","abstract":"We introduce Adam, an algorithm for first-order gradient-based optimization of stochastic objective functions.","doi":"10.48550/arXiv.1412.6980","source":"arxiv","authors_raw":"Kingma, D., Ba, J.","institution_raw":"University of Amsterdam","year":2014,"citations":100000},
        {"id":"11111111-0007-0007-0007-000000000007","title":"ImageNet Large Scale Visual Recognition Challenge","abstract":"A benchmark in object category classification and detection on hundreds of object categories.","doi":"10.1007/s11263-015-0816-y","source":"direct","authors_raw":"Russakovsky, O., Deng, J.","institution_raw":"Stanford University","year":2015,"citations":30000},
        {"id":"11111111-0008-0008-0008-000000000008","title":"Language Models are Few-Shot Learners (GPT-3)","abstract":"We demonstrate that scaling language models greatly improves task-agnostic few-shot performance.","doi":"10.48550/arXiv.2005.14165","source":"arxiv","authors_raw":"Brown, T., Mann, B., Ryder, N.","institution_raw":"OpenAI","year":2020,"citations":30000},
        {"id":"11111111-0009-0009-0009-000000000009","title":"RoBERTa: A Robustly Optimized BERT Pretraining Approach","abstract":"We present RoBERTa, a replication study of BERT pretraining.","doi":"10.48550/arXiv.1907.11692","source":"arxiv","authors_raw":"Liu, Y., Ott, M., Goyal, N.","institution_raw":"Facebook AI","year":2019,"citations":20000},
        {"id":"11111111-0010-0010-0010-000000000010","title":"Exploring the Limits of Transfer Learning with T5","abstract":"A unified framework that converts all text-based language problems into a text-to-text format.","doi":"10.48550/arXiv.1910.10683","source":"arxiv","authors_raw":"Raffel, C., Shazeer, N., Roberts, A.","institution_raw":"Google Brain","year":2019,"citations":15000},
        {"id":"11111111-0011-0011-0011-000000000011","title":"Very Deep Convolutional Networks for Large-Scale Image Recognition (VGG)","abstract":"We investigate the effect of convolutional network depth on accuracy in large-scale image recognition.","doi":"10.48550/arXiv.1409.1556","source":"arxiv","authors_raw":"Simonyan, K., Zisserman, A.","institution_raw":"University of Oxford","year":2014,"citations":80000},
        {"id":"11111111-0012-0012-0012-000000000012","title":"You Only Look Once: Unified Real-Time Object Detection (YOLO)","abstract":"We present YOLO, a new approach to object detection using a single neural network.","doi":"10.48550/arXiv.1506.02640","source":"arxiv","authors_raw":"Redmon, J., Divvala, S.","institution_raw":"University of Washington","year":2015,"citations":25000},
        {"id":"11111111-0013-0013-0013-000000000013","title":"Efficient Estimation of Word Representations in Vector Space (Word2Vec)","abstract":"We propose two novel model architectures for computing continuous vector representations of words.","doi":"10.48550/arXiv.1301.3781","source":"arxiv","authors_raw":"Mikolov, T., Chen, K., Corrado, G.","institution_raw":"Google","year":2013,"citations":70000},
        {"id":"11111111-0014-0014-0014-000000000014","title":"Deep Learning","abstract":"Deep learning allows computational models composed of multiple processing layers to learn representations of data.","doi":"10.1038/nature14539","source":"nature","authors_raw":"LeCun, Y., Bengio, Y., Hinton, G.","institution_raw":"Nature Publishing Group","year":2015,"citations":45000},
        {"id":"11111111-0015-0015-0015-000000000015","title":"An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale (ViT)","abstract":"A pure transformer applied directly to sequences of image patches performs well on image classification.","doi":"10.48550/arXiv.2010.11929","source":"arxiv","authors_raw":"Dosovitskiy, A., Beyer, L.","institution_raw":"Google Brain","year":2020,"citations":20000},
    ]
    RELS = [
        ("11111111-0002-0002-0002-000000000002","11111111-0001-0001-0001-000000000001"),
        ("11111111-0008-0008-0008-000000000008","11111111-0001-0001-0001-000000000001"),
        ("11111111-0009-0009-0009-000000000009","11111111-0002-0002-0002-000000000002"),
        ("11111111-0010-0010-0010-000000000010","11111111-0001-0001-0001-000000000001"),
        ("11111111-0010-0010-0010-000000000010","11111111-0002-0002-0002-000000000002"),
        ("11111111-0015-0015-0015-000000000015","11111111-0001-0001-0001-000000000001"),
        ("11111111-0015-0015-0015-000000000015","11111111-0003-0003-0003-000000000003"),
        ("11111111-0012-0012-0012-000000000012","11111111-0007-0007-0007-000000000007"),
        ("11111111-0012-0012-0012-000000000012","11111111-0003-0003-0003-000000000003"),
        ("11111111-0011-0011-0011-000000000011","11111111-0007-0007-0007-000000000007"),
        ("11111111-0003-0003-0003-000000000003","11111111-0007-0007-0007-000000000007"),
        ("11111111-0003-0003-0003-000000000003","11111111-0005-0005-0005-000000000005"),
        ("11111111-0003-0003-0003-000000000003","11111111-0006-0006-0006-000000000006"),
        ("11111111-0004-0004-0004-000000000004","11111111-0005-0005-0005-000000000005"),
        ("11111111-0008-0008-0008-000000000008","11111111-0006-0006-0006-000000000006"),
        ("11111111-0009-0009-0009-000000000009","11111111-0013-0013-0013-000000000013"),
        ("11111111-0002-0002-0002-000000000002","11111111-0013-0013-0013-000000000013"),
        ("11111111-0014-0014-0014-000000000014","11111111-0005-0005-0005-000000000005"),
        ("11111111-0014-0014-0014-000000000014","11111111-0006-0006-0006-000000000006"),
        ("11111111-0010-0010-0010-000000000010","11111111-0013-0013-0013-000000000013"),
    ]
    created = skipped = 0
    for p in PUBS:
        if db.query(Publication).filter(Publication.doi == p["doi"]).first():
            skipped += 1
            continue
        pub = Publication(id=uuid.UUID(p["id"]), title=p["title"], abstract=p["abstract"], doi=p["doi"], source=p["source"], authors_raw=p["authors_raw"], institution_raw=p["institution_raw"], submitted_at=datetime(p["year"], 1, 1, tzinfo=timezone.utc), kpt_status="certified", source_origin="direct_deposit")
        db.add(pub); db.flush()
        s_source = 0.90 if p["source"] == "nature" else 0.70 if p["source"] == "arxiv" else 0.50
        s_citation = round(1 - math.exp(-0.05 * p["citations"]), 4)
        s_freshness = round(math.exp(-0.10 * (2026 - p["year"])), 4)
        s_data = round((1 + 0 + 0 + 1) / 6, 4)
        s_consistency = 1.0
        score = round(0.30*s_source + 0.20*s_data + 0.20*s_citation + 0.15*s_freshness + 0.10*s_consistency, 4)
        db.add(KPT(id=uuid.uuid4(), publication_id=pub.id, kpt_id=f"KPT-{str(pub.id).upper().replace('-','')[:12]}-v1", content_hash=f"certified-{p['doi'].replace('//','-')}", status="active", version=1, is_indexed=False))
        db.add(TrustScore(publication_id=pub.id, score=score, source_score=s_source, completeness_score=s_data, freshness_score=s_freshness, citation_score=s_citation, dataset_score=s_data, scoring_version="3.0", is_indexation_score=False))
        db.commit(); created += 1
    for src_id, tgt_id in RELS:
        s = db.query(Publication).filter(Publication.id == uuid.UUID(src_id)).first()
        t = db.query(Publication).filter(Publication.id == uuid.UUID(tgt_id)).first()
        if s and t and not db.query(PublicationRelation).filter(PublicationRelation.source_id==s.id, PublicationRelation.target_id==t.id).first():
            db.add(PublicationRelation(id=uuid.uuid4(), source_id=s.id, target_id=t.id, relation_type="cites"))
    db.commit()
    from sqlalchemy import func as sqlfunc
    total = db.query(sqlfunc.count(Publication.id)).filter(Publication.kpt_status == "certified").scalar()
    return {"status": "ok", "certified_total": total}


@router.post("/fix-hashes")
def fix_certified_hashes(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    import hashlib
    from app.models.kpt import KPT
    from app.models.publication import Publication

    UPDATES = [
        ("10.48550/arXiv.1706.03762", "4fe4597b6b88ddc617b84679ff54d3f1ab5c794ec069fd4d90902dcd75318760"),
        ("10.48550/arXiv.1810.04805", "83319cccd42f00e28ed38ce32ae509ebd9a2ee8af74a66aa6637f2714c0edc59"),
        ("10.48550/arXiv.1512.03385", "4137ed3fd645c79c2184c9335fd43d21c3a322e8a24b8988371cb338bac36f40"),
        ("10.48550/arXiv.1406.2661", "854bc0afd0719be7a758534ca466b980609377c375d9276cf7cf4ee99399c9dd"),
        ("10.5555/2627435.2670313", "7c248ce83cf1e31d5be1af25bd1f581a5400c043aa3de55406da87d0f149e183"),
        ("10.48550/arXiv.1412.6980", "801a0dcfd1477af38f98c088901b9c0acb390518c3843ac832388047485f7e08"),
        ("10.1007/s11263-015-0816-y", "06aea9a7c2d4d627ae9028fe7776b7ca80f49661c116d92c9757df74afd76dce"),
        ("10.48550/arXiv.2005.14165", "d72374c7cbc2618a595d3d18383b25f91bbf8e0ff4f729076413dbc4211927a3"),
        ("10.48550/arXiv.1907.11692", "6317be2bfb6e19fd3dd33bf42eeb92c4cc8d2114fbbc16474b661de57c2061a9"),
        ("10.48550/arXiv.1910.10683", "b249014941204dd58424f2183c7ae75346c3e6cb607c232833704ce71d37a9f1"),
        ("10.48550/arXiv.1409.1556", "03781f38374baf56a157e33645511c6beb44c0ce6e0568cddd36e72f52a398eb"),
        ("10.48550/arXiv.1506.02640", "10335cd0c822ee01f40432f63c8be164d3d70e6fb1dd06cb6e5d8e2704aa6230"),
        ("10.48550/arXiv.1301.3781", "e9b5aa29e632c1b1a7c2306bdbe4f6a5d72ac0820aa10db6f577ebe1e851932c"),
        ("10.1038/nature14539", "23d4b9b2ce98cfde1f1e231bd79d63c248073631313f50ced169457a849ab64f"),
        ("10.48550/arXiv.2010.11929", "bd1b35295c04f5a622696b8942c21faf7cbc8e376dec7f8d6403bd2f5743c382"),
    ]

    updated = 0
    for doi, new_hash in UPDATES:
        pub = db.query(Publication).filter(Publication.doi == doi).first()
        if not pub:
            continue
        kpt = db.query(KPT).filter(KPT.publication_id == pub.id).first()
        if kpt:
            kpt.content_hash = new_hash
            updated += 1
    db.commit()
    return {"status": "ok", "updated": updated}
