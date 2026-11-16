// Graphiques légers en SVG/CSS pur (aucune lib)
Object.assign(I18N.fr, {
  ch_titre: "Statistiques",
  ch_quartier: "Pannes ouvertes par quartier",
  ch_jours: "Pannes signalées (7 derniers jours)",
  ch_chaleur: "Pannes ouvertes : quartier × jour",
  ch_ouverts: "Signalements ouverts : {n}",
  ch_vide: "Aucune donnée",
});
Object.assign(I18N.ar, {
  ch_titre: "إحصائيات",
  ch_quartier: "الأعطال المفتوحة حسب الحي",
  ch_jours: "الأعطال المبلّغ عنها (آخر 7 أيام)",
  ch_chaleur: "الأعطال المفتوحة: الحي × اليوم",
  ch_ouverts: "البلاغات المفتوحة: {n}",
  ch_vide: "لا توجد بيانات",
});
document.querySelectorAll("#graphes [data-i18n]").forEach((e) => (e.textContent = t(e.dataset.i18n)));

const SVG = "http://www.w3.org/2000/svg";
const quartiersVus = new Set(); // garde les quartiers à 0 après réparation

function el(tag, attrs = {}, txt) {
  const e = document.createElementNS(SVG, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (txt !== undefined) e.textContent = txt;
  return e;
}

// 7 derniers jours (UTC, comme la base) au format AAAA-MM-JJ
function septJours() {
  const j = [];
  for (let i = 6; i >= 0; i--) j.push(new Date(Date.now() - i * 864e5).toISOString().slice(0, 10));
  return j;
}
const court = (d) => d.slice(8, 10) + "/" + d.slice(5, 7);

// Barres horizontales : pannes par quartier
function barres(cible, donnees) {
  const max = Math.max(1, ...donnees.map((d) => d.total));
  const h = 26, lg = 110, W = 340;
  const svg = el("svg", { viewBox: `0 0 ${W} ${donnees.length * h + 4}`, role: "img", direction: "ltr" }); // coordonnées fixes, même en RTL
  donnees.forEach((d, i) => {
    const y = i * h + 2, w = ((W - lg - 30) * d.total) / max;
    svg.append(
      el("text", { x: lg - 6, y: y + 16, "text-anchor": "end", class: "lbl" }, d.quartier),
      el("rect", { x: lg, y: y + 3, width: Math.max(w, 1), height: h - 8, rx: 3, class: "bar" }),
      el("text", { x: lg + w + 4, y: y + 16, class: "val" }, d.total),
    );
  });
  cible.replaceChildren(svg);
}

// Courbe : pannes par jour sur 7 jours
function courbe(cible, parJour) {
  const jours = septJours();
  const val = jours.map((j) => (parJour.find((d) => String(d.jour) === j) || { total: 0 }).total);
  const max = Math.max(1, ...val), W = 340, H = 140, g = 24, b = 22;
  const x = (i) => g + (i * (W - 2 * g)) / 6;
  const y = (v) => H - b - (v * (H - b - 14)) / max;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", direction: "ltr" }); // coordonnées fixes, même en RTL
  svg.append(el("line", { x1: g, y1: H - b, x2: W - g, y2: H - b, class: "axe" }));
  svg.append(el("polyline", { points: val.map((v, i) => `${x(i)},${y(v)}`).join(" "), class: "courbe" }));
  val.forEach((v, i) => {
    svg.append(
      el("circle", { cx: x(i), cy: y(v), r: 3.5, class: "pt" }),
      el("text", { x: x(i), y: y(v) - 7, "text-anchor": "middle", class: "val" }, v),
      el("text", { x: x(i), y: H - 6, "text-anchor": "middle", class: "lbl" }, court(jours[i])),
    );
  });
  cible.replaceChildren(svg);
}

// Tableau « chaleur » quartier × jour (HTML + couleur CSS)
function chaleur(cible, quartiers, sigs) {
  const jours = septJours();
  const n = {};
  for (const s of sigs) {
    const k = s.quartier + "|" + new Date(s.cree_le).toISOString().slice(0, 10);
    n[k] = (n[k] || 0) + 1;
  }
  const max = Math.max(1, ...Object.values(n));
  const table = document.createElement("table");
  const tr0 = table.insertRow();
  tr0.insertCell();
  jours.forEach((j) => (tr0.insertCell().textContent = court(j)));
  for (const q of quartiers) {
    const tr = table.insertRow();
    tr.insertCell().textContent = q;
    for (const j of jours) {
      const v = n[q + "|" + j] || 0;
      const td = tr.insertCell();
      td.textContent = v || "";
      td.className = "case";
      if (v) td.style.background = `rgba(198, 40, 40, ${0.15 + (0.85 * v) / max})`;
      if (v / max > 0.5) td.style.color = "#fff";
    }
  }
  cible.replaceChildren(table);
}

async function rafraichir() {
  try {
    // /stats + signalements ouverts (pour la chaleur quartier × jour)
    const [stats, sigs] = await Promise.all([
      fetch(`${API_URL}/stats`).then((r) => r.json()),
      fetch(`${API_URL}/signalements?statut=ouvert`).then((r) => r.json()),
    ]);
    const pannes = sigs.filter((s) => s.type === "panne");
    stats.pannes_par_quartier.forEach((d) => quartiersVus.add(d.quartier));
    pannes.forEach((s) => s.quartier && quartiersVus.add(s.quartier));
    const quartiers = [...quartiersVus].sort();
    const parQ = quartiers.map((q) => ({
      quartier: q,
      total: (stats.pannes_par_quartier.find((d) => d.quartier === q) || { total: 0 }).total,
    }));

    document.getElementById("g-ouverts").textContent = t("ch_ouverts", { n: stats.total_ouverts });
    const gq = document.getElementById("g-quartier"), gc = document.getElementById("g-chaleur");
    if (quartiers.length) { barres(gq, parQ); chaleur(gc, quartiers, pannes); }
    else { gq.textContent = t("ch_vide"); gc.textContent = t("ch_vide"); }
    courbe(document.getElementById("g-jours"), stats.pannes_par_jour);
  } catch {
    document.getElementById("g-ouverts").textContent = t("adm_err");
  }
}

// Recharge quand la liste change (chargement, réparation), appels regroupés
let attente = null;
new MutationObserver(() => {
  clearTimeout(attente);
  attente = setTimeout(rafraichir, 300);
}).observe(document.getElementById("liste"), { childList: true });
