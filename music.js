import { Bot } from "grammy";
import { searchMusics } from "node-youtube-music";

const bot = new Bot("7941535778:AAHuXyvkY5jlLi4bUlQWDjTCZHEJhfSqJ2c");

bot.command("search", async (ctx) => {
  const input = ctx.message.text;
  const args = input.split(" ").slice(1);
  if (args.length === 0) {
    return ctx.reply("Please provide a music name. Usage: /search {music_name}");
  }
  
  const query = args.join(" ");
  try {
    const musics = await searchMusics(query);
    if (musics.length === 0) {
      return ctx.reply("No results found.");
    }
    const jsonString = JSON.stringify(musics, null, 2);
    const limitedJsonString = jsonString.length > 3500 ? jsonString.slice(0, 3500) + "\n...[truncated]" : jsonString;

    await ctx.reply(`\`\`\`json\n${limitedJsonString}\n\`\`\``, { parse_mode: "MarkdownV2" });
  } catch (error) {
    console.error(error);
    await ctx.reply("Error occurred while searching. Please try again later.");
  }
});

bot.start();
