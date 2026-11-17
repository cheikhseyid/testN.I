// i18n: loads i18n/<lang>.json, fills [data-i18n], sets <html lang/dir>, remembers the choice.
(function () {
  const cfg = window.MAWJOUD_CONFIG || {};
  const LANGS = cfg.LANGS || ["fr", "ar"];
  const DEFAULT = cfg.DEFAULT_LANG || "fr";
  const RTL = ["ar"];
  const STORE_KEY = "mawjoud.lang";

  let dict = {};
  let current = DEFAULT;

  function stored() {
    try { return localStorage.getItem(STORE_KEY); } catch (e) { return null; }
  }
  function remember(lang) {
    try { localStorage.setItem(STORE_KEY, lang); } catch (e) { /* private mode */ }
  }

  function t(key) {
    return Object.prototype.hasOwnProperty.call(dict, key) ? dict[key] : key;
  }

  function apply(root) {
    root = root || document;
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      const v = dict[el.dataset.i18n];
      if (v !== undefined) el.textContent = v;
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const v = dict[el.dataset.i18nPlaceholder];
      if (v !== undefined) el.placeholder = v;
    });
    root.querySelectorAll("[data-i18n-aria]").forEach((el) => {
      const v = dict[el.dataset.i18nAria];
      if (v !== undefined) el.setAttribute("aria-label", v);
    });
    // The toggle shows the *other* language.
    document.querySelectorAll("[data-lang-toggle]").forEach((btn) => {
      btn.textContent = current === "ar" ? "Français" : "عربي";
      btn.setAttribute("lang", current === "ar" ? "fr" : "ar");
    });
  }

  async function setLang(lang) {
    if (!LANGS.includes(lang)) lang = DEFAULT;
    try {
      const res = await fetch(`i18n/${lang}.json`, { cache: "no-cache" });
      if (!res.ok) throw new Error(res.status);
      dict = await res.json();
    } catch (e) {
      console.error(`i18n: impossible de charger i18n/${lang}.json`, e);
      return;
    }
    current = lang;
    document.documentElement.lang = lang;
    document.documentElement.dir = RTL.includes(lang) ? "rtl" : "ltr";
    remember(lang);
    apply();
    document.dispatchEvent(new CustomEvent("i18n:change", { detail: { lang } }));
  }

  function toggle() {
    return setLang(current === "ar" ? "fr" : "ar");
  }

  window.i18n = { t, apply, setLang, toggle, get lang() { return current; } };

  function init() {
    document.querySelectorAll("[data-lang-toggle]").forEach((btn) =>
      btn.addEventListener("click", toggle)
    );
    setLang(stored() || DEFAULT);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
