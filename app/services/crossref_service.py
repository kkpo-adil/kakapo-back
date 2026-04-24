import httpx
from typing import Any


CROSSREF_API = "https://api.crossref.org/works"


async def fetch_doi_metadata(doi: str) -> dict[str, Any] | None:
    url = f"{CROSSREF_API}/{doi}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers={"User-Agent": "KAKAPO/1.0 (mailto:contact@kakapo.io)"})
            if r.status_code != 200:
                return None
            data = r.json()
            work = data.get("message", {})
            title = work.get("title", [""])[0]
            abstract = work.get("abstract", "")
            authors = [
                {"name": f"{a.get('given', '')} {a.get('family', '')}".strip()}
                for a in work.get("author", [])
            ]
            published = work.get("published", {}).get("date-parts", [[None]])[0]
            pub_date = None
            if published and published[0]:
                parts = published + [1, 1]
                pub_date = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
            journal = ""
            container = work.get("container-title", [])
            if container:
                journal = container[0]
            institution = ""
            affiliations = work.get("author", [{}])[0].get("affiliation", [])
            if affiliations:
                institution = affiliations[0].get("name", "")
            return {
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "institution": institution,
                "published_at": pub_date,
                "doi": doi,
            }
    except Exception:
        return None
