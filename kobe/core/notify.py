from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from telegram import Bot
import asyncio

class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str

class Notifier:
    def __init__(self, tg: TelegramConfig):
        self.bot = Bot(token=tg.bot_token)
        self.chat_id = tg.chat_id

    async def send(self, text: str, disable_web_page_preview: bool = True) -> None:
        """Envoie un message Telegram (python-telegram-bot v21 est async)."""
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            disable_web_page_preview=disable_web_page_preview,
        )

    def send_sync(self, text: str, disable_web_page_preview: bool = True) -> None:
        """Helper synchrone pour contextes non-async (utilise asyncio.run)."""
        asyncio.run(self.send(text, disable_web_page_preview=disable_web_page_preview))
