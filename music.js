import { Bot } from "grammy";
import YTMusic from '@codyduong/ytmusicapi';

const bot = new Bot("7941535778:AAHuXyvkY5jlLi4bUlQWDjTCZHEJhfSqJ2c");

const ytm = new YTMusic();

bot.command("search", async (ctx) => {
  const input = ctx.message.text;
  const args = input.split(' ').slice(1);
  if (args.length === 0) {
    return ctx.reply("Please provide a music name. Usage: /search {music_name}");
  }

  const query = args.join(' ');
  try {
    const results = await ytm.search(query);
    const jsonString = JSON.stringify(results, null, 2);
    await ctx.reply(`\`\`\`json\n${jsonString}\n\`\`\``, { parse_mode: "MarkdownV2" });
  } catch (error) {
    console.error(error);
    await ctx.reply("Error occurred while searching. Try again later.");
  }
});

bot.start();
