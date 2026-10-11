(function () {
  "use strict";

  var grid = document.getElementById("grid");
  var cards = Array.prototype.slice.call(grid.querySelectorAll(".tag"));
  var search = document.getElementById("search");
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
  var emptyState = document.getElementById("empty-state");
  var activeCategory = "all";

  function applyFilters() {
    var query = search.value.trim().toLowerCase();
    var visible = 0;
    cards.forEach(function (card) {
      var matchesCategory = activeCategory === "all" || card.dataset.category === activeCategory;
      var matchesQuery = !query || card.textContent.toLowerCase().indexOf(query) !== -1;
      var show = matchesCategory && matchesQuery;
      card.hidden = !show;
      if (show) visible += 1;
    });
    emptyState.hidden = visible !== 0;
  }

  search.addEventListener("input", applyFilters);

  function toggleCard(toggle) {
    var card = toggle.closest(".tag");
    var expanded = card.classList.toggle("is-expanded");
    Array.prototype.slice.call(card.querySelectorAll(".tag-toggle")).forEach(function (el) {
      el.setAttribute("aria-expanded", expanded ? "true" : "false");
    });
  }

  Array.prototype.slice.call(grid.querySelectorAll(".tag-toggle")).forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      toggleCard(toggle);
    });
    toggle.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleCard(toggle);
      }
    });
  });

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      chips.forEach(function (c) {
        c.classList.remove("is-active");
      });
      chip.classList.add("is-active");
      activeCategory = chip.dataset.category;
      applyFilters();
    });
  });

  var copyBtn = document.getElementById("copy-btn");
  var feedUrl = document.getElementById("feed-url");
  var copyLabel = copyBtn.textContent;
  var copyTimer;
  var copyAttempt = 0;
  // English until a language is applied; also what a cached page without the translation table gets.
  var messages = {
    copied: "Stamped ✓",
    copy_failed: "Copy failed — select the URL",
    copied_label: "Feed URL copied",
    copy_failed_label: "Copy failed. Select and copy the feed URL manually."
  };

  function copyFeedback(copied) {
    clearTimeout(copyTimer);
    copyBtn.textContent = copied ? messages.copied : messages.copy_failed;
    copyBtn.classList.toggle("is-copied", copied);
    copyBtn.setAttribute("aria-label", copied ? messages.copied_label : messages.copy_failed_label);
    copyTimer = setTimeout(function () {
      copyBtn.textContent = copyLabel;
      copyBtn.classList.remove("is-copied");
      copyBtn.removeAttribute("aria-label");
    }, 1600);
  }

  copyBtn.addEventListener("click", function () {
    var text = feedUrl.textContent.trim();
    var attempt = ++copyAttempt;
    function complete(copied) {
      if (attempt === copyAttempt) copyFeedback(copied);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        navigator.clipboard.writeText(text).then(function () { complete(true); }, function () { complete(false); });
      } catch (error) {
        complete(false);
      }
    } else {
      try {
        var range = document.createRange();
        range.selectNode(feedUrl);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        complete(document.execCommand("copy") === true);
      } catch (error) {
        complete(false);
      }
    }
  });

  // ---------- language ----------

  var tableNode = document.getElementById("i18n");
  if (!tableNode) return;
  var table = JSON.parse(tableNode.textContent);

  function all(selector) {
    return Array.prototype.slice.call(document.querySelectorAll(selector));
  }

  var switchLinks = all(".lang-switch a");
  // Category names are data, so the English name on the page is the key of its translation.
  var categoryLabels = all(".badge, .chip-label").map(function (el) {
    return { el: el, name: el.textContent };
  });
  var description = document.querySelector('meta[name="description"]');
  var canonical = document.querySelector('link[rel="canonical"]');
  var canonicalRoot = canonical ? canonical.getAttribute("href") : "";

  function supported(value) {
    var code = String(value || "").toLowerCase().split("-")[0];
    return Object.prototype.hasOwnProperty.call(table, code) ? code : null;
  }

  function remembered() {
    try {
      return window.localStorage.getItem("dockyard-lang");
    } catch (error) {
      return null;
    }
  }

  // ?lang= first, then the remembered choice, then the browser's languages.
  function preferredLanguage() {
    var query = /[?&]lang=([^&#]*)/.exec(window.location.search || "");
    var wanted = [query && query[1], remembered()].concat(navigator.languages || [navigator.language]);
    for (var i = 0; i < wanted.length; i += 1) {
      var code = supported(wanted[i]);
      if (code) return code;
    }
    return "en";
  }

  function applyLanguage(code) {
    messages = table[code];
    document.documentElement.lang = code;
    all("[data-i18n]").forEach(function (el) {
      el.textContent = messages[el.dataset.i18n];
    });
    all("[data-i18n-placeholder]").forEach(function (el) {
      el.setAttribute("placeholder", messages[el.dataset.i18nPlaceholder]);
    });
    all("[data-i18n-aria-label]").forEach(function (el) {
      el.setAttribute("aria-label", messages[el.dataset.i18nAriaLabel]);
    });
    all(".tag-toggle").forEach(function (el) {
      el.title = messages.expand_hint;
    });
    all(".source-link").forEach(function (el) {
      el.textContent = messages.source;
    });
    categoryLabels.forEach(function (label) {
      label.el.textContent = messages.categories[label.name] || label.name;
    });
    document.title = messages.meta_title;
    if (description) description.setAttribute("content", messages.meta_description);
    if (canonical) canonical.setAttribute("href", canonicalRoot + (code === "en" ? "" : "?lang=" + code));
    switchLinks.forEach(function (link) {
      if (link.dataset.lang === code) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
    copyLabel = messages.copy;
  }

  switchLinks.forEach(function (link) {
    link.addEventListener("click", function (event) {
      var code = supported(link.dataset.lang);
      if (!code) return;
      event.preventDefault();
      applyLanguage(code);
      try {
        window.localStorage.setItem("dockyard-lang", code);
      } catch (error) {
        // The choice still holds for this visit.
      }
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", code === "en" ? window.location.pathname : "?lang=" + code);
      }
    });
  });

  var initial = preferredLanguage();
  if (initial !== "en") applyLanguage(initial);
})();
