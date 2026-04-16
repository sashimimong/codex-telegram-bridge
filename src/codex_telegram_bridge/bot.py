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

    def _is_allowed(self, user_id: int) -> bool:
        config = self.config_store.load_config()
        return str(user_id) in config.telegram_allowed_user_ids

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        config = self.config_store.load_config()
        if not update.message:
            return
        await update.message.reply_text(
            f"{config.bot_name}\n\n"
            "Use /status to run diagnostics.\n"
            "Use /reset to clear the current session."
        )

    async def _cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        chat_id = str(update.effective_chat.id)
        self.runtime.reset_session(chat_id)
        await update.message.reply_text("Session history cleared.")

    async def _cmd_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        config = self.config_store.load_config()
        await update.message.reply_text(f"Current template: {config.default_template}")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        config = self.config_store.load_config()
        provider: AgentProvider = self.provider_factory(config)
        install_check = await provider.check_installation()
        auth_check = await provider.check_auth()

        lines = [
            f"Bot: {config.bot_name}",
            f"Workspace: {config.workspace_path or '(not set)'}",
            f"Template: {config.default_template}",
            "",
            f"Codex install: {install_check.status} - {install_check.message}",
            *[f"- {item}" for item in install_check.details],
            "",
            f"Codex auth: {auth_check.status} - {auth_check.message}",
            *[f"- {item}" for item in auth_check.details],
        ]
        await update.message.reply_text("\n".join(lines))

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        if not self._is_allowed(user_id):
            await update.message.reply_text("You are not allowed to use this bot.")
            return

        chat_id = str(update.effective_chat.id)
        if self.runtime.is_busy(chat_id):
            await update.message.reply_text("Still working on the previous request for this chat.")
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await update.message.reply_text("Working on it...")

        result = await self.runtime.handle_user_message(chat_id, str(user_id), update.message.text)
        if result.ok:
            await update.message.reply_text(result.output[:4000])
        else:
            message = result.error or result.output or "Request failed."
            await update.message.reply_text(message[:4000])

    async def start_if_configured(self) -> str:
        secrets = self.config_store.load_secrets()
        token = secrets.telegram_bot_token.strip()
        if not token:
            logger.info("Telegram bot token not configured; skipping bot startup.")
            return "skipped"

        if self._app and self._token_in_use == token:
            return "running"

        await self.stop()

        self._app = Application.builder().token(token).build()
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("reset", self._cmd_reset))
        self._app.add_handler(CommandHandler("template", self._cmd_template))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        self._token_in_use = token
        logger.info("Telegram bridge started.")
        return "started"

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
