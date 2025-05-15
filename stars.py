from pyrogram import Client, filters
from pyrogram.types import Message, LabeledPrice, PreCheckoutQuery

API_ID = "25335325"
API_HASH = "9c3e5c9ac118570fad529aabff46fe44"
BOT_TOKEN = "YOUR_BOT_TOKEN"
COMMAND_HANDLER = ["/", "!"]

app = Client("PayBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command(["pay"], COMMAND_HANDLER))
async def pay_command(self: Client, ctx: Message):
    amount = ctx.command[1] if len(ctx.command) == 2 and ctx.command[1].isdigit() else 5
    await self.send_invoice(
        ctx.chat.id,
        title="Pay Donation",
        description="Donate via Pay",
        currency="XTR",
        prices=[LabeledPrice(label="Donation", amount=int(amount))],
        message_thread_id=ctx.message_thread_id,
        payload="pay",
    )

@app.on_pre_checkout_query()
async def pre_checkout_query_handler(_: Client, query: PreCheckoutQuery):
    await query.answer(success=True)

@app.on_message(filters.private, group=3)
async def successful_payment_handler(_: Client, message: Message):
    if message.successful_payment:
        await message.reply(
            f"Thanks for donating <b>{message.successful_payment.total_amount} {message.successful_payment.currency}</b>!\nTransaction ID: <code>{message.successful_payment.telegram_payment_charge_id}</code>"
        )

@app.on_message(filters.command(["refund"], COMMAND_HANDLER))
async def refund_payment(client: Client, message: Message):
    if len(message.command) == 1:
        return await message.reply("Please input telegram_payment_charge_id after command.")
    trx_id = message.command[1]
    try:
        await client.refund_star_payment(message.from_user.id, trx_id)
        await message.reply(f"{message.from_user.mention}, your donation has been refunded.")
    except Exception as e:
        await message.reply(str(e))

app.run()
