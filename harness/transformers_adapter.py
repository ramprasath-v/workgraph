"""Optional local Hugging Face Transformers model adapter."""

from __future__ import annotations

import json
import math
import os
from contextlib import nullcontext
from typing import Any, Callable

from .models import AgentContext, ModelAdapter, ModelOutputError, ModelResponse
from .prompting import build_model_prompt


class TransformersProviderError(RuntimeError):
    """Expected local Transformers runtime failure."""

    failure_type = "provider_error"


class TransformersDependencyError(TransformersProviderError):
    failure_type = "configuration"


class TransformersModelLoadError(TransformersProviderError):
    failure_type = "model_load"


class TransformersDeviceError(TransformersProviderError):
    failure_type = "device_unavailable"


class TransformersOutOfMemoryError(TransformersProviderError):
    failure_type = "out_of_memory"


Loader = Callable[..., Any]


class TransformersModelAdapter(ModelAdapter):
    """Generate provider-neutral structured actions with a local HF model."""

    provider = "transformers"

    def __init__(
        self,
        model_name: str,
        *,
        tokenizer: Any | None = None,
        model: Any | None = None,
        tokenizer_loader: Loader | None = None,
        model_loader: Loader | None = None,
        torch_module: Any | None = None,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ):
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Transformers model name must be non-empty")
        self.name = model_name
        self._tokenizer = tokenizer
        self._model = model
        self._tokenizer_loader = tokenizer_loader
        self._model_loader = model_loader
        self._torch = torch_module
        self.max_new_tokens = self._parse_max_new_tokens(
            max_new_tokens
            if max_new_tokens is not None
            else os.environ.get("TRANSFORMERS_MAX_NEW_TOKENS", "512")
        )
        self.temperature = self._parse_temperature(
            temperature
            if temperature is not None
            else os.environ.get("TRANSFORMERS_TEMPERATURE", "0")
        )

    def generate_action(self, context: AgentContext) -> ModelResponse:
        self._ensure_loaded()
        prompt = build_model_prompt(context)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a coding agent. Return exactly one JSON tool "
                    "action and no prose."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        try:
            rendered = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self._tokenizer(rendered, return_tensors="pt")
            input_ids = inputs["input_ids"]
            input_tokens = self._token_length(input_ids)
            device = getattr(self._model, "device", None)
            if device is not None and hasattr(inputs, "to"):
                inputs = inputs.to(device)
            generation_options: dict[str, Any] = {
                "max_new_tokens": self.max_new_tokens,
                "do_sample": self.temperature > 0,
            }
            if self.temperature > 0:
                generation_options["temperature"] = self.temperature
            no_grad = (
                self._torch.no_grad()
                if self._torch is not None and hasattr(self._torch, "no_grad")
                else nullcontext()
            )
            with no_grad:
                generated = self._model.generate(
                    **inputs, **generation_options
                )
            sequences = getattr(generated, "sequences", generated)
            sequence = sequences[0]
            continuation = sequence[input_tokens:]
            output_tokens = self._token_length(continuation)
            output_text = self._tokenizer.decode(
                continuation, skip_special_tokens=True
            )
        except TransformersProviderError:
            raise
        except Exception as exc:
            raise self._runtime_error(exc, phase="generation") from exc

        action = self._first_json_action(output_text)
        return ModelResponse(
            action=action,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=0.0,
        )

    def _ensure_loaded(self) -> None:
        if self._tokenizer is not None and self._model is not None:
            return
        try:
            if self._tokenizer_loader is None or self._model_loader is None:
                try:
                    import torch
                    from transformers import AutoModelForCausalLM, AutoTokenizer
                except ImportError as exc:
                    raise TransformersDependencyError(
                        "The transformers provider requires optional packages: "
                        "pip install -r requirements-transformers.txt"
                    ) from exc
                self._torch = self._torch or torch
                self._tokenizer_loader = AutoTokenizer.from_pretrained
                self._model_loader = AutoModelForCausalLM.from_pretrained

            if self._tokenizer is None:
                self._tokenizer = self._tokenizer_loader(self.name)
            if self._model is None:
                options: dict[str, Any] = {"device_map": "auto"}
                dtype = self._inference_dtype()
                if dtype is not None:
                    options["torch_dtype"] = dtype
                self._model = self._model_loader(self.name, **options)
                if hasattr(self._model, "eval"):
                    self._model.eval()
        except TransformersProviderError:
            raise
        except Exception as exc:
            raise self._runtime_error(exc, phase="loading") from exc

    def _inference_dtype(self) -> Any | None:
        torch = self._torch
        if torch is None:
            return None
        cuda = getattr(torch, "cuda", None)
        if cuda is not None and cuda.is_available():
            if hasattr(cuda, "is_bf16_supported") and cuda.is_bf16_supported():
                return torch.bfloat16
            return torch.float16
        return getattr(torch, "float32", None)

    def _runtime_error(self, exc: Exception, *, phase: str) -> TransformersProviderError:
        message = str(exc).lower()
        if "out of memory" in message or "cuda oom" in message:
            return TransformersOutOfMemoryError(
                f"Transformers model '{self.name}' ran out of device memory "
                f"during {phase}."
            )
        if "no compatible device" in message or "no available device" in message:
            return TransformersDeviceError(
                f"No compatible inference device is available for Transformers "
                f"model '{self.name}'."
            )
        if phase == "loading":
            return TransformersModelLoadError(
                f"Unable to load Transformers model '{self.name}'. Check model "
                "access, local cache/network availability, and runtime memory."
            )
        return TransformersProviderError(
            f"Transformers model '{self.name}' failed during local generation."
        )

    @staticmethod
    def _first_json_action(text: object) -> dict[str, Any]:
        if not isinstance(text, str):
            raise ModelOutputError("Transformers response was not text")
        decoder = json.JSONDecoder()
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and isinstance(
                candidate.get("action"), str
            ):
                return {
                    key: value
                    for key, value in candidate.items()
                    if value is not None
                }
        raise ModelOutputError(
            "Transformers response contained no valid JSON action object"
        )

    @staticmethod
    def _token_length(tokens: Any) -> int:
        shape = getattr(tokens, "shape", None)
        if shape is not None and len(shape):
            return int(shape[-1])
        try:
            if tokens and isinstance(tokens[0], (list, tuple)):
                return len(tokens[0])
            return len(tokens)
        except (TypeError, IndexError) as exc:
            raise TransformersProviderError(
                "Transformers tokenizer returned invalid token data."
            ) from exc

    @staticmethod
    def _parse_max_new_tokens(value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "TRANSFORMERS_MAX_NEW_TOKENS must be a positive integer"
            ) from exc
        if parsed < 1:
            raise ValueError(
                "TRANSFORMERS_MAX_NEW_TOKENS must be a positive integer"
            )
        return parsed

    @staticmethod
    def _parse_temperature(value: object) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "TRANSFORMERS_TEMPERATURE must be a non-negative number"
            ) from exc
        if not math.isfinite(parsed) or parsed < 0:
            raise ValueError(
                "TRANSFORMERS_TEMPERATURE must be a non-negative number"
            )
        return parsed
