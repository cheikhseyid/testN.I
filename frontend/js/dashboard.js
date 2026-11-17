// Tableau de bord gestionnaire : connexion (JWT en sessionStorage), chiffres clés (/stats, /alertes),
// signalements ouverts (GET /signalements) et clôture (PATCH /signalements/{id}).
(function () {
  const cfg = window.MAWJOUD_CONFIG || {};
  const BASE = (cfg.API_BASE || "").replace(/\/$/, "");
  const TIMEOUT = cfg.TIMEOUT_MS || 8000;
  const SESSION_KEY = "mawjoud.admin";
  const POINTS_CACHE_KEY = "mawjoud.points.v1"; // cache of the home page (carte.js)
  const URG_RANK = { haute: 3, moyenne: 2, basse: 1 };

  const $ = (id) => document.getElementById(id);
  const loginView = $("login-view");
  const dashView = $("dash-view");
  const loginForm = $("login-form");
  const loginBtn = $("login-btn");
  const loginMsg = $("login-msg");
  const dashMsg = $("dash-msg");
  const tbody = $("reports-body");

  let reports = [];   // open reports, sorted
  let stats = null;
  let alertes = [];
  let lastDashMsg = null; // {key, vars, ok} — re-rendered on language change
  let lastLoginMsg = null;

  // ---------- i18n helpers ----------
  function tr(key, vars) {
    const raw = window.i18n ? window.i18n.t(key) : key;
    return String(raw).replace(/\{(\w+)\}/g, (_, k) => (vars && vars[k] !== undefined ? vars[k] : `{${k}}`));
  }
  function locale() {
    return (window.i18n && window.i18n.lang) === "ar" ? "ar-MR-u-nu-latn" : "fr-FR";
  }
  function setMsg(el, m, store) {
    if (store === "dash") lastDashMsg = m; else lastLoginMsg = m;
    el.textContent = m ? (m.key ? tr(m.key, m.vars) : m.text) : "";
    el.className = "msg" + (m && m.ok ? " ok" : "");
  }

  // ---------- Session ----------
  function getSession() {
    try {
      const s = JSON.parse(sessionStorage.getItem(SESSION_KEY));
      if (s && s.token && s.exp > Date.now() + 30000) return s;
    } catch (e) { /* ignore */ }
    return null;
  }
  function saveSession(token, expiresIn) {
    try { sessionStorage.setItem(SESSION_KEY, JSON.stringify({ token, exp: Date.now() + expiresIn * 1000 })); } catch (e) { /* ignore */ }
  }
  function clearSession() {
    try { sessionStorage.removeItem(SESSION_KEY); } catch (e) { /* ignore */ }
  }

  // ---------- Authenticated requests ----------
  class HttpError extends Error {
    constructor(message, status) { super(message); this.status = status; }
  }

  async function authed(method, path, body) {
    const session = getSession();
    if (!session) { showLogin({ key: "dash.err_expired" }); throw new HttpError("expired", 401); }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT);
    const headers = { Accept: "application/json", Authorization: `Bearer ${session.token}` };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let res;
    try {
      res = await fetch(BASE + path, { method, headers, signal: controller.signal, body: body !== undefined ? JSON.stringify(body) : undefined });
    } catch (e) {
      throw new HttpError(tr(e.name === "AbortError" ? "err.timeout" : "err.network"), 0);
    } finally {
      clearTimeout(timer);
    }
    if (res.status === 401) {
      clearSession();
      showLogin({ key: "dash.err_expired" });
      throw new HttpError("expired", 401);
    }
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = data && typeof data.detail === "string" ? ` (${data.detail})` : "";
      throw new HttpError(tr(res.status >= 500 ? "err.server" : "err.request") + detail, res.status);
    }
    return data;
  }

  // ---------- Views ----------
  function showLogin(msg) {
    dashView.hidden = true;
    loginView.hidden = false;
    setMsg(loginMsg, msg || null, "login");
    $("login-email").focus();
  }
  function showDash() {
    loginView.hidden = true;
    dashView.hidden = false;
    loadAll();
  }

  // ---------- Login ----------
  loginForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const email = $("login-email").value.trim();
    const password = $("login-password").value;
    if (!email || !password) { setMsg(loginMsg, { key: "dash.err_fields" }, "login"); return; }
    loginBtn.disabled = true;
    loginBtn.classList.add("is-busy");
    setMsg(loginMsg, null, "login");
    try {
      const res = await window.api.post("/auth/login", { email, password });
      saveSession(res.access_token, res.expires_in);
      $("login-password").value = "";
      showDash();
    } catch (e) {
      const key = e.status === 401 ? "dash.err_login" : e.status === 429 ? "dash.err_login_429" : null;
      setMsg(loginMsg, key ? { key } : { text: e.message }, "login");
    } finally {
      loginBtn.disabled = false;
      loginBtn.classList.remove("is-busy");
    }
  });

  $("logout-btn").addEventListener("click", () => {
    clearSession();
    reports = [];
    showLogin();
  });

  // ---------- Data ----------
  async function loadAll() {
    setMsg(dashMsg, null, "dash");
    const [s, r, a] = await Promise.allSettled([
      window.api.get("/stats"),
      authed("GET", "/signalements?statut=ouvert"),
      window.api.get("/alertes"),
    ]);
    if (r.status === "rejected" && r.reason && r.reason.status === 401) return; // back to login
    if (s.status === "fulfilled") stats = s.value;
    if (a.status === "fulfilled") alertes = a.value;
    if (r.status === "fulfilled") reports = sortReports(r.value);
    const failed = [s, r, a].find((x) => x.status === "rejected");
    if (failed) setMsg(dashMsg, { text: failed.reason.message }, "dash");
    renderKpis();
    renderTable();
  }

  async function refreshStats() {
    try {
      [stats, alertes] = await Promise.all([window.api.get("/stats"), window.api.get("/alertes")]);
      renderKpis();
    } catch (e) { /* keep previous figures */ }
  }

  function sortReports(list) {
    return list.slice().sort((a, b) =>
      (URG_RANK[b.urgence] || 0) - (URG_RANK[a.urgence] || 0) ||
      b.score_urgence - a.score_urgence ||
      new Date(a.cree_le) - new Date(b.cree_le));
  }

  // ---------- KPIs ----------
  function currentMondayISO() {
    const d = new Date();
    const day = (d.getUTCDay() + 6) % 7; // Monday = 0 (weeks are computed in UTC by the API)
    return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - day)).toISOString().slice(0, 10);
  }

  function renderKpis() {
    if (!stats) return;
    const nf = new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 });
    const week = stats.par_semaine.find((w) => w.semaine === currentMondayISO());
    const weekPannes = week ? week.pannes : 0;
    const top = stats.par_quartier[0]; // sorted by pannes desc by the API

    $("kpi-week").textContent = nf.format(weekPannes);
    $("kpi-open").textContent = nf.format(stats.signalements_ouverts);
    $("kpi-repair").textContent = stats.temps_moyen_reparation_h == null ? "–"
      : `${nf.format(stats.temps_moyen_reparation_h)} ${tr("unit.h")}`;
    $("kpi-top").textContent = top ? top.quartier : "–";

    const weekKey = weekPannes === 0 ? "dash.sentence_week_zero" : weekPannes === 1 ? "dash.sentence_week_one" : "dash.sentence_week";
    const parts = [tr(weekKey, { n: nf.format(weekPannes) })];
    if (top) parts.push(tr("dash.sentence_top", { q: top.quartier, n: nf.format(top.pannes) }));
    $("kpi-sentence").textContent = parts.join(" ");

    const box = $("alerts");
    box.replaceChildren(...alertes.map((a) => {
      const p = document.createElement("p");
      p.className = "alert";
      p.textContent = `⚠️ ${tr("dash.alert", { q: a.quartier, n: nf.format(a.nb) })}`;
      return p;
    }));
  }

  // ---------- Table ----------
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function renderTable() {
    const df = new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    const frag = document.createDocumentFragment();
    if (!reports.length) {
      const tr0 = el("tr");
      const td = el("td", "muted", tr("dash.empty"));
      td.colSpan = 6;
      tr0.appendChild(td);
      frag.appendChild(tr0);
    }
    for (const r of reports) {
      const row = el("tr");
      row.dataset.id = r.id;

      const tdUrg = el("td");
      tdUrg.dataset.label = tr("dash.col_urgence");
      tdUrg.appendChild(el("span", `badge urg-${r.urgence || "moyenne"}`, tr(`urg.${r.urgence || "moyenne"}`)));

      const tdPoint = el("td");
      tdPoint.dataset.label = tr("dash.col_point");
      tdPoint.appendChild(el("strong", null, r.point_nom));
      tdPoint.appendChild(el("small", "muted cell-sub", r.quartier));

      const tdPb = el("td");
      tdPb.dataset.label = tr("dash.col_probleme");
      tdPb.appendChild(el("span", "cell-type", tr(`type.${r.type}`)));
      if (r.texte) tdPb.appendChild(el("span", "cell-text", r.texte));

      const tdDate = el("td", "cell-date", df.format(new Date(r.cree_le)));
      tdDate.dataset.label = tr("dash.col_date");

      const tdPhoto = el("td");
      tdPhoto.dataset.label = tr("dash.col_photo");
      if (r.a_photo) {
        const url = `${BASE}/signalements/${encodeURIComponent(r.id)}/photo`;
        const a = el("a", "thumb-link");
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener";
        const img = el("img", "thumb");
        img.src = url;
        img.alt = tr("dash.photo_alt", { point: r.point_nom });
        img.loading = "lazy";
        img.width = 56;
        img.height = 56;
        a.appendChild(img);
        tdPhoto.appendChild(a);
      } else {
        tdPhoto.appendChild(el("span", "muted", "—"));
      }

      const tdAct = el("td", "cell-action");
      const btn = el("button", "btn btn-small btn-repair", `✓ ${tr("dash.repaired_btn")}`);
      btn.type = "button";
      btn.dataset.id = r.id;
      tdAct.appendChild(btn);

      row.append(tdUrg, tdPoint, tdPb, tdDate, tdPhoto, tdAct);
      frag.appendChild(row);
    }
    tbody.replaceChildren(frag);
  }

  // ---------- Repair ----------
  async function syncPointCache(pointId) {
    // Update the home page cache so index.html shows the new colour immediately.
    try {
      const p = await window.api.get(`/points/${encodeURIComponent(pointId)}`);
      const raw = localStorage.getItem(POINTS_CACHE_KEY);
      if (raw) {
        const cache = JSON.parse(raw);
        const item = cache.data && cache.data.find((x) => x.id === p.id);
        if (item) { item.etat = p.etat; localStorage.setItem(POINTS_CACHE_KEY, JSON.stringify(cache)); }
      }
      return p;
    } catch (e) {
      return null;
    }
  }

  tbody.addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".btn-repair");
    if (!btn || btn.disabled) return;
    const id = Number(btn.dataset.id);
    const report = reports.find((r) => r.id === id);
    if (!report) return;
    btn.disabled = true;
    btn.textContent = tr("dash.repairing");
    setMsg(dashMsg, null, "dash");
    try {
      await authed("PATCH", `/signalements/${id}`, { statut: "repare" });
    } catch (e) {
      if (e.status !== 401) {
        btn.disabled = false;
        btn.textContent = `✓ ${tr("dash.repaired_btn")}`;
        setMsg(dashMsg, { text: e.message }, "dash");
      }
      return;
    }
    const row = btn.closest("tr");
    row.classList.add("is-removing");
    reports = reports.filter((r) => r.id !== id);
    setTimeout(renderTable, 250);

    const point = await syncPointCache(report.point_id);
    const remaining = reports.filter((r) => r.point_id === report.point_id).length;
    if (point && point.etat === "ok") {
      setMsg(dashMsg, { key: "dash.repaired_ok", vars: { point: report.point_nom }, ok: true }, "dash");
    } else {
      setMsg(dashMsg, { key: remaining === 1 ? "dash.repaired_still_one" : "dash.repaired_still",
                        vars: { point: report.point_nom, n: remaining }, ok: true }, "dash");
    }
    refreshStats();
  });

  $("refresh-btn").addEventListener("click", loadAll);

  // ---------- Init ----------
  document.addEventListener("i18n:change", () => {
    if (!dashView.hidden) { renderKpis(); renderTable(); }
    setMsg(dashMsg, lastDashMsg, "dash");
    setMsg(loginMsg, lastLoginMsg, "login");
  });

  if (getSession()) showDash(); else showLogin();
})();
