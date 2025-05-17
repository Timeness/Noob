import logging
from telegram import Update, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CURRENCY = "XTR"
TITLE = "Subscription"
DESCRIPTION = "You are subscribing for premium access."
PAYLOAD = "pay"

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

    prices = [LabeledPrice(label=f"{amount} Star(s)", amount=amount)]

    result = await context.bot.create_invoice_link(
        title=TITLE,
        description=DESCRIPTION,
        payload=PAYLOAD,
        currency=CURRENCY,
        prices=prices,
        start_parameter="subscribe",
        need_email=True,
        is_flexible=False,
        #subscription_period=1,
        photo_url="https://via.placeholder.com/300x200.png?text=Star+Subscription",
    )

    await update.message.reply_text(f"Click the link below to pay:\n{result}")

def main():
    app = ApplicationBuilder().token("7941535778:AAHuXyvkY5jlLi4bUlQWDjTCZHEJhfSqJ2c").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create))
    app.run_polling()

if __name__ == "__main__":
    main()
