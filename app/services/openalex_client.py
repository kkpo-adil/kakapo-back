import time
import logging
import httpx
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

OPENALEX_API = "https://api.openalex.org/works"
USER_AGENT = "KAKAPO/1.0 (mailto:contact@kakapo.io)"
TIMEOUT = 30.0


@dataclass
class OpenAlexResult:
    openalex_id: str
    title: str
    abstract: Optional[str]
    authors: list[str]
    doi: Optional[str]
    published: Optional[str]
    journal: Optional[str]
    publisher: Optional[str]
    is_open_access: bool
    oa_url: Optional[str]
    pdf_url: Optional[str]
    keywords: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    citations_count: int = 0
    mesh_terms: list[str] = field(default_factory=list)
    language: Optional[str] = None


def _reconstruct_abstract(inverted_index: dict) -> Optional[str]:
    if not inverted_index:
        return None
    try:
        positions = []
        for word, pos_list in inverted_index.items():
            for pos in pos_list:
                positions.append((pos, word))
        positions.sort()
        return " ".join(w for _, w in positions)
    except Exception:
        return None


def search(
    query: str,
    max_results: int = 100,
    cursor: str = "*",
    year_from: int = 2015,
    year_to: int = 2026,
    filter_open_access: bool = True,
) -> tuple[list[OpenAlexResult], str]:
    filters = [f"publication_year:{year_from}-{year_to}"]
    if filter_open_access:
        filters.append("is_oa:true")

    params = {
        "search": query,
        "filter": ",".join(filters),
        "per_page": min(max_results, 200),
        "cursor": cursor,
        "select": "id,title,abstract_inverted_index,authorships,doi,publication_date,publication_year,primary_location,open_access,keywords,concepts,cited_by_count,mesh,language",
        "mailto": "contact@kakapo.io",
    }

    time.sleep(0.1)
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        resp = client.get(OPENALEX_API, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("results", []):
        try:
            openalex_id = item.get("id", "").replace("https://openalex.org/", "")
            title = item.get("title") or ""
            if not title:
                continue
            abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))
            authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])[:10] if a.get("author", {}).get("display_name")]
            doi = (item.get("doi") or "").replace("https://doi.org/", "") or None
            pub_date = str(item.get("publication_date") or item.get("publication_year") or "")
            source = (item.get("primary_location") or {}).get("source") or {}
            journal = source.get("display_name")
            publisher = source.get("host_organization_name")
            oa = item.get("open_access") or {}
            is_oa = oa.get("is_oa", False)
            oa_url = oa.get("oa_url")
            pdf_url = (item.get("primary_location") or {}).get("pdf_url")
            keywords = [k.get("display_name", "") for k in item.get("keywords", [])[:20] if isinstance(k, dict)]
            concepts = [c.get("display_name", "") for c in item.get("concepts", [])[:15] if isinstance(c, dict) and c.get("score", 0) > 0.3]
            mesh_terms = [m.get("descriptor_name", "") for m in item.get("mesh", [])[:20] if isinstance(m, dict)]
            citations_count = item.get("cited_by_count", 0)
            language = item.get("language")
            results.append(OpenAlexResult(
                openalex_id=openalex_id,
                title=title[:512],
                abstract=abstract[:5000] if abstract else None,
                authors=authors,
                doi=doi,
                published=pub_date or None,
                journal=journal,
                publisher=publisher,
                is_open_access=is_oa,
                oa_url=oa_url,
                pdf_url=pdf_url,
                keywords=[k for k in keywords if k],
                concepts=[c for c in concepts if c],
                citations_count=citations_count or 0,
                mesh_terms=[m for m in mesh_terms if m],
                language=language,
            ))
        except Exception as e:
            logger.warning(f"Failed to parse OpenAlex item: {e}")

    next_cursor = data.get("meta", {}).get("next_cursor", "*")
    return results, next_cursor
