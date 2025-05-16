require("dotenv").config();
const { Bot } = require("grammy");
const { evaluate } = require("./utils/eval");
const { formatError } = require("./utils/formatError");
const { readableTime } = require("./utils/time");

const SUDOERS = process.env.SUDOERS.split(" ").map(Number);
const bot = new Bot(process.env.BOT_TOKEN);

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
