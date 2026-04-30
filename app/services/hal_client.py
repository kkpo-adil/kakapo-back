import time
import logging
import httpx

logger = logging.getLogger(__name__)

HAL_API_BASE = "https://api.archives-ouvertes.fr/search/"
HAL_FIELDS = ",".join([
    "docid", "halId_s", "title_s", "abstract_s",
    "authFullName_s", "authIdHal_s", "authORCIDIdExt_s",
    "doiId_s", "producedDate_s", "submittedDate_s",
    "journalTitle_s", "publisher_s", "docType_s",
    "language_s", "keyword_s", "domain_s", "openAccess_bool",
])
USER_AGENT = "KAKAPO/1.0 (mailto:contact@kakapo.io)"
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.2


def _get(params: dict) -> dict:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(RATE_LIMIT_DELAY)
            with httpx.Client(timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(HAL_API_BASE, params=params)
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(f"HAL 5xx: {response.status_code}", request=response.request, response=response)
                if response.status_code >= 400:
                    raise ValueError(f"HAL 4xx: {response.status_code} — {response.text[:200]}")
                return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning(f"HAL request failed (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {wait}s: {exc}")
            time.sleep(wait)
    raise RuntimeError(f"HAL API unreachable after {MAX_RETRIES} attempts") from last_exc


def search(query: str, rows: int = 100, start: int = 0) -> list[dict]:
    params = {"q": query, "fl": HAL_FIELDS, "rows": rows, "start": start, "wt": "json"}
    data = _get(params)
    docs = data.get("response", {}).get("docs", [])
    logger.info(f"HAL search query={query!r} rows={rows} start={start} → {len(docs)} results")
    return docs


def search_by_domain(domain: str, year_from: int, year_to: int, rows: int = 100, start: int = 0) -> list[dict]:
    query = f"domain_s:{domain} AND producedDate_s:[{year_from}-01-01T00:00:00Z TO {year_to}-12-31T23:59:59Z]"
    return search(query=query, rows=rows, start=start)


def get_by_hal_id(hal_id: str) -> dict | None:
    params = {"q": f"halId_s:{hal_id}", "fl": HAL_FIELDS, "rows": 1, "wt": "json"}
    data = _get(params)
    docs = data.get("response", {}).get("docs", [])
    return docs[0] if docs else None
