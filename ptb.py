import time
from datetime import datetime, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Update, LabeledPrice, PreCheckoutQuery, WebAppInfo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    PreCheckoutQueryHandler
)

BOT_TOKEN = "7941535778:AAHuXyvkY5jlLi4bUlQWDjTCZHEJhfSqJ2c"
SUBSCRIPTION_PERIOD = 2592000

user_subscriptions = {}

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /create <amount>")
        return

    try:
        amount = int(args[0])
        if amount <= 0 or amount > 10000:
            await update.message.reply_text("Amount must be > 0 and ≤ 10000.")
            return
    except ValueError:
        await update.message.reply_text("Amount must be a valid number.")
        return

    prices = [LabeledPrice(label="1 Month Subscription", amount=amount * 100)]
    payload = f"{update.effective_user.id}:1m:{amount}:{int(time.time())}"

    result = await context.bot.create_invoice_link(
        title="Telegram Stars Subscription",
        description="1 Month Access",
        payload=payload,
        currency="XTR",
        prices=prices,
        subscription_period=SUBSCRIPTION_PERIOD,
        photo_url="https://via.placeholder.com/300x200.png?text=Subscribe",
        read_timeout=10.0,
        write_timeout=10.0
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Pay with Stars", url=result)]]
    )
    await update.message.reply_text(
        "Click below to continue payment:", reply_markup=keyboard
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query: PreCheckoutQuery = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    payload_parts = payment.invoice_payload.split(":")
    if len(payload_parts) == 4:
        _, _, amount, _ = payload_parts
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=SUBSCRIPTION_PERIOD)
        user_subscriptions[user_id] = {
            "plan": "1m",
            "amount": amount,
            "start": start_time,
            "end": end_time
        }
        await update.message.reply_text(
            f"✅ Subscribed for 1 Month\nAmount: {amount} Stars\nExpires: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

async def current_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sub = user_subscriptions.get(user_id)
    now = datetime.now()
    if sub and sub["end"] > now:
        remaining = sub["end"] - now
        await update.message.reply_text(
            f"Current Plan: 1 Month\nAmount: {sub['amount']} Stars\nExpires in: {str(remaining).split('.')[0]}"
        )
    else:
        await update.message.reply_text("No active subscription.")

async def cancel_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sub = user_subscriptions.get(user_id)
    if not sub:
        await update.message.reply_text("No active subscription to cancel.")
        return
    del user_subscriptions[user_id]
    await update.message.reply_text("Subscription canceled.")

async def refund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sub = user_subscriptions.get(user_id)
    if not sub:
        await update.message.reply_text("No payment history found.")
        return
    await update.message.reply_text("Manual refund logic not implemented. Contact admin.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /create <amount> to subscribe for 1 month.")

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("create", create))
app.add_handler(CommandHandler("currentplan", current_plan))
app.add_handler(CommandHandler("cancel", cancel_subscription))
app.add_handler(CommandHandler("refund", refund))
app.add_handler(PreCheckoutQueryHandler(precheckout))
app.add_handler(CommandHandler("successfulpayment", successful_payment))

app.run_polling()
