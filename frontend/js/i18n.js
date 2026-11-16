// Traduction FR/AR + RTL, bascule sans rechargement
// À charger juste après config.js : remplace t() pour toute la page.
const I18N_JSON = {}; // dictionnaires JSON chargés à la demande
const RENDUS = new Map(); // texte produit -> {cle, vars} (pour retraduire)
let langue = choisirLangue();

function choisirLangue() {
  const q = new URLSearchParams(location.search).get("lang");
  if (q === "ar" || q === "fr") return q;
  try {
    const s = localStorage.getItem("lang");
    if (s === "ar" || s === "fr") return s;
  } catch {}
  return (navigator.language || "fr").slice(0, 2) === "ar" ? "ar" : "fr";
}

// Traduit dans la langue courante, sans jamais retomber sur l'autre langue
function traduire(cle, vars = {}, lg = langue) {
  let s = (I18N_JSON[lg] && I18N_JSON[lg][cle])
    || (typeof I18N !== "undefined" && I18N[lg] && I18N[lg][cle]) || cle;
  for (const k in vars) s = s.replace(`{${k}}`, vars[k]);
  return s;
}

// Remplace le t() de config.js
t = function (cle, vars = {}) {
  const s = traduire(cle, vars);
  RENDUS.set(s, { cle, vars });
  return s;
};

async function chargerJson(lg) {
  if (I18N_JSON[lg]) return;
  try {
    const r = await fetch(`i18n/${lg}.json`);
    if (r.ok) I18N_JSON[lg] = await r.json();
  } catch {}
}

// Retraduit un texte produit par t() (y compris "a · b · c")
function retraduire(txt) {
  const r = RENDUS.get(txt);
  if (r) return t(r.cle, r.vars);
  if (!txt.includes(" · ")) return null;
  const parts = txt.split(" · ");
  let change = false;
  const out = parts.map((p) => {
    const x = RENDUS.get(p);
    if (!x) return p;
    change = true;
    return t(x.cle, x.vars);
  });
  return change ? out.join(" · ") : null;
}

function appliquer() {
  document.documentElement.lang = langue;
  document.documentElement.dir = langue === "ar" ? "rtl" : "ltr";
  // 1. Textes écrits par les scripts (bandeau, listes, popups…)
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const noeuds = [];
  while (w.nextNode()) noeuds.push(w.currentNode);
  for (const n of noeuds) {
    const v = retraduire(n.nodeValue);
    if (v !== null) n.nodeValue = v;
  }
  // 2. Textes statiques des pages
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
}

async function changerLangue(lg) {
  langue = lg;
  try { localStorage.setItem("lang", lg); } catch {}
  await chargerJson(lg);
  appliquer();
  document.dispatchEvent(new CustomEvent("langue", { detail: lg }));
}

// Bouton « عربي / Français » dans l'en-tête
function bouton() {
  const header = document.querySelector("header");
  if (!header) return;
  header.style.cssText += "display:flex;align-items:center;justify-content:space-between;gap:8px";
  const b = document.createElement("button");
  b.type = "button";
  b.dataset.i18n = "langue_autre";
  b.style.cssText = "font:inherit;padding:6px 12px;border:1px solid #fff;border-radius:999px;"
    + "background:transparent;color:#fff;cursor:pointer";
  b.addEventListener("click", () => changerLangue(langue === "ar" ? "fr" : "ar"));
  header.append(b);
}

bouton();
// Après les scripts de la page (qui fixent dir avec l'ancien LANG), puis à l'arrivée du JSON
const pret = new Promise((ok) => document.addEventListener("DOMContentLoaded", ok));
pret.then(appliquer);
Promise.all([pret, chargerJson(langue)]).then(appliquer);
