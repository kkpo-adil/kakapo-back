import time
import logging
import hashlib
import httpx
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

EPMC_API_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EPMC_FULL_TEXT_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
USER_AGENT = "KAKAPO/1.0 (mailto:contact@kakapo.io)"
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.5


@dataclass
class EPMCResult:
    pmid: Optional[str]
    pmcid: Optional[str]
    title: str
    abstract: Optional[str]
    authors: list[str]
    doi: Optional[str]
    published: Optional[str]
    journal: Optional[str]
    source: str
    is_open_access: bool
    keywords: list[str] = field(default_factory=list)
    full_text: Optional[str] = None
    full_text_hash: Optional[str] = None


def _get(url: str, params: dict) -> dict:
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
                    logger.warning("Europe PMC rate limit — sleeping 5s")
                    time.sleep(5)
                    continue
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"EPMC 5xx: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            last_exc = e
            wait = 0.5 * (2 ** attempt)
            logger.warning(f"EPMC attempt {attempt+1} failed: {e} — retrying in {wait}s")
            time.sleep(wait)
    raise last_exc


def _parse_result(item: dict) -> EPMCResult:
    authors = []
    author_list = item.get("authorList", {})
    if isinstance(author_list, dict):
        for a in author_list.get("author", []):
            name = a.get("fullName") or f"{a.get('lastName', '')} {a.get('firstName', '')}".strip()
            if name:
                authors.append(name)

    keywords = []
    kw_list = item.get("keywordList", {})
    if isinstance(kw_list, dict):
        keywords = kw_list.get("keyword", [])

    return EPMCResult(
        pmid=item.get("pmid"),
        pmcid=item.get("pmcid"),
        title=item.get("title", "").strip(),
        abstract=item.get("abstractText", "").strip() or None,
        authors=authors,
        doi=item.get("doi"),
        published=item.get("firstPublicationDate") or item.get("pubYear"),
        journal=item.get("journalTitle") or item.get("journalInfo", {}).get("journal", {}).get("title"),
        source=item.get("source", "MED"),
        is_open_access=item.get("isOpenAccess", "N") == "Y",
        keywords=keywords,
    )


def search(
    query: str,
    max_results: int = 100,
    cursor_mark: str = "*",
    filter_open_access: bool = True,
    year_from: int = 2015,
    year_to: int = 2026,
) -> tuple[list[EPMCResult], str]:
    q = query
    if filter_open_access:
        q = f"({query}) AND OPEN_ACCESS:y"
    if year_from and year_to:
        q = f"({q}) AND (FIRST_PDATE:[{year_from}-01-01 TO {year_to}-12-31])"

    params = {
        "query": q,
        "resultType": "core",
        "pageSize": min(max_results, 1000),
        "format": "json",
        "cursorMark": cursor_mark,
    }

    logger.info(f"EPMC search: query={q[:80]} cursor={cursor_mark}")
    data = _get(EPMC_API_BASE, params)
    results_raw = data.get("resultList", {}).get("result", [])
    next_cursor = data.get("nextCursorMark", "*")
    results = []
    for item in results_raw:
        try:
            results.append(_parse_result(item))
        except Exception as e:
            logger.warning(f"Failed to parse EPMC result: {e}")
    return results, next_cursor


def get_full_text(pmcid: str) -> Optional[str]:
    if not pmcid:
        return None
    url = f"{EPMC_FULL_TEXT_BASE}/{pmcid}/fullTextXML"
    try:
        time.sleep(RATE_LIMIT_DELAY)
        with httpx.Client(
            timeout=60.0,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                texts = []
                for elem in root.iter():
                    if elem.text and elem.tag not in ["xref", "ref", "label"]:
                        t = elem.text.strip()
                        if len(t) > 20:
                            texts.append(t)
                full = " ".join(texts)[:100000]
                return full if len(full) > 500 else None
    except Exception as e:
        logger.warning(f"EPMC full text failed for {pmcid}: {e}")
    return None


def get_full_text_hash(pmcid: str) -> tuple[Optional[str], Optional[str]]:
    text = get_full_text(pmcid)
    if not text:
        return None, None
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    return text, text_hash
