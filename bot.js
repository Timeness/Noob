require("dotenv").config();
const { Bot } = require("grammy");
const { evaluate } = require("./utils/eval");
const { formatError } = require("./utils/formatError");
const { readableTime } = require("./utils/time");

const SUDOERS = process.env.SUDOERS.split(" ").map(Number);
const bot = new Bot(process.env.BOT_TOKEN);

const paidUsers = new Map();

bot.command("pay", async (ctx) => {
  const args = ctx.message?.text?.split(" ");
  const amount = args?.[1] && /^\d+$/.test(args[1]) ? parseInt(args[1]) : 5;

  await ctx.replyWithInvoice(
    "Pay Donation",
    "Donate via Stars",
    "{}",
    "XTR",
    [{ amount: amount, label: "Donation" }],
    photo_url: "https://i.ibb.co/6RLCFgQ7/logo-black.png"
  );
});

bot.on("message:successful_payment", (ctx) => {
  const payment = ctx.message.successful_payment;
  if (ctx.from && payment) {
    paidUsers.set(ctx.from.id, payment.telegram_payment_charge_id);
    ctx.reply(`Thanks for donating ${payment.total_amount} ${payment.currency}!\nTransaction ID: ${payment.telegram_payment_charge_id}`);
  }
});

bot.on("pre_checkout_query", (ctx) => {
  return ctx.answerPreCheckoutQuery(true);
});

bot.command("refund", async (ctx) => {
  const args = ctx.message?.text?.split(" ");
  const txId = args?.[1];

  if (!txId) {
    return ctx.reply("Please provide telegram_payment_charge_id like /refund {tx_id}");
  }

  try {
    await ctx.api.refundStarPayment(ctx.from.id, txId);
    paidUsers.delete(ctx.from.id);
    ctx.reply("Refund successful");
  } catch (err) {
    ctx.reply("Refund failed: " + err.message);
  }
});

bot.command("status", (ctx) => {
  const paid = paidUsers.has(ctx.from.id);
  ctx.reply(paid ? "You have paid" : "You have not paid yet");
});

bot.command("start", (ctx) => ctx.reply("Bot is alive."));

bot.command("ex", async (ctx) => {
  if (!SUDOERS.includes(ctx.from.id)) return;
  const code = ctx.message.text.split(" ").slice(1).join(" ");
  if (!code) return ctx.reply("No code to evaluate!");
  await ctx.reply("Processing...");
  try {
    const result = await evaluate(code, ctx);
    ctx.reply(`✅ Result:\n\`${result}\``, { parse_mode: "Markdown" });
  } catch (error) {
    ctx.reply(`❌ Error:\n\`${formatError(error)}\``, { parse_mode: "Markdown" });
  }
});

bot.catch((err) => {
  console.error("Bot error:", err);
});

bot.start();
