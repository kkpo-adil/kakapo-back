from datetime import datetime, timezone


def _s(val) -> str:
    if isinstance(val, list):
        return val[0] if val else ""
    return str(val) if val else ""


def compute(publication_metadata: dict, citation_count: int) -> int:
    score = 0

    doi = _s(publication_metadata.get("doiId_s", ""))
    abstract = _s(publication_metadata.get("abstract_s", ""))
    orcids = publication_metadata.get("authORCIDIdExt_s", []) or []
    date_str = _s(publication_metadata.get("producedDate_s", ""))
    keywords = publication_metadata.get("keyword_s", []) or []
    journal = _s(publication_metadata.get("journalTitle_s", ""))
    publisher = _s(publication_metadata.get("publisher_s", ""))
    domain = publication_metadata.get("domain_s", []) or []
    open_access = publication_metadata.get("openAccess_bool", False)

    if doi.strip():
        score += 10
    if abstract and len(abstract.strip()) > 50:
        score += 5
    if orcids:
        score += 5
    if date_str.strip():
        score += 3
    if keywords:
        score += 2

    if journal.strip() or publisher.strip():
        score += 10
    if domain:
        score += 5

    if date_str.strip():
        try:
            year = int(date_str[:4])
            age = datetime.now(timezone.utc).year - year
            if age <= 5:
                score += 10
            elif age <= 10:
                score += 6
            else:
                score += 3
        except (ValueError, IndexError):
            score += 3

    if citation_count == 0:
        score += 0
    elif citation_count <= 5:
        score += 8
    elif citation_count <= 20:
        score += 16
    elif citation_count <= 100:
        score += 24
    else:
        score += 30

    if open_access:
        score += 10

    if orcids:
        score += 10

    return min(max(score, 0), 100)
