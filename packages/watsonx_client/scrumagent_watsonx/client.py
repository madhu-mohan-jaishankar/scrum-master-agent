"""WatsonX AI inference client.

Wraps ibm-watsonx-ai for two usage patterns:
- classify(prompt) → one of a small label set (fast, small model)
- generate(prompt) → free-form prose (larger model call)

Configuration is loaded from environment variables; no secrets in code.
"""

from __future__ import annotations

import os
from typing import Any

from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams


class WatsonxClient:
    """Synchronous (thread-safe) wrapper for WatsonX foundation model calls.

    Instantiate once at process start and reuse across all requests.
    """

    def __init__(self) -> None:
        api_key = os.environ["WATSONX_API_KEY"]
        project_id = os.environ["WATSONX_PROJECT_ID"]
        url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

        credentials = Credentials(url=url, api_key=api_key)
        self._client = APIClient(credentials)
        self._project_id = project_id

        self._classify_model_id = os.environ.get(
            "WATSONX_MODEL_ID_CLASSIFY", "ibm/granite-3-3-8b-instruct"
        )
        self._generate_model_id = os.environ.get(
            "WATSONX_MODEL_ID_GENERATE", "ibm/granite-3-3-8b-instruct"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def classify(self, prompt: str, max_tokens: int = 50) -> str:
        """Run a low-latency classification call.

        Args:
            prompt: Fully assembled prompt string (system + user content).
            max_tokens: Token budget for the label response.

        Returns:
            The model's text response, stripped.
        """
        model = ModelInference(
            model_id=self._classify_model_id,
            api_client=self._client,
            project_id=self._project_id,
        )
        params: dict[str, Any] = {
            GenParams.MAX_NEW_TOKENS: max_tokens,
            GenParams.TEMPERATURE: 0.0,
        }
        response = model.generate_text(prompt=prompt, params=params)
        return str(response).strip()

    def generate(self, prompt: str, max_tokens: int = 800) -> str:
        """Run a prose-generation call.

        Args:
            prompt: Fully assembled prompt string.
            max_tokens: Token budget for the generated response.

        Returns:
            The model's text response, stripped.
        """
        model = ModelInference(
            model_id=self._generate_model_id,
            api_client=self._client,
            project_id=self._project_id,
        )
        params: dict[str, Any] = {
            GenParams.MAX_NEW_TOKENS: max_tokens,
            GenParams.TEMPERATURE: 0.3,
        }
        response = model.generate_text(prompt=prompt, params=params)
        return str(response).strip()
