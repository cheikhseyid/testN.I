"""Tests for admin auth: /auth/login, get_admin, GET/PATCH /signalements, seed_admin.

Each test uses its own admin / water points (deleted afterwards) and a fresh
rate-limit counter; JWT_SECRET is set per test with monkeypatch.
"""
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlalchemy import delete

from app.auth import ALGORITHM, hash_password, verify_password
from app.db import SessionLocal
from app.models import Admin, PointEau, Signalement
from app.routers.signalements import limiter
from seed import seed_admin

SECRET = "test-secret-for-pytest-only-0123456789"
EMAIL = "pytest-admin@mawjoud.test"
PASSWORD = "Pytest-Password-42"
Q = "Quartier-Test-Auth"


@pytest.fixture(autouse=True)
def env_and_limits(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def admin(client):
    with SessionLocal() as db:
        db.execute(delete(Admin).where(Admin.email == EMAIL))
        a = Admin(email=EMAIL, password_hash=hash_password(PASSWORD))
        db.add(a)
        db.commit()
        admin_id = a.id
    yield admin_id
    with SessionLocal() as db:
        db.execute(delete(Admin).where(Admin.email.like("pytest-%@mawjoud.test")))
        db.commit()


@pytest.fixture
def headers(client, admin):
    r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def points(client):
    """Two points with reports: A (2 open reports), B (1 open report)."""
    with SessionLocal() as db:
        a = PointEau(nom="Borne Auth A", type="borne", quartier=Q, lat=18.1, lon=-15.95, etat="panne", potable=True)
        b = PointEau(nom="Puits Auth B", type="puits", quartier=Q, lat=18.2, lon=-15.96, etat="faible", potable=False)
        db.add_all([a, b])
        db.flush()
        t0 = datetime.now(timezone.utc) - timedelta(hours=3)
        sigs = {
            "a_old_moy": Signalement(point_id=a.id, type="panne", texte="", urgence="moyenne", score_urgence=0.5, cree_le=t0),
            "a_new_moy": Signalement(point_id=a.id, type="panne", texte="", urgence="moyenne", score_urgence=0.5,
                                     cree_le=t0 + timedelta(hours=1), photo=b"\xff\xd8\xff\x00"),
            "b_haute": Signalement(point_id=b.id, type="faible_debit", texte="", urgence="haute", score_urgence=0.9,
                                   cree_le=t0 + timedelta(hours=2)),
            "b_basse": Signalement(point_id=b.id, type="autre", texte="", urgence="basse", score_urgence=0.1, cree_le=t0),
        }
        db.add_all(sigs.values())
        db.commit()
        ids = {"A": a.id, "B": b.id, **{k: s.id for k, s in sigs.items()}}
    yield ids
    with SessionLocal() as db:
        db.execute(delete(PointEau).where(PointEau.quartier == Q))
        db.commit()


def my_reports(client, headers, ids, **params):
    r = client.get("/signalements", headers=headers, params=params)
    assert r.status_code == 200
    mine = {ids["A"], ids["B"]}
    return [s for s in r.json() if s["point_id"] in mine]


def point_etat(pid):
    with SessionLocal() as db:
        return db.get(PointEau, pid).etat


# ---------- Passwords ----------

def test_password_hash_is_bcrypt_and_verifies():
    h = hash_password(PASSWORD)
    assert h.startswith("$2b$")
    assert verify_password(PASSWORD, h)
    assert not verify_password("wrong", h)
    assert not verify_password("x" * 100, h)  # > 72 bytes: rejected, no crash
    assert not verify_password(PASSWORD, "not-a-hash")


# ---------- Login ----------

def test_login_ok_returns_8h_jwt(client, admin):
    r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 8 * 3600
    claims = jwt.decode(body["access_token"], SECRET, algorithms=[ALGORITHM])
    assert claims["sub"] == str(admin)
    assert 8 * 3600 - 60 <= claims["exp"] - claims["iat"] <= 8 * 3600


def test_login_email_is_case_and_space_insensitive(client, admin):
    r = client.post("/auth/login", json={"email": f"  {EMAIL.upper()} ", "password": PASSWORD})
    assert r.status_code == 200


@pytest.mark.parametrize("email, password", [(EMAIL, "wrong-password"), ("nobody@mawjoud.test", PASSWORD)])
def test_login_bad_credentials_401(client, admin, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 401
    assert r.json()["detail"] == "Email ou mot de passe incorrect"


def test_login_rate_limited_after_5_attempts(client, admin):
    codes = [client.post("/auth/login", json={"email": EMAIL, "password": "bad"}).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    # Even the right password is blocked for the rest of the minute.
    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 429


def test_me(client, admin, headers):
    assert client.get("/auth/me", headers=headers).json() == {"id": admin, "email": EMAIL}


# ---------- get_admin ----------

def _token(sub, secret=SECRET, exp_delta=timedelta(hours=1)):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(sub), "iat": now, "exp": now + exp_delta}, secret, algorithm=ALGORITHM)


@pytest.mark.parametrize("make_headers", [
    lambda a: {},
    lambda a: {"Authorization": "Bearer not-a-jwt"},
    lambda a: {"Authorization": f"Basic {_token(a)}"},
    lambda a: {"Authorization": f"Bearer {_token(a, secret='another-secret-0123456789')}"},
    lambda a: {"Authorization": f"Bearer {_token(a, exp_delta=timedelta(seconds=-1))}"},
    lambda a: {"Authorization": f"Bearer {_token(999999999)}"},
], ids=["no-token", "garbage", "wrong-scheme", "wrong-secret", "expired", "unknown-admin"])
def test_protected_routes_reject_bad_tokens(client, admin, points, make_headers):
    h = make_headers(admin)
    r = client.get("/signalements", headers=h)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert client.patch(f"/signalements/{points['a_old_moy']}", json={"statut": "repare"}, headers=h).status_code == 401
    assert point_etat(points["A"]) == "panne"


def test_missing_jwt_secret_fails_loudly(client, admin, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "short")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})


# ---------- GET /signalements ----------

def test_list_with_token_sorted_and_enriched(client, headers, points):
    data = my_reports(client, headers, points, statut="ouvert")
    # haute → moyenne (oldest first) → basse
    assert [s["id"] for s in data] == [points["b_haute"], points["a_old_moy"], points["a_new_moy"], points["b_basse"]]
    first = data[0]
    assert first["point_nom"] == "Puits Auth B" and first["quartier"] == Q
    assert {s["id"]: s["a_photo"] for s in data}[points["a_new_moy"]] is True
    assert {s["id"]: s["a_photo"] for s in data}[points["a_old_moy"]] is False
    assert all("photo" not in s for s in data)


def test_list_statut_filter(client, headers, points):
    client.patch(f"/signalements/{points['b_basse']}", json={"statut": "repare"}, headers=headers)
    ouverts = {s["id"] for s in my_reports(client, headers, points, statut="ouvert")}
    repares = {s["id"] for s in my_reports(client, headers, points, statut="repare")}
    tous = {s["id"] for s in my_reports(client, headers, points)}
    assert points["b_basse"] in repares and points["b_basse"] not in ouverts
    assert tous == ouverts | repares and len(tous) == 4


def test_list_invalid_statut_422(client, headers):
    assert client.get("/signalements", headers=headers, params={"statut": "ferme"}).status_code == 422


# ---------- PATCH /signalements/{id} ----------

def test_patch_point_back_to_ok_only_when_no_open_report(client, headers, points):
    r = client.patch(f"/signalements/{points['a_old_moy']}", json={"statut": "repare"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["statut"] == "repare" and r.json()["repare_le"] is not None
    assert point_etat(points["A"]) == "panne"  # a_new_moy still open

    r = client.patch(f"/signalements/{points['a_new_moy']}", json={"statut": "repare"}, headers=headers)
    assert r.status_code == 200
    assert point_etat(points["A"]) == "ok"
    assert point_etat(points["B"]) == "faible"  # other point untouched


def test_patch_is_idempotent(client, headers, points):
    url = f"/signalements/{points['b_haute']}"
    first = client.patch(url, json={"statut": "repare"}, headers=headers).json()["repare_le"]
    again = client.patch(url, json={"statut": "repare"}, headers=headers)
    assert again.status_code == 200 and again.json()["repare_le"] == first


def test_patch_validation_and_404(client, headers, points):
    url = f"/signalements/{points['a_old_moy']}"
    assert client.patch(url, json={"statut": "ouvert"}, headers=headers).status_code == 422
    assert client.patch(url, json={}, headers=headers).status_code == 422
    assert client.patch("/signalements/999999999", json={"statut": "repare"}, headers=headers).status_code == 404


# ---------- seed_admin ----------

def test_seed_admin_creates_then_updates(client, monkeypatch, capsys):
    email = "pytest-seed@mawjoud.test"
    try:
        monkeypatch.setenv("ADMIN_EMAIL", f" {email.upper()} ")
        monkeypatch.setenv("ADMIN_PASSWORD", "first-password-1")
        seed_admin()
        monkeypatch.setenv("ADMIN_PASSWORD", "second-password-2")
        seed_admin()
        out = capsys.readouterr().out
        assert "Admin créé" in out and "Admin mis à jour" in out
        with SessionLocal() as db:
            rows = db.query(Admin).filter(Admin.email == email).all()
            assert len(rows) == 1
            assert verify_password("second-password-2", rows[0].password_hash)
            assert not verify_password("first-password-1", rows[0].password_hash)
    finally:
        with SessionLocal() as db:
            db.execute(delete(Admin).where(Admin.email == email))
            db.commit()


def test_seed_admin_skips_without_env(client, monkeypatch, capsys):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with SessionLocal() as db:
        before = db.query(Admin).count()
    seed_admin()
    assert "aucun admin créé" in capsys.readouterr().out
    with SessionLocal() as db:
        assert db.query(Admin).count() == before


def test_seed_admin_rejects_short_password(client, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "pytest-short@mawjoud.test")
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    with pytest.raises(SystemExit):
        seed_admin()
