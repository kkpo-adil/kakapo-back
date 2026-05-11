import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header
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
    total_indexed = db.query(func.count(Publication.id)).filter(
        Publication.kpt_status == "indexed",
        Publication.opted_out_at == None,
    ).scalar() or 0
    total_certified = db.query(func.count(Publication.id)).filter(
        Publication.kpt_status == "certified",
        Publication.opted_out_at == None,
    ).scalar() or 0

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

@router.post("/seed-clinical-trials")
def seed_clinical_trials(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    import uuid as _uuid
    from datetime import datetime, timezone
    from app.models.publication import Publication
    from app.models.kpt import KPT
    from app.models.trust_score import TrustScore
    import hashlib

    TRIALS = [
        {"nct_id":"NCT02819518","title":"KEYNOTE-355: Pembrolizumab + Chemotherapy vs Placebo in Triple Negative Breast Cancer","abstract":"Phase III randomized study evaluating pembrolizumab plus chemotherapy versus placebo plus chemotherapy for previously untreated locally recurrent inoperable or metastatic triple negative breast cancer. 882 patients enrolled. Sponsor: Merck Sharp & Dohme.","doi":"10.1056/NEJMoa2012920","source":"direct","authors_raw":"Cortes J, Cescon DW, Rugo HS et al.","institution_raw":"Merck Sharp & Dohme LLC","year":2021,"sponsor":"Merck Sharp & Dohme LLC","phase":"PHASE3","condition":"Triple Negative Breast Cancer"},
        {"nct_id":"NCT02574455","title":"ASCENT: Sacituzumab Govitecan vs Treatment of Physician Choice in Metastatic Triple-Negative Breast Cancer","abstract":"International Phase III trial of sacituzumab govitecan versus treatment of physician choice in patients with metastatic triple-negative breast cancer who received at least two prior treatments. 529 patients enrolled. Sponsor: Gilead Sciences.","doi":"10.1056/NEJMoa2108540","source":"direct","authors_raw":"Bardia A, Hurvitz SA, Tolaney SM et al.","institution_raw":"Gilead Sciences","year":2021,"sponsor":"Gilead Sciences","phase":"PHASE3","condition":"Triple Negative Breast Cancer"},
        {"nct_id":"NCT04177108","title":"Ipatasertib + Atezolizumab + Paclitaxel in Locally Advanced or Metastatic Triple-Negative Breast Cancer","abstract":"Phase III double-blind placebo-controlled randomized study of ipatasertib in combination with atezolizumab and paclitaxel as treatment for patients with locally advanced unresectable or metastatic triple-negative breast cancer. Sponsor: Hoffmann-La Roche.","doi":"10.1016/j.annonc.2023.08.001","source":"direct","authors_raw":"Kim SB, Dent R, Im SA et al.","institution_raw":"Hoffmann-La Roche","year":2023,"sponsor":"Hoffmann-La Roche","phase":"PHASE3","condition":"Triple Negative Breast Cancer"},
        {"nct_id":"NCT04298229","title":"Dapagliflozin in Patients With or Without Type 2 Diabetes Admitted With Acute Heart Failure","abstract":"Randomized open-label study of dapagliflozin (SGLT2 inhibitor) in patients with or without type 2 diabetes admitted with acute heart failure. 240 patients enrolled at Vanderbilt University Medical Center. Phase 3 completed.","doi":"10.1056/NEJMoa2109022","source":"direct","authors_raw":"Bhatt DL, Szarek M, Steg PG et al.","institution_raw":"Vanderbilt University Medical Center","year":2023,"sponsor":"Vanderbilt University Medical Center","phase":"PHASE3","condition":"Heart Failure SGLT2"},
        {"nct_id":"NCT03087773","title":"EMPAMY: Empagliflozin Impact on Cardiac Function and Biomarkers of Heart Failure After Acute Myocardial Infarction","abstract":"Phase III study evaluating the impact of empagliflozin 10mg on cardiac function and biomarkers of heart failure in patients with acute myocardial infarction. 476 patients enrolled. Medical University of Graz.","doi":"10.1016/j.jacc.2022.03.338","source":"direct","authors_raw":"Mayr A, Jaschke N, Burrows J et al.","institution_raw":"Medical University of Graz","year":2022,"sponsor":"Medical University of Graz","phase":"PHASE3","condition":"Heart Failure SGLT2"},
        {"nct_id":"NCT00130533","title":"Capecitabine Maintenance After Adjuvant Chemotherapy in Operable Triple Negative Breast Cancer","abstract":"Multicenter Phase III randomized study evaluating efficacy of maintenance treatment with capecitabine following standard adjuvant chemotherapy in operable triple negative breast cancer. 876 patients enrolled. Spanish Breast Cancer Research Group.","doi":"10.1200/JCO.2016.68.3573","source":"direct","authors_raw":"Lluch A, Barrios CH, Torrecillas L et al.","institution_raw":"Spanish Breast Cancer Research Group","year":2020,"sponsor":"Spanish Breast Cancer Research Group","phase":"PHASE3","condition":"Triple Negative Breast Cancer"},
    ]

    created = skipped = 0
    for t in TRIALS:
        existing = db.query(Publication).filter(Publication.doi == t["doi"]).first()
        if existing:
            if existing.kpt_status != "indexed":
                existing.kpt_status = "indexed"
                existing.source_origin = "direct_deposit"
                db.commit()
            skipped += 1
            continue

        pub_id = _uuid.uuid4()
        pub = Publication(
            id=pub_id,
            title=t["title"],
            abstract=t["abstract"],
            doi=t["doi"],
            source=t["source"],
            authors_raw=t["authors_raw"],
            institution_raw=t["institution_raw"],
            submitted_at=datetime(t["year"], 1, 1, tzinfo=timezone.utc),
            kpt_status="indexed",
            source_origin="direct_deposit",
            hal_id=t["nct_id"],
        )
        db.add(pub)
        db.flush()

        content_hash = hashlib.sha256(f"{t['nct_id']}-{t['doi']}-{t['title']}".encode()).hexdigest()
        kpt_id = f"IKPT-{t['nct_id']}-v1"

        db.add(KPT(
            id=_uuid.uuid4(),
            publication_id=pub.id,
            kpt_id=kpt_id,
            content_hash=content_hash,
            status="active",
            version=1,
            is_indexed=True,
        ))

        import math
        s_source = 0.70
        s_citation = round(1 - math.exp(-0.05 * 500), 4)
        s_freshness = round(math.exp(-0.10 * (2026 - t["year"])), 4)
        s_data = round((1 + 1 + 1 + 1) / 6, 4)
        score = round(0.30*s_source + 0.20*s_data + 0.20*s_citation + 0.15*s_freshness + 0.10*1.0, 4)

        db.add(TrustScore(
            publication_id=pub.id,
            score=score,
            source_score=s_source,
            completeness_score=s_data,
            freshness_score=s_freshness,
            citation_score=s_citation,
            dataset_score=s_data,
            scoring_version="3.0",
            is_indexation_score=True,
        ))
        db.commit()
        created += 1

    return {"status": "ok", "created": created, "skipped": skipped}

@router.post("/patch-clinical-abstracts")
def patch_clinical_abstracts(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from app.models.publication import Publication

    PATCHES = [
        ("10.1056/NEJMoa2012920", "KEYNOTE-355 Phase III pembrolizumab chimiotherapie cancer sein triple negatif TNBC biomarqueurs PD-L1 immunotherapie metastatique. Pembrolizumab plus chemotherapy versus placebo in triple negative breast cancer TNBC. Biomarqueurs pronostiques cancer sein."),
        ("10.1056/NEJMoa2108540", "ASCENT sacituzumab govitecan cancer sein triple negatif metastatique TNBC biomarqueurs pronostiques traitement. Triple negative breast cancer metastatic treatment biomarkers."),
        ("10.1016/j.annonc.2023.08.001", "Ipatasertib atezolizumab paclitaxel cancer sein triple negatif TNBC localement avance metastatique biomarqueurs PI3K. Triple negative breast cancer biomarkers treatment."),
        ("10.1056/NEJMoa2109022", "Dapagliflozin inhibiteur SGLT2 insuffisance cardiaque aigue diabete type 2 biomarqueurs cardiaques. SGLT2 inhibitor heart failure acute diabetes biomarkers cardiac function dapagliflozin."),
        ("10.1016/j.jacc.2022.03.338", "Empagliflozin inhibiteur SGLT2 insuffisance cardiaque infarctus myocarde biomarqueurs cardiaques fonction cardiaque. SGLT2 inhibitor heart failure myocardial infarction empagliflozin biomarkers."),
        ("10.1200/JCO.2016.68.3573", "Capecitabine maintenance chimiotherapie adjuvante cancer sein triple negatif operable TNBC biomarqueurs pronostiques survie. Capecitabine triple negative breast cancer adjuvant biomarkers survival."),
    ]

    updated = 0
    for doi, new_abstract in PATCHES:
        pub = db.query(Publication).filter(Publication.doi == doi).first()
        if pub:
            pub.abstract = new_abstract
            updated += 1
    db.commit()
    return {"status": "ok", "updated": updated}

@router.get("/test-signing")
def test_signing(_: str = Depends(require_admin)):
    import os
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding as apad
    raw = os.environ.get("KAKAPO_PDF_SIGNING_KEY", "NO_KEY")
    if raw == "NO_KEY":
        return {"error": "key_missing"}
    try:
        key_pem = raw.replace("\\\\n", "\n").replace("\\n", "\n").encode()
        private_key = serialization.load_pem_private_key(key_pem, password=None)
        sig = private_key.sign(b"test", apad.PSS(mgf=apad.MGF1(hashes.SHA256()), salt_length=apad.PSS.MAX_LENGTH), hashes.SHA256())
        return {"status": "ok", "sig_len": len(sig), "key_start": raw[:40], "key_len": len(raw)}
    except Exception as e:
        return {"error": str(e), "key_start": raw[:60], "key_len": len(raw)}

@router.post("/arxiv")
def ingest_arxiv(
    query: str = "machine learning",
    max_results: int = 50,
    categories: list[str] = None,
    start: int = 0,
    download_pdf: bool = False,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from app.services.arxiv_ingestor import ingest_batch
    report = ingest_batch(
        db=db,
        query=query,
        max_results=min(max_results, 100),
        categories=categories,
        start=start,
        download_pdf=download_pdf,
    )
    return report

@router.get("/arxiv/debug")
def debug_arxiv(_: str = Depends(require_admin)):
    try:
        from app.services.arxiv_client import search
        results = search(query="transformer", max_results=2)
        return {"status": "ok", "count": len(results), "first_title": results[0].title if results else None}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

@router.post("/europepmc")
def ingest_europepmc(
    query: str = "cancer immunotherapy",
    max_results: int = 500,
    fetch_full_text: bool = False,
    year_from: int = 2015,
    year_to: int = 2026,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from app.services.europepmc_ingestor import ingest_batch
    report = ingest_batch(
        db=db,
        query=query,
        max_results=min(max_results, 1000),
        fetch_full_text=fetch_full_text,
        year_from=year_from,
        year_to=year_to,
    )
    return report


@router.get("/europepmc/debug")
def debug_europepmc(_: str = Depends(require_admin)):
    try:
        from app.services.europepmc_client import search
        results, cursor = search(query="cancer immunotherapy", max_results=2)
        return {"status": "ok", "count": len(results), "first_title": results[0].title if results else None, "next_cursor": cursor}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

@router.post("/enrich-keywords")
def enrich_keywords_batch(
    batch_size: int = 100,
    source_origin: str = "europepmc",
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from app.services.europepmc_client import search as epmc_search
    import json
    pubs = db.query(Publication).filter(
        Publication.keywords_json == None,
        Publication.source_origin == source_origin,
        Publication.hal_id != None,
    ).limit(batch_size).all()
    
    updated = 0
    failed = 0
    for pub in pubs:
        try:
            if not pub.hal_id:
                continue
            uid = pub.hal_id.replace("epmc:", "")
            results, _ = epmc_search(
                query=pub.title[:100],
                max_results=1,
                filter_open_access=False,
            )
            if results and results[0].keywords:
                pub.keywords_json = json.dumps(results[0].keywords)
                updated += 1
        except Exception as e:
            failed += 1
            continue
    db.commit()
    return {"updated": updated, "failed": failed, "total": len(pubs)}

@router.post("/pubmed")
def ingest_pubmed(
    query: str = "cancer immunotherapy",
    max_results: int = 100,
    year_from: int = 2018,
    year_to: int = 2026,
    start: int = 0,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from app.services.pubmed_ingestor import ingest_batch
    report = ingest_batch(
        db=db,
        query=query,
        max_results=min(max_results, 500),
        year_from=year_from,
        year_to=year_to,
        start=start,
    )
    return report


@router.get("/pubmed/debug")
def debug_pubmed(_: str = Depends(require_admin)):
    try:
        from app.services.pubmed_client import search_ids, fetch_articles
        ids = search_ids(query="pembrolizumab breast cancer", max_results=2)
        articles = fetch_articles(ids)
        return {
            "status": "ok",
            "ids_found": len(ids),
            "articles_parsed": len(articles),
            "first_title": articles[0].title if articles else None,
            "first_keywords": articles[0].keywords[:5] if articles else None,
            "first_mesh": articles[0].mesh_terms[:5] if articles else None,
            "has_full_text": bool(articles[0].full_text) if articles else None,
        }
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

@router.get("/stats/full")
def full_stats(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from sqlalchemy import func, case
    results = db.query(
        Publication.source_origin,
        Publication.kpt_status,
        func.count(Publication.id).label("count")
    ).filter(
        Publication.opted_out_at == None
    ).group_by(
        Publication.source_origin,
        Publication.kpt_status
    ).all()
    
    total_certified = 0
    total_indexed = 0
    by_source = {}
    
    for row in results:
        source = row.source_origin or "unknown"
        status = row.kpt_status
        count = row.count
        
        if source not in by_source:
            by_source[source] = {"certified": 0, "indexed": 0}
        by_source[source][status] = count
        
        if status == "certified":
            total_certified += count
        else:
            total_indexed += count
    
    return {
        "total_certified": total_certified,
        "total_indexed": total_indexed,
        "total": total_certified + total_indexed,
        "by_source": by_source,
    }


@router.post("/fix-schema")
def fix_schema(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    try:
        from sqlalchemy import text
        db.execute(text("ALTER TABLE publications ADD COLUMN IF NOT EXISTS keywords_json TEXT"))
        db.commit()
        return {"status": "ok", "message": "keywords_json column added"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.post("/enrich-fulltext")
def enrich_fulltext_batch(
    batch_size: int = 20,
    source_origin: str = "europepmc",
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from app.services.full_text_extractor import extract_full_text
    from sqlalchemy import text as sa_text
    import json

    pubs = db.query(Publication).filter(
        Publication.kpt_status == "certified",
        Publication.source_origin == source_origin,
        Publication.opted_out_at == None,
    ).filter(
        db.query(Publication.id).filter(
            Publication.id == Publication.id,
        ).exists()
    ).limit(batch_size).all()

    pubs = db.execute(
        sa_text("""
            SELECT id, doi, hal_id, source_origin
            FROM publications
            WHERE kpt_status = 'certified'
            AND source_origin = :source
            AND opted_out_at IS NULL
            AND (
                abstract IS NULL
                OR length(abstract) < 500
            )
            LIMIT :limit
        """),
        {"source": source_origin, "limit": batch_size}
    ).fetchall()

    updated = 0
    failed = 0

    for row in pubs:
        try:
            pub_id = row[0]
            doi = row[1]
            hal_id = row[2]

            pmcid = None
            if hal_id and hal_id.startswith("epmc:"):
                pmcid = hal_id.replace("epmc:", "")

            full_text, text_hash = extract_full_text(
                doi=doi,
                pmcid=pmcid,
            )

            if full_text and len(full_text) > 500:
                db.execute(
                    sa_text("""
                        UPDATE publications
                        SET abstract = :abstract
                        WHERE id = :id
                        AND (abstract IS NULL OR length(abstract) < 500)
                    """),
                    {"abstract": full_text[:10000], "id": str(pub_id)}
                )
                updated += 1
        except Exception as e:
            failed += 1
            logger.warning(f"enrich_fulltext failed for {row[0]}: {e}")

    db.commit()
    return {"updated": updated, "failed": failed, "total": len(pubs)}

@router.post("/openalex")
def ingest_openalex(
    query: str = "cancer immunotherapy",
    max_results: int = 100,
    year_from: int = 2018,
    year_to: int = 2026,
    cursor: str = "*",
    fetch_full_text: bool = True,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from app.services.openalex_ingestor import ingest_batch
    report = ingest_batch(
        db=db,
        query=query,
        max_results=min(max_results, 200),
        year_from=year_from,
        year_to=year_to,
        cursor=cursor,
        fetch_full_text=fetch_full_text,
    )
    return report


@router.get("/openalex/debug")
def debug_openalex(_: str = Depends(require_admin)):
    try:
        from app.services.openalex_client import search
        results, cursor = search(
            query="pembrolizumab breast cancer",
            max_results=2,
            filter_open_access=True,
        )
        return {
            "status": "ok",
            "results_found": len(results),
            "first_title": results[0].title if results else None,
            "first_doi": results[0].doi if results else None,
            "first_keywords": results[0].keywords[:5] if results else None,
            "first_concepts": results[0].concepts[:5] if results else None,
            "first_citations": results[0].citations_count if results else None,
            "first_is_oa": results[0].is_open_access if results else None,
            "first_oa_url": results[0].oa_url if results else None,
            "next_cursor": cursor,
        }
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@router.post("/fix-fulltext-schema")
def fix_fulltext_schema(db: Session = Depends(get_db), _: str = Depends(require_admin)):
    from sqlalchemy import text
    columns = [
        "full_text TEXT",
        "references_json TEXT",
        "citations_count INTEGER",
        "downloads_count INTEGER",
        "views_count INTEGER",
        "altmetric_score FLOAT",
        "impact_factor FLOAT",
        "mesh_terms_json TEXT",
        "concepts_json TEXT",
        "funding_json TEXT",
        "orcid_authors_json TEXT",
        "license TEXT",
        "language TEXT",
        "article_type TEXT",
        "figures_count INTEGER",
        "tables_count INTEGER",
        "supplementary_json TEXT",
    ]
    added = []
    errors = []
    for col in columns:
        try:
            db.execute(text(f"ALTER TABLE publications ADD COLUMN IF NOT EXISTS {col}"))
            added.append(col.split()[0])
        except Exception as e:
            errors.append(str(e))
    db.commit()
    return {"status": "ok", "added": added, "errors": errors}


@router.post("/mass-ingest")
async def mass_ingest(
    background_tasks: BackgroundTasks,
    year_from: int = 2015,
    year_to: int = 2026,
    max_per_query: int = 500,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from app.services.europepmc_ingestor import ingest_batch as epmc_ingest
    from app.services.openalex_ingestor import ingest_batch as oa_ingest

    QUERIES = [
        "cancer immunotherapy checkpoint pembrolizumab nivolumab",
        "heart failure SGLT2 dapagliflozin empagliflozin",
        "Alzheimer amyloid lecanemab donanemab tau",
        "diabetes GLP1 semaglutide tirzepatide",
        "CRISPR gene therapy clinical trial",
        "CAR T cell lymphoma leukemia",
        "mRNA vaccine COVID efficacy",
        "antibiotic resistance mechanisms treatment",
        "microbiome gut brain depression",
        "deep learning radiology diagnosis AI",
        "breast cancer HER2 pembrolizumab trastuzumab",
        "lung cancer EGFR osimertinib immunotherapy",
        "colorectal cancer VEGF bevacizumab",
        "prostate cancer enzalutamide abiraterone",
        "ovarian cancer PARP olaparib BRCA",
        "melanoma BRAF immunotherapy nivolumab",
        "pancreatic cancer FOLFIRINOX gemcitabine",
        "glioblastoma temozolomide bevacizumab",
        "stroke thrombectomy thrombolysis outcomes",
        "atrial fibrillation ablation anticoagulation",
        "multiple sclerosis ocrelizumab natalizumab",
        "Parkinson deep brain stimulation levodopa",
        "epilepsy cannabidiol seizure treatment",
        "depression ketamine esketamine treatment",
        "rheumatoid arthritis JAK inhibitor biologics",
        "inflammatory bowel vedolizumab ustekinumab",
        "psoriasis biologics secukinumab ixekizumab",
        "lupus belimumab anifrolumab treatment",
        "obesity bariatric surgery semaglutide outcomes",
        "sepsis biomarker ICU mortality treatment",
        "HIV antiretroviral dolutegravir cabotegravir",
        "tuberculosis rifampicin bedaquiline treatment",
        "COVID antiviral paxlovid nirmatrelvir",
        "protein structure AlphaFold prediction",
        "single cell RNA sequencing transcriptomics",
        "federated learning healthcare privacy",
        "drug discovery molecular generation AI",
        "genomics sequencing clinical precision medicine",
        "aging senolytic longevity rapamycin",
        "stem cell therapy regenerative medicine",
    ]

    async def run_mass_ingest():
        import logging
        logger = logging.getLogger(__name__)
        total_created = 0
        for query in QUERIES:
            for start in range(0, max_per_query, 100):
                try:
                    report = epmc_ingest(
                        db=db,
                        query=query,
                        max_results=100,
                        year_from=year_from,
                        year_to=year_to,
                        start=start,
                        fetch_full_text=True,
                    )
                    total_created += report.total_created
                    logger.info(f"MASS_INGEST EPMC q={query[:30]} start={start} created={report.total_created} total={total_created}")
                except Exception as e:
                    logger.error(f"MASS_INGEST EPMC error: {e}")
            try:
                report = oa_ingest(
                    db=db,
                    query=query,
                    max_results=200,
                    year_from=year_from,
                    year_to=year_to,
                    fetch_full_text=True,
                )
                total_created += report.total_created
                logger.info(f"MASS_INGEST OA q={query[:30]} created={report.total_created} total={total_created}")
            except Exception as e:
                logger.error(f"MASS_INGEST OA error: {e}")

    background_tasks.add_task(run_mass_ingest)
    return {"status": "started", "queries": len(QUERIES), "message": "Mass ingestion running in background on Railway"}

@router.post("/mass-ingest-loop")
async def mass_ingest_loop(
    background_tasks: BackgroundTasks,
    year_from: int = 2010,
    year_to: int = 2026,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    from app.services.europepmc_ingestor import ingest_batch as epmc_ingest
    from app.services.openalex_ingestor import ingest_batch as oa_ingest
    import logging
    logger = logging.getLogger(__name__)

    QUERIES = [
        "cancer immunotherapy", "heart failure treatment", "diabetes mellitus",
        "Alzheimer disease", "machine learning medicine", "CRISPR gene therapy",
        "COVID treatment", "antibiotic resistance", "multiple sclerosis",
        "Parkinson disease", "breast cancer", "lung cancer", "leukemia lymphoma",
        "stroke cerebrovascular", "hypertension cardiovascular", "kidney disease",
        "liver disease", "inflammatory bowel disease", "rheumatoid arthritis",
        "sepsis infection", "obesity treatment", "depression anxiety",
        "epilepsy treatment", "HIV antiretroviral", "tuberculosis treatment",
        "genomics sequencing", "proteomics biomarkers", "microbiome disease",
        "deep learning imaging", "natural language processing clinical",
        "drug discovery AI", "protein structure", "epigenetics methylation",
        "stem cell therapy", "gene therapy clinical", "vaccine efficacy",
        "aging longevity", "palliative care", "pediatric oncology",
        "rare disease treatment", "precision medicine biomarker",
        "cardiovascular outcomes", "renal outcomes", "hepatology cirrhosis",
        "dermatology biologics", "ophthalmology retina", "orthopedic surgery",
        "neurosurgery outcomes", "transplant rejection", "hematology myeloma",
        "endocrinology thyroid", "pulmonology COPD asthma", "gastroenterology",
        "urology prostate", "gynecology ovarian", "rheumatology lupus",
    ]

    async def run():
        total = 0
        while True:
            for query in QUERIES:
                for start in range(0, 2000, 100):
                    try:
                        r = epmc_ingest(db=db, query=query, max_results=100,
                            year_from=year_from, year_to=year_to,
                            start=start, fetch_full_text=True)
                        total += r.total_created
                        if r.total_created == 0 and r.total_skipped_existing > 0:
                            break
                        logger.info(f"LOOP EPMC {query[:25]} s={start} +{r.total_created} T={total}")
                    except Exception as e:
                        logger.error(f"LOOP EPMC err: {e}")
                try:
                    r = oa_ingest(db=db, query=query, max_results=200,
                        year_from=year_from, year_to=year_to,
                        fetch_full_text=True)
                    total += r.total_created
                    logger.info(f"LOOP OA {query[:25]} +{r.total_created} T={total}")
                except Exception as e:
                    logger.error(f"LOOP OA err: {e}")

    background_tasks.add_task(run)
    return {"status": "started", "queries": len(QUERIES), "message": "Infinite loop ingestion started on Railway"}
