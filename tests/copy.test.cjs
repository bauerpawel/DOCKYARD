const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../site_src/static/app.js"), "utf8");

function harness(clipboard, fallback = () => true) {
  const classes = new Set();
  const attributes = new Map();
  const button = {
    textContent: "Copy", events: {},
    addEventListener(name, callback) { this.events[name] = callback; },
    classList: {
      toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
      remove(name) { classes.delete(name); },
    },
    setAttribute(name, value) { attributes.set(name, value); },
    removeAttribute(name) { attributes.delete(name); },
  };
  const elements = {
    "copy-btn": button,
    "feed-url": { textContent: " https://example.com/templates.json " },
    grid: { querySelectorAll: () => [] },
    search: { addEventListener() {} },
    "empty-state": {},
  };
  const timers = new Map();
  let nextTimer = 0;
  vm.runInNewContext(source, {
    document: {
      getElementById: (id) => elements[id], querySelectorAll: () => [],
      createRange: () => ({ selectNode() {} }), execCommand: fallback,
    },
    window: { getSelection: () => ({ removeAllRanges() {}, addRange() {} }) },
    navigator: clipboard ? { clipboard } : {},
    setTimeout: (callback) => { timers.set(++nextTimer, callback); return nextTimer; },
    clearTimeout: (id) => timers.delete(id),
  });
  return {
    button, classes, attributes, timers,
    async click() { button.events.click(); await Promise.resolve(); await Promise.resolve(); },
    expire() { for (const [id, callback] of timers) { timers.delete(id); callback(); } },
  };
}

test("successful clipboard write reports success and restores the original label", async () => {
  let copied;
  const ui = harness({ writeText: (value) => { copied = value; return Promise.resolve(); } });
  await ui.click();
  assert.equal(copied, "https://example.com/templates.json");
  assert.equal(ui.button.textContent, "Stamped ✓");
  assert.equal(ui.classes.has("is-copied"), true);
  ui.expire();
  assert.equal(ui.button.textContent, "Copy");
  assert.equal(ui.classes.has("is-copied"), false);
});

test("rejected clipboard write reports failure", async () => {
  const ui = harness({ writeText: () => Promise.reject(new Error("permission denied")) });
  await ui.click();
  assert.match(ui.button.textContent, /Copy failed/);
  assert.equal(ui.classes.has("is-copied"), false);
  assert.match(ui.attributes.get("aria-label"), /manually/);
});

test("synchronous clipboard exception reports failure", async () => {
  const ui = harness({ writeText: () => { throw new Error("clipboard unavailable"); } });
  await ui.click();
  assert.match(ui.button.textContent, /Copy failed/);
});

for (const success of [false, true]) {
  test(`fallback respects execCommand result ${success}`, async () => {
    const ui = harness(null, () => success);
    await ui.click();
    assert.equal(ui.classes.has("is-copied"), success);
    assert.equal(ui.button.textContent === "Stamped ✓", success);
  });
}

test("fallback exception reports failure", async () => {
  const ui = harness(null, () => { throw new Error("copy blocked"); });
  await ui.click();
  assert.match(ui.button.textContent, /Copy failed/);
});

test("repeated clicks reset one timer and preserve the initial label", async () => {
  const ui = harness({ writeText: () => Promise.resolve() });
  await ui.click();
  await ui.click();
  assert.equal(ui.timers.size, 1);
  ui.expire();
  assert.equal(ui.button.textContent, "Copy");
});

test("an older promise cannot overwrite feedback from the latest attempt", async () => {
  let resolveFirst, rejectSecond;
  let calls = 0;
  const ui = harness({ writeText: () => ++calls === 1
    ? new Promise((resolve) => { resolveFirst = resolve; })
    : new Promise((resolve, reject) => { rejectSecond = reject; }) });
  await ui.click();
  await ui.click();
  rejectSecond(new Error("denied"));
  await Promise.resolve();
  resolveFirst();
  await Promise.resolve();
  assert.match(ui.button.textContent, /Copy failed/);
  assert.equal(ui.classes.has("is-copied"), false);
});
