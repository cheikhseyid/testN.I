import os

from sqlalchemy import inspect

from app.db import engine


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_cors_allowed_origin(client):
    origin = os.environ["CORS_ORIGINS"].split(",")[0].strip()
    r = client.get("/health", headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_unknown_origin_rejected(client):
    r = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_tables_exist(client):
    tables = set(inspect(engine).get_table_names())
    assert {"points_eau", "signalements", "admins"} <= tables


def test_signalement_columns(client):
    cols = {c["name"]: c for c in inspect(engine).get_columns("signalements")}
    assert cols["texte"]["type"].length == 500
    assert cols["photo"]["nullable"] and cols["repare_le"]["nullable"]
    fks = inspect(engine).get_foreign_keys("signalements")
    assert fks[0]["referred_table"] == "points_eau"


def test_admin_email_unique(client):
    insp = inspect(engine)
    uniques = [i for i in insp.get_indexes("admins") if i["unique"]]
    uniques += insp.get_unique_constraints("admins")
    assert any(u["column_names"] == ["email"] for u in uniques)


def test_parse_cors_origins_tolerates_dashboard_typos():
    from app.main import parse_origins

    assert parse_origins("") == []
    assert parse_origins("https://test-n-i.vercel.app") == ["https://test-n-i.vercel.app"]
    assert parse_origins(' "https://Test-N-I.vercel.app/" ') == ["https://test-n-i.vercel.app"]
    assert parse_origins("https://a.vercel.app/path/, 'http://localhost:5501';https://a.vercel.app") == [
        "https://a.vercel.app", "http://localhost:5501",
    ]
