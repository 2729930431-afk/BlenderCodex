const assert = require("assert");

const { shouldUseKeepAlive } = require("../scripts/blendercodex_mcp_server.js");

assert.strictEqual(
  shouldUseKeepAlive({ background: true, keepAlive: true }),
  true,
  "background bridge can use keepAlive",
);

for (const args of [
  { keepAlive: true },
  { background: false, keepAlive: true },
  { background: true, keepAlive: false },
  { background: false, keepAlive: false },
  {},
]) {
  assert.strictEqual(
    shouldUseKeepAlive(args),
    false,
    `visible or disabled keepAlive should not pass --keep-alive: ${JSON.stringify(args)}`,
  );
}

console.log(JSON.stringify({ ok: true, checked: 6 }, null, 2));
