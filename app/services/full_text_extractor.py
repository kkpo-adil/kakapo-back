import logging
import hashlib
import time
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

USER_AGENT = "KAKAPO/1.0 (mailto:contact@kakapo.io)"
TIMEOUT = 30.0


def _get_html(url: str) -> Optional[str]:
    try:
        time.sleep(0.5)
        with httpx.Client(
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.warning(f"HTML fetch failed for {url}: {e}")
    return None


def _extract_text_from_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "iframe", "noscript", "figure"]):
            tag.decompose()
        article = (
            soup.find("article") or
            soup.find("div", class_=lambda x: x and "article" in x.lower()) or
            soup.find("div", id=lambda x: x and "article" in x.lower()) or
            soup.find("main") or
            soup.body
        )
        if article:
            paragraphs = []
            for p in article.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
                text = p.get_text(separator=" ").strip()
                if len(text) > 30:
                    paragraphs.append(text)
            return " ".join(paragraphs)[:100000]
    except Exception as e:
        logger.warning(f"HTML extraction failed: {e}")
    return ""


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages[:50]:
            try:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text.strip())
            except Exception:
                pass
        return " ".join(pages)[:100000]
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
    return ""


def _get_pdf_bytes(pdf_url: str) -> Optional[bytes]:
    try:
        time.sleep(0.5)
        with httpx.Client(
            timeout=60.0,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = client.get(pdf_url)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                if "pdf" in ct or pdf_url.endswith(".pdf"):
                    return resp.content
    except Exception as e:
        logger.warning(f"PDF download failed for {pdf_url}: {e}")
    return None


def _get_unpaywall_pdf_url(doi: str) -> Optional[str]:
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email=contact@kakapo.io"
        with httpx.Client(timeout=10.0, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                best_oa = data.get("best_oa_location")
                if best_oa:
                    return best_oa.get("url_for_pdf") or best_oa.get("url")
    except Exception as e:
        logger.warning(f"Unpaywall failed for {doi}: {e}")
    return None


def _get_pmc_full_text(pmcid: str) -> str:
    try:
        clean = pmcid.replace("PMC", "")
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/PMC{clean}/fullTextXML"
        html = _get_html(url)
        if html and "<article" in html:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(html)
            texts = []
            for elem in root.iter():
                if elem.tag in ["p", "title", "sec", "abstract"]:
                    text = "".join(elem.itertext()).strip()
                    if len(text) > 20:
                        texts.append(text)
            result = " ".join(texts)[:100000]
            if len(result) > 500:
                return result
    except Exception as e:
        logger.warning(f"PMC full text failed for {pmcid}: {e}")
    return ""


def _get_plos_full_text(doi: str) -> str:
    try:
        url = f"https://journals.plos.org/plosone/article/file?id={doi}&type=manuscript"
        pdf_bytes = _get_pdf_bytes(url)
        if pdf_bytes:
            return _extract_text_from_pdf(pdf_bytes)
    except Exception as e:
        logger.warning(f"PLOS failed for {doi}: {e}")
    return ""


def _get_cureus_full_text(doi: str) -> str:
    try:
        article_id = doi.split("/")[-1] if "/" in doi else doi
        url = f"https://www.cureus.com/articles/{article_id}"
        html = _get_html(url)
        if html:
            return _extract_text_from_html(html)
    except Exception as e:
        logger.warning(f"Cureus failed for {doi}: {e}")
    return ""


def _get_frontiers_full_text(doi: str) -> str:
    try:
        url = f"https://www.frontiersin.org/articles/{doi}/full"
        html = _get_html(url)
        if html:
            return _extract_text_from_html(html)
    except Exception as e:
        logger.warning(f"Frontiers failed for {doi}: {e}")
    return ""


def extract_full_text(
    doi: Optional[str] = None,
    pmcid: Optional[str] = None,
    article_url: Optional[str] = None,
    source_origin: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """
    Extract full text from all available sources.
    Returns (full_text, sha256_hash) or ("", None)
    """
    text = ""

    if pmcid:
        text = _get_pmc_full_text(pmcid)
        if text and len(text) > 500:
            logger.info(f"PMC full text: {len(text)} chars for {pmcid}")

    if not text and doi:
        if "cureus.com" in (article_url or "") or "10.7759" in (doi or ""):
            text = _get_cureus_full_text(doi)
            if text:
                logger.info(f"Cureus full text: {len(text)} chars for {doi}")

        if not text and "frontiersin.org" in (article_url or "") or "10.3389" in (doi or ""):
            text = _get_frontiers_full_text(doi)
            if text:
                logger.info(f"Frontiers full text: {len(text)} chars for {doi}")

        if not text and "plos" in (article_url or "").lower():
            text = _get_plos_full_text(doi)
            if text:
                logger.info(f"PLOS full text: {len(text)} chars for {doi}")

        if not text:
            pdf_url = _get_unpaywall_pdf_url(doi)
            if pdf_url:
                if pdf_url.endswith(".pdf") or "pdf" in pdf_url.lower():
                    pdf_bytes = _get_pdf_bytes(pdf_url)
                    if pdf_bytes:
                        text = _extract_text_from_pdf(pdf_bytes)
                        if text:
                            logger.info(f"PDF full text: {len(text)} chars for {doi}")
                else:
                    html = _get_html(pdf_url)
                    if html:
                        text = _extract_text_from_html(html)
                        if text:
                            logger.info(f"HTML full text: {len(text)} chars for {doi}")

    if not text and article_url:
        html = _get_html(article_url)
        if html:
            text = _extract_text_from_html(html)

    if text and len(text) > 200:
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return text, text_hash

    return "", None
