"""Tests for GET /stats, GET /alertes and the simulated history (historique.csv / seed_history).

The database already holds seeded data, so tests insert their own points in
dedicated quartiers (and reports in a far-past week), assert exact numbers for
those, use before/after deltas for global figures, and clean up afterwards.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import PointEau, Signalement
from seed import CSV_PATH, HISTORY_PATH, load_history, load_rows, seed_history

QA = "Quartier-Test-Stats-A"
QB = "Quartier-Test-Stats-B"
WEEK = datetime(2001, 1, 3, 12, tzinfo=timezone.utc)  # a Wednesday; week starts Monday 2001-01-01


def _cleanup():
    with SessionLocal() as db:
        db.execute(delete(PointEau).where(PointEau.quartier.in_([QA, QB])))
        db.commit()


@pytest.fixture
def make_points(client):
    """make_points(quartier, etats) -> list of ids."""
    def make(quartier, etats):
        with SessionLocal() as db:
            pts = [PointEau(nom=f"{quartier} {i}", type="borne", quartier=quartier, lat=18.1, lon=-15.95,
                            etat=e, potable=True) for i, e in enumerate(etats)]
            db.add_all(pts)
            db.commit()
            return [p.id for p in pts]
    yield make
    _cleanup()


def add_reports(point_id, specs):
    """specs: list of (type, hours_to_repair | None, created_at)."""
    with SessionLocal() as db:
        for type_, hours, cree in specs:
            db.add(Signalement(
                point_id=point_id, type=type_, texte="", urgence="moyenne", score_urgence=0.5,
                statut="repare" if hours is not None else "ouvert", cree_le=cree,
                repare_le=cree + timedelta(hours=hours) if hours is not None else None,
            ))
        db.commit()


def get_stats(client):
    r = client.get("/stats")
    assert r.status_code == 200
    return r.json()


# ---------- /stats ----------

def test_stats_has_the_five_results(client):
    s = get_stats(client)
    assert set(s) == {"par_quartier", "par_semaine", "par_type", "temps_moyen_reparation_h", "signalements_ouverts"}
    assert isinstance(s["signalements_ouverts"], int)


def test_stats_par_quartier_exact_for_own_quartier(client, make_points):
    a1, a2 = make_points(QA, ["ok", "ok"])
    add_reports(a1, [("panne", 5, WEEK), ("panne", None, WEEK), ("eau_trouble", 2, WEEK)])
    add_reports(a2, [("faible_debit", None, WEEK)])
    row = next(q for q in get_stats(client)["par_quartier"] if q["quartier"] == QA)
    assert row == {"quartier": QA, "signalements": 4, "pannes": 2}


def test_stats_par_quartier_sorted_by_pannes(client):
    rows = get_stats(client)["par_quartier"]
    keys = [(-q["pannes"], -q["signalements"]) for q in rows]
    assert keys == sorted(keys)


def test_stats_quartier_without_reports_is_absent(client, make_points):
    make_points(QB, ["ok"])
    assert QB not in {q["quartier"] for q in get_stats(client)["par_quartier"]}


def test_stats_par_semaine_groups_by_monday(client, make_points):
    (a,) = make_points(QA, ["ok"])
    add_reports(a, [
        ("panne", 1, WEEK),                                   # Wednesday
        ("autre", None, WEEK - timedelta(days=2)),            # Monday 2001-01-01
        ("panne", None, WEEK + timedelta(days=4)),            # Sunday 2001-01-07
        ("panne", None, WEEK + timedelta(days=5)),            # Monday 2001-01-08 → next week
    ])
    weeks = {w["semaine"]: w for w in get_stats(client)["par_semaine"]}
    assert weeks["2001-01-01"] == {"semaine": "2001-01-01", "signalements": 3, "pannes": 2}
    assert weeks["2001-01-08"] == {"semaine": "2001-01-08", "signalements": 1, "pannes": 1}
    semaines = [w["semaine"] for w in get_stats(client)["par_semaine"]]
    assert semaines == sorted(semaines)


def test_stats_par_type_and_ouverts_deltas(client, make_points):
    before = get_stats(client)
    (a,) = make_points(QA, ["ok"])
    add_reports(a, [("panne", None, WEEK), ("panne", 3, WEEK), ("autre", None, WEEK)])
    after = get_stats(client)
    t0 = {t["type"]: t["signalements"] for t in before["par_type"]}
    t1 = {t["type"]: t["signalements"] for t in after["par_type"]}
    assert t1["panne"] - t0.get("panne", 0) == 2
    assert t1["autre"] - t0.get("autre", 0) == 1
    assert after["signalements_ouverts"] - before["signalements_ouverts"] == 2
    counts = [t["signalements"] for t in after["par_type"]]
    assert counts == sorted(counts, reverse=True)


def test_stats_temps_moyen_matches_python(client, make_points):
    (a,) = make_points(QA, ["ok"])
    add_reports(a, [("panne", 10, WEEK), ("panne", 31.5, WEEK)])
    with SessionLocal() as db:
        pairs = db.execute(select(Signalement.cree_le, Signalement.repare_le)
                           .where(Signalement.repare_le.is_not(None))).all()
    expected = round(sum((r - c).total_seconds() for c, r in pairs) / len(pairs) / 3600, 1)
    assert get_stats(client)["temps_moyen_reparation_h"] == pytest.approx(expected, abs=0.1)  # both rounded to 0.1 h


# ---------- /alertes ----------

def test_alertes_threshold_is_3_points_en_panne(client, make_points):
    make_points(QA, ["panne", "panne", "panne", "ok", "faible"])
    make_points(QB, ["panne", "panne", "faible", "faible"])
    r = client.get("/alertes")  # public: no token
    assert r.status_code == 200
    by_q = {a["quartier"]: a["nb"] for a in r.json()}
    assert by_q.get(QA) == 3
    assert QB not in by_q


def test_alertes_sorted_by_nb_desc(client, make_points):
    make_points(QA, ["panne"] * 3)
    make_points(QB, ["panne"] * 5)
    data = client.get("/alertes").json()
    nbs = [a["nb"] for a in data]
    assert nbs == sorted(nbs, reverse=True)
    assert [a["quartier"] for a in data if a["quartier"] in (QA, QB)] == [QB, QA]


def test_alertes_ignores_reports_only_point_etat(client, make_points):
    ids = make_points(QA, ["ok", "ok", "ok"])
    for pid in ids:
        add_reports(pid, [("panne", None, WEEK)])  # inserted directly: point etat unchanged
    assert QA not in {a["quartier"] for a in client.get("/alertes").json()}


# ---------- historique.csv / seed_history ----------

@pytest.fixture(scope="module")
def history():
    ids = {p.nom: i for i, p in enumerate(load_rows(CSV_PATH), start=1)}
    quartier = {p.nom: p.quartier for p in load_rows(CSV_PATH)}
    rows = load_history(HISTORY_PATH, ids)
    nom_by_id = {v: k for k, v in ids.items()}
    return rows, {id(r): quartier[nom_by_id[r.point_id]] for r in rows}


def test_history_size_and_70_percent_repaired(history):
    rows, _ = history
    assert len(rows) == 400
    repaired = [r for r in rows if r.statut == "repare"]
    assert len(repaired) == 280
    assert all(r.repare_le is not None and r.repare_le > r.cree_le for r in repaired)
    assert all(r.repare_le is None for r in rows if r.statut == "ouvert")


def test_history_window_and_hot_season_peak(history):
    rows, _ = history
    start = datetime(2026, 4, 6, tzinfo=timezone.utc)
    assert all(start <= r.cree_le < start + timedelta(weeks=8) for r in rows)
    per_week = Counter((r.cree_le - start).days // 7 for r in rows)
    assert sum(per_week[w] for w in range(4, 8)) > 1.5 * sum(per_week[w] for w in range(4))


def test_history_arafat_and_dar_naim_lead(history):
    rows, quartier_of = history
    pannes = Counter(quartier_of[id(r)] for r in rows if r.type == "panne")
    assert {q for q, _ in pannes.most_common(2)} == {"Arafat", "Dar Naim"}


def test_history_unknown_point_fails(tmp_path):
    bad = tmp_path / "h.csv"
    bad.write_text("point_nom,type,texte,urgence,score_urgence,statut,cree_le,repare_le\n"
                   "Inconnu,panne,,haute,0.9,ouvert,2026-04-06T08:00:00Z,\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Inconnu"):
        load_history(bad, {})


def test_seed_history_does_not_touch_existing_reports(client, make_points):
    (a,) = make_points(QA, ["ok"])
    add_reports(a, [("panne", None, WEEK)])  # guarantees the table is not empty
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Signalement))
    assert seed_history() == 0
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Signalement)) == before
