// Carte des points d'eau
document.documentElement.lang = LANG;
document.documentElement.dir = LANG === "ar" ? "rtl" : "ltr";
document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));

const bandeau = document.getElementById("bandeau");
const EMOJI = { ok: "🟢", faible: "🟠", panne: "🔴" };

// Centre de Nouakchott
const carte = L.map("carte").setView([18.086, -15.975], 12);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "© OpenStreetMap",
}).addTo(carte);

function icone(txt) {
  return L.divIcon({ className: "pin", html: txt, iconSize: [24, 24], iconAnchor: [12, 12] });
}

// Distance en mètres (haversine)
function distance(a, b, c, d) {
  const R = 6371000, r = Math.PI / 180;
  const x = Math.sin(((c - a) * r) / 2) ** 2
    + Math.cos(a * r) * Math.cos(c * r) * Math.sin(((d - b) * r) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

function plusProche(points, lat, lon) {
  let best = null, min = Infinity;
  for (const p of points) {
    if (p.etat !== "ok") continue;
    const dist = distance(lat, lon, p.lat, p.lon);
    if (dist < min) { min = dist; best = p; }
  }
  if (!best) { bandeau.textContent = t("aucun"); return; }
  bandeau.textContent = t("proche", { nom: best.nom, dist: Math.round(min) });
}

async function init() {
  bandeau.textContent = t("chargement");
  let points;
  try {
    const r = await fetch(`${API_URL}/points`); // un seul appel API
    if (!r.ok) throw new Error(r.status); // erreur API (500…)
    points = await r.json();
  } catch {
    bandeau.textContent = t("erreur");
    return;
  }

  for (const p of points) {
    L.marker([p.lat, p.lon], { icon: icone(EMOJI[p.etat] || "⚪") })
      .addTo(carte)
      .bindPopup(() => {
        // Construit en DOM (textContent) pour éviter toute injection HTML
        const div = document.createElement("div");
        const b = document.createElement("b");
        b.textContent = p.nom;
        div.append(b, document.createElement("br"),
          `${t("type_" + p.type)} · ${t("etat_" + p.etat)} · ${p.quartier}`);
        return div;
      });
  }

  if (!navigator.geolocation) { bandeau.textContent = t("geo_refus"); return; }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude: lat, longitude: lon } = pos.coords;
      L.marker([lat, lon], { icon: icone("📍") }).addTo(carte).bindPopup(t("vous"));
      plusProche(points, lat, lon);
    },
    () => { bandeau.textContent = t("geo_refus"); },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
  );
}

init();
