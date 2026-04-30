import logging
import httpx

logger = logging.getLogger(__name__)

OPENCITATIONS_BASE = "https://opencitations.net/index/coci/api/v2/citations/"
TIMEOUT = 15.0
MAX_RETRIES = 2


def fetch_citation_count(doi: str) -> int:
    if not doi or not doi.strip():
        return 0
    url = f"{OPENCITATIONS_BASE}{doi.strip()}"
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                response = client.get(url)
                if response.status_code == 404:
                    return 0
                if response.status_code >= 400:
                    logger.warning(f"OpenCitations {response.status_code} for DOI {doi}")
                    return 0
                data = response.json()
                count = len(data) if isinstance(data, list) else 0
                logger.debug(f"OpenCitations DOI={doi} citations={count}")
                return count
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            last_exc = exc
            logger.warning(f"OpenCitations timeout/error for DOI {doi} attempt {attempt + 1}: {exc}")
    logger.error(f"OpenCitations failed for DOI {doi} after {MAX_RETRIES} attempts: {last_exc}")
    return 0
