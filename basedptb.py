import logging
from telegram import Update, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CURRENCY = "USD"
TITLE = "Star Subscription"
DESCRIPTION = "You are subscribing for star access!"
PAYLOAD = "custom-payload-star"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /create <amount> to generate an invoice link.")

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please enter the amount like this:\n/create 10")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number.")
        return

    if amount <= 0:
        await update.message.reply_text("Amount must be greater than 0.")
        return

    prices = [LabeledPrice(label=f"{amount} Star(s)", amount=amount * 100)]

    result = await context.bot.create_invoice_link(
        title=TITLE,
        description=DESCRIPTION,
        payload=PAYLOAD,
        currency=CURRENCY,
        prices=prices,
        subscription_period=1,
        need_email=True,
        photo_url="https://via.placeholder.com/300x200.png?text=Star+Subscription",
    )

    await update.message.reply_text(f"Click the link below to pay:\n{result}")

def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create))
    app.run_polling()

if __name__ == "__main__":
    main()
