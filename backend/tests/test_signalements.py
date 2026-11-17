"""Tests for POST /signalements and GET /signalements/{id}/photo.

Each test gets its own water point (deleted afterwards, with its reports via
ON DELETE CASCADE) and a fresh rate-limit counter.
"""
import struct
import zlib

import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.models import PointEau, Signalement
from app.routers.signalements import limiter

Q = "Quartier-Test-Signalements"


def make_png() -> bytes:
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"


@pytest.fixture(autouse=True)
def reset_rate_limit():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def point(client):
    with SessionLocal() as db:
        p = PointEau(nom="Borne Test", type="borne", quartier=Q, lat=18.1, lon=-15.95, etat="ok", potable=True)
        db.add(p)
        db.commit()
        pid, maj_le = p.id, p.maj_le
    yield {"id": pid, "maj_le": maj_le}
    with SessionLocal() as db:
        db.execute(delete(PointEau).where(PointEau.quartier == Q))
        db.commit()


def post(client, point_id, type_="autre", texte="", photo=None):
    files = {"photo": photo} if photo else None
    return client.post("/signalements", data={"point_id": point_id, "type": type_, "texte": texte}, files=files)


def get_point(pid):
    with SessionLocal() as db:
        return db.get(PointEau, pid)


# ---------- Creation ----------

def test_create_returns_201_and_row_in_db(client, point):
    r = post(client, point["id"], "eau_trouble", "  Eau marron  ")
    assert r.status_code == 201
    body = r.json()
    assert body["point_id"] == point["id"]
    assert body["type"] == "eau_trouble"
    assert body["texte"] == "Eau marron"
    # Filled by the AI classifier (app/ia/classifier.py).
    assert body["urgence"] in ("haute", "moyenne", "basse")
    assert 0.0 <= body["score_urgence"] <= 1.0
    assert body["statut"] == "ouvert" and body["repare_le"] is None
    assert "photo" not in body
    with SessionLocal() as db:
        row = db.get(Signalement, body["id"])
        assert row is not None and row.point_id == point["id"] and row.photo is None


@pytest.mark.parametrize("type_, etat", [
    ("panne", "panne"),
    ("faible_debit", "faible"),
    ("eau_trouble", "ok"),
    ("autre", "ok"),
])
def test_type_updates_point_etat(client, point, type_, etat):
    assert post(client, point["id"], type_).status_code == 201
    p = get_point(point["id"])
    assert p.etat == etat
    assert p.maj_le > point["maj_le"]


def test_unknown_point_returns_404(client):
    r = post(client, 999999999, "panne")
    assert r.status_code == 404


def test_invalid_type_returns_422(client, point):
    assert post(client, point["id"], "inondation").status_code == 422


def test_texte_over_500_chars_rejected(client, point):
    assert post(client, point["id"], texte="x" * 501).status_code == 422
    assert post(client, point["id"], texte="x" * 500).status_code == 201


# ---------- Photo ----------

@pytest.mark.parametrize("name, data, mime", [
    ("p.png", make_png(), "image/png"),
    ("p.jpg", JPEG, "image/jpeg"),
])
def test_photo_roundtrip(client, point, name, data, mime):
    r = post(client, point["id"], photo=(name, data, mime))
    assert r.status_code == 201
    g = client.get(f"/signalements/{r.json()['id']}/photo")
    assert g.status_code == 200
    assert g.headers["content-type"] == mime
    assert g.content == data


def test_photo_wrong_format_rejected_even_if_mime_lies(client, point):
    r = post(client, point["id"], photo=("x.png", b"GIF89a" + b"0" * 50, "image/png"))
    assert r.status_code == 400
    assert "JPEG ou PNG" in r.json()["detail"]


def test_photo_over_300kb_rejected(client, point):
    big = b"\xff\xd8\xff" + b"0" * (300 * 1024)
    r = post(client, point["id"], photo=("big.jpg", big, "image/jpeg"))
    assert r.status_code == 400
    assert "300 Ko" in r.json()["detail"]


def test_photo_exactly_300kb_accepted(client, point):
    ok = b"\xff\xd8\xff" + b"0" * (300 * 1024 - 3)
    assert post(client, point["id"], photo=("ok.jpg", ok, "image/jpeg")).status_code == 201


def test_rejected_photo_creates_nothing(client, point):
    post(client, point["id"], "panne", photo=("x.gif", b"GIF89a", "image/gif"))
    with SessionLocal() as db:
        assert db.query(Signalement).filter_by(point_id=point["id"]).count() == 0
    assert get_point(point["id"]).etat == "ok"


def test_get_photo_404_when_absent(client, point):
    sid = post(client, point["id"]).json()["id"]
    assert client.get(f"/signalements/{sid}/photo").status_code == 404
    assert client.get("/signalements/999999999/photo").status_code == 404


# ---------- Rate limit ----------

def test_sixth_post_in_a_minute_returns_429(client, point):
    codes = [post(client, point["id"]).status_code for _ in range(6)]
    assert codes == [201] * 5 + [429]
    with SessionLocal() as db:
        assert db.query(Signalement).filter_by(point_id=point["id"]).count() == 5


def test_photo_endpoint_not_rate_limited(client, point):
    sid = post(client, point["id"], photo=("p.png", make_png(), "image/png")).json()["id"]
    for _ in range(4):
        post(client, point["id"])
    assert post(client, point["id"]).status_code == 429
    assert client.get(f"/signalements/{sid}/photo").status_code == 200
