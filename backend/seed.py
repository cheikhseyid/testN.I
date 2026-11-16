"""Remplit points_eau depuis data/points.csv SI la table est vide,
puis signalements depuis data/historique.csv SI cette table est vide,
puis crée (ou met à jour) l'admin à partir de ADMIN_EMAIL / ADMIN_PASSWORD.

Usage (depuis backend/) :
  python seed.py           # sans risque : ne touche pas aux données existantes (utilisé au déploiement)
  python seed.py --reset   # vide points_eau ET les signalements (CASCADE), puis recharge les 2 CSV
"""
import argparse
import csv
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select, text

from app import models  # noqa: F401
from app.auth import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Admin, PointEau, Signalement

CSV_PATH = Path(__file__).parent / "data" / "points.csv"
HISTORY_PATH = Path(__file__).parent / "data" / "historique.csv"


def load_rows(path: Path) -> list[PointEau]:
    with path.open(encoding="utf-8", newline="") as f:
        return [
            PointEau(
                nom=r["nom"].strip(),
                type=r["type"].strip(),
                quartier=r["quartier"].strip(),
                lat=float(r["lat"]),
                lon=float(r["lon"]),
                etat=r["etat"].strip(),
                potable=r["potable"].strip().lower() in ("true", "1", "oui", "yes"),
            )
            for r in csv.DictReader(f)
        ]


def seed_points(reset: bool = False) -> int:
    """Return the number of points inserted (0 when the table already had data)."""
    Base.metadata.create_all(bind=engine)
    points = load_rows(CSV_PATH)
    with SessionLocal() as db, db.begin():
        if reset:
            db.execute(text("TRUNCATE TABLE points_eau RESTART IDENTITY CASCADE"))
        else:
            # Lock so two concurrent deploys can't both see an empty table and insert twice.
            db.execute(text("LOCK TABLE points_eau IN SHARE ROW EXCLUSIVE MODE"))
            existing = db.scalar(select(func.count()).select_from(PointEau))
            if existing:
                print(f"points_eau contient déjà {existing} points : rien à faire (--reset pour recharger)")
                return 0
        db.add_all(points)
    print(f"{len(points)} points d'eau insérés depuis {CSV_PATH.name}")
    return len(points)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true",
                        help="vide points_eau et les signalements avant de recharger le CSV")
    args = parser.parse_args(argv)
    seed_points(reset=args.reset)
    seed_history()
    seed_admin()


def _dt(value: str) -> datetime | None:
    value = value.strip()
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def load_history(path: Path, point_ids: dict[str, int]) -> list[Signalement]:
    """Rows reference points by name (ids depend on insertion order)."""
    rows = []
    with path.open(encoding="utf-8", newline="") as f:
        for n, r in enumerate(csv.DictReader(f), start=2):
            nom = r["point_nom"].strip()
            if nom not in point_ids:
                raise SystemExit(f"{path.name} ligne {n} : point inconnu « {nom} »")
            rows.append(Signalement(
                point_id=point_ids[nom],
                type=r["type"].strip(),
                texte=r["texte"].strip(),
                urgence=r["urgence"].strip() or None,
                score_urgence=float(r["score_urgence"]),
                statut=r["statut"].strip(),
                cree_le=_dt(r["cree_le"]),
                repare_le=_dt(r["repare_le"]),
            ))
    return rows


def seed_history() -> int:
    """Load the simulated history only if there are no reports at all (never mixes with real data)."""
    with SessionLocal() as db, db.begin():
        db.execute(text("LOCK TABLE signalements IN SHARE ROW EXCLUSIVE MODE"))
        existing = db.scalar(select(func.count()).select_from(Signalement))
        if existing:
            print(f"signalements contient déjà {existing} lignes : historique non chargé")
            return 0
        point_ids = dict(db.execute(select(PointEau.nom, PointEau.id)).all())
        rows = load_history(HISTORY_PATH, point_ids)
        db.add_all(rows)
    print(f"{len(rows)} signalements historiques insérés depuis {HISTORY_PATH.name}")
    return len(rows)


def seed_admin() -> None:
    """Upsert: the password is re-hashed each time, so changing ADMIN_PASSWORD and re-running updates it."""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        print("ADMIN_EMAIL / ADMIN_PASSWORD absents : aucun admin créé")
        return
    if len(password) < 8:
        raise SystemExit("ADMIN_PASSWORD trop court (8 caractères minimum)")
    with SessionLocal() as db, db.begin():
        admin = db.query(Admin).filter(Admin.email == email).one_or_none()
        if admin is None:
            db.add(Admin(email=email, password_hash=hash_password(password)))
            print(f"Admin créé : {email}")
        else:
            admin.password_hash = hash_password(password)
            print(f"Admin mis à jour : {email}")


if __name__ == "__main__":
    main()
