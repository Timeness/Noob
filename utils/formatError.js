function formatError(err) {
  return `${err.name}: ${err.message}\n${err.stack}`;
}

module.exports = { formatError };
