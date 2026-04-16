from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .config_store import ConfigStore
from .models import BridgeConfig, RunResult, SessionContext
from .provider_base import AgentProvider
from .templates import get_template


@dataclass
class SessionState:
    history: list[dict[str, str]] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class BridgeRuntime:
    def __init__(self, config_store: ConfigStore, provider_factory) -> None:
        self.config_store = config_store
        self.provider_factory = provider_factory
        self.sessions: dict[str, SessionState] = {}

    def _get_state(self, chat_id: str) -> SessionState:
        if chat_id not in self.sessions:
            self.sessions[chat_id] = SessionState()
        return self.sessions[chat_id]

    def reset_session(self, chat_id: str) -> None:
        self.sessions.pop(chat_id, None)

    def _build_prompt(self, config: BridgeConfig, state: SessionState, user_prompt: str, chat_id: str, user_id: str) -> tuple[str, SessionContext]:
        template = get_template(config.default_template)
        merged_history = state.history[-config.max_history_messages :]
        lines = [
            f"Bot Name: {config.bot_name}",
            f"Template: {template.name}",
            f"System Rules: {config.system_rules or template.system_rules}",
            f"Response Style: {config.response_style or template.response_style}",
            f"Working Style: {config.working_style or template.working_style}",
            f"Allowed Guidance: {config.allowed_guidance or template.allowed_guidance}",
            f"Blocked Guidance: {config.blocked_guidance or template.blocked_guidance}",
            "",
            "Conversation history:",
        ]
        if not merged_history:
            lines.append("(no prior messages)")
        else:
            for item in merged_history:
                lines.append(f"{item['role'].title()}: {item['content']}")

        lines.extend(
            [
                "",
                "Current user message:",
                user_prompt,
                "",
                "Return a plain-text answer suitable for a Telegram message.",
            ]
        )
        session_context = SessionContext(
            session_id=chat_id,
            user_id=user_id,
            chat_id=chat_id,
            template_key=config.default_template,
            history=merged_history,
        )
        return "\n".join(lines), session_context

    async def handle_user_message(self, chat_id: str, user_id: str, text: str) -> RunResult:
        config = self.config_store.load_config()
        state = self._get_state(chat_id)
        provider: AgentProvider = self.provider_factory(config)
        async with state.lock:
            state.history.append({"role": "user", "content": text})
            prompt, session_context = self._build_prompt(config, state, text, chat_id, user_id)
            result = await provider.run(prompt, config.workspace_path, session_context)
            assistant_text = result.output if result.ok else (result.error or result.output or "Request failed.")
            state.history.append({"role": "assistant", "content": assistant_text})
            state.history = state.history[-(config.max_history_messages * 2) :]
            return result

    def is_busy(self, chat_id: str) -> bool:
        return chat_id in self.sessions and self.sessions[chat_id].lock.locked()
