from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .config_store import ConfigStore
from .models import BridgeConfig, RunResult, SessionContext
from .provider_base import AgentProvider
from .templates import get_template
from .translation import contains_hangul, translate_to_english


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

    def _effective_history_window(self, config: BridgeConfig, template) -> int:
        return max(1, min(config.max_history_messages, template.history_window))

    def _workspace_policy_lines(self, workspace_path: str, workspace_context: str) -> list[str]:
        lines = [
            f"Workspace Context Policy: {workspace_context}",
            f"Workspace Path: {workspace_path or '(not configured)'}",
        ]
        if workspace_context == "required":
            if workspace_path:
                lines.append("You must ground the answer in the workspace context before giving generic advice.")
            else:
                lines.append("You must clearly state that workspace context is missing and limit the answer accordingly.")
        elif workspace_context == "prefer":
            if workspace_path:
                lines.append("Prefer workspace-specific context first, then add general guidance if needed.")
            else:
                lines.append("Workspace is missing, so provide general guidance and mention that limitation briefly.")
        else:
            lines.append("Workspace context is optional. Use it when it helps, but keep the answer practical.")
        return lines

    def _build_prompt(self, config: BridgeConfig, state: SessionState, user_prompt: str, chat_id: str, user_id: str) -> tuple[str, SessionContext]:
        template = get_template(config.default_template)
        history_window = self._effective_history_window(config, template)
        merged_history = state.history[-history_window:]
        translation_enabled = getattr(config, "translation_enabled", False)
        translated_user_prompt = (
            translate_to_english(user_prompt)
            if translation_enabled and contains_hangul(user_prompt)
            else user_prompt
        )
        response_format = config.response_format or template.response_format
        lines = [
            "Critical Rules:",
            "- Always answer in Korean unless the user explicitly requests another language.",
            "- Return only the final user-facing answer.",
            "- Never include startup logs, warnings, HTML, telemetry output, or raw tool noise.",
            "- If information is missing, explain that briefly in Korean.",
            "- Follow the required output format exactly unless the user explicitly asks for a different format.",
            "",
            f"Bot Name: {config.bot_name}",
            f"Template: {template.name}",
            f"System Rules: {config.system_rules or template.system_rules}",
            f"Response Style: {config.response_style or template.response_style}",
            f"Required Output Format: {response_format}",
            f"Template Policy Summary: {template.policy_summary}",
            f"Working Style: {config.working_style or template.working_style}",
            f"Allowed Guidance: {config.allowed_guidance or template.allowed_guidance}",
            f"Blocked Guidance: {config.blocked_guidance or template.blocked_guidance}",
            f"Conversation History Window: {history_window}",
            "",
            "Template Runtime Rules:",
            *[f"- {rule}" for rule in template.runtime_rules],
            "",
            "Workspace Rules:",
            *[f"- {rule}" for rule in self._workspace_policy_lines(config.workspace_path, template.workspace_context)],
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
                "Current user message (original):",
                user_prompt,
                "",
                "Required output checklist:",
                response_format,
                "",
                *(
                    [
                        "Current user message (English translation for compatibility):",
                        translated_user_prompt,
                        "",
                    ]
                    if translation_enabled
                    else []
                ),
                "Return a plain-text Korean answer suitable for a Telegram message.",
                "Use short section headings when the format requires sections.",
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
            state.history = state.history[-(self._effective_history_window(config, get_template(config.default_template)) * 2) :]
            return result

    def is_busy(self, chat_id: str) -> bool:
        return chat_id in self.sessions and self.sessions[chat_id].lock.locked()
