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

  copyBtn.addEventListener("click", function () {
    var text = feedUrl.textContent.trim();

    function markCopied() {
      var original = copyBtn.textContent;
      copyBtn.textContent = "Stamped ✓";
      copyBtn.classList.add("is-copied");
      setTimeout(function () {
        copyBtn.textContent = original;
        copyBtn.classList.remove("is-copied");
      }, 1600);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(markCopied, markCopied);
    } else {
      var range = document.createRange();
      range.selectNode(feedUrl);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
      document.execCommand("copy");
      markCopied();
    }
  });
})();
