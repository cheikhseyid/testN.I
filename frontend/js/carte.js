// Accueil : bandeau d'alerte (/alertes), liste des points (cache localStorage + tri par distance)
// et carte Leaflet chargée à la demande. Tout le texte suit la langue (FR / AR, RTL).
(function () {
  const CACHE_KEY = "mawjoud.points.v1";
  const NOUAKCHOTT = [18.0858, -15.9785];
  const LEAFLET = {
    css: "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    cssSri: "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=",
    js: "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    jsSri: "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
  };
  // OSM standard tiles carry French/Latin place names; in Arabic we use a label-free basemap
  // and draw our own Arabic neighbourhood labels instead.
  const TILES = {
    fr: { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", subdomains: "abc",
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' },
    // Esri Light Gray Canvas, base layer only: streets and coastline, no text at all, no API key.
    ar: { url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
          subdomains: "", maxZoom: 16,
          attribution: '&copy; <a href="https://www.esri.com/">Esri</a>' },
  };
  const ETAT = {
    ok: { emoji: "🟢", color: "#1e8a4c" },
    faible: { emoji: "🟠", color: "#e08a00" },
    panne: { emoji: "🔴", color: "#c0392b" },
  };
  // French fallbacks, used until the i18n JSON has loaded.
  const FALLBACK = {
    "ptype.puits": "Puits", "ptype.borne": "Borne-fontaine", "ptype.citerne": "Citerne",
    "etat.ok": "En service", "etat.faible": "Débit faible", "etat.panne": "En panne",
    "home.sort_distance": "Triés par distance", "home.sort_quartier": "Triés par quartier",
    "home.locating": "Localisation en cours…", "home.offline": "Données hors ligne",
    "home.waking": "Le serveur démarre, patientez environ 1 minute…",
    "home.retrying": "Nouvel essai automatique…",
    "home.wake_failed": "Le serveur ne répond toujours pas. Réessayez dans quelques minutes.",
    "home.empty": "Aucun point d'eau trouvé.", "home.see_map": "Voir la carte",
    "home.hide_map": "Masquer la carte", "home.map_loading": "Chargement de la carte…",
    "home.map_error": "Impossible de charger la carte. Vérifiez votre connexion.",
    "home.report_btn": "Signaler", "home.you_are_here": "Vous êtes ici",
    "home.zoom_in": "Zoomer", "home.zoom_out": "Dézoomer", "home.close_popup": "Fermer",
    "alert.banner": "⚠️ Pénurie à {q} : {n} points en panne",
    "unit.m": "m", "unit.km": "km",
  };
  // Seeded names look like "<Type> <Quartier> <n>"; rebuilt in the current language.
  const GENERATED_NAME = /^(Puits|Borne-fontaine|Citerne)\s+(.+?)\s+(\d+)$/;

  const $ = (sel) => document.querySelector(sel);
  const listEl = $("#points");
  const statusEl = $("#list-status");
  const searchEl = $("#search");
  const mapBtn = $("#map-toggle");
  const mapEl = $("#map");
  const bannerEl = $("#alert-banner");

  let points = [];
  let alertes = [];
  let userPos = null; // {lat, lon}
  let locating = false;
  let offline = false;
  let map = null, tileLayer = null, zoomControl = null, markersLayer = null, labelsLayer = null,
      userMarker = null, leafletPromise = null;

  // ---------- i18n helpers ----------
  const lang = () => (window.i18n && window.i18n.lang) || "fr";
  function tr(key, vars) {
    const v = window.i18n && window.i18n.t(key);
    const s = v && v !== key ? v : FALLBACK[key] || key;
    return vars ? s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? vars[k] : `{${k}}`)) : s;
  }
  function quartierLabel(q) {
    const v = window.i18n && window.i18n.t(`q.${q}`);
    return v && v !== `q.${q}` ? v : q;
  }
  function pointName(p) {
    const m = GENERATED_NAME.exec(p.nom);
    if (lang() === "fr" || !m || m[2] !== p.quartier) return p.nom; // free-text names are shown as entered
    return `${tr(`ptype.${p.type}`)} ${quartierLabel(p.quartier)} ${m[3]}`;
  }
  function numberFmt(opts) {
    return new Intl.NumberFormat(lang() === "ar" ? "ar-MR-u-nu-latn" : "fr-FR", opts);
  }

  // ---------- Cache ----------
  function readCache() {
    try {
      const c = JSON.parse(localStorage.getItem(CACHE_KEY));
      return c && Array.isArray(c.data) ? c.data : null;
    } catch (e) { return null; }
  }
  function writeCache(data) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify({ t: Date.now(), data })); } catch (e) { /* quota / private */ }
  }

  // ---------- Distance (Haversine) ----------
  function haversineKm(a, b) {
    const R = 6371;
    const rad = (d) => (d * Math.PI) / 180;
    const dLat = rad(b.lat - a.lat);
    const dLon = rad(b.lon - a.lon);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function formatDistance(km) {
    if (km < 1) {
      const m = Math.max(10, Math.round((km * 1000) / 10) * 10);
      return `${numberFmt().format(m)} ${tr("unit.m")}`;
    }
    return `${numberFmt({ maximumFractionDigits: 1 }).format(km)} ${tr("unit.km")}`;
  }

  function sorted(list) {
    const withDist = list.map((p) => ({ ...p, dist: userPos ? haversineKm(userPos, p) : null }));
    if (userPos) return withDist.sort((a, b) => a.dist - b.dist);
    return withDist.sort((a, b) =>
      quartierLabel(a.quartier).localeCompare(quartierLabel(b.quartier), lang()) ||
      pointName(a).localeCompare(pointName(b), lang(), { numeric: true })
    );
  }

  function filtered() {
    const q = (searchEl && searchEl.value.trim().toLowerCase()) || "";
    if (!q) return points;
    return points.filter((p) =>
      [p.quartier, p.nom, quartierLabel(p.quartier), pointName(p)].some((s) => s.toLowerCase().includes(q))
    );
  }

  // ---------- Alert banner ----------
  function renderBanner() {
    if (!bannerEl) return;
    const nf = numberFmt();
    bannerEl.replaceChildren(...alertes.map((a) => {
      const p = document.createElement("p");
      p.className = "alert";
      p.textContent = tr("alert.banner", { q: quartierLabel(a.quartier), n: nf.format(a.nb) });
      return p;
    }));
    bannerEl.hidden = alertes.length === 0;
  }

  async function loadAlertes() {
    try {
      alertes = await window.api.get("/alertes");
    } catch (e) {
      return; // keep whatever was shown; the list has its own offline notice
    }
    renderBanner();
  }

  // ---------- List rendering ----------
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function renderList() {
    const items = sorted(filtered());
    const frag = document.createDocumentFragment();
    if (!items.length) {
      frag.appendChild(el("li", "card muted", tr("home.empty")));
    }
    let lastQuartier = null;
    for (const p of items) {
      if (!userPos && p.quartier !== lastQuartier) {
        frag.appendChild(el("li", "list-group", quartierLabel(p.quartier)));
        lastQuartier = p.quartier;
      }
      const etat = ETAT[p.etat] || ETAT.ok;
      const li = el("li", `card point-card etat-${p.etat}`);
      const badge = el("span", "etat-dot", etat.emoji);
      badge.setAttribute("role", "img");
      badge.setAttribute("aria-label", tr(`etat.${p.etat}`));
      const body = el("div", "point-body");
      body.appendChild(el("strong", "point-name", pointName(p)));
      const meta = el("span", "point-meta", `${tr(`ptype.${p.type}`)} · ${tr(`etat.${p.etat}`)}`);
      if (userPos) meta.textContent += ` · ${quartierLabel(p.quartier)}`;
      body.appendChild(meta);
      li.appendChild(badge);
      li.appendChild(body);
      if (p.dist !== null) li.appendChild(el("span", "point-dist", formatDistance(p.dist)));
      frag.appendChild(li);
    }
    listEl.replaceChildren(frag);
    renderStatus();
  }

  function renderStatus() {
    const parts = [];
    if (locating && !userPos) parts.push(tr("home.locating"));
    else parts.push(tr(userPos ? "home.sort_distance" : "home.sort_quartier"));
    if (offline) parts.push(tr("home.offline"));
    if (waking) parts.push(tr("home.retrying"));
    statusEl.textContent = parts.join(" · ");
  }

  function showError(message) {
    if (points.length) return; // keep showing cached list
    listEl.replaceChildren(el("li", "card msg", message));
  }

  // ---------- Data ----------
  // The free Render instance sleeps: its first request can take ~1 min. While it wakes up we keep
  // the cached list (or a "server is starting" message) and retry on our own, so nobody has to reload.
  const RETRY_EVERY_MS = 10000;
  const RETRY_FOR_MS = 90000;
  let retryStartedAt = null;
  let retryTimer = null;
  let waking = false;

  function showWaking() {
    if (points.length) return; // the cached list stays visible
    listEl.replaceChildren(el("li", "card muted", tr("home.waking")));
  }

  async function refresh() {
    clearTimeout(retryTimer);
    try {
      const data = await window.api.get("/points");
      points = data;
      offline = false;
      waking = false;
      retryStartedAt = null;
      writeCache(data);
      renderList();
      updateMarkers();
      if (!alertes.length) loadAlertes(); // probably failed too while the server was asleep
    } catch (e) {
      if (retryStartedAt === null) retryStartedAt = Date.now();
      const canRetry = e.retryable && Date.now() - retryStartedAt + RETRY_EVERY_MS <= RETRY_FOR_MS;
      offline = points.length > 0;
      waking = canRetry;
      if (canRetry) {
        showWaking();
        retryTimer = setTimeout(refresh, RETRY_EVERY_MS);
      } else {
        showError(e.retryable ? tr("home.wake_failed") : e.message);
      }
      renderStatus();
    }
  }

  function locate() {
    if (!("geolocation" in navigator)) return;
    locating = true;
    renderStatus();
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        locating = false;
        userPos = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        renderList();
        updateUserMarker();
      },
      () => { locating = false; renderStatus(); },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 5 * 60 * 1000 }
    );
  }

  // ---------- Leaflet (lazy) ----------
  function loadLeaflet() {
    if (window.L) return Promise.resolve(window.L);
    if (leafletPromise) return leafletPromise;
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = LEAFLET.css;
    css.integrity = LEAFLET.cssSri;
    css.crossOrigin = "";
    document.head.appendChild(css);
    leafletPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = LEAFLET.js;
      s.integrity = LEAFLET.jsSri;
      s.crossOrigin = "";
      s.onload = () => resolve(window.L);
      s.onerror = () => { leafletPromise = null; s.remove(); reject(new Error("leaflet")); };
      document.head.appendChild(s);
    });
    return leafletPromise;
  }

  function popupContent(p) {
    const box = el("div", "popup");
    box.dir = document.documentElement.dir;
    box.lang = lang();
    box.appendChild(el("strong", null, pointName(p)));
    box.appendChild(el("div", null, `${tr(`ptype.${p.type}`)} · ${quartierLabel(p.quartier)}`));
    box.appendChild(el("div", null, `${(ETAT[p.etat] || ETAT.ok).emoji} ${tr(`etat.${p.etat}`)}`));
    const a = el("a", "btn btn-primary btn-small", tr("home.report_btn"));
    a.href = `signaler.html?point=${encodeURIComponent(p.id)}`;
    box.appendChild(a);
    return box;
  }

  function updateMarkers() {
    if (!map) return;
    markersLayer.clearLayers();
    const bounds = [];
    for (const p of points) {
      const c = (ETAT[p.etat] || ETAT.ok).color;
      window.L.circleMarker([p.lat, p.lon], {
        radius: 9, color: "#ffffff", weight: 2, fillColor: c, fillOpacity: 0.95,
      })
        .bindPopup(() => popupContent(p))
        .addTo(markersLayer);
      bounds.push([p.lat, p.lon]);
    }
    if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
    updateQuartierLabels();
  }

  function updateQuartierLabels() {
    if (!map) return;
    labelsLayer.clearLayers();
    const groups = {};
    for (const p of points) (groups[p.quartier] = groups[p.quartier] || []).push(p);
    for (const [q, pts] of Object.entries(groups)) {
      // Just north of the group's markers, so the label doesn't hide them.
      const lat = Math.max(...pts.map((p) => p.lat)) + 0.003;
      const lon = pts.reduce((s, p) => s + p.lon, 0) / pts.length;
      window.L.tooltip({ permanent: true, direction: "top", className: "q-label", interactive: false })
        .setLatLng([lat, lon])
        .setContent(quartierLabel(q))
        .addTo(labelsLayer);
    }
  }

  function updateUserMarker() {
    if (!map || !userPos) return;
    const ll = [userPos.lat, userPos.lon];
    if (userMarker) userMarker.setLatLng(ll);
    else userMarker = window.L.circleMarker(ll, { radius: 7, color: "#0b6fa4", weight: 3, fillColor: "#ffffff", fillOpacity: 1 }).addTo(map);
    userMarker.unbindTooltip().bindTooltip(tr("home.you_are_here"));
  }

  function applyMapLanguage() {
    // Tiles, zoom button tooltips and labels follow the language.
    if (!map) return;
    const L = window.L;
    const t = TILES[lang() === "ar" ? "ar" : "fr"];
    if (tileLayer) map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(t.url, { maxZoom: t.maxZoom || 19, subdomains: t.subdomains || "abc", attribution: t.attribution }).addTo(map);
    if (zoomControl) map.removeControl(zoomControl);
    zoomControl = L.control.zoom({
      position: document.documentElement.dir === "rtl" ? "topright" : "topleft",
      zoomInTitle: tr("home.zoom_in"),
      zoomOutTitle: tr("home.zoom_out"),
    }).addTo(map);
    map.attributionControl.setPrefix(false);
    map.closePopup();
    updateQuartierLabels();
    updateUserMarker();
  }

  async function toggleMap() {
    const opening = mapEl.hidden;
    mapEl.hidden = !opening;
    mapBtn.setAttribute("aria-expanded", String(opening));
    mapBtn.textContent = tr(opening ? "home.hide_map" : "home.see_map");
    if (!opening) return;
    if (map) { map.invalidateSize(); return; }
    mapEl.textContent = tr("home.map_loading");
    try {
      const L = await loadLeaflet();
      mapEl.textContent = "";
      map = L.map(mapEl, { zoomControl: false }).setView(NOUAKCHOTT, 12);
      markersLayer = L.layerGroup().addTo(map);
      labelsLayer = L.layerGroup().addTo(map);
      map.on("popupopen", (e) => { // Leaflet's close button is labelled "Close popup" in English
        const btn = e.popup.getElement() && e.popup.getElement().querySelector(".leaflet-popup-close-button");
        if (btn) { btn.setAttribute("aria-label", tr("home.close_popup")); btn.title = tr("home.close_popup"); }
      });
      applyMapLanguage();
      updateMarkers();
    } catch (e) {
      mapEl.textContent = tr("home.map_error");
    }
  }

  // ---------- Init ----------
  const cached = readCache();
  if (cached) {
    points = cached;
    renderList();
  }
  locate();
  refresh();
  loadAlertes();

  mapBtn.addEventListener("click", toggleMap);
  if (searchEl) searchEl.addEventListener("input", renderList);
  document.addEventListener("i18n:change", () => {
    if (points.length) renderList(); else { renderStatus(); if (waking) showWaking(); }
    renderBanner();
    mapBtn.textContent = tr(mapEl.hidden ? "home.see_map" : "home.hide_map");
    applyMapLanguage();
  });
})();
