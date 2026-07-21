"""Unit tests for WatsonxClient — uses mocking to avoid live API calls."""

from unittest.mock import MagicMock, patch

import pytest
from scrumagent_watsonx.client import WatsonxClient


@pytest.fixture()
def env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WATSONX_API_KEY", "test-key")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")
    monkeypatch.setenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")


@patch("scrumagent_watsonx.client.APIClient")
@patch("scrumagent_watsonx.client.Credentials")
@patch("scrumagent_watsonx.client.ModelInference")
def test_classify_returns_stripped_response(
    mock_model_cls: MagicMock,
    mock_creds_cls: MagicMock,
    mock_api_cls: MagicMock,
    env_vars: None,
) -> None:
    mock_model_cls.return_value.generate_text.return_value = "  blocking  "
    client = WatsonxClient()
    result = client.classify("Is this comment blocking?")
    assert result == "blocking"


@patch("scrumagent_watsonx.client.APIClient")
@patch("scrumagent_watsonx.client.Credentials")
@patch("scrumagent_watsonx.client.ModelInference")
def test_generate_returns_stripped_response(
    mock_model_cls: MagicMock,
    mock_creds_cls: MagicMock,
    mock_api_cls: MagicMock,
    env_vars: None,
) -> None:
    mock_model_cls.return_value.generate_text.return_value = "  Yesterday I reviewed PR #42.  "
    client = WatsonxClient()
    result = client.generate("Write a standup for Alice.")
    assert result == "Yesterday I reviewed PR #42."
