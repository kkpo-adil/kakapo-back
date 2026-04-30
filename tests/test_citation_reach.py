import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"

from unittest.mock import patch, MagicMock
from app.services.citation_reach import fetch_citation_count


def mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def test_fetch_citation_count_normal():
    citations = [{"citing": "doi:a"}, {"citing": "doi:b"}, {"citing": "doi:c"}]
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response(citations)
        assert fetch_citation_count("10.1234/test") == 3


def test_fetch_citation_count_empty_doi():
    assert fetch_citation_count("") == 0
    assert fetch_citation_count(None) == 0


def test_fetch_citation_count_404():
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response({}, status_code=404)
        assert fetch_citation_count("10.9999/notfound") == 0


def test_fetch_citation_count_timeout():
    import httpx
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.side_effect = httpx.TimeoutException("timeout")
        assert fetch_citation_count("10.1234/test") == 0
