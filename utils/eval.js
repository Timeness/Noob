const vm = require("vm");
const axios = require("axios");
const cheerio = require("cheerio");
const fetch = require("node-fetch");

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
  };

  const script = new vm.Script(
    code.includes("await") ? `(async () => { ${code} })()` : code
  );
  const context = vm.createContext(sandbox);
  const result = await script.runInContext(context, { timeout: 5000 });
  return typeof result === "object" ? JSON.stringify(result, null, 2) : String(result);
}

module.exports = { evaluate };
