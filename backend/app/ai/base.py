from dataclasses import dataclass
from typing import Any, Protocol


class AIAdapterUnavailable(RuntimeError):
    def __init__(self, message: str, setup_hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.setup_hint = setup_hint


@dataclass(frozen=True)
class AdapterHealth:
    name: str
    available: bool
    provider: str
    model_name: str | None
    message: str
    setup_hint: str | None = None


class AIAdapter(Protocol):
    name: str
    provider: str

    def health_check(self) -> AdapterHealth:
        ...

    def run(self, payload: Any) -> dict[str, Any]:
        ...
