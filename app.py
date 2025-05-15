from pyrogram import Client
from pyrogram import filters
from pyrogram.types import BotCommand
import asyncio
import pyrogram
import logging
import os
from dotenv import load_dotenv
from typing import Dict, List, Callable
from dataclasses import dataclass
from functools import wraps

load_dotenv()
logging.basicConfig(level=logging.INFO)

@dataclass
class BotModule:
    handler: filters
    callback: Callable

class ControllerBot:
    def __init__(self):
        self.api_id: int = int(os.getenv("API_ID", "25335325"))
        self.api_hash: str = os.getenv("API_HASH", "9c3e5c9ac118570fad529aabff46fe44")
        self.owner_id: int = int(os.getenv("OWNER_ID", "5220416927"))
        self.bot_token: str = os.getenv("CONTROLLER_BOT_TOKEN", "7740247503:AAHh8C1JTdOH2ZZfV_A-2UlvfCG3jLafuv0")
        self.cloned_bots: Dict[str, Client] = {}
        self.client: Client = Client(
            "controller_bot",
            api_id=self.api_id,
            api_hash=self.api_hash,
            bot_token=self.bot_token
        )
        self.modules: List[BotModule] = self._initialize_modules()

    def _initialize_modules(self) -> List[BotModule]:
        return [
            BotModule(filters.command("start") & filters.private, self.start_command),
            BotModule(filters.command("help") & filters.private, self.help_command),
            BotModule(filters.command("about") & filters.private, self.about_command),
            BotModule(filters.command("ping") & filters.private, self.ping_command)
        ]

    @staticmethod
    async def restrict_owner(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, client, message):
            if message.from_user.id != self.owner_id:
                await message.reply("Unauthorized access.")
                return
            return await func(self, client, message)
        return wrapper

    async def start_command(self, client: Client, message) -> None:
        await message.reply("Hello! I'm a cloned bot. Use /help for commands.")

    async def help_command(self, client: Client, message) -> None:
        await message.reply("Commands:\n/start - Greet\n/help - Help\n/about - Info\n/ping - Ping")

    async def about_command(self, client: Client, message) -> None:
        await message.reply("Cloned bot by ControllerBot.")

    async def ping_command(self, client: Client, message) -> None:
        await message.reply("Pong!")

    @restrict_owner
    async def clone_bot(self, client: Client, message) -> None:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /clone {bot_token}")
            return

        bot_token = args[1].strip()
        if not self._is_valid_token(bot_token):
            await message.reply("Invalid bot token format.")
            return

        if bot_token in self.cloned_bots:
            await message.reply("Bot already running.")
            return

        try:
            cloned_client = Client(
                f"cloned_bot_{bot_token[:10]}",
                api_id=self.api_id,
                api_hash=self.api_hash,
                bot_token=bot_token
            )

            for module in self.modules:
                cloned_client.add_handler(
                    pyrofork.handlers.MessageHandler(
                        module.callback,
                        module.handler
                    )
                )

            await cloned_client.start()
            await cloned_client.set_bot_commands([
                BotCommand("start", "Start the bot"),
                BotCommand("help", "Show help message"),
                BotCommand("about", "About this bot"),
                BotCommand("ping", "Ping the bot")
            ])

            self.cloned_bots[bot_token] = cloned_client
            await message.reply("Bot cloned successfully!")

        except Exception as e:
            await message.reply(f"Failed to clone bot: {str(e)}")

    @restrict_owner
    async def stop_bot(self, client: Client, message) -> None:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /stop {bot_token}")
            return

        bot_token = args[1].strip()
        if bot_token not in self.cloned_bots:
            await message.reply("No bot running with this token.")
            return

        try:
            await self.cloned_bots[bot_token].stop()
            del self.cloned_bots[bot_token]
            await message.reply("Bot stopped successfully.")
        except Exception as e:
            await message.reply(f"Failed to stop bot: {str(e)}")

    @staticmethod
    def _is_valid_token(token: str) -> bool:
        return token.count(":") == 1 and len(token) >= 30

    async def setup_handlers(self) -> None:
        self.client.add_handler(
            pyrogram.handlers.MessageHandler(
                self.clone_bot,
                filters.command("clone")
            )
        )
        self.client.add_handler(
            pyrogram.handlers.MessageHandler(
                self.stop_bot,
                filters.command("stop")
            )
        )

    async def run(self) -> None:
        await self.setup_handlers()
        await self.client.start()
        await asyncio.Event().wait()

bot = ControllerBot()
asyncio.run(bot.run())
