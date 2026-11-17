"""Remplit points_eau depuis data/points.csv SI la table est vide,
puis signalements depuis data/historique.csv SI cette table est vide (dates recalées sur aujourd'hui),
puis crée (ou met à jour) l'admin à partir de ADMIN_EMAIL / ADMIN_PASSWORD.

Usage (depuis backend/) :
  python seed.py              # sans risque : ne touche pas aux données existantes (utilisé au déploiement)
  python seed.py --reset      # vide points_eau ET les signalements (CASCADE), puis recharge les 2 CSV
  python seed.py --recalcul   # base en ligne : recale l'historique SIMULÉ sur aujourd'hui, clôt les
                              # signalements simulés de plus de 14 jours, puis recalcule l'état des points.
                              # Les vrais signalements ne sont jamais modifiés ni effacés.
"""
import argparse
import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, text

from app import models  # noqa: F401
from app.auth import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Admin, PointEau, Signalement

CSV_PATH = Path(__file__).parent / "data" / "points.csv"
HISTORY_PATH = Path(__file__).parent / "data" / "historique.csv"

# Simulated history: the most recent report is put at "now - 1 day"; reports older than 14 days are closed.
LATEST_AGE = timedelta(days=1)
CLOSE_AFTER = timedelta(days=14)
# Typical repair time (hours) used to date the reports closed by the 14-day rule (same medians as the CSV).
REPAIR_HOURS = {"panne": 30, "faible_debit": 18, "eau_trouble": 12, "autre": 24}
# Ids of the simulated reports, so --recalcul never touches real ones (no schema change in models.py).
MARKER_TABLE = "seed_historique"


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
    parser.add_argument("--recalcul", action="store_true",
                        help="recale l'historique simulé sur aujourd'hui et recalcule l'état des points "
                             "(sans effacer les vrais signalements)")
    args = parser.parse_args(argv)
    seed_points(reset=args.reset)
    loaded = seed_history()  # a fresh load is recalculated right away
    if args.recalcul and not loaded:
        refresh_history()
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


def _ensure_marker_table(db) -> None:
    db.execute(text(
        f"CREATE TABLE IF NOT EXISTS {MARKER_TABLE} ("
        "signalement_id INTEGER PRIMARY KEY REFERENCES signalements(id) ON DELETE CASCADE)"
    ))


def seed_history() -> int:
    """Load the simulated history only if there are no reports at all (never mixes with real data),
    then recalculate it (dates moved to today, old reports closed, point states)."""
    with SessionLocal() as db, db.begin():
        db.execute(text("LOCK TABLE signalements IN SHARE ROW EXCLUSIVE MODE"))
        existing = db.scalar(select(func.count()).select_from(Signalement))
        if existing:
            print(f"signalements contient déjà {existing} lignes : historique non chargé")
            return 0
        _ensure_marker_table(db)
        point_ids = dict(db.execute(select(PointEau.nom, PointEau.id)).all())
        rows = load_history(HISTORY_PATH, point_ids)
        db.add_all(rows)
        db.flush()
        db.execute(text(f"INSERT INTO {MARKER_TABLE} (signalement_id) VALUES (:id)"), [{"id": r.id} for r in rows])
    print(f"{len(rows)} signalements historiques insérés depuis {HISTORY_PATH.name}")
    refresh_history()
    return len(rows)


def _backfill_markers(db) -> int:
    """Databases seeded before the marker table existed: find the simulated rows by an exact match
    on (point, type, text, original date) with historique.csv. Real reports can't match: the CSV dates
    (April–May 2026) are before the app went online."""
    if db.scalar(text(f"SELECT count(*) FROM {MARKER_TABLE}")):
        return 0
    noms = dict(db.execute(select(PointEau.nom, PointEau.id)).all())
    wanted = set()
    with HISTORY_PATH.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["point_nom"].strip() in noms:
                wanted.add((noms[r["point_nom"].strip()], r["type"].strip(), r["texte"].strip(), _dt(r["cree_le"])))
    ids = [sid for sid, pid, typ, txt, cree in db.execute(
        select(Signalement.id, Signalement.point_id, Signalement.type, Signalement.texte, Signalement.cree_le)
    ).all() if (pid, typ, txt, cree) in wanted]
    if ids:
        db.execute(text(f"INSERT INTO {MARKER_TABLE} (signalement_id) VALUES (:id) ON CONFLICT DO NOTHING"),
                   [{"id": i} for i in ids])
    return len(ids)


def recompute_point_states(db, now: datetime) -> int:
    """etat of every point from its OPEN reports (real and simulated): panne > faible_debit > ok."""
    open_types = {}
    for pid, typ in db.execute(
        select(Signalement.point_id, Signalement.type).where(Signalement.statut == "ouvert")
    ).all():
        open_types.setdefault(pid, set()).add(typ)
    changed = 0
    for point in db.scalars(select(PointEau)).all():
        types = open_types.get(point.id, set())
        etat = "panne" if "panne" in types else "faible" if "faible_debit" in types else "ok"
        if point.etat != etat:
            point.etat = etat
            point.maj_le = now
            changed += 1
    return changed


def refresh_history(now: datetime | None = None) -> dict:
    """Recalculation, safe on the live database: only the simulated reports are moved/closed."""
    now = now or datetime.now(timezone.utc)
    with SessionLocal() as db, db.begin():
        _ensure_marker_table(db)
        backfilled = _backfill_markers(db)
        sim = select(text("signalement_id")).select_from(text(MARKER_TABLE))
        latest = db.scalar(select(func.max(Signalement.cree_le)).where(Signalement.id.in_(sim)))
        shift = (now - LATEST_AGE) - latest if latest else timedelta(0)

        rows = db.scalars(select(Signalement).where(Signalement.id.in_(sim))).all()
        reopened = closed = 0
        for s in rows:
            s.cree_le = s.cree_le + shift  # same gaps between dates
            if s.repare_le is not None:
                s.repare_le = s.repare_le + shift
                if s.repare_le > now:      # a repair can't be in the future: still open today
                    s.statut, s.repare_le = "ouvert", None
                    reopened += 1
            if s.statut == "ouvert" and now - s.cree_le > CLOSE_AFTER:
                s.statut = "repare"
                s.repare_le = min(s.cree_le + timedelta(hours=REPAIR_HOURS.get(s.type, 24)), now)
                closed += 1
        db.flush()
        changed = recompute_point_states(db, now)
    report = {"simules": len(rows), "reperes_ajoutes": backfilled, "decalage_jours": round(shift.total_seconds() / 86400, 1),
              "rouverts": reopened, "clos_14j": closed, "points_modifies": changed}
    print("Recalcul de l'historique : " + ", ".join(f"{k}={v}" for k, v in report.items()))
    return report


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
