# Score d'urgence explicable (règles pondérées, sans ML)
import re
import unicodedata

# Points de base selon le type de signalement
BASE = {"eau_trouble": 45, "panne": 40, "faible_debit": 20, "autre": 10}
NOM_TYPE = {"eau_trouble": "eau trouble", "panne": "panne",
            "faible_debit": "faible débit", "autre": "autre"}

# Mots-clés FR / AR / Darija (sans accents ni tashkeel), un bonus par catégorie
MOTS = [
    ("santé", 25, ["malade", "diarrhee", "vomi", "fievre", "intoxi", "enfant", "bebe",
                   "مريض", "مرض", "اسهال", "إسهال", "حمى", "تسمم", "اطفال", "أطفال",
                   "mrid", "mridin", "sbitar", "drari"]),
    ("sans eau", 20, ["pas d'eau", "plus d'eau", "sans eau", "a sec", "coupe", "rien ne coule",
                      "بدون ماء", "لا ماء", "ماكاين", "ما كاين", "مقطوع", "انقطاع",
                      "ma kayn", "makaynch", "ma fih lma", "bla lma"]),
    ("eau impropre", 15, ["trouble", "sale", "odeur", "boue", "marron", "jaune", "vers",
                          "عكر", "وسخ", "رائحة", "ريحة", "طين", "mkhenz", "khanez"]),
    ("danger", 10, ["fuite", "inond", "electri", "cass", "تسرب", "فيضان", "كهرباء"]),
]


def _normalise(texte: str) -> str:
    # Minuscules, sans accents latins ni voyelles arabes
    t = unicodedata.normalize("NFD", (texte or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t.replace("’", "'"))


def score_urgence(type_sig: str, texte: str | None = None, nb_ouverts: int = 0,
                  type_point: str | None = None, anciennete_h: float = 0) -> tuple[int, str]:
    """Renvoie (score 0-100, raison courte).

    nb_ouverts : signalements déjà ouverts sur le même point.
    anciennete_h : âge (heures) du plus ancien signalement ouvert sur ce point.
    """
    facteurs = [(NOM_TYPE.get(type_sig, type_sig), BASE.get(type_sig, 10))]

    t = _normalise(texte)
    for nom, pts, mots in MOTS:
        if any(_normalise(m) in t for m in mots):
            facteurs.append((nom, pts))

    if nb_ouverts > 0:
        facteurs.append((f"{nb_ouverts} déjà ouvert(s)", min(5 * nb_ouverts, 15)))
    if type_point == "borne":
        facteurs.append(("borne publique", 10))
    if anciennete_h >= 72:
        facteurs.append(("non résolu > 3 j", 10))
    elif anciennete_h >= 24:
        facteurs.append(("non résolu > 24 h", 5))

    score = max(0, min(100, sum(p for _, p in facteurs)))
    raison = ", ".join(f"{n} +{p}" for n, p in sorted(facteurs, key=lambda f: -f[1]))
    return score, raison
