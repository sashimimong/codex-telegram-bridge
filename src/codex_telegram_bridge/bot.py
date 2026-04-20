from __future__ import annotations

import logging
from typing import Optional

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .config_store import ConfigStore
from .provider_base import AgentProvider
from .runtime import BridgeRuntime

logger = logging.getLogger(__name__)


class TelegramBridgeService:
    def __init__(self, config_store: ConfigStore, runtime: BridgeRuntime, provider_factory) -> None:
        self.config_store = config_store
        self.runtime = runtime
        self.provider_factory = provider_factory
        self._app: Optional[Application] = None
        self._token_in_use: str = ""
        self._last_status: str = "idle"
        self._last_error: str = ""

    def _is_allowed(self, user_id: int) -> bool:
        config = self.config_store.load_config()
        return str(user_id) in config.telegram_allowed_user_ids

    def get_service_state(self) -> dict[str, str | bool]:
        return {
            "status": self._last_status,
            "running": self._app is not None,
            "has_error": bool(self._last_error),
            "error": self._last_error,
        }

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        config = self.config_store.load_config()
        if not update.message:
            return
        await update.message.reply_text(
            f"{config.bot_name}\n\n"
            "/status 로 현재 연결 상태를 확인할 수 있습니다.\n"
            "/reset 으로 현재 대화 기록을 초기화할 수 있습니다."
        )

    async def _cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        chat_id = str(update.effective_chat.id)
        self.runtime.reset_session(chat_id)
        await update.message.reply_text("대화 기록을 초기화했습니다.")

    async def _cmd_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        config = self.config_store.load_config()
        await update.message.reply_text(f"현재 기본 템플릿: {config.default_template}")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        config = self.config_store.load_config()
        provider: AgentProvider = self.provider_factory(config)
        install_check = await provider.check_installation()
        auth_check = await provider.check_auth()
        service_state = self.get_service_state()

        lines = [
            f"봇 이름: {config.bot_name}",
            f"작업 폴더: {config.workspace_path or '(설정되지 않음)'}",
            f"기본 템플릿: {config.default_template}",
            f"자동 번역: {'켜짐' if config.translation_enabled else '꺼짐'}",
            "",
            f"브리지 상태: {service_state['status']}",
            "",
            f"Codex 설치: {install_check.status} - {install_check.message}",
            *[f"- {item}" for item in install_check.details],
            "",
            f"Codex 로그인: {auth_check.status} - {auth_check.message}",
            *[f"- {item}" for item in auth_check.details],
        ]
        if service_state["has_error"]:
            lines.extend(["", f"최근 봇 시작 오류: {service_state['error']}"])
        await update.message.reply_text("\n".join(lines))

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        if not self._is_allowed(user_id):
            await update.message.reply_text("이 봇을 사용할 권한이 없습니다.")
            return

        chat_id = str(update.effective_chat.id)
        if self.runtime.is_busy(chat_id):
            await update.message.reply_text("이 채팅은 이전 요청을 아직 처리 중입니다.")
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await update.message.reply_text("처리 중입니다...")

        result = await self.runtime.handle_user_message(chat_id, str(user_id), update.message.text)
        if result.ok:
            await update.message.reply_text(result.output[:4000])
        else:
            message = result.error or result.output or "요청 처리에 실패했습니다."
            await update.message.reply_text(message[:4000])

    async def start_if_configured(self) -> str:
        secrets = self.config_store.load_secrets()
        token = secrets.telegram_bot_token.strip()
        if not token:
            logger.info("Telegram bot token not configured; skipping bot startup.")
            self._last_status = "skipped"
            self._last_error = ""
            return "skipped"

        if self._app and self._token_in_use == token:
            self._last_status = "running"
            self._last_error = ""
            return "running"

        await self.stop()

        try:
            self._app = Application.builder().token(token).build()
            self._app.add_handler(CommandHandler("start", self._cmd_start))
            self._app.add_handler(CommandHandler("status", self._cmd_status))
            self._app.add_handler(CommandHandler("reset", self._cmd_reset))
            self._app.add_handler(CommandHandler("template", self._cmd_template))
            self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

            await self._app.initialize()
            await self._app.start()
            if self._app.updater:
                await self._app.updater.start_polling()

            self._token_in_use = token
            self._last_status = "running"
            self._last_error = ""
            logger.info("Telegram bridge started.")
            return "started"
        except Exception as exc:  # pragma: no cover - external API failure path
            logger.exception("Failed to start Telegram bridge.")
            self._last_status = "error"
            self._last_error = str(exc)
            await self.stop()
            return "error"

    async def stop(self) -> None:
        if not self._app:
            return
        try:
            if self._app.updater:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        finally:
            self._app = None
            self._token_in_use = ""
