"""Tests for the urgency classifier (app/ia): normalization, safety rule, predict(),
fallback without a model, training script, and the POST /signalements integration."""
from collections import Counter

import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.ia import classifier, train
from app.ia.classifier import LABELS, normalize, predict, safety_rule
from app.models import PointEau
from app.routers.signalements import limiter

Q = "Quartier-Test-IA"


@pytest.fixture
def no_model(monkeypatch, tmp_path):
    """Point the classifier at a missing model file; restore the real cached model afterwards."""
    classifier._load.cache_clear()
    monkeypatch.setattr(classifier, "MODEL_PATH", tmp_path / "absent.joblib")
    yield
    monkeypatch.undo()
    classifier._load.cache_clear()


# ---------- normalize / safety rule ----------

@pytest.mark.parametrize("raw, expected", [
    ("  L'EAU   est   Trouble ", "l'eau est trouble"),
    ("Débit très FAIBLE", "debit tres faible"),
    ("الْمَاءُ", "الماء"),                 # harakat removed
    ("رائحة", "رايحه"),                    # ئ→ي, ة→ه
    ("أمي مريضة", "امي مريضه"),            # أ→ا
    ("مـــاء", "ماء"),                     # tatweel removed
    ("", ""),
    (None, ""),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("text", [
    "mon enfant est malade", "les enfants sont MALADES", "Malade depuis hier",
    "ولدي مريض", "أمي مريضة", "il y a une odeur", "ODEURS d'égout", "فيه رائحة", "الماء له رائحه",
])
def test_safety_rule_matches(text):
    assert safety_rule(text)


@pytest.mark.parametrize("text", ["la pompe est cassée", "lma 9lil", "الماء عكر", "", "ça sent mauvais"])
def test_safety_rule_does_not_match(text):
    assert not safety_rule(text)


# ---------- predict ----------

def test_spec_example_is_haute():
    urgence, score = predict("l'eau sent mauvais, mon enfant est malade", "eau_trouble")
    assert urgence == "haute" and score >= 0.9


@pytest.mark.parametrize("type_", ["panne", "faible_debit", "eau_trouble", "autre"])
def test_safety_rule_overrides_model_for_every_type(type_):
    # "rien d'urgent" pushes the model towards "basse"; the keyword must still win.
    urgence, score = predict("rien d'urgent, juste une odeur", type_)
    assert urgence == "haute" and score >= classifier.RULE_MIN_SCORE


@pytest.mark.parametrize("text, type_", [
    ("la pompe est cassée", "panne"), ("lma 9lil", "faible_debit"), ("", "autre"),
    ("الحنفية معطلة", "panne"), ("x" * 500, "panne"), ("🙂🙂", "autre"),
])
def test_predict_returns_plain_types_in_range(text, type_):
    urgence, score = predict(text, type_)
    assert type(urgence) is str and urgence in LABELS
    assert type(score) is float and 0.0 <= score <= 1.0


def test_predict_obvious_cases():
    assert predict("le robinet goutte un peu, rien d'urgent", "autre")[0] == "basse"
    assert predict("lma ma ja, drari mrad", "panne")[0] == "haute"  # "mrad" learned, not in the rule


def test_score_orders_severity():
    assert predict("ma mère vomit, l'eau pue", "eau_trouble")[1] > predict("la pompe est cassée", "panne")[1] \
        > predict("juste pour info, petite fuite", "autre")[1]


def test_model_loaded_once():
    classifier._load.cache_clear()
    predict("a", "panne")
    predict("b", "autre")
    info = classifier._load.cache_info()
    assert info.misses == 1 and info.hits >= 1
    assert classifier.model_available()


def test_fallback_without_model(no_model):
    assert not classifier.model_available()
    assert predict("la pompe est cassée", "panne") == classifier.FALLBACK
    assert predict("mon enfant est malade", "panne") == ("haute", classifier.RULE_MIN_SCORE)


# ---------- training data / script ----------

def test_training_data_is_valid():
    X, y = train.load()
    assert len(y) == 300
    assert set(y) == set(LABELS)
    assert min(Counter(y).values()) >= 50                       # no tiny class
    assert set(X[:, 1]) <= set(classifier.TYPES)
    # Raw CSV rows are unique; a few differ only by case/accents and collapse after normalize():
    # those must carry the same label (otherwise the data contradicts itself).
    import csv
    with train.DATA_PATH.open(encoding="utf-8", newline="") as f:
        raw = list(csv.DictReader(f))
    assert len({(r["texte"], r["type"]) for r in raw}) == len(raw)
    labels_by_key = {}
    for (t, ty), label in zip(X, y):
        assert labels_by_key.setdefault((t, ty), label) == label, f"labels contradictoires pour {t!r}"
    assert sum(any("؀" <= c <= "ۿ" for c in t) for t in X[:, 0]) >= 60   # Arabic present


def test_train_main_prints_report_and_saves(monkeypatch, tmp_path, capsys):
    out_path = tmp_path / "model.joblib"
    monkeypatch.setattr(train, "MODEL_PATH", out_path)   # don't overwrite the real model
    train.main()
    out = capsys.readouterr().out
    assert "Rapport de classification" in out and "Matrice de confusion" in out
    for label in LABELS:
        assert label in out
    assert out_path.exists() and out_path.stat().st_size > 10_000


def test_holdout_quality_floor():
    """Regression guard on the fixed 80/20 split (seeded): currently ~0.70."""
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
    X, y = train.load()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=train.SEED)
    pred = train.build_pipeline().fit(X_tr, y_tr).predict(X_te)
    assert accuracy_score(y_te, pred) >= 0.6


# ---------- POST /signalements integration ----------

@pytest.fixture
def point(client):
    limiter.reset()
    with SessionLocal() as db:
        p = PointEau(nom="Borne IA", type="borne", quartier=Q, lat=18.1, lon=-15.95, etat="ok", potable=True)
        db.add(p)
        db.commit()
        pid = p.id
    yield pid
    with SessionLocal() as db:
        db.execute(delete(PointEau).where(PointEau.quartier == Q))
        db.commit()
    limiter.reset()


def test_post_fills_urgence_from_classifier(client, point):
    r = client.post("/signalements", data={"point_id": point, "type": "eau_trouble",
                                           "texte": "l'eau sent mauvais, mon enfant est malade"})
    assert r.status_code == 201
    assert r.json()["urgence"] == "haute" and r.json()["score_urgence"] >= 0.9


def test_post_uses_stripped_text_and_type(client, point):
    texte, type_ = "   le robinet goutte un peu, rien d'urgent   ", "autre"
    body = client.post("/signalements", data={"point_id": point, "type": type_, "texte": texte}).json()
    assert (body["urgence"], body["score_urgence"]) == predict(texte.strip(), type_)


def test_post_still_works_without_model(client, point, no_model):
    r = client.post("/signalements", data={"point_id": point, "type": "panne", "texte": "la pompe est cassée"})
    assert r.status_code == 201
    assert (r.json()["urgence"], r.json()["score_urgence"]) == classifier.FALLBACK
