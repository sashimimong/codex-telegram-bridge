from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ProviderCheck, RunResult, SessionContext


class AgentProvider(ABC):
    @abstractmethod
    async def check_installation(self) -> ProviderCheck:
        raise NotImplementedError

    @abstractmethod
    async def check_auth(self) -> ProviderCheck:
        raise NotImplementedError

    @abstractmethod
    async def run(self, prompt: str, workspace: str, session_context: SessionContext) -> RunResult:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, session_id: str) -> None:
        raise NotImplementedError
