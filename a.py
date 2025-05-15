from pyrofork import Client, filters
from pyrofork.types import BotCommand
import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Controller Bot configuration
CONTROLLER_BOT_TOKEN = os.getenv("CONTROLLER_BOT_TOKEN")  # Store in .env
OWNER_ID = int(os.getenv("OWNER_ID"))  # Your Telegram user ID

# Dictionary to keep track of cloned bots
cloned_bots = {}

# Define a set of default modules (commands) for cloned bots
async def start_command(client, message):
    await message.reply("Hello! I'm a cloned bot. Use /help to see what I can do.")

async def help_command(client, message):
    await message.reply("Available commands:\n/start - Greet the bot\n/help - Show this message\n/about - About this bot")

async def about_command(client, message):
    await message.reply("I'm a bot cloned by the Controller Bot. That's all you need to know!")

# Module definitions
MODULES = [
    {
        "handler": filters.command("start") & filters.private,
        "callback": start_command
    },
    {
        "handler": filters.command("help") & filters.private,
        "callback": help_command
    },
    {
        "handler": filters.command("about") & filters.private,
        "callback": about_command
    }
]

# Initialize the Controller Bot
controller_bot = Client(
    "controller_bot",
    api_id=int(os.getenv("API_ID")),  # Your API ID from my.telegram.org
    api_hash=os.getenv("API_HASH"),  # Your API Hash from my.telegram.org
    bot_token=CONTROLLER_BOT_TOKEN
)

# Command to clone a bot
@controller_bot.on_message(filters.command("clone") & filters.user(OWNER_ID))
async def clone_bot_command(client, message):
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.reply("Usage: /clone {bot_token}")
        return

    bot_token = args[1].strip()
    
    # Validate bot token format (basic check)
    if not bot_token.count(":") == 1 or len(bot_token) < 30:
        await message.reply("Invalid bot token format.")
        return

    # Check if bot is already running
    if bot_token in cloned_bots:
        await message.reply("This bot is already running.")
        return

    try:
        # Initialize a new bot client
        cloned_client = Client(
            f"cloned_bot_{bot_token[:10]}",  # Unique session name
            api_id=int(os.getenv("API_ID")),
            api_hash=os.getenv("API_HASH"),
            bot_token=bot_token
        )

        # Attach modules to the cloned bot
        for module in MODULES:
            cloned_client.add_handler(
                pyrofork.handlers.MessageHandler(
                    module["callback"],
                    module["handler"]
                )
            )

        # Start the cloned bot
        await cloned_client.start()
        
        # Set bot commands for the cloned bot
        await cloned_client.set_bot_commands([
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help message"),
            BotCommand("about", "About this bot")
        ])

        # Store the cloned bot in the dictionary
        cloned_bots[bot_token] = cloned_client
        logger.info(f"Cloned bot started with token: {bot_token[:10]}...")
        await message.reply("Bot cloned successfully! Try /start on the new bot.")

    except Exception as e:
        logger.error(f"Failed to clone bot: {e}")
        await message.reply(f"Failed to clone bot: {str(e)}")

# Command to stop a cloned bot
@controller_bot.on_message(filters.command("stop") & filters.user(OWNER_ID))
async def stop_bot_command(client, message):
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.reply("Usage: /stop {bot_token}")
        return

    bot_token = args[1].strip()
    
    if bot_token not in cloned_bots:
        await message.reply("No bot running with this token.")
        return

    try:
        # Stop the cloned bot
        await cloned_bots[bot_token].stop()
        del cloned_bots[bot_token]
        logger.info(f"Cloned bot stopped with token: {bot_token[:10]}...")
        await message.reply("Bot stopped successfully.")
    except Exception as e:
        logger.error(f"Failed to stop bot: {e}")
        await message.reply(f"Failed to stop bot: {str(e)}")

# Start the Controller Bot
async def main():
    await controller_bot.start()
    logger.info("Controller Bot is running...")
    await asyncio.Event().wait()  # Keep the bot running

if __name__ == "__main__":
    asyncio.run(main())
