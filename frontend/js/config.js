// Configuration du front
const API_URL = "http://localhost:8000";

// Textes fr/ar (à déplacer dans i18n/ plus tard)
const I18N = {
  fr: {
    titre: "Mawjoud — points d'eau",
    chargement: "Chargement…",
    proche: "Point d'eau fonctionnel le plus proche : {nom}, {dist} m",
    aucun: "Aucun point d'eau fonctionnel trouvé",
    geo_refus: "Activez la localisation pour trouver le point le plus proche",
    erreur: "Impossible de charger les points",
    vous: "Vous êtes ici",
    etat_ok: "Fonctionnel", etat_faible: "Faible débit", etat_panne: "En panne",
    type_puits: "Puits", type_borne: "Borne-fontaine", type_citerne: "Citerne",
  },
  ar: {
    titre: "موجود — نقاط المياه",
    chargement: "جارٍ التحميل…",
    proche: "أقرب نقطة مياه تعمل: {nom}، {dist} م",
    aucun: "لم يتم العثور على نقطة مياه تعمل",
    geo_refus: "فعّل تحديد الموقع لإيجاد أقرب نقطة",
    erreur: "تعذّر تحميل النقاط",
    vous: "أنت هنا",
    etat_ok: "تعمل", etat_faible: "تدفق ضعيف", etat_panne: "معطّلة",
    type_puits: "بئر", type_borne: "حنفية عمومية", type_citerne: "صهريج",
  },
};

// Langue : ?lang=ar ou langue du téléphone
const LANG = (new URLSearchParams(location.search).get("lang")
  || (navigator.language || "fr").slice(0, 2)) === "ar" ? "ar" : "fr";

function t(cle, vars = {}) {
  let s = (I18N[LANG] && I18N[LANG][cle]) || I18N.fr[cle] || cle;
  for (const k in vars) s = s.replace(`{${k}}`, vars[k]);
  return s;
}
