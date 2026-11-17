// Page "Conseils" : 12 conseils en 3 catégories. Les textes sont dans i18n/<lang>.json
// (clés tips.<id>_t pour le titre, tips.<id> pour le texte).
(function () {
  const CATEGORIES = [
    { id: "maison", emoji: "🏠", tips: [
      { id: "bidons", emoji: "🪣" },
      { id: "legumes", emoji: "🥬" },
      { id: "fuites", emoji: "🔧" },
      { id: "bassine", emoji: "🍽️" },
    ] },
    { id: "hygiene", emoji: "🧼", tips: [
      { id: "ablutions", emoji: "🫖" },
      { id: "mains", emoji: "👐" },
      { id: "gobelet", emoji: "🥤" },
      { id: "nettoyer", emoji: "🧽" },
    ] },
    { id: "potable", emoji: "🚰", tips: [
      { id: "bouillir", emoji: "🔥" },
      { id: "javel", emoji: "💧" },
      { id: "charrette", emoji: "🛒" },
      { id: "trouble", emoji: "⚠️" },
    ] },
  ];

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "i18n") e.dataset.i18n = v;
      else if (k === "text") e.textContent = v;
      else e.setAttribute(k, v);
    }
    (children || []).forEach((c) => e.appendChild(c));
    return e;
  }

  function render() {
    const root = document.getElementById("tips");
    const frag = document.createDocumentFragment();
    for (const cat of CATEGORIES) {
      const headingId = `cat-${cat.id}`;
      const list = el("ul", { class: "card-list" }, cat.tips.map((t) =>
        el("li", { class: "card tip" }, [
          el("span", { class: "tip-emoji", "aria-hidden": "true", text: t.emoji }),
          el("div", null, [
            el("h3", { i18n: `tips.${t.id}_t` }),
            el("p", { i18n: `tips.${t.id}` }),
          ]),
        ])
      ));
      frag.appendChild(el("section", { class: "tip-section", "aria-labelledby": headingId }, [
        el("h2", { id: headingId }, [
          el("span", { class: "tip-emoji", "aria-hidden": "true", text: cat.emoji }),
          el("span", { i18n: `tips.cat_${cat.id}` }),
        ]),
        list,
      ]));
    }
    root.replaceChildren(frag);
    // If the language file is already loaded, fill the texts now;
    // otherwise i18n.js fills every [data-i18n] when it finishes loading.
    if (window.i18n && window.i18n.t("tips.title") !== "tips.title") window.i18n.apply(root);
  }

  render();
})();
