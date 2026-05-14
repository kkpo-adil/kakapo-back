import time
import logging
import hashlib
import httpx
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

NCBI_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
USER_AGENT = "KAKAPO/1.0 (mailto:contact@kakapo.io)"
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.34


@dataclass
class PMCResult:
    pmc_id: str
    pubmed_id: Optional[str]
    title: str
    abstract: Optional[str]
    authors: list[str]
    doi: Optional[str]
    published: Optional[str]
    journal: Optional[str]
    keywords: list[str] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    full_text: Optional[str] = None
    full_text_hash: Optional[str] = None


def _get(url: str, params: dict) -> str:
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(RATE_LIMIT_DELAY)
            with httpx.Client(
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = client.get(url, params=params)
                if response.status_code == 429:
                    logger.warning("NCBI rate limit — sleeping 10s")
                    time.sleep(10)
                    continue
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"NCBI 5xx: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response.text
        except Exception as e:
            last_exc = e
            wait = 1.0 * (2 ** attempt)
            logger.warning(f"NCBI attempt {attempt+1} failed: {e} — retrying in {wait}s")
            time.sleep(wait)
    raise last_exc


def search_ids(
    query: str,
    max_results: int = 100,
    start: int = 0,
    year_from: int = 2015,
    year_to: int = 2026,
) -> list[str]:
    params = {
        "db": "pmc",
        "term": f"({query}) AND ({year_from}:{year_to}[pdat]) AND open access[filter]",
        "retmax": min(max_results, 10000),
        "retstart": start,
        "retmode": "json",
        "email": "contact@kakapo.io",
    }
    text = _get(NCBI_SEARCH_URL, params)
    data = json.loads(text)
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_articles(pmc_ids: list[str]) -> list[PMCResult]:
    if not pmc_ids:
        return []
    params = {
        "db": "pmc",
        "id": ",".join(pmc_ids),
        "retmode": "xml",
        "rettype": "full",
        "email": "contact@kakapo.io",
    }
    text = _get(NCBI_FETCH_URL, params)
    return _parse_articles(text)


def _parse_articles(xml_text: str) -> list[PMCResult]:
    results = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"XML parse error: {e}")
        return []

    for article in root.findall(".//article"):
        try:
            pmc_id = ""
            pubmed_id = ""
            for article_id in article.findall(".//article-id"):
                id_type = article_id.get("pub-id-type", "")
                if id_type == "pmc":
                    pmc_id = f"PMC{article_id.text}"
                elif id_type == "pmid":
                    pubmed_id = article_id.text
                elif id_type == "doi" and not pmc_id:
                    pass

            doi = None
            for article_id in article.findall(".//article-id"):
                if article_id.get("pub-id-type") == "doi":
                    doi = article_id.text

            title_el = article.find(".//article-title")
            title = "".join(title_el.itertext()).strip() if title_el is not None else ""
            if not title:
                continue

            abstract_parts = []
            for ab in article.findall(".//abstract"):
                for p in ab.findall(".//p"):
                    abstract_parts.append("".join(p.itertext()).strip())
            abstract = " ".join(abstract_parts)[:5000] if abstract_parts else None

            authors = []
            for contrib in article.findall(".//contrib[@contrib-type='author']"):
                surname = contrib.find(".//surname")
                given = contrib.find(".//given-names")
                if surname is not None:
                    name = surname.text or ""
                    if given is not None and given.text:
                        name = f"{given.text} {name}"
                    authors.append(name.strip())

            keywords = []
            for kwd in article.findall(".//kwd"):
                kw = "".join(kwd.itertext()).strip()
                if kw:
                    keywords.append(kw)

            mesh_terms = []
            for mesh in article.findall(".//subject"):
                term = "".join(mesh.itertext()).strip()
                if term:
                    mesh_terms.append(term)

            journal = ""
            journal_el = article.find(".//journal-title")
            if journal_el is not None:
                journal = "".join(journal_el.itertext()).strip()

            published = ""
            pub_date = article.find(".//pub-date[@pub-type='epub']") or \
                       article.find(".//pub-date[@pub-type='ppub']") or \
                       article.find(".//pub-date")
            if pub_date is not None:
                year_el = pub_date.find("year")
                month_el = pub_date.find("month")
                if year_el is not None:
                    published = year_el.text or ""
                    if month_el is not None and month_el.text:
                        published = f"{published}-{month_el.text.zfill(2)}-01"

            full_text_parts = []
            for body in article.findall(".//body"):
                for p in body.findall(".//p"):
                    text = "".join(p.itertext()).strip()
                    if len(text) > 20:
                        full_text_parts.append(text)
            full_text = " ".join(full_text_parts)[:10000000] if full_text_parts else None
            full_text_hash = hashlib.sha256(full_text.encode()).hexdigest() if full_text else None

            results.append(PMCResult(
                pmc_id=pmc_id or f"PMC{pubmed_id}",
                pubmed_id=pubmed_id,
                title=title[:512],
                abstract=abstract,
                authors=authors[:10],
                doi=doi,
                published=published,
                journal=journal,
                keywords=keywords,
                mesh_terms=mesh_terms,
                full_text=full_text,
                full_text_hash=full_text_hash,
            ))
        except Exception as e:
            logger.warning(f"Failed to parse PMC article: {e}")

    return results
