"""
Oparence Canonical Fingerprint v1.1
====================================

CHANGELOG v1.1 (2026-05-21):
- Added _normalize_outcome() and _normalize_intervention()
- Handles BOTH DB format (m/t/d compact) AND API format (measure/timeFrame/description verbose)
- Guarantees same hash regardless of source format
- Strings JSON parsed automatically

CDC v1.0 : voir docs/CERTIFICATION_SPEC.md
"""
import hashlib
import json
import re
from typing import Any, Dict, List, Optional


SPEC_VERSION = "v1.1"


def _normalize_str(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def _parse_if_string(v):
    """If v is a JSON string, parse it. Otherwise return as-is."""
    if isinstance(v, str):
        v_stripped = v.strip()
        if v_stripped.startswith('[') or v_stripped.startswith('{'):
            try:
                return json.loads(v_stripped)
            except Exception:
                pass
    return v


def _normalize_list_str(lst: Optional[List]) -> List[str]:
    if lst is None:
        return []
    lst = _parse_if_string(lst)
    if not isinstance(lst, list):
        lst = [lst]
    out = []
    for x in lst:
        if x is None:
            continue
        if isinstance(x, dict):
            x = x.get("name") or x.get("measure") or x.get("m") or str(x)
        out.append(_normalize_str(str(x)))
    return sorted([x for x in out if x])


def _normalize_outcome(o):
    """Normalize outcome object — accepts DB compact (m/t/d) or API verbose (measure/timeFrame/description)."""
    if o is None:
        return None
    if isinstance(o, str):
        return {"measure": _normalize_str(o), "timeFrame": "", "description": ""}
    if not isinstance(o, dict):
        return None
    return {
        "measure": _normalize_str(o.get("measure") or o.get("m") or ""),
        "timeFrame": _normalize_str(o.get("timeFrame") or o.get("t") or ""),
        "description": _normalize_str(o.get("description") or o.get("d") or ""),
    }


def _normalize_intervention(i):
    """Normalize intervention object — accepts DB and API format."""
    if i is None:
        return None
    if isinstance(i, str):
        return {"name": _normalize_str(i), "type": "", "description": ""}
    if not isinstance(i, dict):
        return None
    return {
        "name": _normalize_str(i.get("name") or ""),
        "type": _normalize_str(i.get("type") or ""),
        "description": _normalize_str(i.get("description") or ""),
    }


def _normalize_outcomes_list(raw):
    if raw is None:
        return []
    raw = _parse_if_string(raw)
    if not isinstance(raw, list):
        return []
    out = [_normalize_outcome(o) for o in raw]
    out = [o for o in out if o and o.get("measure")]
    out.sort(key=lambda x: (x["measure"], x["timeFrame"], x["description"]))
    return out


def _normalize_interventions_list(raw):
    if raw is None:
        return []
    raw = _parse_if_string(raw)
    if not isinstance(raw, list):
        return []
    out = [_normalize_intervention(i) for i in raw]
    out = [i for i in out if i and i.get("name")]
    out.sort(key=lambda x: (x["name"], x["type"]))
    return out


def _canonical_hash(obj: Any) -> str:
    canonical = json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(',', ':'),
        default=str,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p]


def _word_count(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def compute_ct_fingerprints(study: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcule tous les fingerprints d'un clinical trial.
    Accepts both DB-stored format (JSON strings, compact keys) and API live format.
    """
    nct_id = _normalize_str(study.get("nct_id"))
    title = _normalize_str(study.get("title"))
    sponsor = _normalize_str(study.get("sponsor"))
    
    status = _normalize_str(study.get("status"))
    phase = _normalize_list_str(study.get("phase"))
    study_type = _normalize_str(study.get("study_type"))
    conditions = _normalize_list_str(study.get("conditions"))
    interventions = _normalize_interventions_list(study.get("interventions"))
    eligibility = _normalize_str(study.get("eligibility_criteria"))
    
    primary_outcomes = _normalize_outcomes_list(study.get("primary_outcomes"))
    secondary_outcomes = _normalize_outcomes_list(study.get("secondary_outcomes"))
    
    brief = _normalize_str(study.get("brief_summary"))
    detailed = _normalize_str(study.get("detailed_description"))
    
    fp_identity = _canonical_hash({
        "nct_id": nct_id,
        "title": title,
        "sponsor": sponsor,
    })
    
    fp_protocol = _canonical_hash({
        "study_type": study_type,
        "phase": phase,
        "conditions": conditions,
        "interventions": interventions,
        "eligibility": eligibility,
        "status": status,
    })
    
    fp_outcomes = _canonical_hash({
        "primary": primary_outcomes,
        "secondary": secondary_outcomes,
    })
    
    fp_narrative = _canonical_hash({
        "brief": brief,
        "detailed": detailed,
    })
    
    fp_canonical = _canonical_hash({
        "identity": fp_identity,
        "protocol": fp_protocol,
        "outcomes": fp_outcomes,
        "narrative": fp_narrative,
    })
    
    sentences = _split_sentences(detailed)
    first_s = sentences[0] if sentences else ""
    last_s = sentences[-1] if sentences else ""
    
    fp_first_sentence = _canonical_hash(first_s) if first_s else None
    fp_last_sentence = _canonical_hash(last_s) if last_s else None
    
    total_text = brief + " " + detailed + " " + eligibility
    
    return {
        "fp_identity": fp_identity,
        "fp_protocol": fp_protocol,
        "fp_outcomes": fp_outcomes,
        "fp_narrative": fp_narrative,
        "fp_canonical": fp_canonical,
        "fp_content_length": len(total_text),
        "fp_word_count": _word_count(total_text),
        "fp_first_sentence": fp_first_sentence,
        "fp_last_sentence": fp_last_sentence,
        "fp_spec_version": SPEC_VERSION,
    }


def compute_pub_fingerprints(pub: Dict[str, Any]) -> Dict[str, Any]:
    doi = _normalize_str(pub.get("doi"))
    title = _normalize_str(pub.get("title"))
    
    authors_raw = _parse_if_string(pub.get("authors_raw") or pub.get("authors"))
    if isinstance(authors_raw, list):
        authors = sorted([_normalize_str(str(a)) for a in authors_raw if a])
    else:
        authors = []
    
    journal = _normalize_str(pub.get("institution_raw") or pub.get("journal"))
    abstract = _normalize_str(pub.get("abstract"))
    full_text = _normalize_str(pub.get("full_text"))
    
    refs_raw = _parse_if_string(pub.get("references_json") or pub.get("references"))
    references = sorted([_normalize_str(str(r)) for r in (refs_raw if isinstance(refs_raw, list) else []) if r])
    
    fp_identity = _canonical_hash({"doi": doi, "title": title, "authors": authors, "journal": journal})
    fp_metadata = _canonical_hash({"title": title, "authors": authors, "journal": journal})
    fp_content = _canonical_hash({"abstract": abstract, "full_text": full_text})
    fp_references = _canonical_hash({"refs": references})
    fp_canonical = _canonical_hash({"identity": fp_identity, "metadata": fp_metadata, "content": fp_content, "references": fp_references})
    
    body = full_text if full_text else abstract
    sentences = _split_sentences(body)
    first_s = sentences[0] if sentences else ""
    last_s = sentences[-1] if sentences else ""
    fp_first_sentence = _canonical_hash(first_s) if first_s else None
    fp_last_sentence = _canonical_hash(last_s) if last_s else None
    total_text = abstract + " " + full_text
    
    return {
        "fp_identity": fp_identity,
        "fp_metadata": fp_metadata,
        "fp_content": fp_content,
        "fp_references": fp_references,
        "fp_canonical": fp_canonical,
        "fp_content_length": len(total_text),
        "fp_word_count": _word_count(total_text),
        "fp_first_sentence": fp_first_sentence,
        "fp_last_sentence": fp_last_sentence,
        "fp_spec_version": SPEC_VERSION,
    }


def compare_ct_fingerprints(stored: Dict, current: Dict) -> Dict[str, Any]:
    zones_to_check = ['fp_identity', 'fp_protocol', 'fp_outcomes', 'fp_narrative']
    changed = []
    for z in zones_to_check:
        if stored.get(z) and current.get(z) and stored[z] != current[z]:
            changed.append(z.replace('fp_', ''))
    if not changed:
        return {"integrity_status": "verified", "zones_changed": [], "alteration_type": None, "significant": False}
    alteration_type = changed[0] if len(changed) == 1 else "multiple"
    significant = any(z in ['identity', 'protocol', 'outcomes'] for z in changed)
    return {"integrity_status": "altered", "zones_changed": changed, "alteration_type": alteration_type, "significant": significant}


if __name__ == "__main__":
    import sys
    
    db_format = {
        "nct_id": "NCT03273621",
        "title": "Bariatric Surgery and Epicardial Adipose Tissue: a MRI Study",
        "sponsor": "IRCCS Policlinico S. Donato",
        "status": "COMPLETED",
        "phase": "[]",
        "study_type": "OBSERVATIONAL",
        "conditions": '["Obesity"]',
        "interventions": '[{"type": "PROCEDURE", "name": "Bariatic surgery", "description": "One of two different types"}]',
        "eligibility_criteria": "Adult patients with morbid obesity",
        "primary_outcomes": '[{"m": "EAT volume", "t": "Immediately after MRI", "d": "EAT volume measured in ml"}]',
        "secondary_outcomes": "[]",
        "brief_summary": "Brief study summary here.",
        "detailed_description": "Detailed description.",
    }
    
    api_format = {
        "nct_id": "NCT03273621",
        "title": "Bariatric Surgery and Epicardial Adipose Tissue: a MRI Study",
        "sponsor": "IRCCS Policlinico S. Donato",
        "status": "COMPLETED",
        "phase": [],
        "study_type": "OBSERVATIONAL",
        "conditions": ["Obesity"],
        "interventions": [{"type": "PROCEDURE", "name": "Bariatic surgery", "description": "One of two different types", "armGroupLabels": ["Obese"]}],
        "eligibility_criteria": "Adult patients with morbid obesity",
        "primary_outcomes": [{"measure": "EAT volume", "timeFrame": "Immediately after MRI", "description": "EAT volume measured in ml"}],
        "secondary_outcomes": [],
        "brief_summary": "Brief study summary here.",
        "detailed_description": "Detailed description.",
    }
    
    print("=== TEST 1: DETERMINISME ===")
    r1 = [compute_ct_fingerprints(db_format) for _ in range(10)]
    determ = all(r == r1[0] for r in r1)
    print(f"  10 hashes identiques : {determ}")
    
    print("\n=== TEST 2: ROBUSTESSE (espaces) ===")
    db_ws = dict(db_format)
    db_ws["title"] = "  " + db_ws["title"] + "  "
    db_ws["brief_summary"] = "Brief  study  summary  here."
    r2 = compute_ct_fingerprints(db_ws)
    robust = r2['fp_canonical'] == r1[0]['fp_canonical']
    print(f"  Robust to whitespace : {robust}")
    
    print("\n=== TEST 3: DETECTION (changement protocol) ===")
    db_diff = dict(db_format)
    db_diff["interventions"] = '[{"type": "PROCEDURE", "name": "Bariatic surgery", "description": "MODIFIED DESCRIPTION"}]'
    r3 = compute_ct_fingerprints(db_diff)
    detect_proto = r3['fp_protocol'] != r1[0]['fp_protocol']
    detect_others = r3['fp_outcomes'] == r1[0]['fp_outcomes'] and r3['fp_narrative'] == r1[0]['fp_narrative']
    print(f"  Protocol change detected : {detect_proto}")
    print(f"  Other zones inchangees   : {detect_others}")
    
    print("\n=== TEST 4: TOLERANCE BRUIT (champ non hashe) ===")
    db_noise = dict(db_format)
    db_noise["enrollment"] = 999
    db_noise["last_update_posted"] = "2026-01-01"
    r4 = compute_ct_fingerprints(db_noise)
    noise_tol = r4['fp_canonical'] == r1[0]['fp_canonical']
    print(f"  Noise tolerated : {noise_tol}")
    
    print("\n=== TEST 5 (CRITIQUE): DB FORMAT == API FORMAT ===")
    r_db = compute_ct_fingerprints(db_format)
    r_api = compute_ct_fingerprints(api_format)
    db_eq_api = r_db['fp_canonical'] == r_api['fp_canonical']
    print(f"  DB hash         : {r_db['fp_canonical']}")
    print(f"  API hash        : {r_api['fp_canonical']}")
    print(f"  EQUAL (CRITICAL): {db_eq_api}")
    
    all_ok = determ and robust and detect_proto and detect_others and noise_tol and db_eq_api
    print(f"\n=== VERDICT ===")
    print(f"  All tests pass : {all_ok}")
    if not all_ok:
        sys.exit(1)
