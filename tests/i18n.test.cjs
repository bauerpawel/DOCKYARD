const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../site_src/static/app.js"), "utf8");
const table = JSON.parse(fs.readFileSync(path.join(__dirname, "../site_src/i18n.json"), "utf8"));

function element(textContent = "", dataset = {}) {
  const attributes = new Map();
  return {
    textContent, dataset, attributes, events: {}, title: "",
    addEventListener(name, callback) { this.events[name] = callback; },
    setAttribute(name, value) { attributes.set(name, value); },
    getAttribute(name) { return attributes.has(name) ? attributes.get(name) : null; },
    removeAttribute(name) { attributes.delete(name); },
    classList: { toggle() {}, remove() {}, add() {} },
  };
}

// The page as the template renders it: English text, one element per translated spot.
function page({ search = "", stored = null, languages = ["en-US"], storage = "works" } = {}) {
  const tagline = element(table.en.tagline, { i18n: "tagline" });
  const searchBox = element("", { i18nPlaceholder: "search_placeholder", i18nAriaLabel: "search_label" });
  const copy = element(table.en.copy, { i18n: "copy" });
  const toggle = element();
  const sourceLink = element(table.en.source);
  const badge = element("Media");
  const chipLabel = element("Media");
  const unknownBadge = element("Brand New Category");
  const description = element();
  description.setAttribute("content", table.en.meta_description);
  const canonical = element();
  canonical.setAttribute("href", "https://catalog.example/");
  const links = ["en", "pl", "de", "fr"].map((code) => element(code.toUpperCase(), { lang: code }));
  links[0].setAttribute("aria-current", "true");
  const selectors = {
    "[data-i18n]": [tagline, copy],
    "[data-i18n-placeholder]": [searchBox],
    "[data-i18n-aria-label]": [searchBox],
    ".tag-toggle": [toggle],
    ".source-link": [sourceLink],
    ".badge, .chip-label": [badge, chipLabel, unknownBadge],
    ".lang-switch a": links,
    ".chip": [],
  };
  const elements = {
    i18n: { textContent: JSON.stringify(table) },
    "copy-btn": copy,
    "feed-url": { textContent: "https://example.com/templates.json" },
    grid: { querySelectorAll: (selector) => selectors[selector] || [] },
    search: searchBox,
    "empty-state": {},
  };
  const store = new Map(stored ? [["dockyard-lang", stored]] : []);
  const visited = [];
  const timers = new Map();
  let nextTimer = 0;
  const document = {
    title: table.en.meta_title,
    documentElement: { lang: "en" },
    getElementById: (id) => elements[id],
    querySelectorAll: (selector) => selectors[selector] || [],
    querySelector: (selector) => ({ 'meta[name="description"]': description, 'link[rel="canonical"]': canonical })[selector] || null,
    createRange: () => ({ selectNode() {} }), execCommand: () => true,
  };
  const localStorage = {
    getItem(key) { if (storage === "blocked") throw new Error("storage blocked"); return store.has(key) ? store.get(key) : null; },
    setItem(key, value) { if (storage === "blocked") throw new Error("storage blocked"); store.set(key, value); },
  };
  vm.runInNewContext(source, {
    document,
    window: {
      location: { search, pathname: "/" }, localStorage,
      history: { replaceState(state, title, url) { visited.push(url); } },
      getSelection: () => ({ removeAllRanges() {}, addRange() {} }),
    },
    navigator: { languages, clipboard: { writeText: () => Promise.resolve() } },
    setTimeout: (callback) => { timers.set(++nextTimer, callback); return nextTimer; },
    clearTimeout: (id) => timers.delete(id),
  });
  return {
    document, tagline, searchBox, copy, toggle, sourceLink, badge, chipLabel, unknownBadge, description, canonical, links, store, visited,
    current() { return links.filter((link) => link.getAttribute("aria-current") === "true").map((link) => link.dataset.lang); },
    choose(code) {
      let prevented = false;
      links.find((link) => link.dataset.lang === code).events.click({ preventDefault() { prevented = true; } });
      return prevented;
    },
    async copyFeed() { copy.events.click(); await Promise.resolve(); await Promise.resolve(); },
    expire() { for (const [id, callback] of timers) { timers.delete(id); callback(); } },
  };
}

test("a Polish browser gets the Polish page", () => {
  const ui = page({ languages: ["pl-PL", "pl", "en"] });
  assert.equal(ui.document.documentElement.lang, "pl");
  assert.equal(ui.tagline.textContent, table.pl.tagline);
  assert.equal(ui.searchBox.getAttribute("placeholder"), table.pl.search_placeholder);
  assert.equal(ui.searchBox.getAttribute("aria-label"), table.pl.search_label);
  assert.equal(ui.toggle.title, table.pl.expand_hint);
  assert.equal(ui.sourceLink.textContent, table.pl.source);
  assert.equal(ui.document.title, table.pl.meta_title);
  assert.equal(ui.description.getAttribute("content"), table.pl.meta_description);
  assert.equal(ui.canonical.getAttribute("href"), "https://catalog.example/?lang=pl");
  assert.deepEqual(ui.current(), ["pl"]);
});

test("category names are translated and unknown ones stay as they are", () => {
  const ui = page({ languages: ["de"] });
  assert.equal(ui.badge.textContent, table.de.categories.Media);
  assert.equal(ui.chipLabel.textContent, table.de.categories.Media);
  assert.equal(ui.unknownBadge.textContent, "Brand New Category");
});

test("?lang= wins over the remembered choice and the browser", () => {
  const ui = page({ search: "?lang=de", stored: "fr", languages: ["pl"] });
  assert.equal(ui.document.documentElement.lang, "de");
});

test("the remembered choice wins over the browser", () => {
  const ui = page({ stored: "fr", languages: ["pl"] });
  assert.equal(ui.document.documentElement.lang, "fr");
  assert.equal(ui.tagline.textContent, table.fr.tagline);
});

test("an unsupported browser language leaves the English page alone", () => {
  const ui = page({ search: "?lang=xx", languages: ["es-ES", "it"] });
  assert.equal(ui.document.documentElement.lang, "en");
  assert.equal(ui.tagline.textContent, table.en.tagline);
  assert.equal(ui.canonical.getAttribute("href"), "https://catalog.example/");
  assert.deepEqual(ui.current(), ["en"]);
});

test("choosing a language switches in place, is remembered and shows in the address", () => {
  const ui = page();
  assert.equal(ui.choose("fr"), true);
  assert.equal(ui.tagline.textContent, table.fr.tagline);
  assert.equal(ui.badge.textContent, table.fr.categories.Media);
  assert.equal(ui.store.get("dockyard-lang"), "fr");
  assert.deepEqual(ui.visited, ["?lang=fr"]);
  assert.deepEqual(ui.current(), ["fr"]);
});

test("switching back to English restores the original page and a clean address", () => {
  const ui = page({ languages: ["pl"] });
  ui.choose("en");
  assert.equal(ui.document.documentElement.lang, "en");
  assert.equal(ui.tagline.textContent, table.en.tagline);
  assert.equal(ui.badge.textContent, "Media");
  assert.equal(ui.document.title, table.en.meta_title);
  assert.equal(ui.canonical.getAttribute("href"), "https://catalog.example/");
  assert.deepEqual(ui.visited, ["/"]);
  assert.equal(ui.store.get("dockyard-lang"), "en");
});

test("copy feedback speaks the chosen language", async () => {
  const ui = page({ languages: ["pl"] });
  assert.equal(ui.copy.textContent, table.pl.copy);
  await ui.copyFeed();
  assert.equal(ui.copy.textContent, table.pl.copied);
  ui.expire();
  assert.equal(ui.copy.textContent, table.pl.copy);
});

test("switching language during copy feedback restores the new label", async () => {
  const ui = page();
  await ui.copyFeed();
  ui.choose("de");
  ui.expire();
  assert.equal(ui.copy.textContent, table.de.copy);
});

test("blocked storage does not stop the switch", () => {
  const ui = page({ languages: ["fr"], storage: "blocked" });
  assert.equal(ui.document.documentElement.lang, "fr");
  ui.choose("de");
  assert.equal(ui.tagline.textContent, table.de.tagline);
});
