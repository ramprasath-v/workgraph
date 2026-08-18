"""Local Ollama chat adapter using native structured JSON output."""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .models import AgentContext, ModelAdapter, ModelOutputError, ModelResponse
from .prompting import ACTION_SCHEMA, build_model_prompt


Transport = Callable[[dict[str, Any]], dict[str, Any]]


class OllamaProviderError(RuntimeError):
    """Expected Ollama runtime failure safe to record as a run outcome."""

    failure_type = "provider_error"


class OllamaUnavailableError(OllamaProviderError):
    """Raised when the configured local Ollama endpoint cannot be reached."""

    failure_type = "unavailable"


class OllamaTimeoutError(OllamaProviderError):
    """Raised when a local model exceeds the configured response timeout."""

    failure_type = "timeout"


class OllamaModelUnavailableError(OllamaProviderError):
    """Raised when the requested model is not installed locally."""

    failure_type = "model_unavailable"


@dataclass(frozen=True)
class OllamaDiagnosticResult:
    success: bool
    elapsed_seconds: float
    input_tokens: int
    output_tokens: int
    request_body_bytes: int
    structured_schema: bool
    failure_type: str | None = None
    failure_message: str | None = None


class OllamaModelAdapter(ModelAdapter):
    """Generate one structured action through Ollama's local HTTP API."""

    provider = "ollama"

    def __init__(
        self,
        model_name: str,
        *,
        base_url: str | None = None,
        transport: Transport | None = None,
        timeout_seconds: float | None = None,
    ):
        if not re.fullmatch(r"[A-Za-z0-9._:/-]+", model_name):
            raise ValueError("Ollama model name contains unsupported characters")
        self.name = model_name
        self.base_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        ).rstrip("/")
        configured_timeout: object = (
            timeout_seconds
            if timeout_seconds is not None
            else os.environ.get("OLLAMA_TIMEOUT_SECONDS", "180")
        )
        self.timeout_seconds = self._parse_timeout(configured_timeout)
        self.debug = os.environ.get("OLLAMA_DEBUG") == "1"
        self.debug_prompt = self.debug and os.environ.get("OLLAMA_DEBUG_PROMPT") == "1"
        self._transport = transport or self._http_transport(
            self.base_url + "/api/chat", self.timeout_seconds
        )

    def generate_action(self, context: AgentContext) -> ModelResponse:
        prompt_started = time.perf_counter()
        prompt = build_model_prompt(context)
        prompt_finished = time.perf_counter()
        self._debug_phase("prompt_rendering", prompt_started, prompt_finished)
        payload = self._agent_payload(prompt)
        serialization_started = time.perf_counter()
        serialized = self._serialize_payload(payload)
        serialization_finished = time.perf_counter()
        self._debug_phase(
            "json_serialization", serialization_started, serialization_finished
        )
        self._debug_request(payload, serialized, context)
        transport_started = time.perf_counter()
        response = self._transport(payload)
        transport_finished = time.perf_counter()
        self._debug_phase("http_round_trip", transport_started, transport_finished)
        if not isinstance(response, dict):
            raise ModelOutputError("Ollama response was not a JSON object")
        error = response.get("error")
        if isinstance(error, str):
            if "not found" in error.lower():
                raise OllamaModelUnavailableError(
                    f"Ollama model '{self.name}' is unavailable; "
                    f"run: ollama pull {self.name}"
                )
            raise OllamaProviderError(
                "Ollama returned an error while generating an action"
            )
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ModelOutputError("Ollama response contained no message content")
        parsing_started = time.perf_counter()
        try:
            action = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ModelOutputError(
                "Ollama response was not valid structured JSON"
            ) from exc
        if not isinstance(action, dict) or not isinstance(action.get("action"), str):
            raise ModelOutputError("Ollama response was not an action object")
        action = {key: value for key, value in action.items() if value is not None}
        self._debug_phase(
            "structured_output_parsing", parsing_started, time.perf_counter()
        )
        input_tokens = self._token_count(response, "prompt_eval_count")
        output_tokens = self._token_count(response, "eval_count")
        return ModelResponse(
            action=action,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=0.0,
            total_tokens=input_tokens + output_tokens,
        )

    def diagnose_request(
        self,
        prompt: str,
        *,
        structured_schema: bool,
        agent_style: bool = False,
    ) -> OllamaDiagnosticResult:
        """Send one non-mutating diagnostic chat request."""

        if agent_style:
            payload = self._agent_payload(prompt)
        else:
            payload = {
                "model": self.name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0},
            }
            if structured_schema:
                payload["format"] = ACTION_SCHEMA
        serialization_started = time.perf_counter()
        serialized = self._serialize_payload(payload)
        self._debug_phase(
            "json_serialization", serialization_started, time.perf_counter()
        )
        self._debug_request(payload, serialized, None)
        started = time.perf_counter()
        try:
            response = self._transport(payload)
            self._debug_phase("http_round_trip", started, time.perf_counter())
            if not isinstance(response, dict):
                raise ModelOutputError("Ollama response was not a JSON object")
            error = response.get("error")
            if isinstance(error, str):
                if "not found" in error.lower():
                    raise OllamaModelUnavailableError(
                        f"Ollama model '{self.name}' is unavailable; "
                        f"run: ollama pull {self.name}"
                    )
                raise OllamaProviderError(
                    "Ollama returned an error during diagnostics"
                )
            message = response.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str):
                raise ModelOutputError(
                    "Ollama response contained no message content"
                )
            if structured_schema:
                parsing_started = time.perf_counter()
                parsed = json.loads(content)
                if not isinstance(parsed, dict) or not isinstance(
                    parsed.get("action"), str
                ):
                    raise ModelOutputError(
                        "Ollama diagnostic response was not an action object"
                    )
                self._debug_phase(
                    "structured_output_parsing",
                    parsing_started,
                    time.perf_counter(),
                )
        except json.JSONDecodeError as exc:
            failure: Exception = ModelOutputError(
                "Ollama diagnostic response was not valid structured JSON"
            )
            failure.__cause__ = exc
        except (OllamaProviderError, ModelOutputError) as exc:
            failure = exc
        else:
            return OllamaDiagnosticResult(
                success=True,
                elapsed_seconds=round(time.perf_counter() - started, 6),
                input_tokens=self._token_count(response, "prompt_eval_count"),
                output_tokens=self._token_count(response, "eval_count"),
                request_body_bytes=len(serialized),
                structured_schema=structured_schema,
            )
        return OllamaDiagnosticResult(
            success=False,
            elapsed_seconds=round(time.perf_counter() - started, 6),
            input_tokens=0,
            output_tokens=0,
            request_body_bytes=len(serialized),
            structured_schema=structured_schema,
            failure_type=getattr(failure, "failure_type", "model_output"),
            failure_message=str(failure),
        )

    def _http_transport(self, url: str, timeout: float) -> Transport:
        def send(payload: dict[str, Any]) -> dict[str, Any]:
            request = urllib.request.Request(
                url,
                data=self._serialize_payload(payload),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            request_started = time.perf_counter()
            self._debug_event("http_request_start", request_started)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    headers_received = time.perf_counter()
                    self._debug_phase(
                        "http_headers", request_started, headers_received
                    )
                    body_started = time.perf_counter()
                    body = response.read().decode("utf-8")
                    self._debug_phase(
                        "response_body_read", body_started, time.perf_counter()
                    )
            except TimeoutError as exc:
                raise self._timeout_error() from exc
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise OllamaModelUnavailableError(
                        f"Ollama model '{self.name}' is unavailable; "
                        f"run: ollama pull {self.name}"
                    ) from exc
                raise OllamaProviderError(
                    f"Ollama request failed with HTTP {exc.code}"
                ) from exc
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, TimeoutError):
                    raise self._timeout_error() from exc
                raise OllamaUnavailableError(
                    f"Ollama is unavailable at {self.base_url}; start Ollama "
                    "or set OLLAMA_BASE_URL"
                ) from exc
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as exc:
                raise ModelOutputError("Ollama returned invalid response JSON") from exc
            if not isinstance(parsed, dict):
                raise ModelOutputError("Ollama response was not a JSON object")
            return parsed

        return send

    def _agent_payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a coding agent operating through a restricted "
                        "tool harness. Choose exactly one safe action."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": ACTION_SCHEMA,
            "options": {"temperature": 0},
        }

    @staticmethod
    def _serialize_payload(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload).encode("utf-8")

    def _debug_request(
        self,
        payload: dict[str, Any],
        serialized: bytes,
        context: AgentContext | None,
    ) -> None:
        if not self.debug:
            return
        messages = payload.get("messages", [])
        message_characters = [
            len(message.get("content", ""))
            for message in messages
            if isinstance(message, dict)
        ]
        schema = payload.get("format")
        schema_characters = (
            len(json.dumps(schema)) if schema is not None else 0
        )
        metadata = {
            "model": self.name,
            "endpoint": self.base_url + "/api/chat",
            "timeout_seconds": self.timeout_seconds,
            "message_count": len(messages),
            "message_character_counts": message_characters,
            "total_prompt_characters": sum(message_characters),
            "schema_characters": schema_characters,
            "format_sent": schema is not None,
            "streaming": payload.get("stream", True),
            "request_body_bytes": len(serialized),
            "agent_step": context.current_step if context else None,
            "history_entries": len(context.history) if context else 0,
        }
        print(
            "[ollama-debug] request " + json.dumps(metadata, sort_keys=True),
            file=sys.stderr,
        )
        if self.debug_prompt:
            prompt = messages[-1].get("content", "") if messages else ""
            print("[ollama-debug] prompt-begin", file=sys.stderr)
            print(prompt, file=sys.stderr)
            print("[ollama-debug] prompt-end", file=sys.stderr)

    def _debug_phase(self, phase: str, started: float, finished: float) -> None:
        if not self.debug:
            return
        print(
            f"[ollama-debug] phase={phase} start={started:.6f} "
            f"end={finished:.6f} elapsed_seconds={finished - started:.6f}",
            file=sys.stderr,
        )

    def _debug_event(self, event: str, timestamp: float) -> None:
        if self.debug:
            print(
                f"[ollama-debug] event={event} timestamp={timestamp:.6f}",
                file=sys.stderr,
            )

    @staticmethod
    def _parse_timeout(raw_value: object) -> float:
        try:
            timeout = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "OLLAMA_TIMEOUT_SECONDS must be a positive number"
            ) from exc
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be a positive number")
        return timeout

    def _timeout_error(self) -> OllamaTimeoutError:
        timeout = f"{self.timeout_seconds:g}"
        return OllamaTimeoutError(
            f"Ollama model '{self.name}' did not respond within the configured "
            f"timeout of {timeout} seconds; increase OLLAMA_TIMEOUT_SECONDS"
        )

    @staticmethod
    def _token_count(response: dict[str, Any], field: str) -> int:
        value = response.get(field, 0)
        return value if isinstance(value, int) and value >= 0 else 0
