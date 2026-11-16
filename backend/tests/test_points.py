"""Tests for /points.

They insert their own rows under a dedicated quartier and delete them afterwards,
so they don't depend on (or wipe) the data loaded by seed.py.
"""
from collections import Counter

import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.models import PointEau
from seed import CSV_PATH, load_rows

Q = "Quartier-Test-Pytest"
LIGHT_FIELDS = {"id", "nom", "type", "quartier", "lat", "lon", "etat"}


@pytest.fixture
def sample_points(client):
    rows = [
        PointEau(nom="Borne T1", type="borne", quartier=Q, lat=18.1, lon=-15.95, etat="ok", potable=True),
        PointEau(nom="Puits T2", type="puits", quartier=Q, lat=18.11, lon=-15.96, etat="panne", potable=False),
        PointEau(nom="Citerne T3", type="citerne", quartier=Q, lat=18.12, lon=-15.97, etat="faible", potable=True),
    ]
    with SessionLocal() as db:
        db.add_all(rows)
        db.commit()
        ids = [p.id for p in rows]
    yield ids
    with SessionLocal() as db:
        db.execute(delete(PointEau).where(PointEau.quartier == Q))
        db.commit()


def test_list_points_light_payload(client, sample_points):
    r = client.get("/points")
    assert r.status_code == 200
    data = r.json()
    returned = {p["id"] for p in data}
    assert set(sample_points) <= returned
    assert all(set(p) == LIGHT_FIELDS for p in data)  # no potable / maj_le


def test_list_points_ordered_by_id(client, sample_points):
    ids = [p["id"] for p in client.get("/points").json()]
    assert ids == sorted(ids)


def test_filter_by_quartier(client, sample_points):
    data = client.get("/points", params={"quartier": Q}).json()
    assert sorted(p["id"] for p in data) == sorted(sample_points)
    assert {p["quartier"] for p in data} == {Q}


def test_filter_by_quartier_case_and_spaces(client, sample_points):
    data = client.get("/points", params={"quartier": f"  {Q.upper()} "}).json()
    assert len(data) == len(sample_points)


def test_filter_unknown_quartier_returns_empty(client):
    r = client.get("/points", params={"quartier": "Quartier-Inexistant"})
    assert r.status_code == 200
    assert r.json() == []


def test_get_point_detail(client, sample_points):
    pid = sample_points[1]
    r = client.get(f"/points/{pid}")
    assert r.status_code == 200
    p = r.json()
    assert p["id"] == pid and p["nom"] == "Puits T2"
    assert p["etat"] == "panne" and p["potable"] is False
    assert "maj_le" in p


def test_get_point_not_found(client):
    r = client.get("/points/999999999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Point d'eau introuvable"


def test_get_point_invalid_id(client):
    assert client.get("/points/abc").status_code == 422


def test_seed_csv_content():
    rows = load_rows(CSV_PATH)
    assert len(rows) == 40
    etats = Counter(p.etat for p in rows)
    assert etats == {"ok": 24, "faible": 10, "panne": 6}
    assert {p.quartier for p in rows} == {
        "Tevragh Zeina", "Ksar", "Teyarett", "Toujounine", "Dar Naim",
        "Sebkha", "El Mina", "Arafat", "Riyad",
    }
    # Nouakchott bounding box
    assert all(17.95 < p.lat < 18.20 and -16.05 < p.lon < -15.85 for p in rows)
    assert {p.type for p in rows} <= {"puits", "borne", "citerne"}
