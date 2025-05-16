const axios = require("axios");
const cheerio = require("cheerio");
const vm = require("vm");
const fs = require("fs");
const path = require("path");

async function webscrap(url) {
  const { data } = await axios.get(url);
  const $ = cheerio.load(data);
  return $("body").text();
}

async function evaluate(code, ctx) {
  const msg = ctx.message;
  const sandbox = {
    console,
    ctx,
    msg,
    axios,
    cheerio,
    fetch,
    process,
    Buffer,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    Date,
    webscrap,
  };

  const script = new vm.Script(
    code.includes("await") ? `(async () => { ${code} })()` : code
  );
  const context = vm.createContext(sandbox);

  try {
    const result = await script.runInContext(context, { timeout: 5000 });
    const output = typeof result === "object" ? JSON.stringify(result, null, 2) : String(result);

    if (output.length > 1000) {
      const filePath = path.join(__dirname, "../temp.txt");
      fs.writeFileSync(filePath, output);
      await ctx.replyWithDocument({ source: filePath, filename: "output.txt" });
      fs.unlinkSync(filePath);
    } else {
      await ctx.reply(output);
    }
  } catch (err) {
    await ctx.reply("Error:\n" + err.message);
  }
}

module.exports = { evaluate };
