"""
Oparence IntegrityChecker — V1
Detects content alteration between Oparence's stored SHA-256 hash
and the live source at primary URL.

3-tier detection:
1. Periodic re-crawl (background cron)
2. On-demand verify (via /integrity/verify/{kpt_id})
3. Verify-on-stream (called by /demo/stream endpoint)
"""
import hashlib
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

USER_AGENT = "OparenceIntegrityBot/1.0 (+https://oparence.io/bot)"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fetch_source(url: str) -> Tuple[Optional[bytes], int]:
    if not url:
        return None, 0
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as cli:
            r = cli.get(url)
            return r.content if r.status_code == 200 else None, r.status_code
    except Exception as ex:
        logger.warning(f"fetch fail {url}: {ex}")
        return None, 0


def verify_kpt(db: Session, kpt_id: str, triggered_by: str = "manual") -> dict:
    """Re-fetch source, recompute CANONICAL FINGERPRINTS, compare per zone.
    
    Uses canonical_fingerprint v1.0 multi-zone hashing.
    Distinguishes between identity / protocol / outcomes / narrative changes.
    """
    from app.services.canonical_fingerprint import compute_ct_fingerprints, compare_ct_fingerprints
    import json
    
    row = db.execute(text("""
        SELECT p.id, k.kpt_id, k.content_hash AS file_hash, p.source_url, 
               p.kpl_version, p.integrity_status
        FROM publications p
        JOIN kpts k ON k.publication_id = p.id
        WHERE k.kpt_id = :kpt_id
        LIMIT 1
    """), {"kpt_id": kpt_id}).first()
    
    table = "publications"
    if not row:
        ct_row = db.execute(text("""
            SELECT id, kpt_id, hash_ct, nct_id,
                   fp_identity, fp_protocol, fp_outcomes, fp_narrative, fp_canonical,
                   kpl_version, integrity_status
            FROM clinical_trials
            WHERE kpt_id = :kpt_id
            LIMIT 1
        """), {"kpt_id": kpt_id}).first()
        
        if ct_row:
            return _verify_ct_canonical(db, ct_row, triggered_by)
        
        row = None
        table = None
    
    if not row:
        return {"kpt_id": kpt_id, "status": "not_found", "verified": False}
    
    stored_hash = row[2]
    source_url = row[3] if table == "publications" else None
    current_version = row[4] or 1
    
    if not source_url:
        if table == "clinical_trials":
            nct_id = db.execute(text("SELECT nct_id FROM clinical_trials WHERE kpt_id = :k"), {"k": kpt_id}).scalar()
            if nct_id:
                source_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
    
    if not source_url:
        db.execute(text(f"UPDATE {table} SET last_verified_at = NOW(), integrity_status = 'no_source' WHERE kpt_id = :k"), {"k": kpt_id})
        db.commit()
        return {"kpt_id": kpt_id, "status": "no_source_url", "verified": False}
    
    content, response_code = fetch_source(source_url)
    
    if response_code == 404:
        _log_alteration(db, kpt_id, table, stored_hash, None, current_version, current_version + 1, "retracted", 404, triggered_by)
        db.execute(text(f"UPDATE {table} SET last_verified_at = NOW(), integrity_status = 'retracted', kpl_version = :v WHERE kpt_id = :k"), {"k": kpt_id, "v": current_version + 1})
        db.commit()
        return {"kpt_id": kpt_id, "status": "retracted", "verified": True, "alteration_type": "retracted"}
    
    if content is None:
        db.execute(text(f"UPDATE {table} SET last_verified_at = NOW(), integrity_status = 'fetch_failed' WHERE kpt_id = :k"), {"k": kpt_id})
        db.commit()
        return {"kpt_id": kpt_id, "status": "fetch_failed", "verified": False, "http_code": response_code}
    
    new_hash = compute_sha256(content)
    
    if new_hash == stored_hash:
        db.execute(text(f"UPDATE {table} SET last_verified_at = NOW(), integrity_status = 'verified' WHERE kpt_id = :k"), {"k": kpt_id})
        db.commit()
        return {"kpt_id": kpt_id, "status": "verified", "verified": True, "hash_match": True}
    
    _log_alteration(db, kpt_id, table, stored_hash, new_hash, current_version, current_version + 1, "content_changed", response_code, triggered_by)
    db.execute(text(f"""
        UPDATE {table} 
        SET last_verified_at = NOW(), integrity_status = 'altered', 
            previous_hash = :prev, kpl_version = :v 
        WHERE kpt_id = :k
    """), {"k": kpt_id, "prev": stored_hash, "v": current_version + 1})
    db.commit()
    return {"kpt_id": kpt_id, "status": "altered", "verified": True, "previous_hash": stored_hash, "new_hash": new_hash, "new_version": current_version + 1}


def _verify_ct_canonical(db: Session, ct_row, triggered_by: str) -> dict:
    """Verify a clinical_trial KPT using canonical multi-zone fingerprints."""
    from app.services.canonical_fingerprint import compute_ct_fingerprints, compare_ct_fingerprints
    
    nct_id = ct_row[3]
    stored_fps = {
        "fp_identity": ct_row[4],
        "fp_protocol": ct_row[5],
        "fp_outcomes": ct_row[6],
        "fp_narrative": ct_row[7],
        "fp_canonical": ct_row[8],
    }
    current_version = ct_row[9] or 1
    
    if not stored_fps.get("fp_canonical"):
        return {"kpt_id": ct_row[1], "status": "not_yet_backfilled", "verified": False,
                "message": "Fingerprints not yet computed for this KPT"}
    
    source_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
    content, response_code = fetch_source(source_url)
    
    if response_code == 404:
        _log_alteration(db, ct_row[1], "clinical_trials", stored_fps["fp_canonical"], None,
                        current_version, current_version + 1, "retracted", 404, triggered_by)
        db.execute(text("""
            UPDATE clinical_trials
            SET last_verified_at = NOW(), integrity_status = 'retracted',
                kpl_version = :v
            WHERE kpt_id = :k
        """), {"k": ct_row[1], "v": current_version + 1})
        db.commit()
        return {"kpt_id": ct_row[1], "status": "retracted", "verified": True}
    
    if content is None:
        db.execute(text("""
            UPDATE clinical_trials
            SET last_verified_at = NOW(), integrity_status = 'fetch_failed'
            WHERE kpt_id = :k
        """), {"k": ct_row[1]})
        db.commit()
        return {"kpt_id": ct_row[1], "status": "fetch_failed", "http_code": response_code}
    
    import json as _json
    try:
        data = _json.loads(content)
        ps = data.get("protocolSection", {})
        
        def _sl(v):
            if v is None: return []
            if isinstance(v, list): return v
            return [str(v)]
        
        study_data = {
            "nct_id": nct_id,
            "title": ps.get("identificationModule", {}).get("briefTitle", ""),
            "sponsor": ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
            "status": ps.get("statusModule", {}).get("overallStatus", ""),
            "phase": _sl(ps.get("designModule", {}).get("phases", [])),
            "study_type": ps.get("designModule", {}).get("studyType", ""),
            "conditions": _sl(ps.get("conditionsModule", {}).get("conditions", [])),
            "interventions": [
                {
                    "type": i.get("type", "") or "",
                    "name": i.get("name", "") or "",
                    "description": i.get("description", "") or "",
                }
                for i in ps.get("armsInterventionsModule", {}).get("interventions", [])
                if i.get("name")
            ],
            "eligibility_criteria": ps.get("eligibilityModule", {}).get("eligibilityCriteria", ""),
            "primary_outcomes": [
                {
                    "measure": o.get("measure", "") or "",
                    "timeFrame": o.get("timeFrame", "") or "",
                    "description": o.get("description", "") or "",
                }
                for o in ps.get("outcomesModule", {}).get("primaryOutcomes", [])
                if o.get("measure")
            ],
            "secondary_outcomes": [
                {
                    "measure": o.get("measure", "") or "",
                    "timeFrame": o.get("timeFrame", "") or "",
                    "description": o.get("description", "") or "",
                }
                for o in ps.get("outcomesModule", {}).get("secondaryOutcomes", [])
                if o.get("measure")
            ],
            "brief_summary": ps.get("descriptionModule", {}).get("briefSummary", ""),
            "detailed_description": ps.get("descriptionModule", {}).get("detailedDescription", ""),
        }
        current_fps = compute_ct_fingerprints(study_data)
    except Exception as ex:
        logger.error(f"Parse error for {nct_id}: {ex}")
        return {"kpt_id": ct_row[1], "status": "parse_failed", "error": str(ex)}
    
    comparison = compare_ct_fingerprints(stored_fps, current_fps)
    
    if comparison["integrity_status"] == "verified":
        db.execute(text("""
            UPDATE clinical_trials
            SET last_verified_at = NOW(), integrity_status = 'verified'
            WHERE kpt_id = :k
        """), {"k": ct_row[1]})
        db.commit()
        return {
            "kpt_id": ct_row[1], "status": "verified", "verified": True,
            "zones_checked": ["identity", "protocol", "outcomes", "narrative"],
        }
    
    _log_alteration(
        db, ct_row[1], "clinical_trials",
        stored_fps["fp_canonical"], current_fps["fp_canonical"],
        current_version, current_version + 1,
        comparison["alteration_type"], response_code, triggered_by
    )
    db.execute(text("""
        UPDATE clinical_trials
        SET last_verified_at = NOW(),
            integrity_status = 'altered',
            previous_hash = :prev,
            kpl_version = :v
        WHERE kpt_id = :k
    """), {"k": ct_row[1], "prev": stored_fps["fp_canonical"], "v": current_version + 1})
    db.commit()
    
    return {
        "kpt_id": ct_row[1], "status": "altered", "verified": True,
        "zones_changed": comparison["zones_changed"],
        "alteration_type": comparison["alteration_type"],
        "significant": comparison["significant"],
        "new_version": current_version + 1,
    }



def _log_alteration(db, kpt_id, source_type, prev_hash, new_hash, prev_ver, new_ver, alt_type, response_code, triggered_by):
    db.execute(text("""
        INSERT INTO alterations 
        (kpt_id, source_type, previous_hash, new_hash, previous_version, new_version,
         alteration_type, source_response_code, triggered_by)
        VALUES (:kpt_id, :st, :ph, :nh, :pv, :nv, :at, :sc, :tb)
    """), {
        "kpt_id": kpt_id, "st": source_type, "ph": prev_hash, "nh": new_hash,
        "pv": prev_ver, "nv": new_ver, "at": alt_type, "sc": response_code, "tb": triggered_by
    })


def recrawl_batch(db: Session, batch_size: int = 100, max_age_hours: int = 24) -> dict:
    """Re-crawl KPTs not verified in last max_age_hours.
    
    Two architectures handled:
    - publications : JOIN with kpts table (kpt_id, content_hash via kpts FK)
    - clinical_trials : kpt_id stored directly in the table
    """
    t0 = time.time()
    half = max(batch_size // 2, 1)
    
    pub_rows = db.execute(text("""
        SELECT k.kpt_id 
        FROM publications p
        JOIN kpts k ON k.publication_id = p.id
        WHERE p.source_url IS NOT NULL 
          AND (p.last_verified_at IS NULL OR p.last_verified_at < NOW() - (INTERVAL '1 hour' * :h))
        ORDER BY p.last_verified_at NULLS FIRST
        LIMIT :n
    """), {"n": half, "h": max_age_hours}).all()
    
    ct_rows = db.execute(text("""
        SELECT kpt_id FROM clinical_trials 
        WHERE (last_verified_at IS NULL OR last_verified_at < NOW() - (INTERVAL '1 hour' * :h))
        ORDER BY last_verified_at NULLS FIRST
        LIMIT :n
    """), {"n": half, "h": max_age_hours}).all()
    
    all_rows = list(pub_rows) + list(ct_rows)
    
    stats = {"verified": 0, "altered": 0, "retracted": 0, "failed": 0, "no_source": 0}
    for (kpt_id,) in all_rows:
        try:
            result = verify_kpt(db, kpt_id, triggered_by="recrawl_cron")
            status = result.get("status", "failed")
            if status == "verified": stats["verified"] += 1
            elif status == "altered": stats["altered"] += 1
            elif status == "retracted": stats["retracted"] += 1
            elif status == "no_source_url": stats["no_source"] += 1
            else: stats["failed"] += 1
        except Exception as ex:
            logger.error(f"verify error {kpt_id}: {ex}")
            stats["failed"] += 1
    
    stats["duration_s"] = round(time.time() - t0, 1)
    stats["batch_size_processed"] = len(all_rows)
    stats["publications_picked"] = len(pub_rows)
    stats["clinical_trials_picked"] = len(ct_rows)
    return stats


def get_integrity_summary(db: Session) -> dict:
    """Summary stats for /demo/integrity-summary endpoint."""
    pub_stats = db.execute(text("""
        SELECT 
            COUNT(*) FILTER (WHERE fp_canonical IS NOT NULL) AS verified,
            COUNT(*) FILTER (WHERE integrity_status = 'altered') AS altered,
            COUNT(*) FILTER (WHERE integrity_status = 'retracted') AS retracted,
            COUNT(*) FILTER (WHERE fp_canonical IS NULL) AS unverified,
            MAX(fp_computed_at) AS last_check
        FROM publications
    """)).first()
    
    ct_stats = db.execute(text("""
        SELECT 
            COUNT(*) FILTER (WHERE fp_canonical IS NOT NULL) AS verified,
            COUNT(*) FILTER (WHERE integrity_status = 'altered') AS altered,
            COUNT(*) FILTER (WHERE integrity_status = 'retracted') AS retracted,
            COUNT(*) FILTER (WHERE fp_canonical IS NULL) AS unverified,
            MAX(fp_computed_at) AS last_check
        FROM clinical_trials
    """)).first()
    
    recent_alterations = db.execute(text("""
        SELECT kpt_id, alteration_type, detected_at
        FROM alterations
        ORDER BY detected_at DESC
        LIMIT 5
    """)).all()
    
    return {
        "publications": {
            "verified": pub_stats[0] or 0,
            "altered": pub_stats[1] or 0,
            "retracted": pub_stats[2] or 0,
            "unverified": pub_stats[3] or 0,
            "last_check": pub_stats[4].isoformat() if pub_stats[4] else None,
        },
        "clinical_trials": {
            "verified": ct_stats[0] or 0,
            "altered": ct_stats[1] or 0,
            "retracted": ct_stats[2] or 0,
            "unverified": ct_stats[3] or 0,
            "last_check": ct_stats[4].isoformat() if ct_stats[4] else None,
        },
        "recent_alterations": [
            {"kpt_id": r[0], "type": r[1], "detected_at": r[2].isoformat() if r[2] else None}
            for r in recent_alterations
        ],
    }
