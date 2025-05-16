function readableTime(seconds) {
  const d = Math.floor(seconds / (3600 * 24));
  const h = Math.floor((seconds % (3600 * 24)) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${d ? d + "d:" : ""}${h ? h + "h:" : ""}${m ? m + "m:" : ""}${s}s`;
}

module.exports = { readableTime };
