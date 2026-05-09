import time
import logging
import hashlib
import httpx
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
ARXIV_PDF_BASE = "https://arxiv.org/pdf"
USER_AGENT = "KAKAPO/1.0 (mailto:contact@kakapo.io)"
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 3.0

ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


@dataclass
class ArxivResult:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    doi: Optional[str]
    published: str
    updated: str
    categories: list[str]
    pdf_url: str
    journal_ref: Optional[str] = None
    pdf_text: Optional[str] = None
    pdf_hash: Optional[str] = None


def _get(params: dict) -> str:
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(RATE_LIMIT_DELAY)
            with httpx.Client(timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(ARXIV_API_BASE, params=params)
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(f"arXiv 5xx: {response.status_code}", request=response.request, response=response)
                response.raise_for_status()
                return response.text
        except Exception as e:
            last_exc = e
            wait = 0.5 * (2 ** attempt)
            logger.warning(f"arXiv attempt {attempt+1} failed: {e} — retrying in {wait}s")
            time.sleep(wait)
    raise last_exc


def _download_pdf(arxiv_id: str) -> Optional[bytes]:
    clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
    url = f"{ARXIV_PDF_BASE}/{clean_id}"
    try:
        time.sleep(RATE_LIMIT_DELAY)
        with httpx.Client(timeout=60.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
            response = client.get(url)
            if response.status_code == 200 and response.headers.get("content-type", "").startswith("application/pdf"):
                return response.content
    except Exception as e:
        logger.warning(f"PDF download failed for {arxiv_id}: {e}")
    return None


def _parse_results(xml_text: str) -> list[ArxivResult]:
    root = ET.fromstring(xml_text)
    results = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        try:
            arxiv_id_full = entry.find("atom:id", ARXIV_NS).text.strip()
            arxiv_id = arxiv_id_full.split("/abs/")[-1]
            title = entry.find("atom:title", ARXIV_NS).text.strip().replace("\n", " ")
            abstract = entry.find("atom:summary", ARXIV_NS).text.strip().replace("\n", " ")
            published = entry.find("atom:published", ARXIV_NS).text.strip()[:10]
            updated = entry.find("atom:updated", ARXIV_NS).text.strip()[:10]
            authors = [a.find("atom:name", ARXIV_NS).text.strip() for a in entry.findall("atom:author", ARXIV_NS)]
            doi_el = entry.find("arxiv:doi", ARXIV_NS)
            doi = doi_el.text.strip() if doi_el is not None else None
            journal_el = entry.find("arxiv:journal_ref", ARXIV_NS)
            journal_ref = journal_el.text.strip() if journal_el is not None else None
            categories = [c.attrib.get("term", "") for c in entry.findall("atom:category", ARXIV_NS)]
            pdf_url = f"{ARXIV_PDF_BASE}/{arxiv_id}"
            results.append(ArxivResult(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                authors=authors,
                doi=doi,
                published=published,
                updated=updated,
                categories=categories,
                pdf_url=pdf_url,
                journal_ref=journal_ref,
            ))
        except Exception as e:
            logger.warning(f"Failed to parse arXiv entry: {e}")
    return results


def search(query: str, max_results: int = 100, start: int = 0, categories: list[str] = None) -> list[ArxivResult]:
    search_query = query
    if categories:
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        search_query = f"({query}) AND ({cat_filter})"
    params = {
        "search_query": search_query,
        "start": start,
        "max_results": min(max_results, 100),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    logger.info(f"arXiv search: query={search_query} start={start} max={max_results}")
    xml_text = _get(params)
    return _parse_results(xml_text)


def get_by_id(arxiv_id: str) -> Optional[ArxivResult]:
    params = {"id_list": arxiv_id, "max_results": 1}
    xml_text = _get(params)
    results = _parse_results(xml_text)
    return results[0] if results else None


def download_and_hash_pdf(arxiv_id: str) -> tuple[Optional[str], Optional[str]]:
    pdf_bytes = _download_pdf(arxiv_id)
    if pdf_bytes is None:
        return None, None
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text_pages = []
        for page in reader.pages[:20]:
            try:
                text_pages.append(page.extract_text() or "")
            except Exception:
                pass
        pdf_text = "\n".join(text_pages)[:50000]
        return pdf_text, pdf_hash
    except Exception as e:
        logger.warning(f"PDF text extraction failed for {arxiv_id}: {e}")
        return None, pdf_hash
