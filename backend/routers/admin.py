# Accès responsable + statistiques
import base64
import hashlib
import hmac
import os
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from db import connect

router = APIRouter(tags=["admin"])

DUREE = 8 * 3600  # validité du token : 8 h


def _mdp() -> str:
    return os.environ.get("ADMIN_PASSWORD", "")


def _signe(payload: str) -> str:
    return hmac.new(_mdp().encode(), payload.encode(), hashlib.sha256).hexdigest()


def creer_token() -> str:
    # Token = expiration.signature (base64 url)
    payload = str(int(time.time()) + DUREE)
    return base64.urlsafe_b64encode(f"{payload}.{_signe(payload)}".encode()).decode()


def verifier_token(authorization: str | None = Header(default=None)):
    # Attend "Authorization: Bearer <token>"
    if not _mdp() or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Non autorisé")
    try:
        payload, sig = base64.urlsafe_b64decode(authorization[7:]).decode().split(".")
        valide = hmac.compare_digest(sig, _signe(payload)) and int(payload) > time.time()
    except Exception:
        valide = False
    if not valide:
        raise HTTPException(status_code=401, detail="Non autorisé")


class Login(BaseModel):
    password: str


@router.post("/admin/login")
def login(data: Login):
    if not _mdp() or not hmac.compare_digest(data.password.encode(), _mdp().encode()):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    return {"token": creer_token()}


@router.patch("/signalements/{sig_id}/repare")
def repare(sig_id: int, _=Depends(verifier_token)):
    with connect() as conn:
        row = conn.execute(
            "UPDATE signalements SET statut = 'repare' WHERE id = %s "
            "RETURNING id, point_id, statut",
            (sig_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Signalement introuvable")
        if row["point_id"] is not None:
            # Point remis à ok s'il n'a plus de signalement ouvert
            conn.execute(
                """UPDATE points SET etat = 'ok', maj_le = now()
                   WHERE id = %s AND NOT EXISTS (
                       SELECT 1 FROM signalements WHERE point_id = %s AND statut = 'ouvert')""",
                (row["point_id"], row["point_id"]),
            )
    return row


@router.get("/stats")
def stats():
    with connect() as conn:
        par_quartier = conn.execute(
            """SELECT quartier, count(*) AS total FROM signalements
               WHERE type = 'panne' AND statut = 'ouvert'
               GROUP BY quartier ORDER BY total DESC, quartier"""
        ).fetchall()
        par_jour = conn.execute(
            """SELECT cree_le::date AS jour, count(*) AS total FROM signalements
               WHERE type = 'panne' AND cree_le >= now() - interval '7 days'
               GROUP BY jour ORDER BY jour"""
        ).fetchall()
        ouverts = conn.execute(
            "SELECT count(*) AS n FROM signalements WHERE statut = 'ouvert'"
        ).fetchone()["n"]
    return {"pannes_par_quartier": par_quartier, "pannes_par_jour": par_jour,
            "total_ouverts": ouverts}
