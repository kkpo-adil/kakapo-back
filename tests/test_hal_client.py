import os
os.environ["KAKAPO_API_KEY"] = "test-api-key-123"

from unittest.mock import patch, MagicMock
import httpx
import pytest
from app.services import hal_client


def mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


HAL_SAMPLE = {
    "response": {
        "docs": [
            {
                "halId_s": "hal-01234567",
                "title_s": ["Test Paper"],
                "abstract_s": ["Abstract here"],
                "authFullName_s": ["Alice Martin"],
                "doiId_s": "10.1234/test",
                "producedDate_s": "2022-01-01",
                "openAccess_bool": True,
            }
        ]
    }
}


def test_search_returns_docs():
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response(HAL_SAMPLE)
        docs = hal_client.search("test", rows=1)
        assert len(docs) == 1
        assert docs[0]["halId_s"] == "hal-01234567"


def test_search_empty_response():
    empty = {"response": {"docs": []}}
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response(empty)
        docs = hal_client.search("nothing", rows=1)
        assert docs == []


def test_get_by_hal_id_found():
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response(HAL_SAMPLE)
        doc = hal_client.get_by_hal_id("hal-01234567")
        assert doc is not None
        assert doc["halId_s"] == "hal-01234567"


def test_get_by_hal_id_not_found():
    empty = {"response": {"docs": []}}
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response(empty)
        doc = hal_client.get_by_hal_id("hal-00000000")
        assert doc is None


def test_search_retries_on_5xx():
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        err_resp = mock_response({}, status_code=503)
        instance.get.return_value = err_resp
        with pytest.raises(RuntimeError, match="unreachable"):
            hal_client.search("test")


def test_search_raises_on_4xx():
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_response({}, status_code=400)
        with pytest.raises(ValueError, match="4xx"):
            hal_client.search("test")
