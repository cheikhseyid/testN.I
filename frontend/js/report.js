// Page de signalement
// Textes propres à cette page (complètent I18N de config.js)
Object.assign(I18N.fr, {
  sig_titre: "Signaler un problème",
  sig_point: "Point d'eau",
  sig_type: "Problème",
  sig_t_panne: "Panne", sig_t_eau_trouble: "Eau trouble",
  sig_t_faible_debit: "Faible débit", sig_t_autre: "Autre",
  sig_texte: "Détails (facultatif)",
  sig_photo: "Photo (facultative)",
  sig_poids: "Photo compressée : {ko} Ko",
  sig_envoyer: "Envoyer",
  sig_envoi: "Envoi…",
  sig_ok: "Merci ! Signalement envoyé.",
  sig_413: "Photo trop lourde, essayez une autre photo.",
  sig_429: "Trop de signalements. Réessayez dans une minute.",
  sig_err: "Échec de l'envoi. Vérifiez la connexion.",
  sig_photo_err: "Photo illisible.",
});
Object.assign(I18N.ar, {
  sig_titre: "الإبلاغ عن مشكلة",
  sig_point: "نقطة المياه",
  sig_type: "المشكلة",
  sig_t_panne: "عطل", sig_t_eau_trouble: "مياه عكرة",
  sig_t_faible_debit: "تدفق ضعيف", sig_t_autre: "أخرى",
  sig_texte: "تفاصيل (اختياري)",
  sig_photo: "صورة (اختيارية)",
  sig_poids: "الصورة المضغوطة: {ko} كيلوبايت",
  sig_envoyer: "إرسال",
  sig_envoi: "جارٍ الإرسال…",
  sig_ok: "شكرًا! تم إرسال البلاغ.",
  sig_413: "الصورة كبيرة جدًا، جرّب صورة أخرى.",
  sig_429: "بلاغات كثيرة. أعد المحاولة بعد دقيقة.",
  sig_err: "فشل الإرسال. تحقّق من الاتصال.",
  sig_photo_err: "تعذّرت قراءة الصورة.",
});

document.documentElement.lang = LANG;
document.documentElement.dir = LANG === "ar" ? "rtl" : "ltr";
document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));

const $ = (id) => document.getElementById(id);
const MAX_OCTETS = 80 * 1024; // 80 Ko
let photoB64 = null;

function message(cle, ok) {
  $("message").textContent = t(cle);
  $("message").className = ok ? "ok" : "err";
}

// Liste des points (un appel)
async function chargerPoints() {
  try {
    const r = await fetch(`${API_URL}/points`);
    if (!r.ok) throw new Error(r.status); // erreur API (500…)
    const points = await r.json();
    for (const p of points) {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = `${p.nom} — ${p.quartier}`;
      $("point").append(o);
    }
    // Pré-sélection via ?point=ID
    const id = new URLSearchParams(location.search).get("point");
    if (id) $("point").value = id;
  } catch {
    message("sig_err", false);
  }
}

// Redimensionne (800 px max) et compresse en JPEG jusqu'à <= 80 Ko
async function compresser(fichier) {
  const img = await createImageBitmap(fichier);
  let echelle = Math.min(1, 800 / Math.max(img.width, img.height));
  let qualite = 0.6;
  const canvas = document.createElement("canvas");
  for (let i = 0; i < 8; i++) {
    canvas.width = Math.round(img.width * echelle);
    canvas.height = Math.round(img.height * echelle);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    const b64 = canvas.toDataURL("image/jpeg", qualite).split(",")[1];
    const octets = Math.floor((b64.length * 3) / 4);
    if (octets <= MAX_OCTETS) return { b64, octets };
    // Trop lourd : baisse la qualité puis la taille
    if (qualite > 0.4) qualite -= 0.1;
    else echelle *= 0.8;
  }
  return null;
}

$("photo").addEventListener("change", async () => {
  photoB64 = null;
  $("poids").textContent = "";
  $("apercu").style.display = "none";
  const f = $("photo").files[0];
  if (!f) return;
  try {
    const r = await compresser(f);
    if (!r) throw new Error();
    photoB64 = r.b64;
    $("poids").textContent = t("sig_poids", { ko: Math.ceil(r.octets / 1024) });
    $("apercu").src = "data:image/jpeg;base64," + r.b64;
    $("apercu").style.display = "block";
  } catch {
    $("photo").value = "";
    message("sig_photo_err", false);
  }
});

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("envoyer");
  btn.disabled = true;
  btn.textContent = t("sig_envoi");
  try {
    const r = await fetch(`${API_URL}/signalements`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        point_id: Number($("point").value),
        type: $("type").value,
        texte: $("texte").value.trim() || null,
        photo_b64: photoB64,
      }),
    });
    if (r.status === 201) {
      message("sig_ok", true);
      $("texte").value = "";
      $("photo").value = "";
      $("apercu").style.display = "none";
      $("poids").textContent = "";
      photoB64 = null;
    } else if (r.status === 413) message("sig_413", false);
    else if (r.status === 429) message("sig_429", false);
    else message("sig_err", false);
  } catch {
    message("sig_err", false);
  } finally {
    btn.disabled = false;
    btn.textContent = t("sig_envoyer");
  }
});

chargerPoints();
