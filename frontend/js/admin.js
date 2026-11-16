// Tableau de bord responsable
Object.assign(I18N.fr, {
  adm_titre: "Mawjoud — responsable",
  adm_mdp: "Mot de passe",
  adm_connexion: "Se connecter",
  adm_mauvais: "Mot de passe incorrect",
  adm_quartier: "Quartier",
  adm_tous: "Tous",
  adm_compte: "{n} signalement(s) ouvert(s)",
  adm_vide: "Aucun signalement ouvert",
  adm_repare: "Marquer réparé",
  adm_err: "Erreur réseau, réessayez",
  adm_point: "Point n°{id}",
  sig_t_panne: "Panne", sig_t_eau_trouble: "Eau trouble",
  sig_t_faible_debit: "Faible débit", sig_t_autre: "Autre",
});
Object.assign(I18N.ar, {
  adm_titre: "موجود — المسؤول",
  adm_mdp: "كلمة المرور",
  adm_connexion: "تسجيل الدخول",
  adm_mauvais: "كلمة المرور غير صحيحة",
  adm_quartier: "الحي",
  adm_tous: "الكل",
  adm_compte: "{n} بلاغ مفتوح",
  adm_vide: "لا توجد بلاغات مفتوحة",
  adm_repare: "تم الإصلاح",
  adm_err: "خطأ في الشبكة، أعد المحاولة",
  adm_point: "النقطة رقم {id}",
  sig_t_panne: "عطل", sig_t_eau_trouble: "مياه عكرة",
  sig_t_faible_debit: "تدفق ضعيف", sig_t_autre: "أخرى",
});

document.documentElement.lang = LANG;
document.documentElement.dir = LANG === "ar" ? "rtl" : "ltr";
document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));

const $ = (id) => document.getElementById(id);
let signalements = [];

// Token gardé pour la session de l'onglet seulement
function lireToken() { try { return sessionStorage.getItem("token"); } catch { return null; } }
function ecrireToken(v) { try { v ? sessionStorage.setItem("token", v) : sessionStorage.removeItem("token"); } catch {} }
let token = lireToken();

function afficher(connecte) {
  $("login").hidden = connecte;
  $("tableau").hidden = !connecte;
}

function badge(u) {
  return u >= 70 ? "u-haute" : u >= 40 ? "u-moy" : "u-basse";
}

$("login").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("message").textContent = "";
  try {
    const r = await fetch(`${API_URL}/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: $("mdp").value }),
    });
    if (!r.ok) { $("message").textContent = t("adm_mauvais"); return; }
    token = (await r.json()).token;
    ecrireToken(token);
    $("mdp").value = "";
    demarrer();
  } catch {
    $("message").textContent = t("adm_err");
  }
});

// Charge les signalements ouverts (déjà triés par urgence côté API)
async function charger() {
  try {
    const r = await fetch(`${API_URL}/signalements?statut=ouvert`);
    if (!r.ok) throw new Error(r.status); // erreur API (500…)
    signalements = await r.json();
  } catch {
    $("message").textContent = t("adm_err");
    return;
  }
  const sel = $("quartier"), choix = sel.value;
  sel.length = 1;
  for (const q of [...new Set(signalements.map((s) => s.quartier).filter(Boolean))].sort()) {
    sel.add(new Option(q, q));
  }
  sel.value = choix;
  rendre();
}

function rendre() {
  const q = $("quartier").value;
  const liste = signalements.filter((s) => !q || s.quartier === q);
  $("compte").textContent = t("adm_compte", { n: liste.length });
  const ul = $("liste");
  ul.replaceChildren();
  if (!liste.length) {
    const li = document.createElement("li");
    li.textContent = t("adm_vide");
    ul.append(li);
    return;
  }
  for (const s of liste) {
    const li = document.createElement("li");
    const b = document.createElement("span");
    b.className = "badge " + badge(s.urgence);
    b.textContent = s.urgence;

    const info = document.createElement("div");
    info.className = "info";
    const titre = document.createElement("strong");
    titre.textContent = `${t("sig_t_" + s.type)} · ${t("adm_point", { id: s.point_id })}`;
    const meta = document.createElement("small");
    meta.textContent = `${s.quartier || ""} · ${new Date(s.cree_le).toLocaleString(LANG)}`;
    info.append(titre, meta);
    if (s.texte) {
      const p = document.createElement("p");
      p.textContent = s.texte; // textContent : pas d'injection HTML
      info.append(p);
    }

    const btn = document.createElement("button");
    btn.textContent = t("adm_repare");
    btn.onclick = () => reparer(s.id, btn);

    li.append(b, info, btn);
    ul.append(li);
  }
}

async function reparer(id, btn) {
  btn.disabled = true;
  $("message").textContent = "";
  try {
    const r = await fetch(`${API_URL}/signalements/${id}/repare`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.status === 401) { deconnecter(); return; }
    if (!r.ok) throw new Error();
    // Retire la ligne localement
    signalements = signalements.filter((s) => s.id !== id);
    rendre();
  } catch {
    $("message").textContent = t("adm_err");
    btn.disabled = false;
  }
}

function deconnecter() {
  token = null;
  ecrireToken(null);
  afficher(false);
  $("message").textContent = t("adm_mauvais");
}

function demarrer() {
  afficher(true);
  charger();
}

$("quartier").addEventListener("change", rendre);
if (token) demarrer(); else afficher(false);
