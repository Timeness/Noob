function setupAdminCommands(bot) {
  async function getUserId(ctx) {
    if (ctx.message.reply_to_message) return ctx.message.reply_to_message.from.id;
    const args = ctx.message.text.split(" ");
    return args[1] ? parseInt(args[1]) : null;
  }

  async function isAdmin(ctx) {
    const chatId = ctx.chat.id;
    const userId = ctx.from.id;
    const member = await ctx.api.getChatMember(chatId, userId);
    return ["administrator", "creator"].includes(member.status);
  }

  bot.command(["ban", "unban", "kick", "mute", "unmute", "promote", "demote"], async ctx => {
    if (!(await isAdmin(ctx))) return ctx.reply("You are not an admin.");
    const command = ctx.message.text.split(" ")[0].slice(1);
    const targetId = await getUserId(ctx);
    if (!targetId) return ctx.reply("Mention or reply to a user.");
    const chatId = ctx.chat.id;

    const commands = {
      ban: () => ctx.api.banChatMember(chatId, targetId),
      unban: () => ctx.api.unbanChatMember(chatId, targetId),
      kick: async () => {
        await ctx.api.banChatMember(chatId, targetId);
        await ctx.api.unbanChatMember(chatId, targetId);
      },
      mute: () =>
        ctx.api.restrictChatMember(chatId, targetId, {
          permissions: {
            can_send_messages: false,
            can_send_media_messages: false,
            can_send_other_messages: false,
            can_add_web_page_previews: false,
          },
        }),
      unmute: () =>
        ctx.api.restrictChatMember(chatId, targetId, {
          permissions: {
            can_send_messages: true,
            can_send_media_messages: true,
            can_send_other_messages: true,
            can_add_web_page_previews: true,
          },
        }),
      promote: () =>
        ctx.api.promoteChatMember(chatId, targetId, {
          can_change_info: true,
          can_delete_messages: true,
          can_invite_users: true,
          can_restrict_members: true,
          can_pin_messages: true,
          can_promote_members: false,
        }),
      demote: () =>
        ctx.api.promoteChatMember(chatId, targetId, {
          can_change_info: false,
          can_delete_messages: false,
          can_invite_users: false,
          can_restrict_members: false,
          can_pin_messages: false,
          can_promote_members: false,
        }),
    };

    if (commands[command]) {
      try {
        await commands[command]();
        ctx.reply(`✅ ${command} success.`);
      } catch (err) {
        ctx.reply(`❌ Failed: ${err.message}`);
      }
    }
  });

  const lockTypes = {
    media: ["can_send_media_messages"],
    messages: ["can_send_messages"],
    links: ["can_add_web_page_previews"],
    all: [
      "can_send_messages",
      "can_send_media_messages",
      "can_send_other_messages",
      "can_add_web_page_previews",
    ],
  };

  bot.command(["lock", "unlock"], async ctx => {
    if (!(await isAdmin(ctx))) return ctx.reply("You are not an admin.");
    const [cmd, type] = ctx.message.text.split(" ");
    if (!lockTypes[type]) return ctx.reply("Invalid lock type. Use: media, messages, links, all");

    const permissions = Object.fromEntries(
      lockTypes[type].map(p => [p, cmd === "/unlock"])
    );

    try {
      await ctx.api.setChatPermissions(ctx.chat.id, permissions);
      ctx.reply(`✅ ${cmd === "/lock" ? "Locked" : "Unlocked"} ${type}`);
    } catch (err) {
      ctx.reply(`❌ Failed: ${err.message}`);
    }
  });
}

module.exports = setupAdminCommands;
