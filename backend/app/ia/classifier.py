"""Urgency classifier for reports: predict(texte, type) -> (urgence, score).

- The model (app/ia/model.joblib, produced by `python -m app.ia.train`) is loaded once, lazily.
- score = P(haute) + 0.5 * P(moyenne)  ∈ [0, 1]  (expected severity, used to sort reports).
- Safety rule: health or smell keywords always give "haute" (score ≥ 0.9), whatever the model says.
- If the model file is missing or can't be loaded, falls back to ("moyenne", 0.5) — the rule still applies —
  so a report is never rejected because of the AI.
"""
import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).with_name("model.joblib")
LABELS = ["haute", "moyenne", "basse"]
TYPES = ["panne", "faible_debit", "eau_trouble", "autre"]
FALLBACK = ("moyenne", 0.5)
RULE_MIN_SCORE = 0.9

_TATWEEL = "ـ"


def normalize(text: str) -> str:
    """Lowercase; strip Latin accents and Arabic diacritics/hamza marks; ة→ه, ى→ي; collapse spaces."""
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")  # é→e, أ→ا, ئ→ي, harakat removed
    text = text.replace(_TATWEEL, "").replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"\s+", " ", text).strip()


# Keywords from the spec, normalized the same way as the text (so "مريضة", "malades", "odeurs" also match).
SAFETY_KEYWORDS = tuple(normalize(k) for k in ("malade", "مريض", "odeur", "رائحة"))


def safety_rule(text: str) -> bool:
    norm = normalize(text)
    return any(k in norm for k in SAFETY_KEYWORDS)


@lru_cache(maxsize=1)
def _load():
    try:
        import joblib
        import sklearn

        bundle = joblib.load(MODEL_PATH)
        if bundle.get("sklearn_version") != sklearn.__version__:
            logger.warning("model.joblib entraîné avec scikit-learn %s, version installée %s",
                           bundle.get("sklearn_version"), sklearn.__version__)
        return bundle["pipeline"]
    except Exception:  # missing file, incompatible pickle, ...
        logger.exception("Modèle d'urgence indisponible (%s) : valeur par défaut utilisée", MODEL_PATH)
        return None


def model_available() -> bool:
    return _load() is not None


def predict(texte: str, type_: str) -> tuple[str, float]:
    urgence, score = FALLBACK
    pipeline = _load()
    if pipeline is not None:
        try:
            proba = dict(zip(pipeline.classes_, pipeline.predict_proba([[normalize(texte), type_]])[0]))
            urgence = str(max(proba, key=proba.get))  # numpy str -> plain str
            score = float(proba.get("haute", 0.0) + 0.5 * proba.get("moyenne", 0.0))
        except Exception:
            logger.exception("Échec de la prédiction d'urgence : valeur par défaut utilisée")
            urgence, score = FALLBACK
    if safety_rule(texte):
        urgence, score = "haute", max(score, RULE_MIN_SCORE)
    return urgence, round(float(score), 3)
