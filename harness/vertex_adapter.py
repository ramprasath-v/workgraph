"""Google Vertex AI Gemini adapter using the current google-genai SDK."""

from __future__ import annotations

import json
import os
from typing import Any

from .models import (
    AgentContext,
    ModelAdapter,
    ModelOutputError,
    ModelPricing,
    ModelResponse,
)
from .prompting import ACTION_SCHEMA, build_model_prompt


class VertexGeminiAdapter(ModelAdapter):
    """Generate one structured action through Gemini on Vertex AI."""

    provider = "vertex"

    def __init__(
        self,
        model_name: str,
        *,
        project: str | None = None,
        location: str | None = None,
        client: Any | None = None,
        pricing: ModelPricing | None = None,
    ):
        self.name = model_name
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not self.project:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT is required for Vertex AI model runs"
            )
        self.location = (
            location or os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"
        )
        self.pricing = pricing
        if client is not None:
            self._client = client
            return
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is required for Vertex AI; "
                "install dependencies from requirements.txt"
            ) from exc
        try:
            self._client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
            )
        except Exception as exc:
            raise self._provider_error(exc) from exc

    def generate_action(self, context: AgentContext) -> ModelResponse:
        try:
            response = self._client.models.generate_content(
                model=self.name,
                contents=build_model_prompt(context),
                config={
                    "system_instruction": (
                        "You are a coding agent operating through a restricted "
                        "tool harness. Choose exactly one safe action per response."
                    ),
                    "response_mime_type": "application/json",
                    "response_json_schema": ACTION_SCHEMA,
                    "temperature": 0,
                },
            )
        except Exception as exc:
            raise self._provider_error(exc) from exc

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, dict):
            action = parsed
        else:
            text = getattr(response, "text", None)
            if not isinstance(text, str):
                raise ModelOutputError("Gemini response contained no JSON text")
            try:
                action = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ModelOutputError(
                    "Gemini response was not valid structured JSON"
                ) from exc
        if not isinstance(action, dict) or not isinstance(action.get("action"), str):
            raise ModelOutputError("Gemini response was not an action object")
        action = {key: value for key, value in action.items() if value is not None}

        usage = getattr(response, "usage_metadata", None)
        input_tokens = self._usage_count(usage, "prompt_token_count")
        output_tokens = self._usage_count(usage, "candidates_token_count")
        total_tokens = self._usage_count(usage, "total_token_count") or None
        cost = None
        if self.pricing is not None:
            cost = (
                input_tokens * self.pricing.input_per_million_usd
                + output_tokens * self.pricing.output_per_million_usd
            ) / 1_000_000
        return ModelResponse(
            action,
            input_tokens,
            output_tokens,
            cost,
            total_tokens,
        )

    @staticmethod
    def _usage_count(usage: object, field: str) -> int:
        if isinstance(usage, dict):
            value = usage.get(field, 0)
        else:
            value = getattr(usage, field, 0)
        return value if isinstance(value, int) and value >= 0 else 0

    def _provider_error(self, exc: Exception) -> RuntimeError:
        signature = f"{type(exc).__name__} {exc}".lower()
        if any(term in signature for term in ("quota", "resource_exhausted", "429")):
            message = "Vertex AI quota exceeded"
        elif any(
            term in signature for term in ("permission", "permission_denied", "403")
        ):
            message = (
                "Vertex AI permission denied; verify the project and "
                "roles/aiplatform.user access"
            )
        elif any(
            term in signature
            for term in (
                "defaultcredentials",
                "default credentials",
                "unauthenticated",
                "authentication",
                "401",
            )
        ):
            message = (
                "Vertex AI authentication failed; configure Application Default "
                "Credentials with 'gcloud auth application-default login'"
            )
        elif any(term in signature for term in ("not found", "not_found", "404")):
            message = f"Vertex AI model unavailable: {self.name}"
        else:
            message = "Vertex AI request failed; check configuration and service status"
        return RuntimeError(message)
