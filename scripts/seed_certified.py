#!/usr/bin/env python3
"""
Seed 15 publications certifiées avec vraies relations de citation.
Usage : python scripts/seed_certified.py
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.publication import Publication
from app.models.kpt import KPT
from app.models.trust_score import TrustScore
from app.models.publication_relation import PublicationRelation
from app.services.trust_engine import compute_trust_score

PUBLICATIONS = [
    {
        "id": "11111111-0001-0001-0001-000000000001",
        "title": "Attention Is All You Need",
        "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose the Transformer, a model architecture eschewing recurrence and instead relying entirely on an attention mechanism.",
        "doi": "10.48550/arXiv.1706.03762",
        "source": "arxiv",
        "authors_raw": "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J.",
        "institution_raw": "Google Brain",
        "submitted_at": "2017-06-12T00:00:00Z",
        "citation_count": 90000,
    },
    {
        "id": "11111111-0002-0002-0002-000000000002",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "abstract": "We introduce BERT, a new language representation model designed to pre-train deep bidirectional representations from unlabeled text.",
        "doi": "10.48550/arXiv.1810.04805",
        "source": "arxiv",
        "authors_raw": "Devlin, J., Chang, M., Lee, K., Toutanova, K.",
        "institution_raw": "Google AI Language",
        "submitted_at": "2018-10-11T00:00:00Z",
        "citation_count": 50000,
    },
    {
        "id": "11111111-0003-0003-0003-000000000003",
        "title": "Deep Residual Learning for Image Recognition",
        "abstract": "We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously.",
        "doi": "10.48550/arXiv.1512.03385",
        "source": "arxiv",
        "authors_raw": "He, K., Zhang, X., Ren, S., Sun, J.",
        "institution_raw": "Microsoft Research",
        "submitted_at": "2015-12-10T00:00:00Z",
        "citation_count": 150000,
    },
    {
        "id": "11111111-0004-0004-0004-000000000004",
        "title": "Generative Adversarial Nets",
        "abstract": "We propose a new framework for estimating generative models via an adversarial process, in which we simultaneously train two models.",
        "doi": "10.48550/arXiv.1406.2661",
        "source": "arxiv",
        "authors_raw": "Goodfellow, I., Pouget-Abadie, J., Mirza, M.",
        "institution_raw": "Université de Montréal",
        "submitted_at": "2014-06-10T00:00:00Z",
        "citation_count": 60000,
    },
    {
        "id": "11111111-0005-0005-0005-000000000005",
        "title": "Dropout: A Simple Way to Prevent Neural Networks from Overfitting",
        "abstract": "We describe dropout, a technique for addressing overfitting. The key idea is to randomly drop units from the neural network during training.",
        "doi": "10.5555/2627435.2670313",
        "source": "direct",
        "authors_raw": "Srivastava, N., Hinton, G., Krizhevsky, A.",
        "institution_raw": "University of Toronto",
        "submitted_at": "2014-01-01T00:00:00Z",
        "citation_count": 40000,
    },
    {
        "id": "11111111-0006-0006-0006-000000000006",
        "title": "Adam: A Method for Stochastic Optimization",
        "abstract": "We introduce Adam, an algorithm for first-order gradient-based optimization of stochastic objective functions.",
        "doi": "10.48550/arXiv.1412.6980",
        "source": "arxiv",
        "authors_raw": "Kingma, D., Ba, J.",
        "institution_raw": "University of Amsterdam",
        "submitted_at": "2014-12-22T00:00:00Z",
        "citation_count": 100000,
    },
    {
        "id": "11111111-0007-0007-0007-000000000007",
        "title": "ImageNet Large Scale Visual Recognition Challenge",
        "abstract": "The ImageNet Large Scale Visual Recognition Challenge is a benchmark in object category classification and detection on hundreds of object categories.",
        "doi": "10.1007/s11263-015-0816-y",
        "source": "direct",
        "authors_raw": "Russakovsky, O., Deng, J., Su, H.",
        "institution_raw": "Stanford University",
        "submitted_at": "2015-01-01T00:00:00Z",
        "citation_count": 30000,
    },
    {
        "id": "11111111-0008-0008-0008-000000000008",
        "title": "Language Models are Few-Shot Learners (GPT-3)",
        "abstract": "We demonstrate that scaling language models greatly improves task-agnostic, few-shot performance, sometimes even reaching competitiveness with prior state-of-the-art fine-tuning approaches.",
        "doi": "10.48550/arXiv.2005.14165",
        "source": "arxiv",
        "authors_raw": "Brown, T., Mann, B., Ryder, N.",
        "institution_raw": "OpenAI",
        "submitted_at": "2020-05-28T00:00:00Z",
        "citation_count": 30000,
    },
    {
        "id": "11111111-0009-0009-0009-000000000009",
        "title": "RoBERTa: A Robustly Optimized BERT Pretraining Approach",
        "abstract": "We present RoBERTa, a replication study of BERT pretraining that carefully measures the impact of many key hyperparameters and training data size.",
        "doi": "10.48550/arXiv.1907.11692",
        "source": "arxiv",
        "authors_raw": "Liu, Y., Ott, M., Goyal, N.",
        "institution_raw": "Facebook AI",
        "submitted_at": "2019-07-26T00:00:00Z",
        "citation_count": 20000,
    },
    {
        "id": "11111111-0010-0010-0010-000000000010",
        "title": "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer (T5)",
        "abstract": "We introduce a unified framework that converts all text-based language problems into a text-to-text format.",
        "doi": "10.48550/arXiv.1910.10683",
        "source": "arxiv",
        "authors_raw": "Raffel, C., Shazeer, N., Roberts, A.",
        "institution_raw": "Google Brain",
        "submitted_at": "2019-10-23T00:00:00Z",
        "citation_count": 15000,
    },
    {
        "id": "11111111-0011-0011-0011-000000000011",
        "title": "Very Deep Convolutional Networks for Large-Scale Image Recognition (VGG)",
        "abstract": "We investigate the effect of the convolutional network depth on its accuracy in the large-scale image recognition setting.",
        "doi": "10.48550/arXiv.1409.1556",
        "source": "arxiv",
        "authors_raw": "Simonyan, K., Zisserman, A.",
        "institution_raw": "University of Oxford",
        "submitted_at": "2014-09-04T00:00:00Z",
        "citation_count": 80000,
    },
    {
        "id": "11111111-0012-0012-0012-000000000012",
        "title": "You Only Look Once: Unified, Real-Time Object Detection (YOLO)",
        "abstract": "We present YOLO, a new approach to object detection. Prior work on object detection repurposes classifiers to perform detection.",
        "doi": "10.48550/arXiv.1506.02640",
        "source": "arxiv",
        "authors_raw": "Redmon, J., Divvala, S., Girshick, R.",
        "institution_raw": "University of Washington",
        "submitted_at": "2015-06-08T00:00:00Z",
        "citation_count": 25000,
    },
    {
        "id": "11111111-0013-0013-0013-000000000013",
        "title": "Efficient Estimation of Word Representations in Vector Space (Word2Vec)",
        "abstract": "We propose two novel model architectures for computing continuous vector representations of words from very large data sets.",
        "doi": "10.48550/arXiv.1301.3781",
        "source": "arxiv",
        "authors_raw": "Mikolov, T., Chen, K., Corrado, G.",
        "institution_raw": "Google",
        "submitted_at": "2013-01-16T00:00:00Z",
        "citation_count": 70000,
    },
    {
        "id": "11111111-0014-0014-0014-000000000014",
        "title": "Deep Learning (LeCun, Bengio, Hinton)",
        "abstract": "Deep learning allows computational models that are composed of multiple processing layers to learn representations of data with multiple levels of abstraction.",
        "doi": "10.1038/nature14539",
        "source": "nature",
        "authors_raw": "LeCun, Y., Bengio, Y., Hinton, G.",
        "institution_raw": "Nature Publishing Group",
        "submitted_at": "2015-05-27T00:00:00Z",
        "citation_count": 45000,
    },
    {
        "id": "11111111-0015-0015-0015-000000000015",
        "title": "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale (ViT)",
        "abstract": "We show that a pure transformer applied directly to sequences of image patches can perform very well on image classification tasks.",
        "doi": "10.48550/arXiv.2010.11929",
        "source": "arxiv",
        "authors_raw": "Dosovitskiy, A., Beyer, L., Kolesnikov, A.",
        "institution_raw": "Google Brain",
        "submitted_at": "2020-10-22T00:00:00Z",
        "citation_count": 20000,
    },
]

RELATIONS = [
    ("11111111-0002-0002-0002-000000000002", "11111111-0001-0001-0001-000000000001"),
    ("11111111-0008-0008-0008-000000000008", "11111111-0001-0001-0001-000000000001"),
    ("11111111-0009-0009-0009-000000000009", "11111111-0002-0002-0002-000000000002"),
    ("11111111-0010-0010-0010-000000000010", "11111111-0001-0001-0001-000000000001"),
    ("11111111-0010-0010-0010-000000000010", "11111111-0002-0002-0002-000000000002"),
    ("11111111-0015-0015-0015-000000000015", "11111111-0001-0001-0001-000000000001"),
    ("11111111-0015-0015-0015-000000000015", "11111111-0003-0003-0003-000000000003"),
    ("11111111-0012-0012-0012-000000000012", "11111111-0007-0007-0007-000000000007"),
    ("11111111-0012-0012-0012-000000000012", "11111111-0003-0003-0003-000000000003"),
    ("11111111-0011-0011-0011-000000000011", "11111111-0007-0007-0007-000000000007"),
    ("11111111-0003-0003-0003-000000000003", "11111111-0007-0007-0007-000000000007"),
    ("11111111-0003-0003-0003-000000000003", "11111111-0005-0005-0005-000000000005"),
    ("11111111-0003-0003-0003-000000000003", "11111111-0006-0006-0006-000000000006"),
    ("11111111-0004-0004-0004-000000000004", "11111111-0005-0005-0005-000000000005"),
    ("11111111-0008-0008-0008-000000000008", "11111111-0006-0006-0006-000000000006"),
    ("11111111-0009-0009-0009-000000000009", "11111111-0013-0013-0013-000000000013"),
    ("11111111-0002-0002-0002-000000000002", "11111111-0013-0013-0013-000000000013"),
    ("11111111-0014-0014-0014-000000000014", "11111111-0005-0005-0005-000000000005"),
    ("11111111-0014-0014-0014-000000000014", "11111111-0006-0006-0006-000000000006"),
    ("11111111-0010-0010-0010-000000000010", "11111111-0013-0013-0013-000000000013"),
]


def seed(db: Session):
    created = 0
    skipped = 0
    for p in PUBLICATIONS:
        existing = db.query(Publication).filter(Publication.doi == p["doi"]).first()
        if existing:
            if existing.kpt_status != "certified":
                existing.kpt_status = "certified"
                existing.source_origin = "direct_deposit"
                db.commit()
            skipped += 1
            continue

        pub = Publication(
            id=uuid.UUID(p["id"]),
            title=p["title"],
            abstract=p["abstract"],
            doi=p["doi"],
            source=p["source"],
            authors_raw=p["authors_raw"],
            institution_raw=p["institution_raw"],
            submitted_at=datetime.fromisoformat(p["submitted_at"].replace("Z", "+00:00")),
            kpt_status="certified",
            source_origin="direct_deposit",
        )
        db.add(pub)
        db.flush()

        kpt = KPT(
            id=uuid.uuid4(),
            publication_id=pub.id,
            kpt_id=f"KPT-{str(pub.id).upper()[:8]}-v1",
            content_hash=f"certified-{p['doi'].replace('/', '-')}",
            status="active",
            version=1,
            is_indexed=False,
        )
        db.add(kpt)

        ts = TrustScore(
            publication_id=pub.id,
            score=0.0,
            source_score=0.0,
            completeness_score=0.0,
            freshness_score=0.0,
            citation_score=0.0,
            dataset_score=0.0,
            scoring_version="3.0",
            is_indexation_score=False,
        )
        db.add(ts)
        db.flush()

        ts.score = round(
            0.30 * (0.90 if p["source"] == "nature" else 0.70 if p["source"] == "arxiv" else 0.50)
            + 0.20 * (1 + 2 + 0 + 1) / 6
            + 0.20 * (1 - __import__("math").exp(-0.05 * p["citation_count"]))
            + 0.15 * __import__("math").exp(-0.10 * (2026 - int(p["submitted_at"][:4])))
            + 0.10 * 1.0
            + 0.05 * 0.0,
            4
        )
        db.commit()
        created += 1

    for src_id, tgt_id in RELATIONS:
        src = db.query(Publication).filter(Publication.id == uuid.UUID(src_id)).first()
        tgt = db.query(Publication).filter(Publication.id == uuid.UUID(tgt_id)).first()
        if not src or not tgt:
            continue
        existing = db.query(PublicationRelation).filter(
            PublicationRelation.source_id == src.id,
            PublicationRelation.target_id == tgt.id,
        ).first()
        if not existing:
            db.add(PublicationRelation(
                id=uuid.uuid4(),
                source_id=src.id,
                target_id=tgt.id,
                relation_type="cites",
            ))
    db.commit()

    print(f"Created: {created} | Skipped: {skipped} | Relations: {len(RELATIONS)}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
