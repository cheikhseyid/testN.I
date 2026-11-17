// Page "Signaler" : liste des points, compression de la photo, envoi du signalement.
(function () {
  const CACHE_KEY = "mawjoud.points.v1"; // même cache que la page d'accueil (carte.js)
  const MAX_SIDE = 800;
  const QUALITY = 0.6;
  const MAX_BYTES = 300 * 1024; // limite du serveur
  // The free Render instance sleeps and can take ~1 min to start.
  const POST_TIMEOUT_MS = 45000; // for the report itself
  const WAKE_FOR_MS = 60000;     // how long we keep trying to wake the server before sending

  const FALLBACK = {
    "report.point_choose": "Choisir un point d'eau",
    "report.sending": "Envoi en cours…",
    "report.sending_slow": "Envoi en cours… le serveur peut mettre jusqu'à 1 minute à démarrer.",
    "report.ok": "Merci ! Votre signalement a bien été envoyé.",
    "report.err_429": "Trop de signalements, réessayez dans 1 minute.",
    "report.err_point": "Choisissez un point d'eau.",
    "report.err_type": "Choisissez le type de problème.",
    "report.err_photo": "Impossible de lire cette photo. Essayez-en une autre.",
    "report.err_photo_big": "Photo trop lourde, même après compression. Essayez-en une autre.",
    "report.err_points": "Impossible de charger la liste des points d'eau.",
    "report.compressing": "Compression de la photo…",
  };

  const $ = (id) => document.getElementById(id);
  const form = $("report-form");
  const select = $("point_id");
  const texte = $("texte");
  const charCount = $("char-count");
  const photoInput = $("photo");
  const preview = $("photo-preview");
  const previewImg = $("photo-img");
  const photoSize = $("photo-size");
  const submitBtn = $("submit-btn");
  const msgEl = $("report-msg");

  let photoBlob = null; // compressed JPEG ready to send
  let photoJob = null;  // pending compression
  let lastMsg = null;   // {key | text, ok} — re-rendered on language change
  const wantedPoint = new URLSearchParams(location.search).get("point");

  function tr(key) {
    const v = window.i18n && window.i18n.t(key);
    return v && v !== key ? v : FALLBACK[key] || key;
  }

  // ---------- Messages ----------
  function showMsg(m) {
    lastMsg = m;
    if (!m) { msgEl.textContent = ""; msgEl.className = "msg"; return; }
    msgEl.textContent = m.key ? tr(m.key) : m.text;
    // info = neutral grey text (waiting), ok = green, otherwise red error box
    msgEl.className = m.info ? "muted" : "msg" + (m.ok ? " ok" : "");
  }

  // ---------- Points ----------
  function readCache() {
    try {
      const c = JSON.parse(localStorage.getItem(CACHE_KEY));
      return c && Array.isArray(c.data) ? c.data : null;
    } catch (e) { return null; }
  }

  function fillPoints(points) {
    const lang = (window.i18n && window.i18n.lang) || "fr";
    const current = select.value || wantedPoint || "";
    const byQuartier = {};
    for (const p of points) (byQuartier[p.quartier] = byQuartier[p.quartier] || []).push(p);

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.dataset.i18n = "report.point_choose";
    placeholder.textContent = tr("report.point_choose");
    const frag = document.createDocumentFragment();
    frag.appendChild(placeholder);

    for (const q of Object.keys(byQuartier).sort((a, b) => a.localeCompare(b, lang))) {
      const group = document.createElement("optgroup");
      group.label = q;
      byQuartier[q]
        .sort((a, b) => a.nom.localeCompare(b.nom, lang, { numeric: true }))
        .forEach((p) => {
          const o = document.createElement("option");
          o.value = String(p.id);
          o.textContent = p.nom;
          group.appendChild(o);
        });
      frag.appendChild(group);
    }
    select.replaceChildren(frag);
    if (current && select.querySelector(`option[value="${CSS.escape(current)}"]`)) select.value = current;
  }

  async function loadPoints() {
    const cached = readCache();
    if (cached) fillPoints(cached);
    try {
      const data = await window.api.get("/points");
      try { localStorage.setItem(CACHE_KEY, JSON.stringify({ t: Date.now(), data })); } catch (e) { /* quota */ }
      fillPoints(data);
    } catch (e) {
      if (!cached) showMsg({ key: "report.err_points" });
    }
  }

  // ---------- Photo compression ----------
  async function decode(file) {
    // createImageBitmap applies EXIF orientation (phones store photos rotated).
    if (window.createImageBitmap) {
      try { return await createImageBitmap(file, { imageOrientation: "from-image" }); } catch (e) { /* fallback below */ }
    }
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("decode")); };
      img.src = url;
    });
  }

  function toBlob(canvas, quality) {
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
  }

  async function compress(file) {
    const img = await decode(file);
    const w = img.width, h = img.height;
    const scale = Math.min(1, MAX_SIDE / Math.max(w, h));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(w * scale));
    canvas.height = Math.max(1, Math.round(h * scale));
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff"; // transparent PNG → white background instead of black
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    if (img.close) img.close();

    let blob = await toBlob(canvas, QUALITY);
    for (const q of [0.45, 0.3]) { // rare: very detailed image still above the limit
      if (blob && blob.size <= MAX_BYTES) break;
      blob = await toBlob(canvas, q);
    }
    if (!blob) throw new Error("encode");
    return { blob, width: canvas.width, height: canvas.height };
  }

  function formatKB(bytes) {
    return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} Mo` : `${Math.round(bytes / 1024)} Ko`;
  }

  function clearPhoto() {
    photoBlob = null;
    photoJob = null;
    photoInput.value = "";
    if (previewImg.src) URL.revokeObjectURL(previewImg.src);
    previewImg.removeAttribute("src");
    preview.hidden = true;
  }

  photoInput.addEventListener("change", () => {
    const file = photoInput.files && photoInput.files[0];
    if (!file) return;
    showMsg(null);
    photoBlob = null;
    photoSize.textContent = tr("report.compressing");
    preview.hidden = false;
    const job = (photoJob = compress(file)
      .then((res) => {
        if (job !== photoJob) return; // replaced by a newer photo
        if (res.blob.size > MAX_BYTES) { clearPhoto(); showMsg({ key: "report.err_photo_big" }); return; }
        photoBlob = res.blob;
        if (previewImg.src) URL.revokeObjectURL(previewImg.src);
        previewImg.src = URL.createObjectURL(res.blob);
        photoSize.textContent = `${formatKB(file.size)} → ${formatKB(res.blob.size)} · ${res.width}×${res.height}`;
      })
      .catch(() => {
        if (job !== photoJob) return;
        clearPhoto();
        showMsg({ key: "report.err_photo" });
      }));
  });

  $("photo-remove").addEventListener("click", clearPhoto);

  // ---------- Text counter ----------
  function updateCount() { charCount.textContent = `${texte.value.length} / 500`; }
  texte.addEventListener("input", updateCount);

  // ---------- Submit ----------
  function setBusy(busy) {
    submitBtn.disabled = busy;
    submitBtn.classList.toggle("is-busy", busy);
  }

  // Wake a sleeping server with a side-effect-free GET /health before sending the report.
  // This way the POST is sent only once the server answers: a report can't be created on the
  // server after the browser gave up, so the user is never tempted to send it twice.
  async function wakeServer() {
    const deadline = Date.now() + WAKE_FOR_MS;
    for (;;) {
      try {
        await window.api.get("/health", { timeout: Math.max(5000, deadline - Date.now()) });
        return;
      } catch (e) {
        if (!e.retryable || Date.now() + 3000 >= deadline) throw e;
        await new Promise((r) => setTimeout(r, 3000)); // refused while starting: try again shortly
      }
    }
  }

  let sending = false;

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (sending || submitBtn.disabled) return; // no double send (double click, Enter key…)

    const type = form.querySelector('input[name="type"]:checked');
    if (!select.value) { showMsg({ key: "report.err_point" }); select.focus(); return; }
    if (!type) { showMsg({ key: "report.err_type" }); form.querySelector('input[name="type"]').focus(); return; }

    sending = true;
    setBusy(true);
    showMsg({ key: "report.sending_slow", info: true });
    try {
      if (photoJob) await photoJob; // wait for an in-progress compression
      const fd = new FormData();
      fd.append("point_id", select.value);
      fd.append("type", type.value);
      fd.append("texte", texte.value.trim());
      if (photoBlob) fd.append("photo", photoBlob, "photo.jpg");

      await wakeServer();
      await window.api.post("/signalements", fd, { timeout: POST_TIMEOUT_MS });

      const keepPoint = select.value;
      form.reset();
      select.value = keepPoint;
      clearPhoto();
      updateCount();
      showMsg({ key: "report.ok", ok: true });
    } catch (e) {
      showMsg(e.status === 429 ? { key: "report.err_429" } : { text: e.message });
    } finally {
      sending = false;
      setBusy(false);
    }
  });

  // ---------- Init ----------
  document.addEventListener("i18n:change", () => {
    if (lastMsg && lastMsg.key) showMsg(lastMsg);
  });
  updateCount();
  loadPoints();
})();
