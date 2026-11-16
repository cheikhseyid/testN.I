"""Train the urgency classifier.

Usage (from backend/):  python -m app.ia.train
  - reads data/entrainement_ia.csv (texte, type, urgence)
  - TF-IDF on characters (2-4-grams, robust to typos / transliteration) + one-hot "type"
    -> LogisticRegression(class_weight="balanced")
  - 80/20 stratified split: prints classification report + confusion matrix
  - refits on 100 % of the data and saves app/ia/model.joblib
"""
import csv
import sys
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .classifier import LABELS, MODEL_PATH, TYPES, normalize

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "entrainement_ia.csv"
SEED = 42


def load(path: Path = DATA_PATH) -> tuple[np.ndarray, np.ndarray]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    X = np.array([[normalize(r["texte"]), r["type"].strip()] for r in rows], dtype=object)
    y = np.array([r["urgence"].strip() for r in rows])
    unknown = set(y) - set(LABELS)
    if unknown:
        raise SystemExit(f"Étiquettes inconnues dans {path.name} : {unknown}")
    return X, y


def build_pipeline() -> Pipeline:
    features = ColumnTransformer([
        ("texte", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, sublinear_tf=True), 0),
        ("type", OneHotEncoder(categories=[TYPES], handle_unknown="ignore"), [1]),
    ])
    clf = LogisticRegression(class_weight="balanced", max_iter=3000, C=20.0, random_state=SEED)
    return Pipeline([("features", features), ("clf", clf)])


def main() -> None:
    X, y = load()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)

    model = build_pipeline().fit(X_tr, y_tr)
    pred = model.predict(X_te)

    print(f"Données : {len(y)} exemples ({len(y_tr)} entraînement / {len(y_te)} test)\n")
    print("Rapport de classification (jeu de test 20 %, modèle seul, sans la règle de sécurité) :")
    print(classification_report(y_te, pred, labels=LABELS, digits=3, zero_division=0))
    print("Matrice de confusion (lignes = vrai, colonnes = prédit) :")
    cm = confusion_matrix(y_te, pred, labels=LABELS)
    width = max(len(label) for label in LABELS) + 2
    print(" " * width + "".join(label.rjust(width) for label in LABELS))
    for label, row in zip(LABELS, cm):
        print(label.ljust(width) + "".join(str(v).rjust(width) for v in row))

    final = build_pipeline().fit(X, y)  # all data for the saved model
    joblib.dump({"pipeline": final, "sklearn_version": sklearn.__version__, "labels": LABELS}, MODEL_PATH)
    print(f"\nModèle entraîné sur les {len(y)} exemples et sauvegardé : {MODEL_PATH}")


if __name__ == "__main__":
    sys.exit(main())
