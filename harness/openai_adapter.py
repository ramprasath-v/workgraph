"""OpenAI Responses API adapter with injectable transport for offline tests."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

from .models import (
    AgentContext,
    ModelAdapter,
    ModelOutputError,
    ModelPricing,
    ModelResponse,
)
from .prompting import ACTION_SCHEMA, build_model_prompt, format_prior_experience


Transport = Callable[[dict[str, Any]], dict[str, Any]]


class OpenAIModelAdapter(ModelAdapter):
    """Generate validated one-step actions through the OpenAI Responses API."""

    provider = "openai"

    def __init__(
        self,
        model_name: str,
        *,
        api_key: str | None = None,
        transport: Transport | None = None,
        pricing: ModelPricing | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 60,
    ):
        self.name = model_name
        self.pricing = pricing
        if transport is not None:
            self._transport = transport
            return
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for an OpenAI model run; "
                "set it in the environment or use --model mock"
            )
        endpoint = (
            base_url
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self._transport = self._http_transport(
            endpoint + "/responses", api_key, timeout_seconds
        )

    @staticmethod
    def _http_transport(url: str, api_key: str, timeout: int) -> Transport:
        def send(payload: dict[str, Any]) -> dict[str, Any]:
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    body = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                raise RuntimeError(
                    f"OpenAI API request failed with HTTP {exc.code}"
                ) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"OpenAI API request failed: {exc.reason}") from exc
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as exc:
                raise RuntimeError("OpenAI API returned invalid JSON") from exc
            if not isinstance(parsed, dict):
                raise RuntimeError("OpenAI API returned an invalid response object")
            return parsed

        return send

    def generate_action(self, context: AgentContext) -> ModelResponse:
        payload = {
            "model": self.name,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a coding agent operating through a restricted tool "
                        "harness. Choose exactly one safe action per response."
                    ),
                },
                {"role": "user", "content": build_model_prompt(context)},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "agent_action",
                    "strict": True,
                    "schema": ACTION_SCHEMA,
                }
            },
        }
        response = self._transport(payload)
        output_text = self._extract_output_text(response)
        try:
            action = json.loads(output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ModelOutputError("response was not valid JSON") from exc
        if not isinstance(action, dict) or not isinstance(action.get("action"), str):
            raise ModelOutputError("response was not an action object")
        action = {key: value for key, value in action.items() if value is not None}
        usage = response.get("usage", {})
        input_tokens = self._token_count(usage, "input_tokens")
        output_tokens = self._token_count(usage, "output_tokens")
        total_tokens = self._token_count(usage, "total_tokens") or None
        cost = None
        if self.pricing is not None:
            cost = (
                input_tokens * self.pricing.input_per_million_usd
                + output_tokens * self.pricing.output_per_million_usd
            ) / 1_000_000
        return ModelResponse(
            action, input_tokens, output_tokens, cost, total_tokens
        )

    @staticmethod
    def _token_count(usage: object, field: str) -> int:
        if not isinstance(usage, dict):
            return 0
        value = usage.get(field, 0)
        return value if isinstance(value, int) and value >= 0 else 0

    @staticmethod
    def _extract_output_text(response: dict[str, Any]) -> str:
        output_text = response.get("output_text")
        if isinstance(output_text, str):
            return output_text
        for item in response.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if (
                    isinstance(content, dict)
                    and content.get("type") == "output_text"
                    and isinstance(content.get("text"), str)
                ):
                    return content["text"]
        raise ModelOutputError("response contained no output text")
