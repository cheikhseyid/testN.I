// Dashboard charts: Chart.js (by quartier / week / type) + Leaflet heat map, from GET /stats (+ /points for coordinates).
// Libraries are injected only once the dashboard is visible (after login), so the login screen stays light.
(function () {
  const cfg = window.MAWJOUD_CONFIG || {};
  const LIBS = {
    chart: { src: "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js" },
    leafletCss: { href: "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css", sri: "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" },
    leaflet: { src: "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js", sri: "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" },
    heat: { src: "https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js" },
  };
  const COLORS = {
    panne: "#c0392b", signalements: "#0b6fa4",
    types: { panne: "#c0392b", faible_debit: "#e08a00", eau_trouble: "#8d6e63", autre: "#6c7a89" },
  };
  const NOUAKCHOTT = [18.0858, -15.9785];

  const $ = (id) => document.getElementById(id);
  const dashView = $("dash-view");
  const msgEl = $("charts-msg");
  const heatEl = $("heatmap");

  let stats = null, points = null;
  let charts = {};
  let map = null, heatLayer = null;
  let loading = null;

  // ---------- helpers ----------
  const lang = () => (window.i18n && window.i18n.lang) || "fr";
  const isRtl = () => document.documentElement.dir === "rtl";
  const locale = () => (lang() === "ar" ? "ar-MR-u-nu-latn" : "fr-FR");
  function tr(key, fallback) {
    const v = window.i18n && window.i18n.t(key);
    return v && v !== key ? v : fallback !== undefined ? fallback : key;
  }
  const quartierLabel = (q) => tr(`q.${q}`, q);

  function loadScript(src, sri) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) return resolve();
      const s = document.createElement("script");
      s.src = src;
      if (sri) { s.integrity = sri; s.crossOrigin = "anonymous"; }
      s.onload = resolve;
      s.onerror = () => { s.remove(); reject(new Error(src)); };
      document.head.appendChild(s);
    });
  }
  function loadCss(href, sri) {
    if (document.querySelector(`link[href="${href}"]`)) return;
    const l = document.createElement("link");
    l.rel = "stylesheet"; l.href = href;
    if (sri) { l.integrity = sri; l.crossOrigin = "anonymous"; }
    document.head.appendChild(l);
  }

  // ---------- data + libs ----------
  async function load() {
    if (loading) return loading;
    loading = (async () => {
      msgEl.textContent = "";
      heatEl.textContent = tr("common.loading", "Chargement…");
      loadCss(LIBS.leafletCss.href, LIBS.leafletCss.sri);
      const leafletReady = loadScript(LIBS.leaflet.src, LIBS.leaflet.sri).then(() => loadScript(LIBS.heat.src));
      const [s, p, chartLib, leafletLib] = await Promise.allSettled([
        window.api.get("/stats"), window.api.get("/points"), loadScript(LIBS.chart.src), leafletReady,
      ]);
      if (s.status === "rejected") throw s.reason;
      stats = s.value;
      points = p.status === "fulfilled" ? p.value : [];
      if (chartLib.status === "fulfilled") renderCharts();
      else msgEl.textContent = tr("chart.lib_error", "Impossible de charger les graphiques.");
      if (leafletLib.status === "fulfilled" && p.status === "fulfilled") renderHeat();
      else heatEl.textContent = tr("chart.map_error", "Impossible de charger la carte.");
    })().catch((e) => {
      msgEl.textContent = e.message;
    }).finally(() => { loading = null; });
    return loading;
  }

  // ---------- Chart.js ----------
  function baseOptions({ legend = false, yTitle = "" } = {}) {
    const rtl = isRtl();
    const font = { family: getComputedStyle(document.body).fontFamily };
    return {
      responsive: true,
      maintainAspectRatio: false,
      locale: locale(),
      animation: { duration: 300 },
      plugins: {
        legend: { display: legend, rtl, position: "bottom", labels: { font } },
        tooltip: { rtl, textDirection: rtl ? "rtl" : "ltr", titleFont: font, bodyFont: font },
      },
      scales: {
        x: { reverse: rtl, ticks: { font }, grid: { display: false } },
        y: { beginAtZero: true, position: rtl ? "right" : "left", ticks: { precision: 0, font },
             title: { display: !!yTitle, text: yTitle, font } },
      },
    };
  }

  function makeChart(id, config) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new window.Chart($(id), config);
  }

  function renderCharts() {
    if (!stats || !window.Chart) return;
    const nPannes = tr("chart.pannes", "Pannes");
    const nSig = tr("chart.signalements", "Signalements");

    // Pannes par quartier (bars; API already sorts by pannes desc)
    makeChart("chart-quartier", {
      type: "bar",
      data: {
        labels: stats.par_quartier.map((q) => quartierLabel(q.quartier)),
        datasets: [{ label: nPannes, data: stats.par_quartier.map((q) => q.pannes), backgroundColor: COLORS.panne, borderRadius: 4 }],
      },
      options: baseOptions({ yTitle: nPannes }),
    });

    // Par semaine (line: pannes + all reports)
    const df = new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short", timeZone: "UTC" });
    makeChart("chart-semaine", {
      type: "line",
      data: {
        labels: stats.par_semaine.map((w) => df.format(new Date(w.semaine + "T00:00:00Z"))),
        datasets: [
          { label: nPannes, data: stats.par_semaine.map((w) => w.pannes), borderColor: COLORS.panne,
            backgroundColor: COLORS.panne + "22", fill: true, tension: 0.3, pointRadius: 3 },
          { label: nSig, data: stats.par_semaine.map((w) => w.signalements), borderColor: COLORS.signalements,
            backgroundColor: COLORS.signalements, tension: 0.3, pointRadius: 3 },
        ],
      },
      options: (() => {
        const o = baseOptions({ legend: true });
        o.scales.x.title = { display: true, text: tr("chart.semaine_axis", "Semaine du"), font: o.scales.x.ticks.font };
        return o;
      })(),
    });

    // Par type (bars)
    makeChart("chart-type", {
      type: "bar",
      data: {
        labels: stats.par_type.map((t) => tr(`type.${t.type}`, t.type)),
        datasets: [{ label: nSig, data: stats.par_type.map((t) => t.signalements),
                     backgroundColor: stats.par_type.map((t) => COLORS.types[t.type] || "#999"), borderRadius: 4 }],
      },
      options: baseOptions({ yTitle: nSig }),
    });
  }

  // ---------- Heat map ----------
  function heatPoints() {
    // /stats gives pannes per quartier; spread them over that quartier's water points (from /points).
    const byQ = {};
    for (const p of points) (byQ[p.quartier] = byQ[p.quartier] || []).push(p);
    const out = [];
    for (const q of stats.par_quartier) {
      const pts = byQ[q.quartier] || [];
      for (const p of pts) out.push([p.lat, p.lon, q.pannes / pts.length]);
    }
    return out;
  }

  function renderHeat() {
    if (!window.L || !window.L.heatLayer || !stats) return;
    const data = heatPoints();
    const max = Math.max(1, ...data.map((d) => d[2]));
    if (!map) {
      heatEl.textContent = "";
      map = window.L.map(heatEl, { scrollWheelZoom: false }).setView(NOUAKCHOTT, 12);
      window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);
    }
    if (heatLayer) map.removeLayer(heatLayer);
    heatLayer = window.L.heatLayer(data, {
      radius: 38, blur: 28, maxZoom: 13, max,
      gradient: { 0.2: "#2b83ba", 0.4: "#abdda4", 0.6: "#ffffbf", 0.8: "#fdae61", 1: "#d7191c" },
    }).addTo(map);
    if (data.length) map.fitBounds(data.map((d) => [d[0], d[1]]), { padding: [20, 20] });
    setTimeout(() => map.invalidateSize(), 50);
  }

  // ---------- lifecycle ----------
  function onVisible() {
    if (!dashView.hidden) load();
  }
  new MutationObserver(onVisible).observe(dashView, { attributes: true, attributeFilter: ["hidden"] });
  onVisible();

  const refreshBtn = $("refresh-btn");
  if (refreshBtn) refreshBtn.addEventListener("click", () => { if (!dashView.hidden) load(); });

  document.addEventListener("i18n:change", () => {
    if (dashView.hidden || !stats) return;
    renderCharts(); // labels, number/date locale and RTL axes follow the language
  });
})();
