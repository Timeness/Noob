from telegram import Update, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "7941535778:AAHuXyvkY5jlLi4bUlQWDjTCZHEJhfSqJ2c"
DURATION_MAP = {
    "1m": 2592000,          # 30 days
    "3m": 2592000 * 3,      # 90 days
    "6m": 2592000 * 6,      # 180 days
    "1y": 2592000 * 12      # 360 days
}

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /create <1m|3m|6m|1y> <amount>")
        return

    duration_key, amount_str = args[0].lower(), args[1]
    
    if duration_key not in DURATION_MAP:
        await update.message.reply_text("Invalid duration. Use: 1m, 3m, 6m, or 1y.")
        return

    try:
        amount = int(amount_str)
        if amount <= 0:
            await update.message.reply_text("Amount must be greater than 0.")
            return
        if amount > 10000:
            await update.message.reply_text("Max allowed is 10000 Stars.")
            return
    except ValueError:
        await update.message.reply_text("Amount must be a valid number.")
        return

    subscription_seconds = DURATION_MAP[duration_key]
    label = f"{duration_key.upper()} Subscription"

    prices = [LabeledPrice(label=label, amount=amount * 100)]

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="Star Subscription",
        description=f"{label} access",
        payload=f"sub-{duration_key}-{amount}",
        currency="XTR",
        prices=prices,
        subscription_period=subscription_seconds,
        photo_url="https://via.placeholder.com/300x200.png?text=Star+Subscription"
    )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("create", create))
app.run_polling()
