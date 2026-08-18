"""Model adapter abstractions and the deterministic test adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelResponse:
    """One structured action and optional provider accounting."""

    action: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = 0.0
    total_tokens: int | None = None


@dataclass(frozen=True)
class ModelPricing:
    """Explicit USD pricing per one million tokens."""

    input_per_million_usd: float
    output_per_million_usd: float


@dataclass(frozen=True)
class AgentContext:
    """Information made available to a model adapter at each step."""

    task_id: str
    task_description: str
    available_tools: tuple[str, ...]
    history: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    prior_experience: dict[str, Any] | None = None
    current_step: int = 1
    max_steps: int = 20


class ModelOutputError(ValueError):
    """Raised when a provider returns unusable structured model output."""


class ModelAdapter(ABC):
    """Small provider-neutral boundary for producing structured actions."""

    name: str
    provider: str = "unknown"

    @abstractmethod
    def generate_action(self, context: AgentContext) -> ModelResponse:
        """Return the next action for the current agent state."""


class MockModelAdapter(ModelAdapter):
    """Deterministically solve the single fixture task without an API key."""

    name = "mock"
    provider = "mock"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        step = len(context.history)
        actions: tuple[dict[str, Any], ...] = (
            {"action": "list_files"},
            {"action": "read_file", "path": "calculator.py"},
            {"action": "run_tests"},
            {
                "action": "write_file",
                "path": "calculator.py",
                "content": (
                    '"""Tiny calculator used by the benchmark fixture."""\n\n'
                    "\n"
                    "def divide(a, b):\n"
                    "    return a / b\n"
                ),
            },
            {"action": "run_tests"},
            {"action": "finish"},
        )
        if context.task_id != "task01_exact":
            return ModelResponse({"action": "finish"})
        return ModelResponse(actions[min(step, len(actions) - 1)])
