require("dotenv").config();
const { Bot } = require("grammy");
const { evaluate } = require("./utils/eval");
const { formatError } = require("./utils/formatError");
const { readableTime } = require("./utils/time");
const { setupAdminCommands } = require("./utils/admins");

const SUDOERS = process.env.SUDOERS.split(" ").map(Number);
const bot = new Bot(process.env.BOT_TOKEN);
setupAdminCommands(bot);
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
    "https://i.ibb.co/6RLCFgQ7/logo-black.png"
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

function getSenderId(ctx) {
    if (ctx.message?.sender_chat) return ctx.message.sender_chat.id;
    if (ctx.message?.from) return ctx.message.from.id;
    return 0;
}

bot.command("id", async (ctx) => {
    try {
        const msg = ctx.message;
        const reply = msg.reply_to_message;
        const chat = msg.chat;
        const yourId = getSenderId(ctx);
        let text = `**[Message ID](https://t.me/c/${chat.id.toString().slice(4)}/${msg.message_id})**: \`${msg.message_id}\`\n`;
        text += `**[Your ID](tg://user?id=${yourId})**: \`${yourId}\`\n`;

        const args = ctx.match?.trim();
        if (args) {
            try {
                const username = args.replace("@", "").split("/").pop();
                const user = await ctx.api.getChat(username);
                text += `**[User ID](tg://user?id=${user.id})**: \`${user.id}\`\n`;
            } catch {
                text += `\nUser not found or not visible to me.`;
            }
        }

        text += `**[Chat ID](https://t.me/${chat.username ?? ""})**: \`${chat.id}\`\n\n`;

        if (reply) {
            text += `**[Replied Message ID](https://t.me/c/${chat.id.toString().slice(4)}/${reply.message_id})**: \`${reply.message_id}\`\n`;
            if (reply.from?.id) {
                text += `**[Replied User ID](tg://user?id=${reply.from.id})**: \`${reply.from.id}\`\n`;
            }
            if (reply.forward_from_chat) {
                text += `The forwarded channel, ${reply.forward_from_chat.title}, has an id of \`${reply.forward_from_chat.id}\`\n`;
            }
            if (reply.sender_chat) {
                text += `ID of the replied chat/channel is \`${reply.sender_chat.id}\`\n`;
            }
            if (reply.new_chat_members) {
                for (const member of reply.new_chat_members) {
                    text += `Added user has an ID of \`${member.id}\`\n`;
                }
            }
            if (reply.photo) {
                const photo = reply.photo[reply.photo.length - 1];
                text += `\n**Replied Image File ID**: \`${photo.file_id}\``;
            }
            if (reply.sticker) {
                text += `\n**Sticker ID**: \`${reply.sticker.file_id}\``;
            }
            if (reply.animation) {
                text += `\n**GIF ID**: \`${reply.animation.file_id}\``;
            }
        }
        await ctx.reply(text, {
            parse_mode: "Markdown",
            disable_web_page_preview: true,
        });

    } catch (err) {
        console.error(err);
        await ctx.reply("An error occurred while fetching the ID.");
    }
});


bot.catch((err) => {
  console.error("Bot error:", err);
});

bot.start();
